from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import Category, Course, Lesson, Enrollment
from .forms import CourseForm, LessonForm
from accounts.models import User


# ─────────────────────────────────────────────
#  PUBLIC PAGES
# ─────────────────────────────────────────────

def home(request):
    """Home page with featured courses and teachers."""
    featured_courses = Course.objects.filter(is_published=True)[:6]
    teachers = User.objects.filter(role=User.Role.TEACHER, is_active=True)[:4]
    context = {
        'featured_courses': featured_courses,
        'teachers': teachers,
    }
    return render(request, 'home.html', context)


def about(request):
    """About page."""
    return render(request, 'about.html')


def course_list(request):
    """Public list of all published courses."""
    level_filter    = request.GET.get('level', '')
    category_filter = request.GET.get('category', '')

    courses = Course.objects.filter(is_published=True).select_related('category', 'teacher')

    if level_filter:
        courses = courses.filter(level=level_filter)
    if category_filter:
        courses = courses.filter(category__slug=category_filter)

    context = {
        'courses': courses,
        'level_filter': level_filter,
        'category_filter': category_filter,
        'levels': Course.Level.choices,
        'categories': Category.objects.all(),
    }
    return render(request, 'courses/course_list.html', context)


def course_detail(request, slug):
    """Public course detail page."""
    course = get_object_or_404(Course, slug=slug, is_published=True)
    lessons = course.lessons.all()
    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = Enrollment.objects.filter(
            student=request.user, course=course
        ).exists()
    context = {
        'course': course,
        'lessons': lessons,
        'is_enrolled': is_enrolled,
    }
    return render(request, 'courses/course_detail.html', context)


# ─────────────────────────────────────────────
#  ENROLLMENT
# ─────────────────────────────────────────────

@login_required
def enroll(request, slug):
    """Enroll the current student in a course."""
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


# ─────────────────────────────────────────────
#  LESSON VIEWER
# ─────────────────────────────────────────────

@login_required
def lesson_view(request, course_slug, lesson_id):
    """View a lesson (student must be enrolled)."""
    course = get_object_or_404(Course, slug=course_slug, is_published=True)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    # Teachers of this course can view any lesson
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

    all_lessons = course.lessons.all()
    context = {
        'course': course,
        'lesson': lesson,
        'all_lessons': all_lessons,
    }
    return render(request, 'courses/lesson_view.html', context)


# ─────────────────────────────────────────────
#  STUDENT DASHBOARD
# ─────────────────────────────────────────────

@login_required
def student_dashboard(request):
    """Student's personal dashboard showing enrolled courses."""
    if not request.user.is_student:
        if request.user.is_teacher:
            return redirect('teacher_dashboard')
        return redirect('home')

    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course', 'course__teacher')

    context = {
        'enrollments': enrollments,
    }
    return render(request, 'courses/student_dashboard.html', context)


# ─────────────────────────────────────────────
#  TEACHER DASHBOARD & COURSE MANAGEMENT
# ─────────────────────────────────────────────

@login_required
def teacher_dashboard(request):
    """Teacher's dashboard showing their courses."""
    if not request.user.is_teacher:
        if request.user.is_student:
            return redirect('student_dashboard')
        return redirect('home')

    courses = Course.objects.filter(teacher=request.user)
    context = {
        'courses': courses,
        'total_courses': courses.count(),
        'published_count': courses.filter(is_published=True).count(),
    }
    return render(request, 'courses/teacher_dashboard.html', context)


@login_required
def course_create(request):
    """Teacher creates a new course."""
    if not request.user.is_teacher:
        raise PermissionDenied

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            messages.success(request, f"Course '{course.title}' created successfully!")
            return redirect('course_manage', slug=course.slug)
    else:
        form = CourseForm()

    return render(request, 'courses/course_form.html', {
        'form': form,
        'action': 'Create',
    })


@login_required
def course_edit(request, slug):
    """Teacher edits an existing course."""
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
        'form': form,
        'course': course,
        'action': 'Edit',
    })


@login_required
def course_manage(request, slug):
    """Teacher manages lessons for a course."""
    course = get_object_or_404(Course, slug=slug)

    if course.teacher != request.user:
        raise PermissionDenied

    lessons = course.lessons.all()
    context = {
        'course': course,
        'lessons': lessons,
    }
    return render(request, 'courses/course_manage.html', context)


@login_required
def lesson_create(request, course_slug):
    """Teacher adds a lesson to a course."""
    course = get_object_or_404(Course, slug=course_slug)

    if course.teacher != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, f"Lesson '{lesson.title}' added!")
            return redirect('course_manage', slug=course_slug)
    else:
        # Auto-set order to next available
        next_order = course.lessons.count() + 1
        form = LessonForm(initial={'order': next_order})

    return render(request, 'courses/lesson_form.html', {
        'form': form,
        'course': course,
        'action': 'Add',
    })


@login_required
def lesson_edit(request, course_slug, lesson_id):
    """Teacher edits a lesson."""
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
        'form': form,
        'course': course,
        'lesson': lesson,
        'action': 'Edit',
    })


@login_required
def lesson_delete(request, course_slug, lesson_id):
    """Teacher deletes a lesson."""
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    if course.teacher != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        lesson_title = lesson.title
        lesson.delete()
        messages.success(request, f"Lesson '{lesson_title}' deleted.")
        return redirect('course_manage', slug=course_slug)

    return render(request, 'courses/lesson_confirm_delete.html', {
        'lesson': lesson,
        'course': course,
    })