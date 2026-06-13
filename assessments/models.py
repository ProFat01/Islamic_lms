"""
assessments/models.py

Phase 3 — Student Assessment & Quiz System
==========================================

Relationship map
----------------
Course (courses app)
  └── Quiz               one course → many quizzes
        └── Question     one quiz   → many questions  (ordered)
              └── Choice one question → many choices  (one marked correct)

accounts.User (student)
  └── QuizAttempt        one student → many attempts  (one per quiz enforced at view layer)
        └── StudentAnswer one attempt → one answer per question
              ├── FK → Question
              └── FK → Choice  (the choice the student actually picked)

No existing file is modified. This app is registered in settings.py only.
"""

from django.db import models
from django.conf import settings


# ─────────────────────────────────────────────────────────────────────────────
# Quiz
# ─────────────────────────────────────────────────────────────────────────────

class Quiz(models.Model):
    """
    A Quiz belongs to one Course. A Course can have many Quizzes
    (e.g. one per chapter, or one final exam).

    Relationship:  courses.Course  ──< Quiz
    on_delete=CASCADE: deleting a course removes all its quizzes and,
    by cascade, all questions, choices, attempts, and answers under them.

    passing_score stores the minimum percentage (0–100) a student must
    achieve to be considered as having passed.  It is stored as a plain
    PositiveSmallIntegerField so it is easy to compare against the
    percentage calculated on QuizAttempt.
    """

    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='quizzes',
        help_text="The course this quiz belongs to.",
    )
    title = models.CharField(
        max_length=200,
        help_text="e.g. 'Chapter 1 Review' or 'Final Assessment'",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional instructions or context shown to the student before they begin.",
    )
    passing_score = models.PositiveSmallIntegerField(
        default=70,
        help_text="Minimum percentage (0–100) required to pass this quiz.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quizzes'

    def __str__(self):
        return f"{self.course.title} — {self.title}"

    @property
    def question_count(self):
        """Convenience property used in admin list_display."""
        return self.questions.count()


# ─────────────────────────────────────────────────────────────────────────────
# Question
# ─────────────────────────────────────────────────────────────────────────────

class Question(models.Model):
    """
    A Question belongs to one Quiz. A Quiz can have many Questions.

    Relationship:  Quiz  ──< Question

    on_delete=CASCADE: deleting a quiz removes all its questions and,
    by cascade, all choices and student answers linked to those questions.

    'order' controls the sequence in which questions are presented to the
    student. The Meta ordering guarantees consistent ordering everywhere
    without needing to sort manually in views.
    """

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        help_text="The quiz this question belongs to.",
    )
    question_text = models.TextField(
        help_text="The full text of the question shown to the student.",
    )
    order = models.PositiveSmallIntegerField(
        default=1,
        help_text="Display order within the quiz. Lower numbers appear first.",
    )

    class Meta:
        ordering = ['order']
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'

    def __str__(self):
        # Truncate long question text for readability in admin/shell
        preview = self.question_text[:60]
        if len(self.question_text) > 60:
            preview += '…'
        return f"Q{self.order}: {preview}"

    @property
    def correct_choice(self):
        """
        Returns the single correct Choice for this question, or None.
        Used in attempt scoring logic (views, Phase 3B).
        """
        return self.choices.filter(is_correct=True).first()


# ─────────────────────────────────────────────────────────────────────────────
# Choice
# ─────────────────────────────────────────────────────────────────────────────

