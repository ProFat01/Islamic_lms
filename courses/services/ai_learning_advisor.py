"""
courses/services/ai_learning_advisor.py

Phase 5A — AI Learning Advisor (AI-ready architecture, no external AI yet)

This module contains ALL advisor analysis logic for the LMS. The view
(advisor_dashboard) never computes advice itself — it calls
AILearningAdvisorService().get_advice(student) and renders whatever
dictionary comes back. This mirrors the exact architecture already
established by CourseRecommendationService in Phase 4C.

This is explicitly NOT machine learning. It is a deterministic, rule-based
advisor — a transparent foundation that can be swapped for a real LLM-backed
implementation later WITHOUT changing the view or template, because both
only ever depend on the shape of the dictionary returned by get_advice():

    {
        "summary": str,
        "strengths": [str, ...],
        "improvements": [str, ...],
        "recommended_next_steps": [str, ...],
        "recommended_courses": [Course, ...],
    }

To swap in a real AI provider later: create a new class (e.g.
LLMLearningAdvisorService) implementing the same get_advice(student)
signature and returning the same dictionary shape, then change one line
in advisor_dashboard() to instantiate the new class instead. Nothing else
in the project needs to change.
"""

from django.db.models import Avg, Count

from ..models import (
    Course,
    Enrollment,
    LessonProgress,
    Review,
    CourseCertificate,
)

from .recommendation import CourseRecommendationService


