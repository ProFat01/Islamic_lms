"""
courses/services/study_planner.py

Phase 5B — Personalized AI Study Planner (rule-based foundation)

This module contains ALL planning logic for the LMS. The view
(study_planner) never computes plan contents itself — it calls
StudyPlannerService().build_plan(student) and renders whatever
dictionary comes back. This mirrors the exact architecture already
established by CourseRecommendationService (Phase 4C) and
AILearningAdvisorService (Phase 5A).

This is explicitly NOT an LLM integration. It is a deterministic,
rule-based planning engine — a transparent foundation that a future
AI-driven planner can be swapped in for later WITHOUT changing the view
or template, because both only ever depend on the shape of the
dictionary returned by build_plan():

    {
        "has_enrollments": bool,
        "summary": {...},
        "todays_focus": [str, ...],
        "weekly_goals": [str, ...],
        "suggested_daily_minutes": int,
        "priority_courses": [{...}, ...],
        "estimated_completions": [{...}, ...],
    }

To swap in a real AI provider later: create a new class (e.g.
LLMStudyPlannerService) implementing the same build_plan(student)
signature and returning the same dictionary shape, then change one line
in study_planner() to instantiate the new class instead. Nothing else
in the project needs to change.
"""

import math
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from ..models import Course, CourseCertificate, Enrollment, Lesson, LessonProgress


