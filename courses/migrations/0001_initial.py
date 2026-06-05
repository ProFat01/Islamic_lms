# Generated migration for courses app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='thumbnails/')),
                ('short_description', models.CharField(max_length=300)),
                ('full_description', models.TextField()),
                ('level', models.CharField(
                    choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')],
                    default='beginner',
                    max_length=15,
                )),
                ('duration', models.CharField(help_text="e.g. '8 weeks', '40 hours'", max_length=100)),
                ('is_published', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('teacher', models.ForeignKey(
                    limit_choices_to={'role': 'teacher'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='courses_taught',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('video_url', models.URLField(blank=True, help_text='YouTube, Vimeo, or any embeddable video URL', null=True)),
                ('note_content', models.TextField(blank=True, null=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lessons',
                    to='courses.course',
                )),
            ],
            options={'ordering': ['order', 'created_at']},
        ),
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enrollments',
                    to='courses.course',
                )),
                ('student', models.ForeignKey(
                    limit_choices_to={'role': 'student'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enrollments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-enrolled_at'],
                'unique_together': {('student', 'course')},
            },
        ),
    ]
