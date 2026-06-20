"""
courses/migrations/0003_lessonprogress.py

Creates the courses_lessonprogress table.

Dependencies
------------
- courses.0002_category  : so Lesson and Course already exist
- accounts.0001_initial  : so we can reference accounts.User

No existing table is modified.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0002_category_course_category'),
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonProgress',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('completed', models.BooleanField(
                    default=False,
                    help_text='True when the student has marked this lesson as complete.',
                )),
                ('completed_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    help_text='Timestamp when the student last marked this lesson complete.',
                )),
                ('student', models.ForeignKey(
                    help_text='The student this progress record belongs to.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lesson_progress',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('lesson', models.ForeignKey(
                    help_text='The lesson this progress record tracks.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='progress_records',
                    to='courses.lesson',
                )),
            ],
            options={
                'verbose_name': 'Lesson Progress',
                'verbose_name_plural': 'Lesson Progress Records',
                'ordering': ['lesson__order', 'lesson__created_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='lessonprogress',
            unique_together={('student', 'lesson')},
        ),
    ]
