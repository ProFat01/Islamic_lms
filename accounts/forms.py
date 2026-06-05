from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class StudentRegistrationForm(UserCreationForm):
    """Form for new student registration."""

    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email Address'})
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CustomLoginForm(AuthenticationForm):
    """Styled login form."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password'})
    )


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'bio', 'profile_picture')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Tell us about yourself...'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email Address'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last Name'}),
        }
