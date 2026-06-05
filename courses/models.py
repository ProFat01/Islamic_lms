from django.db import models
from django.utils.text import slugify
from django.conf import settings


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
