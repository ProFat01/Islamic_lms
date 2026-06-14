"""
assessments/forms.py

Builds the quiz-taking form dynamically from a Quiz instance.

Design
------
QuizAttemptForm is constructed with a Quiz object.  For every Question in
that quiz it adds one ChoiceField rendered as RadioSelect.  Field names
follow the pattern  question_<question_id>  so the submission view can
look up each answer unambiguously without relying on ordering.

No ModelForm is used here because the form spans multiple models
(one StudentAnswer row per question), and saving is handled manually
in the view for full control over the scoring transaction.
"""

from django import forms
from .models import Question, Choice


class QuizAttemptForm(forms.Form):
    """
    Dynamically generated form — one radio-button field per Question.

    Usage in view:
        form = QuizAttemptForm(quiz=quiz_instance)           # GET
        form = QuizAttemptForm(quiz=quiz_instance, data=request.POST)  # POST
    """

    def __init__(self, *args, quiz=None, **kwargs):
        super().__init__(*args, **kwargs)

        if quiz is None:
            raise ValueError("QuizAttemptForm requires a 'quiz' keyword argument.")

        # Fetch all questions with their choices in two queries (no N+1)
        questions = (
            Question.objects
            .filter(quiz=quiz)
            .prefetch_related('choices')
            .order_by('order')
        )

        for question in questions:
            # Build (value, label) pairs from the question's choices
            choice_qs = question.choices.all()
            choices = [(str(c.pk), c.choice_text) for c in choice_qs]

            field_name = f'question_{question.pk}'
            self.fields[field_name] = forms.ChoiceField(
                label=question.question_text,
                choices=choices,
                widget=forms.RadioSelect(attrs={'class': 'quiz-radio'}),
                error_messages={
                    'required': 'Please select an answer for this question.',
                },
            )
            # Store question order on the field so the template can render
            # "Question 1 of N" headings without extra context.
            self.fields[field_name].question_order = question.order
            self.fields[field_name].question_pk    = question.pk
