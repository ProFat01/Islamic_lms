"""
assessments/views.py

Four views for Phase 3B:

  quiz_detail      GET   /assessments/quiz/<id>/
                         Landing page before a student starts the quiz.

  quiz_take        GET   /assessments/quiz/<id>/take/
                         Renders the quiz form (all questions + radio buttons).

  quiz_submit      POST  /assessments/quiz/<id>/submit/
                         Processes the submitted form, scores it, creates
                         QuizAttempt and StudentAnswer rows, redirects to result.

  attempt_detail   GET   /assessments/attempt/<id>/
                         Shows a student their scored attempt with per-answer
                         feedback (correct / incorrect).

  teacher_attempts GET   /assessments/teacher/attempts/
                         Teacher view — all attempts across all their courses.

Security rules applied consistently:
  - @login_required on every view.
  - Students may only access quizzes for courses they are enrolled in.
  - Students may only view their own attempts.
  - Teachers may only view attempts for quizzes in their own courses.
  - PermissionDenied is raised (not a soft redirect) for security violations
    so Django returns a proper 403 response.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from courses.models import Enrollment
from .forms import QuizAttemptForm
from .models import Choice, Question, Quiz, QuizAttempt, StudentAnswer


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_enrollment(user, quiz):
    """
    Raise PermissionDenied if the user is not enrolled in the quiz's course.
    Call this in every student-facing quiz view before rendering anything.
    """
    enrolled = Enrollment.objects.filter(
        student=user,
        course=quiz.course,
    ).exists()
    if not enrolled:
        raise PermissionDenied


def _require_teacher_owns_quiz(user, quiz):
    """
    Raise PermissionDenied if the teacher does not own the quiz's course.
    """
    if quiz.course.teacher != user:
        raise PermissionDenied


# ─────────────────────────────────────────────────────────────────────────────
# Student views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def quiz_detail(request, quiz_id):
    """
    Landing page for a quiz.

    Shows: title, description, number of questions, passing score, and a
    "Start Quiz" button that leads to quiz_take.

    Also shows the student's previous attempts on this quiz (if any),
    so they know their history before starting again.
    """
    quiz = get_object_or_404(
        Quiz.objects.select_related('course', 'course__teacher'),
        pk=quiz_id,
    )

    # Only enrolled students (or the course's teacher) may view the quiz detail
    if request.user.is_student:
        _require_enrollment(request.user, quiz)
    elif request.user.is_teacher:
        _require_teacher_owns_quiz(request.user, quiz)
    # Admin users pass through without restriction

    # Previous attempts by this user on this specific quiz
    previous_attempts = []
    if request.user.is_student:
        previous_attempts = (
            QuizAttempt.objects
            .filter(student=request.user, quiz=quiz)
            .order_by('-created_at')
        )

    context = {
        'quiz': quiz,
        'question_count': quiz.questions.count(),
        'previous_attempts': previous_attempts,
    }
    return render(request, 'assessments/quiz_detail.html', context)


@login_required
def quiz_take(request, quiz_id):
    """
    Renders the quiz form (all questions with radio-button choices).

    GET only — the form is displayed here; submission goes to quiz_submit.
    If the student somehow GETs this page via a POST (e.g. browser back
    button after submission) they are redirected to the detail page.
    """
    quiz = get_object_or_404(
        Quiz.objects.select_related('course'),
        pk=quiz_id,
    )

    if not request.user.is_student:
        messages.error(request, "Only students can take quizzes.")
        return redirect('quiz_detail', quiz_id=quiz.pk)

    _require_enrollment(request.user, quiz)

    # Ensure the quiz has questions before allowing the student to start
    if not quiz.questions.exists():
        messages.warning(request, "This quiz has no questions yet.")
        return redirect('quiz_detail', quiz_id=quiz.pk)

    form = QuizAttemptForm(quiz=quiz)

    context = {
        'quiz': quiz,
        'form': form,
        # Pass total count for "Question X of N" headings in the template
        'total_questions': quiz.questions.count(),
    }
    return render(request, 'assessments/quiz_take.html', context)


@login_required
def quiz_submit(request, quiz_id):
    """
    Handles POST submission of a quiz attempt.

    Steps:
      1. Validate the form (every question must have a selected choice).
      2. Create a QuizAttempt row (with placeholder scores).
      3. Iterate questions; for each, look up the submitted choice,
         check correctness, save a StudentAnswer row.
      4. Calculate score, total_questions, percentage, passed.
      5. Update and save the QuizAttempt with final scores.
      6. Redirect to attempt_detail.

    If the form is invalid (a question was skipped), re-render quiz_take
    with the validation errors so the student can correct them.

    Only accepts POST to prevent replay via browser refresh.
    """
    if request.method != 'POST':
        return redirect('quiz_take', quiz_id=quiz_id)

    quiz = get_object_or_404(
        Quiz.objects.select_related('course'),
        pk=quiz_id,
    )

    if not request.user.is_student:
        raise PermissionDenied

    _require_enrollment(request.user, quiz)

    form = QuizAttemptForm(quiz=quiz, data=request.POST)

    if not form.is_valid():
        # Re-render the quiz with errors; student must answer all questions
        context = {
            'quiz': quiz,
            'form': form,
            'total_questions': quiz.questions.count(),
        }
        return render(request, 'assessments/quiz_take.html', context)

    # ── Fetch all questions + their correct choices in two DB queries ─────
    questions = (
        Question.objects
        .filter(quiz=quiz)
        .prefetch_related('choices')
        .order_by('order')
    )
    total_questions = questions.count()

    # ── Create the attempt row (scores filled in below) ───────────────────
    attempt = QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        score=0,
        total_questions=total_questions,
        percentage=Decimal('0.00'),
        passed=False,
    )

    # ── Score each answer and create StudentAnswer rows ───────────────────
    score = 0
    for question in questions:
        field_name  = f'question_{question.pk}'
        choice_pk   = form.cleaned_data[field_name]

        # get_object_or_404 guards against a tampered POST with a fake choice PK
        chosen_choice = get_object_or_404(Choice, pk=choice_pk, question=question)
        is_correct    = chosen_choice.is_correct

        StudentAnswer.objects.create(
            attempt=attempt,
            question=question,
            choice=chosen_choice,
            is_correct=is_correct,
        )

        if is_correct:
            score += 1

    # ── Calculate final scores ────────────────────────────────────────────
    if total_questions > 0:
        percentage = Decimal(score) / Decimal(total_questions) * Decimal('100')
        # Round to 2 dp to match DecimalField(decimal_places=2)
        percentage = percentage.quantize(Decimal('0.01'))
    else:
        percentage = Decimal('0.00')

    passed = percentage >= Decimal(quiz.passing_score)

    # ── Persist final scores ──────────────────────────────────────────────
    attempt.score           = score
    attempt.percentage      = percentage
    attempt.passed          = passed
    attempt.save()

    result_word = "Passed" if passed else "Not passed"
    messages.success(
        request,
        f"Quiz submitted! You scored {score}/{total_questions} ({percentage}%). {result_word}."
    )
    return redirect('attempt_detail', attempt_id=attempt.pk)


@login_required
def attempt_detail(request, attempt_id):
    """
    Shows the full result of one QuizAttempt.

    Displays:
      - Score / total, percentage, pass/fail status
      - Every question with the student's chosen answer marked ✓ or ✗
      - The correct answer for questions the student got wrong

    Security: students can only view their own attempts.
    Teachers can view any attempt on their own courses.
    """
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related(
            'student', 'quiz', 'quiz__course', 'quiz__course__teacher'
        ),
        pk=attempt_id,
    )

    # Enforce ownership
    if request.user.is_student:
        if attempt.student != request.user:
            raise PermissionDenied
    elif request.user.is_teacher:
        if attempt.quiz.course.teacher != request.user:
            raise PermissionDenied
    # Admin passes through

    # Fetch all answers with their related question and chosen choice
    answers = (
        attempt.answers
        .select_related('question', 'choice')
        .prefetch_related('question__choices')
        .order_by('question__order')
    )

    context = {
        'attempt': attempt,
        'answers': answers,
    }
    return render(request, 'assessments/attempt_detail.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Teacher view
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def teacher_attempts(request):
    """
    Lists all quiz attempts across all quizzes belonging to the teacher's
    courses, ordered most-recent first.

    Security: if a non-teacher accesses this view they are redirected or
    denied rather than shown an empty page.
    """
    if not request.user.is_teacher:
        if request.user.is_student:
            return redirect('student_dashboard')
        raise PermissionDenied

    attempts = (
        QuizAttempt.objects
        .filter(quiz__course__teacher=request.user)
        .select_related('student', 'quiz', 'quiz__course')
        .order_by('-created_at')
    )

    context = {
        'attempts': attempts,
    }
    return render(request, 'assessments/teacher_attempts.html', context)
