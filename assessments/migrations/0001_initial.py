"""
assessments/migrations/0001_initial.py

Creates all five Phase 3 tables in a single migration:
    assessments_quiz
    assessments_question
    assessments_choice
    assessments_quizattempt
    assessments_studentanswer

Dependencies
------------
- courses.0002_category  : so we can reference courses.Course safely
- accounts.0001_initial  : so we can reference accounts.User safely
  (accounts only has one migration)
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # Must come after the migration that introduced courses.Course
        ('courses', '0002_category_course_category'),
        # Must come after the migration that introduced accounts.User
        ('accounts', '0001_initial'),
        # Required whenever we reference AUTH_USER_MODEL
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 1. Quiz ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('title', models.CharField(
                    max_length=200,
                    help_text="e.g. 'Chapter 1 Review' or 'Final Assessment'",
                )),
                ('description', models.TextField(
                    blank=True,
                    null=True,
                    help_text='Optional instructions shown to the student before they begin.',
                )),
                ('passing_score', models.PositiveSmallIntegerField(
                    default=70,
                    help_text='Minimum percentage (0–100) required to pass this quiz.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(
                    help_text='The course this quiz belongs to.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='quizzes',
                    to='courses.course',
                )),
            ],
            options={
                'verbose_name': 'Quiz',
                'verbose_name_plural': 'Quizzes',
                'ordering': ['created_at'],
            },
        ),

        # ── 2. Question ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('question_text', models.TextField(
                    help_text='The full text of the question shown to the student.',
                )),
                ('order', models.PositiveSmallIntegerField(
                    default=1,
                    help_text='Display order within the quiz. Lower numbers appear first.',
                )),
                ('quiz', models.ForeignKey(
                    help_text='The quiz this question belongs to.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='questions',
                    to='assessments.quiz',
                )),
            ],
            options={
                'verbose_name': 'Question',
                'verbose_name_plural': 'Questions',
                'ordering': ['order'],
            },
        ),

        # ── 3. Choice ────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('choice_text', models.CharField(
                    max_length=500,
                    help_text='The text of this answer option.',
                )),
                ('is_correct', models.BooleanField(
                    default=False,
                    help_text=(
                        'Mark True for the single correct answer. '
                        'Only one choice per question should be correct.'
                    ),
                )),
                ('question', models.ForeignKey(
                    help_text='The question this choice belongs to.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='choices',
                    to='assessments.question',
                )),
            ],
            options={
                'verbose_name': 'Choice',
                'verbose_name_plural': 'Choices',
            },
        ),

        # ── 4. QuizAttempt ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('score', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Number of questions answered correctly.',
                )),
                ('total_questions', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Total questions in the quiz at submission time.',
                )),
                ('percentage', models.DecimalField(
                    default=0.00,
                    max_digits=5,
                    decimal_places=2,
                    help_text='score / total_questions × 100.',
                )),
                ('passed', models.BooleanField(
                    default=False,
                    help_text='True if percentage >= quiz.passing_score.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('student', models.ForeignKey(
                    help_text='The student who made this attempt.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='quiz_attempts',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('quiz', models.ForeignKey(
                    help_text='The quiz that was attempted.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attempts',
                    to='assessments.quiz',
                )),
            ],
            options={
                'verbose_name': 'Quiz Attempt',
                'verbose_name_plural': 'Quiz Attempts',
                'ordering': ['-created_at'],
            },
        ),

        # ── 5. StudentAnswer ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='StudentAnswer',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('is_correct', models.BooleanField(
                    default=False,
                    help_text=(
                        'Snapshot of whether this choice was correct at '
                        'submission time.'
                    ),
                )),
                ('attempt', models.ForeignKey(
                    help_text='The quiz attempt this answer belongs to.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='answers',
                    to='assessments.quizattempt',
                )),
                ('choice', models.ForeignKey(
                    help_text='The choice the student selected.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_answers',
                    to='assessments.choice',
                )),
                ('question', models.ForeignKey(
                    help_text='The question that was answered.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_answers',
                    to='assessments.question',
                )),
            ],
            options={
                'verbose_name': 'Student Answer',
                'verbose_name_plural': 'Student Answers',
                'ordering': ['question__order'],
            },
        ),

        # ── unique_together on StudentAnswer ──────────────────────────────────
        # One answer per question per attempt — enforced at DB level
        migrations.AlterUniqueTogether(
            name='studentanswer',
            unique_together={('attempt', 'question')},
        ),
    ]
