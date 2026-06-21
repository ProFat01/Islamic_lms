"""
courses/migrations/0004_coursecertificate.py

Creates the courses_coursecertificate table.

Dependencies
------------
- courses.0003_lessonprogress : most recent prior migration in this app
- accounts.0001_initial       : so we can reference accounts.User

No existing table is modified.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_lessonprogress'),
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseCertificate',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('certificate_id', models.CharField(
                    editable=False,
                    help_text='Auto-generated unique certificate number, e.g. NAL-2026-000001.',
                    max_length=20,
                    unique=True,
                )),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(
                    help_text='The student who earned this certificate.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='certificates',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('course', models.ForeignKey(
                    help_text='The course this certificate was issued for.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='certificates',
                    to='courses.course',
                )),
            ],
            options={
                'verbose_name': 'Course Certificate',
                'verbose_name_plural': 'Course Certificates',
                'ordering': ['-issued_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='coursecertificate',
            unique_together={('student', 'course')},
        ),
    ]
