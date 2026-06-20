from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings


class Category(models.Model):
    """
    A top-level category that groups related courses together.
    e.g. Quran, Aqeedah, Fiqh, Arabic Language, Seerah.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional short description of this category.",
    )

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            original_slug = self.slug
            counter = 1
            while Category.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def course_count(self):
        return self.courses.filter(is_published=True).count()

    def get_absolute_url(self):
        return reverse('category_detail', kwargs={'slug': self.slug})


class Course(models.Model):
    """
    Represents an Islamic course taught by a teacher.
    """

    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses_taught',
        limit_choices_to={'role': 'teacher'},
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses',
        help_text="The subject area this course belongs to.",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    short_description = models.CharField(max_length=300)
    full_description = models.TextField()
    level = models.CharField(max_length=15, choices=Level.choices, default=Level.BEGINNER)
    duration = models.CharField(max_length=100, help_text="e.g. '8 weeks', '40 hours'")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Auto-generate slug from title if not set
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Course.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def lesson_count(self):
        return self.lessons.count()

    @property
    def enrollment_count(self):
        return self.enrollments.count()


class Lesson(models.Model):
    """
    A single lesson within a course.
    Contains a video URL and/or text notes.
    """

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
    )
    title = models.CharField(max_length=200)
    video_url = models.URLField(
        blank=True,
        null=True,
        help_text="YouTube, Vimeo, or any embeddable video URL"
    )
    note_content = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.course.title} — Lesson {self.order}: {self.title}"


class Enrollment(models.Model):
    """
    Records that a student has enrolled in a course.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')  # Prevent duplicate enrollments
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} → {self.course.title}"

# Phase 3D — Lesson Progress Tracking
# ─────────────────────────────────────────────────────────────────────────────
class LessonProgress(models.Model):
    """
    Tracks whether a specific student has completed a specific lesson.

    Relationship map
    ----------------
    accounts.User (student) ──< LessonProgress >── Lesson >── Course

    Design decisions
    ----------------
    - unique_together on (student, lesson) enforces one row per student per
      lesson at the database level.  get_or_create is used in the toggle view
      so there is never a race condition creating duplicates.

    - on_delete=CASCADE on both FKs means:
        • Deleting a student removes all their progress records.
        • Deleting a lesson removes progress records for that lesson.
      No orphaned rows are ever left behind.

    - completed_at is nullable.  It is None while completed=False and
      set to timezone.now() when the student marks the lesson complete.
      This allows future phases to display "completed on" dates.

    - 'completed' is a BooleanField rather than a DateTimeField so the
      toggle logic is a simple True/False flip, and the model stays
      consistent with the spec.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lesson_progress',
        help_text="The student this progress record belongs to.",
    )
    lesson = models.ForeignKey(
        'Lesson',
        on_delete=models.CASCADE,
        related_name='progress_records',
        help_text="The lesson this progress record tracks.",
    )
    completed = models.BooleanField(
        default=False,
        help_text="True when the student has marked this lesson as complete.",
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the student last marked this lesson complete. Null if incomplete.",
    )

    class Meta:
        unique_together = ('student', 'lesson')
        ordering = ['lesson__order', 'lesson__created_at']
        verbose_name = 'Lesson Progress'
        verbose_name_plural = 'Lesson Progress Records'

    def __str__(self):
        status = '✓' if self.completed else '○'
        return (
            f"{status} {self.student.username} — "
            f"{self.lesson.course.title} / {self.lesson.title}"
        )