class AILearningAdvisorService:
    """
    Rule-based learning advisor that analyses one student's full learning
    history and produces personalised, structured advice.

    Usage:
        advice = AILearningAdvisorService().get_advice(request.user)

    Instantiated (not a classmethod) per the spec's exact call pattern —
    this also leaves room for a future implementation to accept
    constructor-level configuration (e.g. a model name, a prompt template,
    an API client) without changing the call site's shape.
    """

    # Thresholds — kept as class constants, mirroring the pattern already
    # established by CourseRecommendationService's POINTS_* constants, so
    # advisor rules are visible and tunable in one place.
    HIGH_QUIZ_SCORE_THRESHOLD     = 80   # Rule A
    LOW_QUIZ_SCORE_THRESHOLD      = 60   # Rule B
    STRONG_COMPLETION_THRESHOLD   = 3    # Rule C
    HIGH_REVIEW_RATING_THRESHOLD  = 4    # Rule E
    RECOMMENDED_COURSES_LIMIT     = 3    # Rule F

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def get_advice(self, student):
        """
        Returns a dictionary of personalised advice for `student`:

            {
                "summary": str,
                "strengths": [str, ...],
                "improvements": [str, ...],
                "recommended_next_steps": [str, ...],
                "recommended_courses": [Course, ...],
                "has_learning_history": bool,
            }

        "has_learning_history" is an extra convenience flag (not in the
        spec's literal dict shape, but additive and harmless) that the
        template uses to decide whether to show the friendly empty state
        ("We need a little more learning activity...") versus the full
        advice sections. A student with zero enrollments, zero completed
        lessons, zero quiz attempts, and zero reviews has no signal for
        any rule to act on, so summary/strengths/improvements would all
        be empty — has_learning_history makes that case explicit and
        unambiguous for the template rather than relying on checking
        multiple empty lists.

        Never raises for "no data" — always returns the dict shape above,
        with empty lists where there is nothing to say.
        """
        metrics = self._gather_metrics(student)

        strengths               = []
        improvements            = []
        recommended_next_steps  = []

        # ── Rule A: High Quiz Performance (avg score >= 80%) ────────────
        if metrics['average_quiz_score'] is not None and \
           metrics['average_quiz_score'] >= self.HIGH_QUIZ_SCORE_THRESHOLD:
            strengths.append("You consistently perform well in assessments.")
            recommended_next_steps.append("Consider moving to more advanced courses.")

        # ── Rule B: Low Quiz Performance (avg score < 60%) ──────────────
        if metrics['average_quiz_score'] is not None and \
           metrics['average_quiz_score'] < self.LOW_QUIZ_SCORE_THRESHOLD:
            improvements.append("Review previous lessons before attempting new quizzes.")

        # ── Rule C: Strong Completion History (completed courses >= 3) ──
        if metrics['completed_courses_count'] >= self.STRONG_COMPLETION_THRESHOLD:
            strengths.append("You have demonstrated excellent learning consistency.")

        # ── Rule D: No Certificates Yet ──────────────────────────────────
        if metrics['certificate_count'] == 0:
            recommended_next_steps.append(
                "Focus on completing a full course to earn your first certificate."
            )

        # ── Rule E: High Review Ratings (avg given rating >= 4) ─────────
        if metrics['average_given_rating'] is not None and \
           metrics['average_given_rating'] >= self.HIGH_REVIEW_RATING_THRESHOLD:
            recommended_next_steps.append("Continue exploring similar highly rated subjects.")

        # ── Rule F: Learning Path Continuation (delegate to Phase 4C) ───
        recommended_courses = CourseRecommendationService.get_recommendations(
            student=student,
            limit=self.RECOMMENDED_COURSES_LIMIT,
        )

        has_learning_history = (
            metrics['enrolled_courses_count'] > 0
            or metrics['completed_lessons_count'] > 0
            or metrics['quiz_attempt_count'] > 0
            or metrics['review_count'] > 0
        )

        summary = self._build_summary(metrics, has_learning_history)

        return {
            'summary':                 summary,
            'strengths':               strengths,
            'improvements':            improvements,
            'recommended_next_steps':  recommended_next_steps,
            'recommended_courses':     recommended_courses,
            'has_learning_history':    has_learning_history,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Metric gathering — one small, fixed set of queries, reused by every
    # rule above and by the summary builder below. No rule or summary
    # logic re-queries the database independently.
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _gather_metrics(student):
        """
        Runs a fixed, small number of queries (6 total, none scaling with
        the amount of data the student has) and returns a flat dict of
        everything every rule needs:

            enrolled_courses_count
            completed_courses_count
            completed_lessons_count
            certificate_count
            quiz_attempt_count
            average_quiz_score      (float|None, percentage 0–100)
            review_count
            average_given_rating    (float|None, 1–5)
        """
        # Avoid a circular import at module load time — assessments imports
        # nothing from courses, so this is safe to import lazily here,
        # mirroring the existing pattern already used in
        # CourseRecommendationService._get_passed_quiz_category_ids.
        from assessments.models import QuizAttempt

        enrollments = (
            Enrollment.objects
            .filter(student=student)
            .select_related('course')
        )
        enrolled_courses_count = enrollments.count()

        # Completed courses: same "all lessons done" definition used
        # everywhere else in this app (course_detail, dashboards,
        # recommendation service) — computed in bulk, not per-course.
        course_info = {
            e.course_id: e.course.lesson_count
            for e in enrollments
        }
        completed_courses_count = 0
        completed_lessons_count = 0

        if course_info:
            completed_counts = (
                LessonProgress.objects
                .filter(
                    student=student,
                    lesson__course_id__in=course_info.keys(),
                    completed=True,
                )
                .values('lesson__course_id')
                .annotate(done=Count('id'))
            )
            completed_by_course = {
                row['lesson__course_id']: row['done']
                for row in completed_counts
            }
            completed_lessons_count = sum(completed_by_course.values())
            completed_courses_count = sum(
                1
                for course_id, total_lessons in course_info.items()
                if total_lessons > 0 and completed_by_course.get(course_id, 0) == total_lessons
            )

        certificate_count = CourseCertificate.objects.filter(student=student).count()

        quiz_stats = QuizAttempt.objects.filter(student=student).aggregate(
            attempt_count=Count('id'),
            avg_score=Avg('percentage'),
        )
        quiz_attempt_count  = quiz_stats['attempt_count'] or 0
        average_quiz_score  = (
            round(quiz_stats['avg_score'])
            if quiz_stats['avg_score'] is not None
            else None
        )

        review_stats = Review.objects.filter(student=student).aggregate(
            review_count=Count('id'),
            avg_rating=Avg('rating'),
        )
        review_count          = review_stats['review_count'] or 0
        average_given_rating  = review_stats['avg_rating']

        return {
            'enrolled_courses_count':   enrolled_courses_count,
            'completed_courses_count':  completed_courses_count,
            'completed_lessons_count':  completed_lessons_count,
            'certificate_count':        certificate_count,
            'quiz_attempt_count':       quiz_attempt_count,
            'average_quiz_score':       average_quiz_score,
            'review_count':             review_count,
            'average_given_rating':     average_given_rating,
        }

    @staticmethod
    def _build_summary(metrics, has_learning_history):
        """
        Builds the human-readable one-paragraph "summary" string from the
        gathered metrics. Kept as a small, separate method so the wording
        can be revised independently of the rule logic above, and so a
        future LLM-backed implementation has an obvious single place to
        look at for "what does the current rule-based summary say" when
        designing prompts.
        """
        if not has_learning_history:
            return (
                "We need a little more learning activity before generating "
                "personalized advice."
            )

        parts = []
        parts.append(
            f"You are enrolled in {metrics['enrolled_courses_count']} "
            f"course{'s' if metrics['enrolled_courses_count'] != 1 else ''} "
            f"and have completed {metrics['completed_lessons_count']} "
            f"lesson{'s' if metrics['completed_lessons_count'] != 1 else ''} so far."
        )

        if metrics['quiz_attempt_count'] > 0:
            parts.append(
                f"Your average quiz score is {metrics['average_quiz_score']}% "
                f"across {metrics['quiz_attempt_count']} "
                f"attempt{'s' if metrics['quiz_attempt_count'] != 1 else ''}."
            )

        if metrics['certificate_count'] > 0:
            parts.append(
                f"You have earned {metrics['certificate_count']} "
                f"certificate{'s' if metrics['certificate_count'] != 1 else ''}."
            )

        return " ".join(parts)
