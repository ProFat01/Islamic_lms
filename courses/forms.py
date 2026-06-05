from django import forms
from .models import Course, Lesson


class CourseForm(forms.ModelForm):
    """Form for teachers to create and edit courses."""

    class Meta:
        model = Course
        fields = (
            'title', 'thumbnail', 'short_description',
            'full_description', 'level', 'duration', 'is_published'
        )
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. Introduction to Tajweed'
            }),
            'short_description': forms.TextInput(attrs={
                'placeholder': 'A brief summary shown on course cards (max 300 chars)'
            }),
            'full_description': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Detailed description of what students will learn...'
            }),
            'duration': forms.TextInput(attrs={
                'placeholder': 'e.g. 8 weeks, 40 hours'
            }),
        }


class LessonForm(forms.ModelForm):
    """Form for teachers to create and edit lessons."""

    class Meta:
        model = Lesson
        fields = ('title', 'video_url', 'note_content', 'order')
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Lesson title'
            }),
            'video_url': forms.URLInput(attrs={
                'placeholder': 'https://www.youtube.com/watch?v=...'
            }),
            'note_content': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': 'Write lesson notes here (supports plain text)...'
            }),
            'order': forms.NumberInput(attrs={
                'min': 0
            }),
        }
