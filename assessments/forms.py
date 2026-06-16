"""
assessments/forms.py

Forms for the Islamic LMS Assessment system.

Phase 3B (unchanged)
--------------------
  QuizAttemptForm   — dynamic radio-button form for students taking a quiz

Phase 3C (new)
--------------
  QuizForm          — teacher creates / edits a Quiz
  QuestionForm      — teacher creates / edits a Question
  ChoiceForm        — teacher creates / edits a Choice
                      includes auto-clear logic: marking a choice as correct
                      automatically unsets is_correct on all sibling choices
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import Choice, Question, Quiz


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3B — unchanged
# ─────────────────────────────────────────────────────────────────────────────

class QuizAttemptForm(forms.Form):
    """
    Dynamically generated form — one radio-button ChoiceField per Question.

    Usage:
        form = QuizAttemptForm(quiz=quiz_instance)                        # GET
        form = QuizAttemptForm(quiz=quiz_instance, data=request.POST)     # POST
    """

    def __init__(self, *args, quiz=None, **kwargs):
        super().__init__(*args, **kwargs)

        if quiz is None:
            raise ValueError("QuizAttemptForm requires a 'quiz' keyword argument.")

        questions = (
            Question.objects
            .filter(quiz=quiz)
            .prefetch_related('choices')
            .order_by('order')
        )

        for question in questions:
            choice_qs  = question.choices.all()
            choices    = [(str(c.pk), c.choice_text) for c in choice_qs]
            field_name = f'question_{question.pk}'

            self.fields[field_name] = forms.ChoiceField(
                label=question.question_text,
                choices=choices,
                widget=forms.RadioSelect(attrs={'class': 'quiz-radio'}),
                error_messages={
                    'required': 'Please select an answer for this question.',
                },
            )
            self.fields[field_name].question_order = question.order
            self.fields[field_name].question_pk    = question.pk


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3C — Teacher quiz management forms
# ─────────────────────────────────────────────────────────────────────────────

class QuizForm(forms.ModelForm):
    """
    Teacher creates or edits a Quiz.

    The 'course' queryset is restricted to the teacher's own courses in the
    view's get_form() / form_valid() so this form never exposes courses
    belonging to another teacher.
    """

    passing_score = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=70,
        help_text="Minimum percentage a student must score to pass (0–100).",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '70'}),
    )

    class Meta:
        model  = Quiz
        fields = ('course', 'title', 'description', 'passing_score')
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "e.g. Chapter 1 Review",
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': "Optional instructions shown to students before they start.",
            }),
        }

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher is not None:
            # Restrict course choices to the requesting teacher's own courses
            from courses.models import Course
            self.fields['course'].queryset = (
                Course.objects
                .filter(teacher=teacher)
                .order_by('title')
            )
            self.fields['course'].empty_label = '— Select a course —'


class QuestionForm(forms.ModelForm):
    """
    Teacher creates or edits a Question belonging to one of their quizzes.
    The quiz FK is set in the view (not shown in the form) to prevent
    a teacher from re-parenting a question to another teacher's quiz.
    """

    class Meta:
        model  = Question
        fields = ('question_text', 'order')
        widgets = {
            'question_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': "Enter the full question text…",
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
            }),
        }
        labels = {
            'question_text': 'Question Text',
            'order': 'Display Order',
        }
        help_texts = {
            'order': 'Lower numbers appear first in the quiz.',
        }


class ChoiceForm(forms.ModelForm):
    """
    Teacher creates or edits an answer Choice.

    Validation rule: a question should have exactly one correct choice.
    When is_correct=True is submitted, the view calls
    Choice.objects.filter(question=question).exclude(pk=self.pk)
                   .update(is_correct=False)
    after save() — see the view for the implementation.

    The form itself validates that choice_text is non-empty (handled by
    CharField) and that is_correct is a valid boolean (handled by
    BooleanField).
    """

    class Meta:
        model  = Choice
        fields = ('choice_text', 'is_correct')
        widgets = {
            'choice_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Enter the answer option text…",
            }),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'choice_text': 'Answer Text',
            'is_correct':  'Mark as Correct Answer',
        }
        help_texts = {
            'is_correct': (
                'Checking this will automatically unmark any other '
                'correct answer for this question.'
            ),
        }