class StudyPlannerService:
    """
    Rule-based study planner that analyses one student's full learning
    activity and produces a structured, actionable study plan.

    Usage:
        plan = StudyPlannerService().build_plan(request.user)

    Exposes exactly one public method, build_plan(student), per the spec.
    Every other method on this class is a private helper and should never
    be called directly from outside this module.
    """

    # ── Daily study-time rule (Section D of the spec) ──────────────────────
    DAILY_MINUTES_0_TO_1_COURSES   = 15
    DAILY_MINUTES_2_TO_3_COURSES   = 30
    DAILY_MINUTES_4_PLUS_COURSES   = 45

    # ── Pace assumption used for completion-date projections (Section E) ──
    # Used only as a default pace estimate when projecting completion —
    # NOT the same number shown to the student as "suggested daily time"
    # (that figure is course-count based per the spec's explicit rule).
    # This is a conservative estimate of how many lessons get completed
    # per week at the recommended pace, used purely for ETA math.
    ASSUMED_LESSONS_PER_WEEK       = 3

    # Recently active window for trend detection — a course with at least
    # one lesson completed in this window counts as "actively progressing"
    # when ranking priority courses.
    RECENT_ACTIVITY_DAYS           = 14

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def build_plan(self, student):
        """
        Returns a dictionary describing a personalised study plan for
        `student`. Never raises for "no data" — if the student has zero
        enrollments, returns has_enrollments=False and empty collections
        for everything else, so the template can render the friendly
        empty state ("No active courses yet.") without any special-casing
        beyond checking that one flag.
        """
        course_rows = self._gather_course_data(student)

        if not course_rows:
            return {
                'has_enrollments':          False,
                'summary':                  self._empty_summary(),
                'todays_focus':              [],
                'weekly_goals':              [],
                'suggested_daily_minutes':   0,
                'priority_courses':          [],
                'estimated_completions':     [],
            }

        summary = self._build_summary(student, course_rows)

        priority_courses = self._rank_priority_courses(course_rows)

        todays_focus = self._build_todays_focus(priority_courses)
        weekly_goals = self._build_weekly_goals(course_rows, summary)
        suggested_daily_minutes = self._suggest_daily_minutes(summary['enrolled_courses_count'])
        estimated_completions = self._build_estimated_completions(
            priority_courses, suggested_daily_minutes
        )

        return {
            'has_enrollments':          True,
            'summary':                  summary,
            'todays_focus':              todays_focus,
            'weekly_goals':              weekly_goals,
            'suggested_daily_minutes':   suggested_daily_minutes,
            'priority_courses':          priority_courses,
            'estimated_completions':     estimated_completions,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Data gathering — bulk queries only, never per-course loops that hit
    # the database. Mirrors the exact pattern already used in
    # AILearningAdvisorService._gather_metrics().
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _gather_course_data(student):
        """
        Returns a list of dicts, one per enrolled course, each containing
        everything every rule below needs:

            {
                'course':              Course instance,
                'total_lessons':       int,
                'completed_lessons':   int,
                'remaining_lessons':   int,
                'progress_percentage': int (0–100),
                'is_complete':         bool,
                'has_certificate':     bool,
                'recently_active':     bool,
                'next_lesson':         Lesson|None,
            }

        Six queries total, regardless of how many courses the student is
        enrolled in:
            1. Enrollment + select_related('course')
            2. All lessons for all enrolled courses (bulk)
            3. Grouped completed-lesson counts across ALL enrolled courses
            4. Completed lesson ids (to resolve "next_lesson" in Python)
            5. Most-recent completed_at per course (for recently_active)
            6. Certificate ids the student already holds (for has_certificate)

        (_build_summary adds one further query for average quiz score —
        none of these scale with the number of courses or lessons.)

        Lesson ordering/lookup for "next_lesson" reuses Course.lessons
        (already ordered by Meta.ordering on Lesson — order, created_at)
        and is resolved in Python from a single bulk lesson fetch, not a
        query per course.
        """
        enrollments = (
            Enrollment.objects
            .filter(student=student)
            .select_related('course', 'course__teacher', 'course__category')
        )
        if not enrollments.exists():
            return []

        course_ids = [e.course_id for e in enrollments]

        # Bulk-fetch all lessons for all enrolled courses in one query,
        # already ordered by (course, order) thanks to Lesson.Meta.ordering
        # plus the explicit order_by below for a stable cross-course sort.
        all_lessons = list(
            Lesson.objects
            .filter(course_id__in=course_ids)
            .order_by('course_id', 'order', 'created_at')
        )
        lessons_by_course = {}
        for lesson in all_lessons:
            lessons_by_course.setdefault(lesson.course_id, []).append(lesson)

        # Completed lesson counts, grouped by course, in one query.
        completed_counts = (
            LessonProgress.objects
            .filter(student=student, lesson__course_id__in=course_ids, completed=True)
            .values('lesson__course_id')
            .annotate(done=Count('id'))
        )
        completed_by_course = {row['lesson__course_id']: row['done'] for row in completed_counts}

        # Which specific lessons are completed (needed to find "next_lesson"
        # — the first lesson in course order that is NOT yet completed).
        completed_lesson_ids = set(
            LessonProgress.objects
            .filter(student=student, lesson__course_id__in=course_ids, completed=True)
            .values_list('lesson_id', flat=True)
        )

        # Most recent completion timestamp per course, for "recently active".
        from django.db.models import Max
        recent_activity = (
            LessonProgress.objects
            .filter(student=student, lesson__course_id__in=course_ids, completed=True)
            .values('lesson__course_id')
            .annotate(last_completed=Max('completed_at'))
        )
        last_completed_by_course = {
            row['lesson__course_id']: row['last_completed']
            for row in recent_activity
        }

        # Certificates the student already holds for these courses.
        certified_course_ids = set(
            CourseCertificate.objects
            .filter(student=student, course_id__in=course_ids)
            .values_list('course_id', flat=True)
        )

        cutoff = timezone.now() - timedelta(days=StudyPlannerService.RECENT_ACTIVITY_DAYS)

        rows = []
        for enrollment in enrollments:
            course = enrollment.course
            lessons = lessons_by_course.get(course.pk, [])
            total_lessons = len(lessons)
            completed_lessons = completed_by_course.get(course.pk, 0)
            remaining_lessons = max(total_lessons - completed_lessons, 0)
            progress_percentage = (
                round((completed_lessons / total_lessons) * 100)
                if total_lessons > 0
                else 0
            )
            is_complete = total_lessons > 0 and completed_lessons == total_lessons

            next_lesson = next(
                (l for l in lessons if l.pk not in completed_lesson_ids),
                None,
            )

            last_completed_at = last_completed_by_course.get(course.pk)
            recently_active = bool(last_completed_at and last_completed_at >= cutoff)

            rows.append({
                'course':               course,
                'total_lessons':        total_lessons,
                'completed_lessons':    completed_lessons,
                'remaining_lessons':    remaining_lessons,
                'progress_percentage':  progress_percentage,
                'is_complete':          is_complete,
                'has_certificate':      course.pk in certified_course_ids,
                'recently_active':      recently_active,
                'next_lesson':          next_lesson,
            })

        return rows

    # ─────────────────────────────────────────────────────────────────────
    # A) Study Summary
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_summary():
        return {
            'enrolled_courses_count':   0,
            'completed_lessons_count':  0,
            'remaining_lessons_count':  0,
            'certificate_count':        0,
            'average_quiz_score':       None,
        }

    @staticmethod
    def _build_summary(student, course_rows):
        """
        Aggregates the per-course rows into the headline numbers shown on
        the Study Summary Card, plus one extra query for quiz performance
        (quiz data lives in the assessments app, not in course_rows).
        """
        from django.db.models import Avg
        # Lazy import — assessments has no dependency on courses, mirrors
        # the existing pattern already used in AILearningAdvisorService.
        from assessments.models import QuizAttempt

        enrolled_courses_count  = len(course_rows)
        completed_lessons_count = sum(r['completed_lessons'] for r in course_rows)
        remaining_lessons_count = sum(r['remaining_lessons'] for r in course_rows)
        certificate_count       = sum(1 for r in course_rows if r['has_certificate'])

        quiz_stats = QuizAttempt.objects.filter(student=student).aggregate(
            avg_score=Avg('percentage'),
        )
        average_quiz_score = (
            round(quiz_stats['avg_score'])
            if quiz_stats['avg_score'] is not None
            else None
        )

        return {
            'enrolled_courses_count':   enrolled_courses_count,
            'completed_lessons_count':  completed_lessons_count,
            'remaining_lessons_count':  remaining_lessons_count,
            'certificate_count':        certificate_count,
            'average_quiz_score':       average_quiz_score,
        }

    # ─────────────────────────────────────────────────────────────────────
    # C) Priority Courses ranking
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _rank_priority_courses(course_rows):
        """
        Ranks enrolled, NOT-YET-complete courses by a simple weighted
        priority score combining three signals from the spec:

            - incomplete progress  : courses with remaining lessons rank
                                      above fully completed ones (completed
                                      courses are excluded entirely — there
                                      is nothing left to prioritise there)
            - high completion %    : a course already at 80% deserves
                                      attention to finish it before
                                      starting something else
            - near-certificate      : a course at >=80% complete with no
                                      certificate yet gets a strong boost,
                                      since 1-2 lessons stand between the
                                      student and a certificate

        Returns the input rows (filtered to incomplete courses only),
        each with an added 'priority_score' key, sorted descending.
        """
        NEAR_CERTIFICATE_THRESHOLD = 80   # % complete to count as "near"
        NEAR_CERTIFICATE_BONUS     = 50
        HIGH_PROGRESS_BONUS_SCALE  = 1.0  # 1 point per % complete

        incomplete_rows = [r for r in course_rows if not r['is_complete'] and r['total_lessons'] > 0]

        for row in incomplete_rows:
            score = row['progress_percentage'] * HIGH_PROGRESS_BONUS_SCALE

            if row['progress_percentage'] >= NEAR_CERTIFICATE_THRESHOLD and not row['has_certificate']:
                score += NEAR_CERTIFICATE_BONUS

            if row['recently_active']:
                score += 10   # small boost to keep momentum on courses the student is actively working through

            row['priority_score'] = round(score)

        incomplete_rows.sort(key=lambda r: r['priority_score'], reverse=True)
        return incomplete_rows

    # ─────────────────────────────────────────────────────────────────────
    # B) Today's Focus
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_todays_focus(priority_courses):
        """
        Builds 1–3 concrete, actionable items for "today" from the top of
        the priority list. Examples per spec:
            - Complete lesson "Introduction to Aqeedah"
            - Continue Arabic Language
            - Review previous quiz
        """
        focus_items = []

        for row in priority_courses[:3]:
            course = row['course']
            if row['next_lesson'] is not None:
                focus_items.append(
                    f"Complete lesson \u201c{row['next_lesson'].title}\u201d in {course.title}"
                )
            else:
                focus_items.append(f"Continue {course.title}")

        return focus_items

    # ─────────────────────────────────────────────────────────────────────
    # B) Weekly Goals
    # ─────────────────────────────────────────────────────────────────────

    def _build_weekly_goals(self, course_rows, summary):
        """
        Builds 2–4 weekly goals based on overall activity level. Examples
        per spec:
            - Finish 2 lessons this week
            - Attempt 1 quiz
            - Complete a course certificate
        """
        goals = []

        remaining = summary['remaining_lessons_count']
        if remaining > 0:
            lesson_goal = min(remaining, self.ASSUMED_LESSONS_PER_WEEK)
            goals.append(f"Finish {lesson_goal} lesson{'s' if lesson_goal != 1 else ''} this week")

        goals.append("Attempt at least 1 quiz this week")

        # If any course is close to completion (near-certificate territory),
        # make finishing it this week an explicit weekly goal.
        near_complete = [
            r for r in course_rows
            if not r['is_complete'] and r['progress_percentage'] >= 80
        ]
        if near_complete:
            goals.append(
                f"Complete \u201c{near_complete[0]['course'].title}\u201d "
                f"and earn your certificate"
            )

        if summary['enrolled_courses_count'] == 0:
            goals.append("Enroll in a new course to keep learning")

        return goals

    # ─────────────────────────────────────────────────────────────────────
    # D) Suggested Daily Study Time
    # ─────────────────────────────────────────────────────────────────────

    def _suggest_daily_minutes(self, enrolled_courses_count):
        """
        Rule-based daily study time, exactly per the spec's table:
            0-1 courses : 15 minutes/day
            2-3 courses : 30 minutes/day
            4+  courses : 45 minutes/day
        """
        if enrolled_courses_count <= 1:
            return self.DAILY_MINUTES_0_TO_1_COURSES
        elif enrolled_courses_count <= 3:
            return self.DAILY_MINUTES_2_TO_3_COURSES
        else:
            return self.DAILY_MINUTES_4_PLUS_COURSES

    # ─────────────────────────────────────────────────────────────────────
    # E) Estimated Completion Dates
    # ─────────────────────────────────────────────────────────────────────

    def _build_estimated_completions(self, priority_courses, suggested_daily_minutes):
        """
        Projects an estimated completion date for each incomplete priority
        course, based on:
            - remaining lessons for that course
            - an assumed study pace derived from suggested_daily_minutes

        Pace model: ASSUMED_LESSONS_PER_WEEK is the baseline at the
        smallest daily-time tier (15 min/day). Suggested daily minutes
        scale the pace proportionally — e.g. 30 min/day is assumed to
        complete lessons twice as fast as 15 min/day. This is a simple,
        transparent heuristic (not a real velocity calculation from
        historical data), appropriate for a rule-based v1 planner.

        Returns a list of dicts:
            {
                'course':          Course,
                'remaining_lessons': int,
                'estimated_date':  date,
                'estimated_weeks': int,
            }
        """
        if suggested_daily_minutes <= 0:
            pace_multiplier = 1.0
        else:
            pace_multiplier = suggested_daily_minutes / self.DAILY_MINUTES_0_TO_1_COURSES

        effective_lessons_per_week = max(
            self.ASSUMED_LESSONS_PER_WEEK * pace_multiplier,
            1,   # never project a pace slower than 1 lesson/week
        )

        results = []
        today = timezone.now().date()

        for row in priority_courses:
            remaining = row['remaining_lessons']
            if remaining <= 0:
                continue

            estimated_weeks = max(math.ceil(remaining / effective_lessons_per_week), 1)
            estimated_date = today + timedelta(weeks=estimated_weeks)

            results.append({
                'course':            row['course'],
                'remaining_lessons': remaining,
                'estimated_date':    estimated_date,
                'estimated_weeks':   estimated_weeks,
            })

        return results
