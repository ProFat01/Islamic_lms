from django.contrib import admin
from .models import Course, Lesson, Enrollment


class LessonInline(admin.TabularInline):
    """Show lessons inline within a course."""
    model = Lesson
    extra = 1
    fields = ('order', 'title', 'video_url')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'level', 'is_published', 'lesson_count', 'enrollment_count', 'created_at')
    list_filter = ('is_published', 'level', 'teacher')
    search_fields = ('title', 'short_description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LessonInline]
    ordering = ('-created_at',)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'created_at')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')
    ordering = ('course', 'order')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at')
    list_filter = ('course',)
    search_fields = ('student__username', 'course__title')
    ordering = ('-enrolled_at',)
