"""
courses/services/recommendation.py

Phase 4C — Intelligent Course Recommendation Engine (Foundation)

This module contains ALL recommendation-scoring logic for the LMS.
Views must never compute recommendation scores themselves — they call
CourseRecommendationService.get_recommendations(student) and receive a
ready-to-render list back. This keeps the scoring rules in one place,
testable in isolation from HTTP concerns, and replaceable later by a
real ML-based engine without touching any view or template.

This is explicitly NOT machine learning. It is a deterministic, rule-based
scoring system — a transparent foundation that a future AI-driven engine
can be swapped in for behind the exact same public method signature:

    CourseRecommendationService.get_recommendations(student)
"""

from collections import defaultdict

from django.db.models import Avg, Count, Q

from courses.models import (
    Category,
    Course,
    Enrollment,
    LessonProgress,
    Review,
)

class CourseRecommendationService:
    """
    Stateless service that scores and ranks courses for a given student
    based on their learning history.

    Usage:
        recommendations = CourseRecommendationService.get_recommendations(
            student=request.user,
            limit=6,
        )

    All scoring rules are implemented as private helper methods so each
    rule can be tested, tuned, or removed independently without touching
    the others. Every helper returns a {course_id: points} dict (or a
    set of category ids / course ids) so the main method can simply sum
    contributions per course.
    """

    # Points awarded by each rule — kept as class constants so the scoring
    # weights are visible and adjustable in one place, per the spec.
    POINTS_SAME_CATEGORY_COMPLETED   = 40   # Rule A
    POINTS_HIGH_REVIEW_CATEGORY      = 30   # Rule B
    POINTS_PASSED_QUIZ_CATEGORY      = 25   # Rule C
    POINTS_LEVEL_PROGRESSION         = 20   # Rule D
    POINTS_POPULARITY_MAX            = 10   # Rule E (scaled 0–10)
    POINTS_HIGH_RATING               = 10   # Rule F

    HIGH_REVIEW_THRESHOLD            = 4    # Rule B: 4 or 5 stars counts as "high"
    HIGH_RATING_THRESHOLD            = 4    # Rule F: avg_rating >= 4
    POPULARITY_ENROLLMENT_CAP        = 50   # Rule E: enrollment count that earns the full +10

    # Defines which level comes after which, for Rule D's progression check.
    LEVEL_PROGRESSION = {
        Course.Level.BEGINNER:     Course.Level.INTERMEDIATE,
        Course.Level.INTERMEDIATE: Course.Level.ADVANCED,
        # ADVANCED has no "next" level — intentionally absent from this map.
    }

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    @classmethod
    def get_recommendations(cls, student, limit=6):
        """
        Returns up to `limit` recommended Course instances for `student`,
        ordered by descending recommendation score.

        Each returned Course has two extra attributes attached (not saved
        to the database — just set on the Python object for the template
        to read directly, the same convention already used elsewhere in
        this codebase, e.g. enrollment.progress in student_dashboard):

            course.recommendation_score   : int  — the total computed score
            course.avg_rating             : float|None — annotated rating
            course.review_count           : int  — annotated review count

        Returns an empty list if the student has no learning history yet
        or if no eligible courses remain after exclusions — the view/
        template handle that case with a friendly empty state, this
        method never raises for "no data".
        """
        candidate_courses = cls._get_eligible_courses(student)

        if not candidate_courses.exists():
            return []

        # Gather the student's learning-history signals up front (a small,
        # fixed number of queries regardless of how many candidate courses
        # exist) — these are reused across every scoring rule below so we
        # never re-query per-candidate-course (which would be N+1).
        completed_category_ids = cls._get_completed_category_ids(student)
        high_review_category_ids = cls._get_high_review_category_ids(student)
        passed_quiz_category_ids = cls._get_passed_quiz_category_ids(student)
        completed_levels_by_category = cls._get_completed_levels_by_category(student)

        scored = []
        for course in candidate_courses:
            score = 0

            # Rule A — completed a course in this category before (+40)
            if course.category_id in completed_category_ids:
                score += cls.POINTS_SAME_CATEGORY_COMPLETED

            # Rule B — gave a 4-5 star review to a course in this category (+30)
            if course.category_id in high_review_category_ids:
                score += cls.POINTS_HIGH_REVIEW_CATEGORY

            # Rule C — passed a quiz in this category before (+25)
            if course.category_id in passed_quiz_category_ids:
                score += cls.POINTS_PASSED_QUIZ_CATEGORY

            # Rule D — level progression: completed Beginner -> recommend
            # Intermediate in the SAME category (and so on). (+20)
            completed_level = completed_levels_by_category.get(course.category_id)
            if completed_level is not None:
                next_level = cls.LEVEL_PROGRESSION.get(completed_level)
                if next_level is not None and course.level == next_level:
                    score += cls.POINTS_LEVEL_PROGRESSION

            # Rule E — popularity boost, scaled 0–10 by enrollment count
            # relative to POPULARITY_ENROLLMENT_CAP (annotated below).
            enrollment_count = course.enrollment_count_annotated or 0
            popularity_points = min(
                cls.POINTS_POPULARITY_MAX,
                round((enrollment_count / cls.POPULARITY_ENROLLMENT_CAP) * cls.POINTS_POPULARITY_MAX),
            )
            score += popularity_points

            # Rule F — highly rated course (+10 if avg rating >= 4)
            if course.avg_rating is not None and course.avg_rating >= cls.HIGH_RATING_THRESHOLD:
                score += cls.POINTS_HIGH_RATING

            # Only keep courses that scored on at least one rule — a score
            # of 0 means "no signal at all" and shouldn't be presented as
            # a personalised recommendation (it would just be a random
            # unrelated course, which defeats the purpose of this feature).
            if score > 0:
                course.recommendation_score = score
                scored.append(course)

        scored.sort(key=lambda c: c.recommendation_score, reverse=True)
        return scored[:limit]

    # ─────────────────────────────────────────────────────────────────────
    # Candidate pool — exclusions applied here, once, up front
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_eligible_courses(student):
        """
        Returns the base queryset of courses that are ALLOWED to be
        recommended, before any scoring happens.

        Exclusions (per spec, Section 4):
            - unpublished courses        -> is_published=True
            - inactive courses           -> is_published=True covers this;
                                             there is no separate "active"
                                             flag on Course in this schema,
                                             so "inactive" and "unpublished"
                                             are the same condition here.
            - already enrolled courses   -> exclude course ids the student
                                             has an Enrollment row for
            - already completed courses  -> a course the student is
                                             enrolled in is already excluded
                                             above, so a *completed* course
                                             (which requires enrollment) is
                                             automatically excluded too.

        Annotated here (not in the caller) so every candidate course
        already carries its rating and enrollment count — avoids a
        second query pass per course in get_recommendations().
        """
        enrolled_course_ids = Enrollment.objects.filter(
            student=student
        ).values_list('course_id', flat=True)

        return (
            Course.objects
            .filter(is_published=True)
            .exclude(pk__in=enrolled_course_ids)
            .select_related('category', 'teacher')
            .annotate(
                avg_rating=Avg('reviews__rating'),
                review_count=Count('reviews', distinct=True),
                # Named distinctly from the existing enrollment_count
                # *property* on Course (Phase 1) to avoid any clash —
                # this is the annotated/queryset version used only here.
                enrollment_count_annotated=Count('enrollments', distinct=True),
            )
        )

    # ─────────────────────────────────────────────────────────────────────
    # Learning-history signal extraction (one query each)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_completed_category_ids(student):
        """
        Rule A support.

        Returns a set of Category ids where the student has fully
        completed at least one course (every lesson marked complete).

        "Completed" is computed the same way as everywhere else in this
        app: completed LessonProgress count == total Lesson count for
        that course, for that student.

        Implementation note: this is a bulk, query-efficient version —
        TWO queries total regardless of how many courses the student is
        enrolled in (one for enrolled courses + their lesson counts, one
        grouped count of completed lessons per course), avoiding the
        N+1 pattern of looping enrollments and querying per-course.
        """
        enrollments = (
            Enrollment.objects
            .filter(student=student)
            .select_related('course')
        )
        # course_id -> (category_id, total_lesson_count)
        course_info = {
            e.course_id: (e.course.category_id, e.course.lesson_count)
            for e in enrollments
        }
        if not course_info:
            return set()

        completed_counts = (
            LessonProgress.objects
            .filter(student=student, lesson__course_id__in=course_info.keys(), completed=True)
            .values('lesson__course_id')
            .annotate(done=Count('id'))
        )
        completed_by_course = {row['lesson__course_id']: row['done'] for row in completed_counts}

        completed_category_ids = set()
        for course_id, (category_id, total_lessons) in course_info.items():
            if total_lessons == 0 or category_id is None:
                continue
            if completed_by_course.get(course_id, 0) == total_lessons:
                completed_category_ids.add(category_id)

        return completed_category_ids

    @staticmethod
    def _get_high_review_category_ids(student):
        """
        Rule B support.

        Returns a set of Category ids where the student left a 4 or 5
        star review on any course. One query, fully database-side.
        """
        return set(
            Review.objects
            .filter(
                student=student,
                rating__gte=CourseRecommendationService.HIGH_REVIEW_THRESHOLD,
                course__category__isnull=False,
            )
            .values_list('course__category_id', flat=True)
            .distinct()
        )

    @staticmethod
    def _get_passed_quiz_category_ids(student):
        """
        Rule C support.

        Returns a set of Category ids where the student has at least one
        PASSED QuizAttempt for a quiz belonging to a course in that
        category. One query, fully database-side.
        """
        # Imported locally to avoid a hard dependency between the courses
        # app and the assessments app at module-import time — mirrors the
        # existing pattern already used in courses/views.py.
        from assessments.models import QuizAttempt

        return set(
            QuizAttempt.objects
            .filter(
                student=student,
                passed=True,
                quiz__course__category__isnull=False,
            )
            .values_list('quiz__course__category_id', flat=True)
            .distinct()
        )

    @staticmethod
    def _get_completed_levels_by_category(student):
        """
        Rule D support.

        Returns {category_id: highest_completed_level} for every category
        where the student has completed at least one course.

        If a student has completed both a Beginner and an Intermediate
        course in the same category, the Intermediate one wins (since the
        spec's progression is Beginner -> Intermediate -> Advanced, the
        "highest" completed level is the most informative signal for what
        to recommend next).

        Implementation note: bulk version — two queries total regardless
        of enrollment count, same pattern as _get_completed_category_ids.
        """
        level_rank = {
            Course.Level.BEGINNER:     1,
            Course.Level.INTERMEDIATE: 2,
            Course.Level.ADVANCED:     3,
        }

        enrollments = (
            Enrollment.objects
            .filter(student=student)
            .select_related('course')
        )
        # course_id -> (category_id, level, total_lesson_count)
        course_info = {
            e.course_id: (e.course.category_id, e.course.level, e.course.lesson_count)
            for e in enrollments
        }
        if not course_info:
            return {}

        completed_counts = (
            LessonProgress.objects
            .filter(student=student, lesson__course_id__in=course_info.keys(), completed=True)
            .values('lesson__course_id')
            .annotate(done=Count('id'))
        )
        completed_by_course = {row['lesson__course_id']: row['done'] for row in completed_counts}

        highest_by_category = {}   # category_id -> (rank, level)
        for course_id, (category_id, level, total_lessons) in course_info.items():
            if total_lessons == 0 or category_id is None:
                continue
            if completed_by_course.get(course_id, 0) != total_lessons:
                continue   # not completed — doesn't count for progression

            current_rank = level_rank.get(level, 0)
            existing = highest_by_category.get(category_id)
            if existing is None or current_rank > existing[0]:
                highest_by_category[category_id] = (current_rank, level)

        return {
            cat_id: level
            for cat_id, (rank, level) in highest_by_category.items()
        }
