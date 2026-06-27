"""
courses/views.py

All existing Phase 1/2/3B/3D/3E/4A/4B/4B.1/4C views are preserved exactly.
Phase 5A (AI Learning Advisor) adds advisor_dashboard — all analysis logic
lives in courses/services/ai_learning_advisor.py, this view only calls it.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, Max, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
# Phase 3B
from assessments.models import Quiz, QuizAttempt

from .forms import CourseForm, LessonForm, ReviewForm
from .models import Category, Course, CourseCertificate, Enrollment, Lesson, LessonProgress, Review
from .services import AILearningAdvisorService, CourseRecommendationService


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3D — Progress helpers  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def _get_course_progress(student, course):
    """
    Returns a dict with progress data for one student / course pair.

    Performance: two queries total per call.  Callers that need progress for
    many courses should use _get_progress_map() instead.
    """
    lessons      = list(course.lessons.order_by('order', 'created_at'))
    total        = len(lessons)

    if total == 0:
        return {
            'total_lessons': 0,
            'completed_lessons': 0,
            'percentage': 0,
            'is_complete': False,
            'first_incomplete': None,
        }

    completed_ids = set(
        LessonProgress.objects
        .filter(student=student, lesson__in=lessons, completed=True)
        .values_list('lesson_id', flat=True)
    )
    completed    = len(completed_ids)
    percentage   = round((completed / total) * 100) if total else 0
    is_complete  = (completed == total)

    first_incomplete = next(
        (l for l in lessons if l.pk not in completed_ids),
        None,
    )

    return {
        'total_lessons':     total,
        'completed_lessons': completed,
        'percentage':        percentage,
        'is_complete':       is_complete,
        'first_incomplete':  first_incomplete,
    }


def _get_progress_map(student, courses):
    """
    Efficient bulk version of _get_course_progress for a list/queryset of courses.
    Fetches all relevant LessonProgress rows in TWO queries total — avoids N+1.
    """
    course_list  = list(courses)
    if not course_list:
        return {}

    course_ids   = [c.pk for c in course_list]

    lessons_qs   = (
        Lesson.objects
        .filter(course_id__in=course_ids)
        .order_by('order', 'created_at')
    )
    from collections import defaultdict
    lessons_by_course = defaultdict(list)
    for lesson in lessons_qs:
        lessons_by_course[lesson.course_id].append(lesson)

    completed_qs = (
        LessonProgress.objects
        .filter(
            student=student,
            lesson__course_id__in=course_ids,
            completed=True,
        )
        .values_list('lesson_id', flat=True)
    )
    completed_set = set(completed_qs)

    result = {}
    for course in course_list:
        lessons     = lessons_by_course[course.pk]
        total       = len(lessons)
        completed   = sum(1 for l in lessons if l.pk in completed_set)
        percentage  = round((completed / total) * 100) if total else 0
        is_complete = (total > 0 and completed == total)
        first_incomplete = next(
            (l for l in lessons if l.pk not in completed_set),
            None,
        )
        result[course.pk] = {
            'total_lessons':     total,
            'completed_lessons': completed,
            'percentage':        percentage,
            'is_complete':       is_complete,
            'first_incomplete':  first_incomplete,
        }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3E — Certificate eligibility & automatic issuance
# ─────────────────────────────────────────────────────────────────────────────

def _quizzes_all_passed(student, course):
    """
    Returns True if every Quiz belonging to `course` has at least one
    PASSED QuizAttempt by `student`.

    If the course has zero quizzes, this returns True (vacuously) — the
    "no quiz OR passed all quizzes" rule in the spec means a course with
    no quizzes never blocks certificate eligibility on this condition.

    Performance: 2 queries regardless of how many quizzes the course has —
    one to list quiz IDs, one to list which of those IDs the student has
    a passing attempt for.
    """
    quiz_ids = list(course.quizzes.values_list('id', flat=True))
    if not quiz_ids:
        return True

    passed_quiz_ids = set(
        QuizAttempt.objects
        .filter(student=student, quiz_id__in=quiz_ids, passed=True)
        .values_list('quiz_id', flat=True)
        .distinct()
    )
    return set(quiz_ids).issubset(passed_quiz_ids)


def _is_eligible_for_certificate(student, course):
    """
    Full eligibility check per Phase 3E spec:

      1. Enrolled in course
      AND
      2. Completed all lessons
      AND
      3. Course contains no quiz  OR  passed all quizzes belonging to course

    Returns True/False. Does not create anything — see
    _check_and_issue_certificate for the side-effecting version.
    """
    enrolled = Enrollment.objects.filter(student=student, course=course).exists()
    if not enrolled:
        return False

    progress = _get_course_progress(student, course)
    if not progress['is_complete'] or progress['total_lessons'] == 0:
        return False

    if not _quizzes_all_passed(student, course):
        return False

    return True


def _check_and_issue_certificate(student, course):
    """
    Checks eligibility and creates a CourseCertificate if one does not
    already exist for this (student, course) pair.

    Safe to call repeatedly — get_or_create on the unique_together
    (student, course) constraint guarantees no duplicates are ever created,
    even under concurrent requests.

    Returns the CourseCertificate instance if the student is eligible
    (whether newly created or pre-existing), or None if not eligible.

    This is called from:
      - lesson_complete  (after marking a lesson complete — the most common
        trigger, since completing the last lesson is what finishes a course)
      - quiz_submit is NOT modified per the "do not modify quiz logic" rule;
        instead, certificate eligibility is also re-checked whenever the
        student visits course_detail, so passing a quiz after finishing all
        lessons still results in a certificate appearing without needing to
        touch assessments/views.py.
    """
    if not _is_eligible_for_certificate(student, course):
        return None

    certificate, created = CourseCertificate.objects.get_or_create(
        student=student,
        course=course,
    )
    return certificate


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4B — Review eligibility helper
# ─────────────────────────────────────────────────────────────────────────────

def _is_eligible_to_review(student, course):
    """
    A student may review a course only if:

      1. Enrolled in the course
      AND
      2. Completed the course (all lessons marked complete)

    Reuses _get_course_progress() (Phase 3D) rather than re-querying
    LessonProgress directly — single source of truth for "completed".

    Note: unlike certificate eligibility, review eligibility does NOT
    require passing quizzes — the spec for Phase 4B defines completion
    purely in terms of "completed the course", matching the same lesson-
    completion definition used everywhere else in the dashboard and
    progress-bar UI.
    """
    enrolled = Enrollment.objects.filter(student=student, course=course).exists()
    if not enrolled:
        return False

    progress = _get_course_progress(student, course)
    return progress['is_complete'] and progress['total_lessons'] > 0


# ─────────────────────────────────────────────────────────────────────────────
#  PUBLIC PAGES  (unchanged except course_detail, marked below)
# ─────────────────────────────────────────────────────────────────────────────

def home(request):
    """Home page with featured courses, teachers, and categories."""
    featured_courses = (
        Course.objects
        .filter(is_published=True)
        .select_related('category', 'teacher')[:6]
    )
    teachers = User.objects.filter(role=User.Role.TEACHER, is_active=True)[:4]
    featured_categories = (
        Category.objects
        .filter(courses__is_published=True)
        .distinct()
        .order_by('name')[:8]
    )
    context = {
        'featured_courses': featured_courses,
        'teachers': teachers,
        'featured_categories': featured_categories,
    }
    return render(request, 'home.html', context)


def about(request):
    return render(request, 'about.html')


def course_list(request):
    """Public course list with level, category, and search filters."""
    level_filter    = request.GET.get('level', '').strip()
    category_filter = request.GET.get('category', '').strip()
    search_query    = request.GET.get('q', '').strip()

    courses = (
        Course.objects
        .filter(is_published=True)
        .select_related('category', 'teacher')
        # Phase 4B: annotate review count + average rating in the same
        # query that already fetches the course list — no extra round trips
        # per course, avoiding N+1 even though each course needs its own
        # aggregate over a different subset of the reviews table.
        .annotate(
            review_count=Count('reviews', distinct=True),
            avg_rating=Avg('reviews__rating'),
        )
    )
    if level_filter:
        courses = courses.filter(level=level_filter)
    if category_filter:
        courses = courses.filter(category__slug=category_filter)
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query)
            | Q(short_description__icontains=search_query)
            | Q(category__name__icontains=search_query)
        ).distinct()

    context = {
        'courses':          courses,
        'level_filter':     level_filter,
        'category_filter':  category_filter,
        'search_query':     search_query,
        'levels':           Course.Level.choices,
        'categories':       Category.objects.all(),
        'any_filter':       bool(level_filter or category_filter or search_query),
    }
    return render(request, 'courses/course_list.html', context)


def course_detail(request, slug):
    """
    Public course detail page.
    Phase 3D: progress bar for enrolled students.
    Phase 3E: certificate eligibility check + certificate CTA.
    Phase 4B: reviews, average rating, review eligibility + CTA.
    """
    course = get_object_or_404(
        Course.objects
        # Phase 4B: annotate rating aggregates directly on this single-object
        # fetch — same pattern as course_list, avoids a second query.
        .annotate(
            review_count=Count('reviews', distinct=True),
            avg_rating=Avg('reviews__rating'),
        ),
        slug=slug,
        is_published=True,
    )
    lessons     = course.lessons.all()
    is_enrolled = False
    progress    = None     # Phase 3D
    certificate = None     # Phase 3E

    # Phase 4B: reviews list + this student's own review (if any)
    reviews = (
        course.reviews
        .select_related('student')
        .order_by('-created_at')
    )
    user_review        = None   # the current student's own review, if it exists
    can_review          = False  # eligible AND hasn't reviewed yet

    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(
            student=request.user, course=course
        ).exists()

        if is_enrolled and request.user.is_student:
            progress = _get_course_progress(request.user, course)

            # Phase 3E: re-check eligibility every time the student views
            # the course detail page. This catches the case where a student
            # finishes their last quiz attempt after already completing
            # all lessons — without touching assessments/views.py at all.
            if progress['is_complete']:
                certificate = _check_and_issue_certificate(request.user, course)

            # Phase 4B: has this student already reviewed this course?
            user_review = Review.objects.filter(
                student=request.user, course=course
            ).first()

            if user_review is None:
                can_review = _is_eligible_to_review(request.user, course)

    context = {
        'course':       course,
        'lessons':      lessons,
        'is_enrolled':  is_enrolled,
        'progress':     progress,      # Phase 3D
        'certificate':  certificate,   # Phase 3E
        # Phase 4B
        'reviews':      reviews,
        'user_review':  user_review,
        'can_review':   can_review,
    }
    return render(request, 'courses/course_detail.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  ENROLLMENT  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)

    if not request.user.is_student:
        messages.error(request, "Only students can enroll in courses.")
        return redirect('course_detail', slug=slug)

    _, created = Enrollment.objects.get_or_create(
        student=request.user, course=course
    )
    if created:
        messages.success(request, f"You are now enrolled in '{course.title}'!")
    else:
        messages.info(request, "You are already enrolled in this course.")

    return redirect('course_detail', slug=slug)


# ─────────────────────────────────────────────────────────────────────────────
#  LESSON VIEWER  (unchanged from Phase 3D)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lesson_view(request, course_slug, lesson_id):
    """View a lesson. Passes completion status and neighbour lessons to template."""
    course = get_object_or_404(Course, slug=course_slug, is_published=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    if request.user.is_teacher and request.user == course.teacher:
        pass
    elif request.user.is_student:
        enrolled = Enrollment.objects.filter(
            student=request.user, course=course
        ).exists()
        if not enrolled:
            messages.error(request, "Please enroll in this course to view lessons.")
            return redirect('course_detail', slug=course_slug)
    else:
        raise PermissionDenied

    all_lessons = list(course.lessons.order_by('order', 'created_at'))

    is_completed = False
    completed_ids = set()
    if request.user.is_student:
        completed_ids = set(
            LessonProgress.objects
            .filter(student=request.user, lesson__in=all_lessons, completed=True)
            .values_list('lesson_id', flat=True)
        )
        is_completed = lesson.pk in completed_ids

    try:
        current_index = next(i for i, l in enumerate(all_lessons) if l.pk == lesson.pk)
    except StopIteration:
        current_index = 0

    prev_lesson = all_lessons[current_index - 1] if current_index > 0 else None
    next_lesson = all_lessons[current_index + 1] if current_index < len(all_lessons) - 1 else None

    context = {
        'course':        course,
        'lesson':        lesson,
        'all_lessons':   all_lessons,
        'completed_ids': completed_ids,
        'is_completed':  is_completed,
        'prev_lesson':   prev_lesson,
        'next_lesson':   next_lesson,
    }
    return render(request, 'courses/lesson_view.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3D — Mark Lesson Complete (toggle)
#  Phase 3E — Now also triggers certificate issuance check on completion
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lesson_complete(request, lesson_id):
    """
    POST-only toggle: marks a lesson complete or incomplete for the student.

    Phase 3E addition: after marking a lesson COMPLETE (not incomplete),
    checks whether the student has now finished the entire course and, if
    so and they also meet the quiz-passing condition, automatically issues
    a CourseCertificate. This is the primary trigger point for certificate
    creation since finishing the last lesson is the most common way a
    course gets completed.
    """
    if request.method != 'POST':
        return redirect('home')

    if not request.user.is_student:
        raise PermissionDenied

    lesson = get_object_or_404(
        Lesson.objects.select_related('course'),
        pk=lesson_id,
    )

    enrolled = Enrollment.objects.filter(
        student=request.user,
        course=lesson.course,
    ).exists()
    if not enrolled:
        raise PermissionDenied

    progress, created = LessonProgress.objects.get_or_create(
        student=request.user,
        lesson=lesson,
        defaults={'completed': False},
    )

    if progress.completed:
        # Toggle OFF — mark incomplete
        progress.completed    = False
        progress.completed_at = None
        progress.save()
        messages.info(request, f"'{lesson.title}' marked as incomplete.")
    else:
        # Toggle ON — mark complete
        progress.completed    = True
        progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, f"✓ '{lesson.title}' marked as complete!")

        # Phase 3E: check for course completion + certificate eligibility
        certificate = _check_and_issue_certificate(request.user, lesson.course)
        if certificate is not None:
            messages.success(
                request,
                f"🎉 Congratulations! You've completed '{lesson.course.title}'. "
                f"Your certificate is ready."
            )

    return redirect('lesson_view', course_slug=lesson.course.slug, lesson_id=lesson.pk)


# ─────────────────────────────────────────────────────────────────────────────
#  STUDENT DASHBOARD  (Phase 3D progress; Phase 3E adds certificate count)
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Phase 4A — Recent Activity helper
# ─────────────────────────────────────────────────────────────────────────────

def _get_recent_activity(student, limit=10):
    """
    Builds a unified, time-ordered activity feed for the student dashboard
    by merging four independent event sources:

        1. LessonProgress  (completed=True)  → "Completed lesson"
        2. QuizAttempt                       → "Passed quiz" / "Failed quiz"
        3. CourseCertificate                 → "Earned certificate"
        4. Enrollment                        → "Enrolled in course"

    None of these four models know about each other, so there is no single
    table to query and sort directly. Instead each source is queried with
    its own small, indexed lookup (4 queries total, each filtered to this
    student and capped to `limit` rows so none of them scan more than
    necessary), normalised into a common dict shape, concatenated, sorted
    by timestamp in Python, and finally truncated to `limit`.

    Each event dict has:
        'type'      : str   — one of 'lesson', 'quiz_pass', 'quiz_fail',
                              'certificate', 'enrollment'
        'icon'      : str   — emoji for the template
        'text'      : str   — human-readable description
        'course'    : Course
        'url'       : str   — link target for "View" action
        'timestamp' : datetime — used for sorting and display

    Performance: 4 queries total regardless of how many courses/quizzes/
    certificates the student has, each using select_related to avoid
    further N+1 lookups when accessing .course / .quiz.course.
    """
    from django.urls import reverse

    events = []

    # ── 1. Completed lessons ──────────────────────────────────────────────
    completed_lessons = (
        LessonProgress.objects
        .filter(student=student, completed=True)
        .select_related('lesson', 'lesson__course')
        .order_by('-completed_at')[:limit]
    )
    for lp in completed_lessons:
        events.append({
            'type':      'lesson',
            'icon':      '✅',
            'text':      f"Completed lesson \u201c{lp.lesson.title}\u201d",
            'course':    lp.lesson.course,
            'url':       reverse('lesson_view', kwargs={
                             'course_slug': lp.lesson.course.slug,
                             'lesson_id': lp.lesson.pk,
                         }),
            'timestamp': lp.completed_at,
        })

    # ── 2. Quiz attempts (pass or fail) ───────────────────────────────────
    quiz_attempts = (
        QuizAttempt.objects
        .filter(student=student)
        .select_related('quiz', 'quiz__course')
        .order_by('-created_at')[:limit]
    )
    for attempt in quiz_attempts:
        events.append({
            'type':      'quiz_pass' if attempt.passed else 'quiz_fail',
            'icon':      '🏅' if attempt.passed else '📝',
            'text':      (
                f"{'Passed' if attempt.passed else 'Failed'} quiz "
                f"\u201c{attempt.quiz.title}\u201d ({attempt.percentage}%)"
            ),
            'course':    attempt.quiz.course,
            'url':       reverse('attempt_detail', kwargs={'attempt_id': attempt.pk}),
            'timestamp': attempt.created_at,
        })

    # ── 3. Certificates earned ────────────────────────────────────────────
    certificates = (
        CourseCertificate.objects
        .filter(student=student)
        .select_related('course')
        .order_by('-issued_at')[:limit]
    )
    for cert in certificates:
        events.append({
            'type':      'certificate',
            'icon':      '🏆',
            'text':      f"Earned certificate for \u201c{cert.course.title}\u201d",
            'course':    cert.course,
            'url':       reverse('certificate_detail', kwargs={'certificate_id': cert.pk}),
            'timestamp': cert.issued_at,
        })

    # ── 4. Course enrollments ─────────────────────────────────────────────
    enrollments = (
        Enrollment.objects
        .filter(student=student)
        .select_related('course')
        .order_by('-enrolled_at')[:limit]
    )
    for enrollment in enrollments:
        events.append({
            'type':      'enrollment',
            'icon':      '📚',
            'text':      f"Enrolled in \u201c{enrollment.course.title}\u201d",
            'course':    enrollment.course,
            'url':       reverse('course_detail', kwargs={'slug': enrollment.course.slug}),
            'timestamp': enrollment.enrolled_at,
        })

    # ── Merge, sort newest-first, truncate ────────────────────────────────
    # Some timestamps (completed_at) can be None if a LessonProgress row
    # exists but was never actually marked complete — filtered out here
    # defensively, though completed=True should always set completed_at.
    events = [e for e in events if e['timestamp'] is not None]
    events.sort(key=lambda e: e['timestamp'], reverse=True)

    return events[:limit]


@login_required
def student_dashboard(request):
    """
    Student dashboard — learning analytics center (Phase 4A) with
    personalised recommendations (Phase 4C).

    Adds on top of existing Phase 3D/3E data:
      - total_completed_lessons : sum across ALL enrolled courses
                                   (distinct from per-course completed_lessons
                                   already available via enrollment.progress)
      - quiz_attempt_count      : total quiz attempts ever made by this student
      - average_quiz_score      : average percentage across all attempts,
                                   rounded to nearest whole number
      - recent_certificates     : latest 5 CourseCertificate rows
      - recommended_courses     : up to 6 personalised course recommendations,
                                   computed entirely by
                                   CourseRecommendationService.get_recommendations()
                                   (Phase 4C) — this view does NOT contain any
                                   scoring logic itself, per the architecture
                                   requirement that all recommendation rules
                                   live in courses/services.py.

    All existing context keys (enrollments, available_quizzes,
    recent_attempts, progress_map, completed_courses, certificate_count)
    are preserved exactly as before.
    """
    if not request.user.is_student:
        if request.user.is_teacher:
            return redirect('teacher_dashboard')
        return redirect('home')

    enrollments = (
        Enrollment.objects
        .filter(student=request.user)
        .select_related('course', 'course__teacher')
    )

    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    available_quizzes   = (
        Quiz.objects
        .filter(course_id__in=enrolled_course_ids)
        .select_related('course')
        .order_by('-created_at')[:10]
    )

    # All quiz attempts by this student (used for both the "recent 5" table
    # and the average score calculation below — built once, reused twice)
    all_attempts = (
        QuizAttempt.objects
        .filter(student=request.user)
        .select_related('quiz', 'quiz__course')
        .order_by('-created_at')
    )
    recent_attempts = all_attempts[:5]

    enrolled_courses = [e.course for e in enrollments]
    progress_map     = _get_progress_map(request.user, enrolled_courses)

    for enrollment in enrollments:
        enrollment.progress = progress_map.get(enrollment.course.pk, {
            'total_lessons': 0, 'completed_lessons': 0,
            'percentage': 0, 'is_complete': False, 'first_incomplete': None,
        })

    completed_courses = sum(
        1 for p in progress_map.values() if p['is_complete']
    )

    # Phase 4A: total completed lessons across ALL enrolled courses.
    # One query — reuses the same LessonProgress table already populated
    # by the Phase 3D lesson-completion feature.
    total_completed_lessons = LessonProgress.objects.filter(
        student=request.user,
        completed=True,
    ).count()

    # Phase 3E: certificate count for the stats row (unchanged)
    certificate_count = CourseCertificate.objects.filter(student=request.user).count()

    # Phase 4A: latest 5 certificates for the "Recent Certificates" section
    recent_certificates = (
        CourseCertificate.objects
        .filter(student=request.user)
        .select_related('course')
        .order_by('-issued_at')[:5]
    )

    # Phase 4A: quiz attempt count + average score (Performance Summary)
    # Aggregate computed in the database rather than in Python — single query.
    quiz_stats = all_attempts.aggregate(
        attempt_count=Count('id'),
        avg_percentage=Avg('percentage'),
    )
    quiz_attempt_count = quiz_stats['attempt_count'] or 0
    average_quiz_score = (
        round(quiz_stats['avg_percentage'])
        if quiz_stats['avg_percentage'] is not None
        else 0
    )

    # Phase 4A: unified recent activity feed (4 queries, merged + sorted)
    recent_activity = _get_recent_activity(request.user, limit=10)

    # Phase 4A: latest certificate for the Certificate Summary section
    # (recent_certificates is already ordered -issued_at, so first() is free)
    latest_certificate = recent_certificates[0] if recent_certificates else None

    # Phase 4C: personalised course recommendations.
    # All scoring logic lives in CourseRecommendationService — this view
    # only calls it and passes the result into the template context.
    recommended_courses = CourseRecommendationService.get_recommendations(
        student=request.user,
        limit=6,
    )

    context = {
        'enrollments':              enrollments,
        'available_quizzes':        available_quizzes,
        'recent_attempts':          recent_attempts,
        'progress_map':             progress_map,
        'completed_courses':        completed_courses,
        'certificate_count':        certificate_count,
        # Phase 4A additions
        'total_completed_lessons':  total_completed_lessons,
        'recent_certificates':      recent_certificates,
        'latest_certificate':       latest_certificate,
        'quiz_attempt_count':       quiz_attempt_count,
        'average_quiz_score':       average_quiz_score,
        'recent_activity':          recent_activity,
        # Phase 4C addition
        'recommended_courses':      recommended_courses,
    }
    return render(request, 'courses/student_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  TEACHER DASHBOARD  (Phase 3D completion analytics; Phase 3E certificates)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def teacher_dashboard(request):
    """Teacher dashboard with completion analytics and certificates issued."""
    if not request.user.is_teacher:
        if request.user.is_student:
            return redirect('student_dashboard')
        return redirect('home')

    courses = (
        Course.objects
        .filter(teacher=request.user)
        .select_related('category')
    )

    recent_attempts = (
        QuizAttempt.objects
        .filter(quiz__course__teacher=request.user)
        .select_related('student', 'quiz', 'quiz__course')
        .order_by('-created_at')[:5]
    )

    # Phase 3D: per-course completion analytics
    course_analytics = []
    for course in courses:
        lesson_count   = course.lesson_count
        enrolled_count = course.enrollment_count

        if lesson_count > 0 and enrolled_count > 0:
            completed_count = (
                LessonProgress.objects
                .filter(lesson__course=course, completed=True)
                .values('student')
                .annotate(done=Count('id'))
                .filter(done=lesson_count)
                .count()
            )
            completion_rate = round((completed_count / enrolled_count) * 100)
        else:
            completed_count = 0
            completion_rate = 0

        course_analytics.append({
            'course':          course,
            'enrolled_count':  enrolled_count,
            'completed_count': completed_count,
            'completion_rate': completion_rate,
        })

    # Phase 3E: certificates issued per course (one query, grouped)
    cert_counts_qs = (
        CourseCertificate.objects
        .filter(course__teacher=request.user)
        .values('course_id')
        .annotate(total=Count('id'))
    )
    cert_counts_by_course = {row['course_id']: row['total'] for row in cert_counts_qs}

    certificate_analytics = [
        {
            'course': course,
            'certificate_count': cert_counts_by_course.get(course.pk, 0),
        }
        for course in courses
    ]
    total_certificates_issued = sum(cert_counts_by_course.values())

    # Phase 4B.1: lightweight summary numbers for the "View Full Analytics"
    # teaser cards on the main dashboard — full breakdowns live on the
    # dedicated /teacher/analytics/ page, these are just headline figures.
    total_quiz_attempts = QuizAttempt.objects.filter(
        quiz__course__teacher=request.user
    ).count()

    rating_agg = Review.objects.filter(course__teacher=request.user).aggregate(
        avg_rating=Avg('rating'),
    )
    average_course_rating = (
        round(rating_agg['avg_rating'], 1)
        if rating_agg['avg_rating'] is not None
        else None
    )

    context = {
        'courses':                   courses,
        'total_courses':             courses.count(),
        'published_count':           courses.filter(is_published=True).count(),
        'recent_attempts':           recent_attempts,
        'course_analytics':          course_analytics,           # Phase 3D
        'certificate_analytics':     certificate_analytics,      # Phase 3E
        'total_certificates_issued': total_certificates_issued,  # Phase 3E
        # Phase 4B.1 — analytics teaser cards
        'total_quiz_attempts':       total_quiz_attempts,
        'average_course_rating':     average_course_rating,
    }
    return render(request, 'courses/teacher_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  COURSE CRUD  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def course_create(request):
    if not request.user.is_teacher:
        raise PermissionDenied

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course          = form.save(commit=False)
            course.teacher  = request.user
            course.save()
            messages.success(request, f"Course '{course.title}' created successfully!")
            return redirect('course_manage', slug=course.slug)
    else:
        form = CourseForm()

    return render(request, 'courses/course_form.html', {'form': form, 'action': 'Create'})


@login_required
def course_edit(request, slug):
    course = get_object_or_404(Course, slug=slug)

    if course.teacher != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated successfully!")
            return redirect('course_manage', slug=course.slug)
    else:
        form = CourseForm(instance=course)

    return render(request, 'courses/course_form.html', {
        'form': form, 'course': course, 'action': 'Edit'
    })


@login_required
def course_manage(request, slug):
    course = get_object_or_404(Course, slug=slug)

    if course.teacher != request.user:
        raise PermissionDenied

    context = {'course': course, 'lessons': course.lessons.all()}
    return render(request, 'courses/course_manage.html', context)


@login_required
def lesson_create(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)

    if course.teacher != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson        = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, f"Lesson '{lesson.title}' added!")
            return redirect('course_manage', slug=course_slug)
    else:
        form = LessonForm(initial={'order': course.lessons.count() + 1})

    return render(request, 'courses/lesson_form.html', {
        'form': form, 'course': course, 'action': 'Add'
    })


@login_required
def lesson_edit(request, course_slug, lesson_id):
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    if course.teacher != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, "Lesson updated!")
            return redirect('course_manage', slug=course_slug)
    else:
        form = LessonForm(instance=lesson)

    return render(request, 'courses/lesson_form.html', {
        'form': form, 'course': course, 'lesson': lesson, 'action': 'Edit'
    })


@login_required
def lesson_delete(request, course_slug, lesson_id):
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    if course.teacher != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        title = lesson.title
        lesson.delete()
        messages.success(request, f"Lesson '{title}' deleted.")
        return redirect('course_manage', slug=course_slug)

    return render(request, 'courses/lesson_confirm_delete.html', {
        'lesson': lesson, 'course': course
    })


# ─────────────────────────────────────────────────────────────────────────────
#  CATEGORY VIEWS  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    courses  = (
        Course.objects
        .filter(category=category, is_published=True)
        .select_related('teacher')
        .order_by('-created_at')
    )
    other_categories = (
        Category.objects
        .filter(courses__is_published=True)
        .distinct()
        .exclude(pk=category.pk)
        .order_by('name')
    )
    context = {
        'category':          category,
        'courses':           courses,
        'other_categories':  other_categories,
    }
    return render(request, 'courses/category_detail.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3E — Certificate Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def certificate_list(request):
    """
    'My Certificates' page.
    Students only see their own certificates.
    """
    if not request.user.is_student:
        if request.user.is_teacher:
            return redirect('teacher_dashboard')
        return redirect('home')

    certificates = (
        CourseCertificate.objects
        .filter(student=request.user)
        .select_related('course', 'course__teacher')
        .order_by('-issued_at')
    )

    context = {'certificates': certificates}
    return render(request, 'courses/certificate_list.html', context)


@login_required
def certificate_detail(request, certificate_id):
    """
    Certificate detail page at /certificates/<id>/.

    Security: students can only view their own certificate; teachers can
    only view certificates from courses they own; admins are unrestricted.
    """
    certificate = get_object_or_404(
        CourseCertificate.objects.select_related(
            'student', 'course', 'course__teacher'
        ),
        pk=certificate_id,
    )

    if request.user.is_student:
        if certificate.student != request.user:
            raise PermissionDenied
    elif request.user.is_teacher:
        if certificate.course.teacher != request.user:
            raise PermissionDenied
    # Admins (is_staff) pass through unrestricted

    context = {'certificate': certificate}
    return render(request, 'courses/certificate_detail.html', context)


@login_required
def certificate_print(request, certificate_id):
    """
    Printable certificate page — minimal layout, browser print only.
    Same security rules as certificate_detail.
    """
    certificate = get_object_or_404(
        CourseCertificate.objects.select_related(
            'student', 'course', 'course__teacher'
        ),
        pk=certificate_id,
    )

    if request.user.is_student:
        if certificate.student != request.user:
            raise PermissionDenied
    elif request.user.is_teacher:
        if certificate.course.teacher != request.user:
            raise PermissionDenied

    context = {'certificate': certificate}
    return render(request, 'courses/certificate_print.html', context)


def certificate_verify(request, certificate_id):
    """
    Public certificate verification page at /certificate/verify/<certificate_id>/.

    No login required — anyone with a certificate_id (e.g. from a printed
    certificate) can verify it is genuine. Looks up by the certificate_id
    string field, NOT the numeric primary key, since that is what is printed
    on the certificate itself.
    """
    certificate = (
        CourseCertificate.objects
        .select_related('student', 'course')
        .filter(certificate_id=certificate_id)
        .first()
    )

    context = {
        'certificate_id_queried': certificate_id,
        'certificate': certificate,
        'is_valid': certificate is not None,
    }
    return render(request, 'courses/certificate_verify.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4B — Review Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def review_create(request, course_id):
    """
    Student creates a review for a course.

    Rules enforced:
      - Must be logged in            (@login_required)
      - Must be a student            (is_student check)
      - Must be enrolled             (_is_eligible_to_review)
      - Must have completed course   (_is_eligible_to_review)
      - Cannot submit duplicate      (unique_together + explicit check below)

    course and student are NEVER taken from form input — course comes from
    the URL (and is fetched fresh from the DB), student is always
    request.user. This makes it impossible for a tampered POST body to
    attribute a review to a different course or a different student.
    """
    course = get_object_or_404(Course, pk=course_id, is_published=True)

    if not request.user.is_student:
        raise PermissionDenied

    if not _is_eligible_to_review(request.user, course):
        messages.error(
            request,
            "You can only review a course after completing all of its lessons."
        )
        return redirect('course_detail', slug=course.slug)

    # Duplicate guard — belt-and-suspenders alongside the DB UniqueConstraint.
    # Checking here lets us show a friendly message instead of letting an
    # IntegrityError bubble up as a 500 error.
    if Review.objects.filter(student=request.user, course=course).exists():
        messages.info(request, "You have already reviewed this course.")
        return redirect('course_detail', slug=course.slug)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review          = form.save(commit=False)
            review.course   = course
            review.student  = request.user
            review.save()
            messages.success(request, "Thank you! Your review has been posted.")
            return redirect('course_detail', slug=course.slug)
    else:
        form = ReviewForm()

    context = {'form': form, 'course': course, 'action': 'Create'}
    return render(request, 'courses/review_form.html', context)


@login_required
def review_edit(request, review_id):
    """
    Student edits their own review.

    Security: only the review's owner may edit it — anyone else gets
    PermissionDenied, including teachers (teachers have a read-only view
    via teacher_reviews, not an edit path).
    """
    review = get_object_or_404(
        Review.objects.select_related('course', 'student'),
        pk=review_id,
    )

    if review.student != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, "Your review has been updated.")
            return redirect('course_detail', slug=review.course.slug)
    else:
        form = ReviewForm(instance=review)

    context = {'form': form, 'course': review.course, 'review': review, 'action': 'Edit'}
    return render(request, 'courses/review_form.html', context)


@login_required
def review_delete(request, review_id):
    """
    Student deletes their own review.
    Confirmation page on GET; actual deletion only on POST.

    Security: only the review's owner may delete it.
    """
    review = get_object_or_404(
        Review.objects.select_related('course', 'student'),
        pk=review_id,
    )

    if review.student != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        course_slug = review.course.slug
        review.delete()
        messages.success(request, "Your review has been deleted.")
        return redirect('course_detail', slug=course_slug)

    context = {'review': review, 'course': review.course}
    return render(request, 'courses/review_confirm_delete.html', context)


@login_required
def teacher_reviews(request):
    """
    Teacher analytics page — all reviews left on the teacher's own courses.

    Security: filtered by course__teacher=request.user at the query level,
    so a teacher can never see reviews for another teacher's courses even
    if they guess a review ID (this view doesn't take an ID at all — it's
    a list view scoped entirely by the logged-in teacher).

    Performance: one query for the review list (select_related avoids
    N+1 on .student and .course), one aggregate query for summary stats,
    one small query for highest-rated course.
    """
    if not request.user.is_teacher:
        if request.user.is_student:
            return redirect('student_dashboard')
        raise PermissionDenied

    reviews = (
        Review.objects
        .filter(course__teacher=request.user)
        .select_related('student', 'course')
        .order_by('-created_at')
    )

    # Summary cards: total reviews + average rating across ALL of this
    # teacher's courses, computed in the database in one aggregate query.
    summary = reviews.aggregate(
        total_reviews=Count('id'),
        avg_rating=Avg('rating'),
    )
    total_reviews = summary['total_reviews'] or 0
    avg_rating    = round(summary['avg_rating'], 1) if summary['avg_rating'] is not None else None

    # Highest rated course: annotate each of the teacher's courses with its
    # average rating and review count, then pick the top one. A course needs
    # at least one review to be considered (review_count__gt=0) so a brand
    # new course with no reviews doesn't show up as "highest rated".
    highest_rated_course = (
        Course.objects
        .filter(teacher=request.user)
        .annotate(
            review_count=Count('reviews', distinct=True),
            avg_rating=Avg('reviews__rating'),
        )
        .filter(review_count__gt=0)
        .order_by('-avg_rating')
        .first()
    )

    context = {
        'reviews':              reviews,
        'total_reviews':        total_reviews,
        'avg_rating':           avg_rating,
        'highest_rated_course': highest_rated_course,
    }
    return render(request, 'courses/teacher_reviews.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4B.1 — Advanced Teacher Analytics Dashboard
# ─────────────────────────────────────────────────────────────────────────────

def _get_teacher_recent_activity(teacher, limit=10):
    """
    Builds a unified, time-ordered activity feed scoped to one teacher's
    courses, merging FIVE independent event sources:

        1. Enrollment        → "X enrolled in Y"
        2. LessonProgress     → "X completed lesson Y"
        3. QuizAttempt        → "X passed/failed quiz Y"
        4. CourseCertificate  → "X earned a certificate for Y"
        5. Review             → "X submitted a review for Y"

    Mirrors the exact pattern of _get_recent_activity() (Phase 4A), but
    every query is scoped by the course's teacher FK instead of by a single
    student, and the resulting text always names the student so a teacher
    reading the feed knows *which* student did *what*.

    Performance: 5 queries total regardless of how many courses/students
    the teacher has, each capped at `limit` rows and using select_related
    to avoid N+1 lookups when accessing related student/course/quiz objects.
    """
    from django.urls import reverse

    events = []

    # ── 1. Enrollments ─────────────────────────────────────────────────────
    enrollments = (
        Enrollment.objects
        .filter(course__teacher=teacher)
        .select_related('student', 'course')
        .order_by('-enrolled_at')[:limit]
    )
    for e in enrollments:
        events.append({
            'type':      'enrollment',
            'icon':      '📚',
            'text':      (
                f"{e.student.get_full_name() or e.student.username} "
                f"enrolled in \u201c{e.course.title}\u201d"
            ),
            'course':    e.course,
            'url':       reverse('course_detail', kwargs={'slug': e.course.slug}),
            'timestamp': e.enrolled_at,
        })

    # ── 2. Completed lessons ──────────────────────────────────────────────
    completed_lessons = (
        LessonProgress.objects
        .filter(lesson__course__teacher=teacher, completed=True)
        .select_related('student', 'lesson', 'lesson__course')
        .order_by('-completed_at')[:limit]
    )
    for lp in completed_lessons:
        events.append({
            'type':      'lesson',
            'icon':      '✅',
            'text':      (
                f"{lp.student.get_full_name() or lp.student.username} "
                f"completed lesson \u201c{lp.lesson.title}\u201d"
            ),
            'course':    lp.lesson.course,
            'url':       reverse('course_manage', kwargs={'slug': lp.lesson.course.slug}),
            'timestamp': lp.completed_at,
        })

    # ── 3. Quiz attempts (pass or fail) ────────────────────────────────────
    quiz_attempts = (
        QuizAttempt.objects
        .filter(quiz__course__teacher=teacher)
        .select_related('student', 'quiz', 'quiz__course')
        .order_by('-created_at')[:limit]
    )
    for attempt in quiz_attempts:
        events.append({
            'type':      'quiz_pass' if attempt.passed else 'quiz_fail',
            'icon':      '🏅' if attempt.passed else '📝',
            'text':      (
                f"{attempt.student.get_full_name() or attempt.student.username} "
                f"{'passed' if attempt.passed else 'failed'} quiz "
                f"\u201c{attempt.quiz.title}\u201d ({attempt.percentage}%)"
            ),
            'course':    attempt.quiz.course,
            'url':       reverse('attempt_detail', kwargs={'attempt_id': attempt.pk}),
            'timestamp': attempt.created_at,
        })

    # ── 4. Certificates issued ─────────────────────────────────────────────
    certificates = (
        CourseCertificate.objects
        .filter(course__teacher=teacher)
        .select_related('student', 'course')
        .order_by('-issued_at')[:limit]
    )
    for cert in certificates:
        events.append({
            'type':      'certificate',
            'icon':      '🏆',
            'text':      (
                f"{cert.student.get_full_name() or cert.student.username} "
                f"earned a certificate for \u201c{cert.course.title}\u201d"
            ),
            'course':    cert.course,
            'url':       reverse('certificate_detail', kwargs={'certificate_id': cert.pk}),
            'timestamp': cert.issued_at,
        })

    # ── 5. Reviews submitted ───────────────────────────────────────────────
    reviews = (
        Review.objects
        .filter(course__teacher=teacher)
        .select_related('student', 'course')
        .order_by('-created_at')[:limit]
    )
    for review in reviews:
        events.append({
            'type':      'review',
            'icon':      '⭐',
            'text':      (
                f"{review.student.get_full_name() or review.student.username} "
                f"submitted a {review.rating}-star review for \u201c{review.course.title}\u201d"
            ),
            'course':    review.course,
            'url':       reverse('course_detail', kwargs={'slug': review.course.slug}),
            'timestamp': review.created_at,
        })

    # ── Merge, sort newest-first, truncate ─────────────────────────────────
    events = [e for e in events if e['timestamp'] is not None]
    events.sort(key=lambda e: e['timestamp'], reverse=True)

    return events[:limit]


@login_required
def teacher_analytics(request):
    """
    Advanced Teacher Analytics Dashboard — /courses/teacher/analytics/

    Security: @login_required + explicit is_teacher check. Students are
    redirected to their own dashboard; any other non-teacher role gets
    PermissionDenied. No course/student ID is ever taken from the URL on
    this page, so there is no object-level permission surface to attack —
    every query below is pre-scoped to course__teacher=request.user (or
    quiz__course__teacher / lesson__course__teacher for the related models),
    meaning a teacher can only ever see aggregates over their own courses.

    Performance notes:
        - All "for course in courses" loops below run a small, fixed number
          of queries per course (typically 1–2). With a realistic number of
          courses per teacher (rarely more than a few dozen) this is far
          simpler and more maintainable than a single giant subquery, and
          is the same pattern already used by the existing course_analytics
          block in teacher_dashboard() — kept consistent here deliberately.
        - Aggregates that don't need to vary per-course (overall totals,
          top students, recent activity) are computed with single
          .aggregate() / .annotate() calls rather than Python loops.
    """
    if not request.user.is_teacher:
        if request.user.is_student:
            return redirect('student_dashboard')
        raise PermissionDenied

    teacher = request.user

    courses = (
        Course.objects
        .filter(teacher=teacher)
        .select_related('category')
        .prefetch_related('quizzes')
    )
    course_count = courses.count()

    # ─────────────────────────────────────────────────────────────────────
    # 1. Teacher Overview Statistics
    # ─────────────────────────────────────────────────────────────────────
    total_courses    = course_count
    published_count  = courses.filter(is_published=True).count()
    draft_count      = total_courses - published_count

    # Total students across all courses == total Enrollment rows for these
    # courses (a student enrolled in 3 of the teacher's courses counts 3x,
    # matching "Total Students Across All Courses" as a sum, not distinct).
    total_enrollments = Enrollment.objects.filter(course__teacher=teacher).count()

    total_quiz_attempts = QuizAttempt.objects.filter(
        quiz__course__teacher=teacher
    ).count()

    total_certificates_issued = CourseCertificate.objects.filter(
        course__teacher=teacher
    ).count()

    # Average rating across ALL of this teacher's courses (one aggregate query)
    rating_agg = Review.objects.filter(course__teacher=teacher).aggregate(
        avg_rating=Avg('rating'),
    )
    average_course_rating = (
        round(rating_agg['avg_rating'], 1)
        if rating_agg['avg_rating'] is not None
        else None
    )

    # ─────────────────────────────────────────────────────────────────────
    # 2 & 3. Per-course analytics — Student Growth + Course Performance
    #         (built together since they iterate the same course list)
    # ─────────────────────────────────────────────────────────────────────
    course_performance = []
    enrollment_counts  = {}   # course.pk -> enrolled_count, reused below for "most/least popular"

    # Pre-fetch certificate counts and review aggregates per course in bulk
    # (2 queries total) instead of querying inside the loop.
    cert_counts_qs = (
        CourseCertificate.objects
        .filter(course__teacher=teacher)
        .values('course_id')
        .annotate(total=Count('id'))
    )
    cert_counts_by_course = {row['course_id']: row['total'] for row in cert_counts_qs}

    rating_by_course_qs = (
        Review.objects
        .filter(course__teacher=teacher)
        .values('course_id')
        .annotate(avg_rating=Avg('rating'))
    )
    rating_by_course = {
        row['course_id']: round(row['avg_rating'], 1)
        for row in rating_by_course_qs
    }

    for course in courses:
        lesson_count   = course.lesson_count
        enrolled_count = course.enrollment_count
        quiz_count     = course.quizzes.count()

        enrollment_counts[course.pk] = enrolled_count

        if lesson_count > 0 and enrolled_count > 0:
            completed_count = (
                LessonProgress.objects
                .filter(lesson__course=course, completed=True)
                .values('student')
                .annotate(done=Count('id'))
                .filter(done=lesson_count)
                .count()
            )
            completion_rate = round((completed_count / enrolled_count) * 100)
        else:
            completed_count = 0
            completion_rate = 0

        course_performance.append({
            'course':            course,
            'enrolled_count':    enrolled_count,
            'completed_count':   completed_count,
            'completion_rate':   completion_rate,
            'avg_rating':        rating_by_course.get(course.pk),
            'certificate_count': cert_counts_by_course.get(course.pk, 0),
            'lesson_count':      lesson_count,
            'quiz_count':        quiz_count,
        })

    # Overall completion rate across ALL courses combined (not averaged
    # per-course — total completions over total enrollments, so a teacher
    # with one huge course and one tiny course gets a fair blended figure).
    total_enrolled_sum   = sum(row['enrolled_count'] for row in course_performance)
    total_completed_sum  = sum(row['completed_count'] for row in course_performance)
    overall_completion_rate = (
        round((total_completed_sum / total_enrolled_sum) * 100)
        if total_enrolled_sum > 0
        else 0
    )

    # ── Student Growth Analytics ───────────────────────────────────────────
    most_popular_course  = None
    least_popular_course = None
    if course_performance:
        most_popular_course  = max(course_performance, key=lambda r: r['enrolled_count'])
        least_popular_course = min(course_performance, key=lambda r: r['enrolled_count'])

    total_active_students = (
        Enrollment.objects
        .filter(course__teacher=teacher)
        .values('student')
        .distinct()
        .count()
    )

    # ─────────────────────────────────────────────────────────────────────
    # 4. Quiz Performance Analytics
    # ─────────────────────────────────────────────────────────────────────
    quizzes = (
        Quiz.objects
        .filter(course__teacher=teacher)
        .select_related('course')
    )

    quiz_performance = []
    for quiz in quizzes:
        stats = QuizAttempt.objects.filter(quiz=quiz).aggregate(
            attempt_count=Count('id'),
            avg_score=Avg('percentage'),
            highest_score=Max('percentage'),
            lowest_score=Min('percentage'),
            pass_count=Count('id', filter=Q(passed=True)),
        )
        attempt_count = stats['attempt_count'] or 0

        if attempt_count > 0:
            pass_rate = round((stats['pass_count'] / attempt_count) * 100)
            fail_rate = 100 - pass_rate
        else:
            pass_rate = 0
            fail_rate = 0

        quiz_performance.append({
            'quiz':           quiz,
            'attempt_count':  attempt_count,
            'pass_rate':      pass_rate,
            'fail_rate':      fail_rate,
            'avg_score':      round(stats['avg_score'], 1) if stats['avg_score'] is not None else None,
            'highest_score':  stats['highest_score'],
            'lowest_score':   stats['lowest_score'],
        })

    # ─────────────────────────────────────────────────────────────────────
    # 5. Top Performing Students (top 10)
    # ─────────────────────────────────────────────────────────────────────
    # Build per-student aggregates across ONLY this teacher's courses:
    #   - courses_completed : count of courses where the student completed
    #                         every lesson (computed the same way as the
    #                         per-course completion check above, but
    #                         grouped by student instead of by course)
    #   - certificates_earned
    #   - avg_quiz_score
    #
    # Three small aggregate queries, merged in Python by student ID —
    # there is no single ORM query that can compute "courses completed"
    # (a derived, cross-table condition) alongside simple counts, so this
    # follows the same merge-and-rank pattern already used by
    # _get_teacher_recent_activity / _get_recent_activity above.

    student_ids = set(
        Enrollment.objects
        .filter(course__teacher=teacher)
        .values_list('student_id', flat=True)
        .distinct()
    )

    # Certificates earned per student (only for this teacher's courses)
    cert_by_student_qs = (
        CourseCertificate.objects
        .filter(course__teacher=teacher)
        .values('student_id')
        .annotate(total=Count('id'))
    )
    certs_by_student = {row['student_id']: row['total'] for row in cert_by_student_qs}

    # Average quiz score per student (only for quizzes in this teacher's courses)
    quiz_score_by_student_qs = (
        QuizAttempt.objects
        .filter(quiz__course__teacher=teacher)
        .values('student_id')
        .annotate(avg_score=Avg('percentage'))
    )
    quiz_score_by_student = {
        row['student_id']: round(row['avg_score'], 1)
        for row in quiz_score_by_student_qs
    }

    # Courses completed per student: for each (student, course) enrollment
    # pair in this teacher's courses, check whether completed lessons ==
    # total lessons. Done with one query per student is too slow at scale,
    # so instead we pull all relevant LessonProgress rows once and reduce
    # in Python — bounded by (students × teacher's courses), which is small.
    enrollments_qs = (
        Enrollment.objects
        .filter(course__teacher=teacher)
        .select_related('course')
    )
    lesson_counts_by_course = {
        cp['course'].pk: cp['lesson_count']
        for cp in course_performance
    }
    completed_lesson_counts = (
        LessonProgress.objects
        .filter(lesson__course__teacher=teacher, completed=True)
        .values('student_id', 'lesson__course_id')
        .annotate(done=Count('id'))
    )
    # Map: (student_id, course_id) -> completed lesson count
    done_map = {
        (row['student_id'], row['lesson__course_id']): row['done']
        for row in completed_lesson_counts
    }

    courses_completed_by_student = {}
    for enrollment in enrollments_qs:
        sid = enrollment.student_id
        cid = enrollment.course_id
        total_lessons_for_course = lesson_counts_by_course.get(cid, 0)
        done_for_pair = done_map.get((sid, cid), 0)
        if total_lessons_for_course > 0 and done_for_pair == total_lessons_for_course:
            courses_completed_by_student[sid] = courses_completed_by_student.get(sid, 0) + 1

    # Fetch the actual User objects for all students who have any data
    relevant_student_ids = student_ids | set(certs_by_student) | set(quiz_score_by_student)
    students_map = {
        u.pk: u for u in User.objects.filter(pk__in=relevant_student_ids)
    }

    top_students = []
    for sid in relevant_student_ids:
        student = students_map.get(sid)
        if student is None:
            continue
        top_students.append({
            'student':            student,
            'courses_completed':  courses_completed_by_student.get(sid, 0),
            'certificates_earned': certs_by_student.get(sid, 0),
            'avg_quiz_score':     quiz_score_by_student.get(sid),
        })

    # Rank by: courses completed (desc), then certificates (desc), then
    # average quiz score (desc, treating None as 0 so it sorts last)
    top_students.sort(
        key=lambda r: (
            r['courses_completed'],
            r['certificates_earned'],
            r['avg_quiz_score'] or 0,
        ),
        reverse=True,
    )
    top_students = top_students[:10]

    # ─────────────────────────────────────────────────────────────────────
    # 6. Recent Activity Feed (5 event types, newest first)
    # ─────────────────────────────────────────────────────────────────────
    recent_activity = _get_teacher_recent_activity(teacher, limit=10)

    context = {
        # 1. Overview statistics
        'total_courses':             total_courses,
        'published_count':           published_count,
        'draft_count':                draft_count,
        'total_enrollments':          total_enrollments,
        'total_quiz_attempts':        total_quiz_attempts,
        'total_certificates_issued':  total_certificates_issued,
        'average_course_rating':      average_course_rating,
        'overall_completion_rate':    overall_completion_rate,

        # 2. Student growth analytics
        'most_popular_course':        most_popular_course,
        'least_popular_course':       least_popular_course,
        'total_active_students':      total_active_students,

        # 3. Course performance analytics
        'course_performance':         course_performance,

        # 4. Quiz performance analytics
        'quiz_performance':           quiz_performance,

        # 5. Top performing students
        'top_students':               top_students,

        # 6. Recent activity feed
        'recent_activity':            recent_activity,
    }
    return render(request, 'courses/teacher_analytics.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5A — AI Learning Advisor
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def advisor_dashboard(request):
    """
    AI Learning Advisor page — /courses/advisor/

    Security: @login_required + explicit role check.
      - Students: full access.
      - Teachers: PermissionDenied (this page analyses a *student's*
        learning history; it has no meaning for a teacher account).
      - Anonymous: redirected to login by @login_required.

    All analysis logic lives in AILearningAdvisorService — this view does
    nothing but call get_advice() and render the result, exactly mirroring
    the existing architecture of CourseRecommendationService (Phase 4C).
    """
    if not request.user.is_student:
        if request.user.is_teacher:
            raise PermissionDenied
        return redirect('home')

    advice = AILearningAdvisorService().get_advice(request.user)

    context = {
        'advice': advice,
    }
    return render(request, 'courses/advisor_dashboard.html', context)