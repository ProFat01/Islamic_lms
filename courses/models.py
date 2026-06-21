from django.db import models, transaction
from django.urls import reverse
from django.utils.text import slugify
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator

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
# ─────────────────────────────────────────────────────────────────────────────
# Phase 3E — Certificate Generation & Graduation System
# ─────────────────────────────────────────────────────────────────────────────

class CourseCertificate(models.Model):
    """
    Represents a certificate of completion issued to a student for a course.

    Relationship map
    ----------------
    accounts.User (student) ──< CourseCertificate >── Course

    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates',
        help_text="The student who earned this certificate.",
    )
    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE,
        related_name='certificates',
        help_text="The course this certificate was issued for.",
    )
    certificate_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Auto-generated unique certificate number, e.g. NAL-2026-000001.",
    )
    issued_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time the certificate was issued.",
    )

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-issued_at']
        verbose_name = 'Course Certificate'
        verbose_name_plural = 'Course Certificates'

    def __str__(self):
        return f"{self.certificate_id} — {self.student.username} — {self.course.title}"

    def save(self, *args, **kwargs):
        if not self.certificate_id:
            self.certificate_id = self._generate_certificate_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_certificate_id():
        """
        Generates the next sequential certificate ID for the current year.

        Format:  NAL-<year>-<6-digit zero-padded sequence>
        Example: NAL-2026-000001, NAL-2026-000002, ...

        The sequence resets each calendar year. Wrapped in select_for_update
        so concurrent requests cannot read the same "last number" and produce
        a duplicate — the row lock serialises certificate creation within
        the same year.
        """
        from django.db import transaction
        from django.utils import timezone

        year = timezone.now().year
        prefix = f"NAL-{year}-"

        with transaction.atomic():
            last = (
                CourseCertificate.objects
                .select_for_update()
                .filter(certificate_id__startswith=prefix)
                .order_by('-certificate_id')
                .first()
            )
            if last:
                last_seq = int(last.certificate_id.split('-')[-1])
                next_seq = last_seq + 1
            else:
                next_seq = 1

            return f"{prefix}{next_seq:06d}"

# ─────────────────────────────────────────────────────────────────────────────
# ADD THIS CLASS to the bottom of courses/models.py
# Phase 4B — Reviews & Ratings System
# ─────────────────────────────────────────────────────────────────────────────

class Review(models.Model):
    """
    A student's rating + written review of a course.

    Relationship map
    ----------------
    accounts.User (student) ──< Review >── Course

    Design decisions
    ----------------
    - rating is an IntegerField restricted to 1–5 by both a model-level
      validator (MinValueValidator/MaxValueValidator, enforced on
      full_clean()/ModelForm validation) AND a database-level CheckConstraint
      (enforced even on direct .objects.create() calls or raw SQL, e.g. from
      a data migration or shell session that skips form validation).

    - UniqueConstraint on (student, course) is the canonical "one review per
      student per course" guarantee — enforced at the database level so it
      holds even under concurrent requests, not just in view-layer checks.

    - on_delete=CASCADE on both FKs: deleting a student or a course removes
      their associated reviews. No orphaned review rows.

    - updated_at uses auto_now (updates on every save), while created_at
      uses auto_now_add (set once, never changes) — this lets the UI show
      "edited" timestamps distinct from the original submission date.

    - Meta.ordering = ['-created_at'] satisfies "order reviews by newest
      first" without every view needing to repeat .order_by().
    """

    course = models.ForeignKey(
        'Course',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="The course being reviewed.",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_reviews',
        help_text="The student who wrote this review.",
    )
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 (Poor) to 5 (Excellent).",
    )
    review_text = models.TextField(
        help_text="The student's written feedback about the course.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_review_per_student_per_course',
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1) & models.Q(rating__lte=5),
                name='review_rating_between_1_and_5',
            ),
        ]

    def __str__(self):
        return f"{self.student.username} rated \u201c{self.course.title}\u201d {self.rating}/5"

    @property
    def star_display(self):
        """Returns a string like '★★★★☆' for template-free star rendering if needed."""
        return '★' * self.rating + '☆' * (5 - self.rating)