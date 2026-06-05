from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import StudentRegistrationForm, CustomLoginForm, UserProfileForm
from .models import User


def register(request):
    """Student self-registration view."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.first_name}! Your account has been created.")
            return redirect('student_dashboard')
    else:
        form = StudentRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def user_login(request):
    """Login view for all user types."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == 'POST':
        form = CustomLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return _redirect_by_role(user)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def user_logout(request):
    """Logout view."""
    logout(request)
    messages.info(request, "You have been logged out. Assalamu Alaikum!")
    return redirect('home')


@login_required
def profile(request):
    """User profile view and edit."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})


def _redirect_by_role(user):
    """Helper: redirect user to their appropriate dashboard."""
    if user.is_admin_user:
        return redirect('/admin/')
    elif user.is_teacher:
        return redirect('teacher_dashboard')
    else:
        return redirect('student_dashboard')
