"""
courses/views.py

All existing Phase 1/2/3B views are preserved exactly.
Phase 3D additions are clearly marked.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
# Phase 3B
from assessments.models import Quiz, QuizAttempt

from .forms import CourseForm, LessonForm
from .models import Category, Course, Enrollment, Lesson, LessonProgress


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3D — Progress helpers
# These are pure functions with no side-effects; they are called by multiple
# views so they live here rather than being duplicated.
# ─────────────────────────────────────────────────────────────────────────────

def _get_course_progress(student, course):
    """
    Returns a dict with progress data for one student / course pair.

    Keys
    ----
    total_lessons      : int   — number of lessons in the course
    completed_lessons  : int   — lessons this student has completed
    percentage         : int   — rounded completion percentage (0–100)
    is_complete        : bool  — True when percentage == 100
    first_incomplete   : Lesson|None — the first lesson not yet completed,
                         used for the "Continue Learning" button

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

    Fetches all relevant LessonProgress rows in TWO queries total regardless
    of how many courses are passed — avoids N+1 on the dashboard.

    Returns a dict keyed by course.pk → progress dict (same shape as above).
    """
    course_list  = list(courses)
    if not course_list:
        return {}

    course_ids   = [c.pk for c in course_list]

    # Query 1: all lessons for these courses
    lessons_qs   = (
        Lesson.objects
        .filter(course_id__in=course_ids)
        .order_by('order', 'created_at')
    )
    # Group by course
    from collections import defaultdict
    lessons_by_course = defaultdict(list)
    for lesson in lessons_qs:
        lessons_by_course[lesson.course_id].append(lesson)

    # Query 2: all completed progress records for this student across these courses
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
#  PUBLIC PAGES  (unchanged)
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
    Phase 3D: adds progress bar for enrolled students.
    """
    course      = get_object_or_404(Course, slug=slug, is_published=True)
    lessons     = course.lessons.all()
    is_enrolled = False
    progress    = None     # Phase 3D — only set for enrolled students

    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(
            student=request.user, course=course
        ).exists()

        # Phase 3D: fetch progress only for enrolled students
        if is_enrolled and request.user.is_student:
            progress = _get_course_progress(request.user, course)

    context = {
        'course':       course,
        'lessons':      lessons,
        'is_enrolled':  is_enrolled,
        'progress':     progress,   # Phase 3D
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
#  LESSON VIEWER  (Phase 3D: adds completion status to context)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lesson_view(request, course_slug, lesson_id):
    """
    View a lesson.
    Phase 3D: passes is_completed flag and neighbour lessons to the template.
    """
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

    # Phase 3D: completion state for sidebar and Mark Complete button
    is_completed = False
    completed_ids = set()
    if request.user.is_student:
        completed_ids = set(
            LessonProgress.objects
            .filter(student=request.user, lesson__in=all_lessons, completed=True)
            .values_list('lesson_id', flat=True)
        )
        is_completed = lesson.pk in completed_ids

    # Determine prev / next lessons for navigation
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
        'completed_ids': completed_ids,   # Phase 3D — for sidebar checkmarks
        'is_completed':  is_completed,    # Phase 3D — for Mark Complete button
        'prev_lesson':   prev_lesson,     # Phase 3D — navigation
        'next_lesson':   next_lesson,     # Phase 3D — navigation
    }
    return render(request, 'courses/lesson_view.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 3D — Mark Lesson Complete (toggle)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lesson_complete(request, lesson_id):
    """
    POST-only toggle: marks a lesson complete or incomplete for the student.

    Security
    --------
    - Student must be authenticated (@login_required).
    - Student must be enrolled in the lesson's course.
    - Only students can use this endpoint; teachers get PermissionDenied.

    After toggling, redirects back to the lesson view so the page reloads
    with the updated button state.
    """
    if request.method != 'POST':
        return redirect('home')

    if not request.user.is_student:
        raise PermissionDenied

    lesson = get_object_or_404(
        Lesson.objects.select_related('course'),
        pk=lesson_id,
    )

    # Must be enrolled
    enrolled = Enrollment.objects.filter(
        student=request.user,
        course=lesson.course,
    ).exists()
    if not enrolled:
        raise PermissionDenied

    # get_or_create is safe against race conditions on the unique constraint
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

    return redirect('lesson_view', course_slug=lesson.course.slug, lesson_id=lesson.pk)


# ─────────────────────────────────────────────────────────────────────────────
#  STUDENT DASHBOARD  (Phase 3D: adds progress data)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def student_dashboard(request):
    """Student dashboard with progress tracking (Phase 3D)."""
    if not request.user.is_student:
        if request.user.is_teacher:
            return redirect('teacher_dashboard')
        return redirect('home')

    enrollments = (
        Enrollment.objects
        .filter(student=request.user)
        .select_related('course', 'course__teacher')
    )

    # Phase 3B
    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    available_quizzes   = (
        Quiz.objects
        .filter(course_id__in=enrolled_course_ids)
        .select_related('course')
        .order_by('-created_at')[:10]
    )
    recent_attempts = (
        QuizAttempt.objects
        .filter(student=request.user)
        .select_related('quiz', 'quiz__course')
        .order_by('-created_at')[:5]
    )

    # Phase 3D: bulk progress for all enrolled courses (2 queries only)
    enrolled_courses = [e.course for e in enrollments]
    progress_map     = _get_progress_map(request.user, enrolled_courses)

    # Attach progress to each enrollment so the template can access it via
    # enrollment.progress — avoids extra lookups in the template
    for enrollment in enrollments:
        enrollment.progress = progress_map.get(enrollment.course.pk, {
            'total_lessons': 0, 'completed_lessons': 0,
            'percentage': 0, 'is_complete': False, 'first_incomplete': None,
        })

    # Phase 3D: completion stats
    completed_courses = sum(
        1 for p in progress_map.values() if p['is_complete']
    )

    context = {
        'enrollments':       enrollments,
        'available_quizzes': available_quizzes,
        'recent_attempts':   recent_attempts,
        'progress_map':      progress_map,    # Phase 3D
        'completed_courses': completed_courses,  # Phase 3D
    }
    return render(request, 'courses/student_dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
#  TEACHER DASHBOARD  (Phase 3D: adds completion analytics)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def teacher_dashboard(request):
    """
    Teacher dashboard.
    Phase 3D: adds per-course completion analytics.
    """
    if not request.user.is_teacher:
        if request.user.is_student:
            return redirect('student_dashboard')
        return redirect('home')

    courses = (
        Course.objects
        .filter(teacher=request.user)
        .select_related('category')
    )

    # Phase 3B
    recent_attempts = (
        QuizAttempt.objects
        .filter(quiz__course__teacher=request.user)
        .select_related('student', 'quiz', 'quiz__course')
        .order_by('-created_at')[:5]
    )

    # Phase 3D: per-course completion analytics
    # For each course, count:
    #   enrolled_count   — total students enrolled
    #   completed_count  — students who have completed every lesson
    #
    # Strategy: for each course get the lesson count, then count distinct
    # students whose completed LessonProgress rows == lesson count.
    # Done in Python to avoid complex subquery syntax across DB backends.
    course_analytics = []
    for course in courses:
        lesson_count   = course.lesson_count   # uses the existing property
        enrolled_count = course.enrollment_count  # uses the existing property

        if lesson_count > 0 and enrolled_count > 0:
            # Students who have all lessons completed
            completed_count = (
                LessonProgress.objects
                .filter(
                    lesson__course=course,
                    completed=True,
                )
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

    context = {
        'courses':           courses,
        'total_courses':     courses.count(),
        'published_count':   courses.filter(is_published=True).count(),
        'recent_attempts':   recent_attempts,
        'course_analytics':  course_analytics,   # Phase 3D
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
