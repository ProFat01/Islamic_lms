"""
courses/forms.py

All existing forms (CourseForm, LessonForm) are preserved exactly.
Phase 4B adds ReviewForm at the bottom.
"""

from django import forms

from .models import Course, Lesson, Review


# ─────────────────────────────────────────────────────────────────────────────
#  CourseForm  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class CourseForm(forms.ModelForm):
    """Teacher-facing form for creating and editing a Course."""

    class Meta:
        model = Course
        fields = [
            'category', 'title', 'thumbnail', 'short_description',
            'full_description', 'level', 'duration', 'is_published',
        ]
        widgets = {
            'category':           forms.Select(attrs={'class': 'form-control'}),
            'title':               forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Course title'}),
            'thumbnail':           forms.FileInput(attrs={'class': 'form-control'}),
            'short_description':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'A one-line summary shown on course cards'}),
            'full_description':    forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Full course description'}),
            'level':               forms.Select(attrs={'class': 'form-control'}),
            'duration':            forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 6 weeks'}),
            'is_published':        forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  LessonForm  (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class LessonForm(forms.ModelForm):
    """Teacher-facing form for creating and editing a Lesson."""

    class Meta:
        model = Lesson
        fields = ['title', 'video_url', 'note_content', 'order']
        widgets = {
            'title':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lesson title'}),
            'video_url':     forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'note_content':  forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Lesson notes / transcript'}),
            'order':         forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Phase 4B — ReviewForm
# ─────────────────────────────────────────────────────────────────────────────

class ReviewForm(forms.ModelForm):
    """
    Student-facing form for creating and editing a Review.

    Only exposes 'rating' and 'review_text' — course and student are set
    in the view (never trusted from form input) to prevent a student from
    submitting a review for a course they didn't complete, or attributing
    a review to a different student via a tampered POST body.

    The rating field uses a Select widget with descriptive labels
    (5 = Excellent ... 1 = Poor) rather than bare numeric radio buttons,
    per the spec, so the choice is unambiguous to the student filling
    out the form.
    """

    RATING_CHOICES = [
        (5, '5 — Excellent'),
        (4, '4 — Very Good'),
        (3, '3 — Good'),
        (2, '2 — Fair'),
        (1, '1 — Poor'),
    ]

    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How would you rate this course overall?",
    )

    class Meta:
        model = Review
        fields = ['rating', 'review_text']
        widgets = {
            'review_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Share your experience with this course — what did you learn, '
                               'how was the teaching style, would you recommend it to others?',
            }),
        }
        labels = {
            'review_text': 'Your Review',
        }

    def clean_rating(self):
        """
        ChoiceField returns a string; coerce to int so it matches the
        model's IntegerField and the database CheckConstraint (1–5).
        """
        return int(self.cleaned_data['rating'])