class Choice(models.Model):
    """
    A Choice (answer option) belongs to one Question.
    A Question can have many Choices, but exactly one should have
    is_correct=True.  This is enforced at the form/view layer in Phase 3B,
    not at the database level, so teachers have flexibility while editing.

    Relationship:  Question  ──< Choice

    on_delete=CASCADE: deleting a question removes all its choices and
    any StudentAnswer rows that referenced those choices.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        help_text="The question this choice belongs to.",
    )
    choice_text = models.CharField(
        max_length=500,
        help_text="The text of this answer option.",
    )
    is_correct = models.BooleanField(
        default=False,
        help_text="Mark True for the single correct answer. Only one choice per question should be correct.",
    )

    class Meta:
        # No specific ordering needed; choices are rendered in insertion order
        # or can be randomised at the view layer in a future phase.
        verbose_name = 'Choice'
        verbose_name_plural = 'Choices'

    def __str__(self):
        marker = '✓' if self.is_correct else '✗'
        return f"[{marker}] {self.choice_text[:80]}"


# ─────────────────────────────────────────────────────────────────────────────
# QuizAttempt
# ─────────────────────────────────────────────────────────────────────────────

class QuizAttempt(models.Model):
    """
    Records one student's submission of one Quiz.

    Relationship:  accounts.User (student)  ──< QuizAttempt  >── Quiz

    Both FKs use on_delete=CASCADE so that:
    - Deleting a user removes all their attempt history.
    - Deleting a quiz removes all attempts (and their answers) for that quiz.

    Scoring fields
    --------------
    score           : raw number of correct answers
    total_questions : snapshot of how many questions existed at attempt time
                      (quiz may be edited later; we preserve the original count)
    percentage      : score / total_questions × 100, stored as DecimalField
                      for precision in borderline pass/fail cases
    passed          : True if percentage >= quiz.passing_score

    All scoring fields are populated by the view (Phase 3B) when the
    student submits the quiz form; they are null/blank until that point
    so the attempt row can be created before answers are saved (useful for
    time-tracking in future phases).

    limit_choices_to is intentionally omitted here — the view layer is
    responsible for ensuring only enrolled students can attempt quizzes.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        help_text="The student who made this attempt.",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
        help_text="The quiz that was attempted.",
    )
    score = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of questions answered correctly.",
    )
    total_questions = models.PositiveSmallIntegerField(
        default=0,
        help_text="Total number of questions in the quiz at the time of this attempt.",
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Score as a percentage: (score / total_questions) × 100.",
    )
    passed = models.BooleanField(
        default=False,
        help_text="True if percentage >= quiz.passing_score.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time the attempt was submitted.",
    )

    class Meta:
        # Most recent attempts first everywhere
        ordering = ['-created_at']
        verbose_name = 'Quiz Attempt'
        verbose_name_plural = 'Quiz Attempts'

    def __str__(self):
        status = 'PASSED' if self.passed else 'FAILED'
        return (
            f"{self.student.username} → {self.quiz.title} "
            f"[{self.score}/{self.total_questions} — {self.percentage}% — {status}]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# StudentAnswer
# ─────────────────────────────────────────────────────────────────────────────

class StudentAnswer(models.Model):
    """
    Records which Choice a student selected for one Question inside one
    QuizAttempt.  One row per question per attempt.

    Relationships
    -------------
    attempt  ──> QuizAttempt   (which submission this answer belongs to)
    question ──> Question      (which question was answered)
    choice   ──> Choice        (which option the student picked)

    All three use on_delete=CASCADE so that deleting an attempt, question,
    or choice cleans up answer rows automatically — no orphaned data.

    is_correct is denormalised from Choice.is_correct and stored here so
    that the attempt's result page can render per-answer feedback even if
    the teacher later edits the correct choice on the Question.  It is set
    by the view at submission time.

    unique_together on (attempt, question) enforces that a student can only
    submit one answer per question per attempt at the database level.
    """

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
        help_text="The quiz attempt this answer belongs to.",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='student_answers',
        help_text="The question that was answered.",
    )
    choice = models.ForeignKey(
        Choice,
        on_delete=models.CASCADE,
        related_name='student_answers',
        help_text="The choice (option) the student selected.",
    )
    is_correct = models.BooleanField(
        default=False,
        help_text=(
            "Snapshot of whether this choice was correct at submission time. "
            "Stored to preserve result history even if the question is later edited."
        ),
    )

    class Meta:
        # One answer per question per attempt — enforced at DB level
        constraints = [
            models.UniqueConstraint(
                fields=['attempt', 'question'],
                name='unique_answer_per_question'
            )
        ]
        ordering = ['question__order']
        verbose_name = 'Student Answer'
        verbose_name_plural = 'Student Answers'

    def __str__(self):
        mark = '✓' if self.is_correct else '✗'
        return (
            f"{mark} {self.attempt.student.username} | "
            f"Q{self.question.order}: {self.choice.choice_text[:40]}"
        )
