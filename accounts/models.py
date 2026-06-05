from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Adds role, profile picture, and bio fields.
    """

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        TEACHER = 'teacher', 'Teacher'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True,
    )
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN or self.is_staff
