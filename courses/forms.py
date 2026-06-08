from django import forms
from .models import Category, Course, Lesson


class CourseForm(forms.ModelForm):
    """Form for teachers to create and edit courses."""

    class Meta:
        model = Course
        fields = (
            'title', 'category', 'thumbnail', 'short_description',
            'full_description', 'level', 'duration', 'is_published'
        )
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. Introduction to Tajweed'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show a blank option so category remains optional
        self.fields['category'].empty_label = '— No category —'
        self.fields['category'].queryset = Category.objects.all()


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