"""
assessments/views.py

Phase 3B views (unchanged)
--------------------------
  quiz_detail       GET  /assessments/quiz/<id>/
  quiz_take         GET  /assessments/quiz/<id>/take/
  quiz_submit       POST /assessments/quiz/<id>/submit/
  attempt_detail    GET  /assessments/attempt/<id>/
  teacher_attempts  GET  /assessments/teacher/attempts/

Phase 3C views (new — teacher quiz management)
----------------------------------------------
  teacher_quiz_list       GET      /assessments/teacher/quizzes/
  teacher_quiz_create     GET/POST /assessments/teacher/quizzes/create/
  teacher_quiz_edit       GET/POST /assessments/teacher/quizzes/<id>/edit/
  teacher_quiz_delete     GET/POST /assessments/teacher/quizzes/<id>/delete/
  teacher_question_list   GET      /assessments/teacher/quizzes/<id>/questions/
  teacher_question_create GET/POST /assessments/teacher/questions/create/<quiz_id>/
  teacher_question_edit   GET/POST /assessments/teacher/questions/<id>/edit/
  teacher_question_delete GET/POST /assessments/teacher/questions/<id>/delete/
  teacher_choice_list     GET      /assessments/teacher/questions/<id>/choices/
  teacher_choice_create   GET/POST /assessments/teacher/questions/<id>/choices/create/
  teacher_choice_edit     GET/POST /assessments/teacher/choices/<id>/edit/
  teacher_choice_delete   GET/POST /assessments/teacher/choices/<id>/delete/

Security model (enforced on every teacher view)
-----------------------------------------------
  1. @login_required
  2. is_teacher check — non-teachers receive PermissionDenied
  3. Ownership check — teachers can only manage objects in their own courses
     (verified through the Course.teacher FK chain)
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from courses.models import Course, Enrollment
from .forms import ChoiceForm, QuestionForm, QuizAttemptForm, QuizForm
from .models import Choice, Question, Quiz, QuizAttempt, StudentAnswer


# ─────────────────────────────────────────────────────────────────────────────
# Shared security helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_teacher(user):
    """Raise PermissionDenied if the user is not a teacher."""
    if not user.is_teacher:
        raise PermissionDenied


def _require_enrollment(user, quiz):
    """Raise PermissionDenied if the student is not enrolled in the quiz's course."""
    if not Enrollment.objects.filter(student=user, course=quiz.course).exists():
        raise PermissionDenied


def _require_teacher_owns_quiz(user, quiz):
    """Raise PermissionDenied if the teacher does not own the quiz's course."""
    if quiz.course.teacher != user:
        raise PermissionDenied


def _require_teacher_owns_question(user, question):
    """Raise PermissionDenied if the teacher does not own the question's quiz's course."""
    if question.quiz.course.teacher != user:
        raise PermissionDenied


def _require_teacher_owns_choice(user, choice):
    """Raise PermissionDenied if the teacher does not own the choice's question's quiz's course."""
    if choice.question.quiz.course.teacher != user:
        raise PermissionDenied


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3B — Student views (UNCHANGED)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def quiz_detail(request, quiz_id):
    """Landing page for a quiz — shows metadata and the student's attempt history."""
    quiz = get_object_or_404(
        Quiz.objects.select_related('course', 'course__teacher'),
        pk=quiz_id,
    )

    if request.user.is_student:
        _require_enrollment(request.user, quiz)
    elif request.user.is_teacher:
        _require_teacher_owns_quiz(request.user, quiz)

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
    """Renders the quiz form with one radio-button field per question."""
    quiz = get_object_or_404(Quiz.objects.select_related('course'), pk=quiz_id)

    if not request.user.is_student:
        messages.error(request, "Only students can take quizzes.")
        return redirect('quiz_detail', quiz_id=quiz.pk)

    _require_enrollment(request.user, quiz)

    if not quiz.questions.exists():
        messages.warning(request, "This quiz has no questions yet.")
        return redirect('quiz_detail', quiz_id=quiz.pk)

    form = QuizAttemptForm(quiz=quiz)
    context = {
        'quiz': quiz,
        'form': form,
        'total_questions': quiz.questions.count(),
    }
    return render(request, 'assessments/quiz_take.html', context)


@login_required
def quiz_submit(request, quiz_id):
    """Processes a submitted quiz, scores it, and redirects to attempt_detail."""
    if request.method != 'POST':
        return redirect('quiz_take', quiz_id=quiz_id)

    quiz = get_object_or_404(Quiz.objects.select_related('course'), pk=quiz_id)

    if not request.user.is_student:
        raise PermissionDenied

    _require_enrollment(request.user, quiz)

    form = QuizAttemptForm(quiz=quiz, data=request.POST)

    if not form.is_valid():
        context = {
            'quiz': quiz,
            'form': form,
            'total_questions': quiz.questions.count(),
        }
        return render(request, 'assessments/quiz_take.html', context)

    questions       = Question.objects.filter(quiz=quiz).prefetch_related('choices').order_by('order')
    total_questions = questions.count()

    attempt = QuizAttempt.objects.create(
        student=request.user,
        quiz=quiz,
        score=0,
        total_questions=total_questions,
        percentage=Decimal('0.00'),
        passed=False,
    )

    score = 0
    for question in questions:
        field_name    = f'question_{question.pk}'
        choice_pk     = form.cleaned_data[field_name]
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

    percentage = (
        (Decimal(score) / Decimal(total_questions) * Decimal('100')).quantize(Decimal('0.01'))
        if total_questions > 0
        else Decimal('0.00')
    )
    passed = percentage >= Decimal(quiz.passing_score)

    attempt.score      = score
    attempt.percentage = percentage
    attempt.passed     = passed
    attempt.save()

    result_word = "Passed" if passed else "Not passed"
    messages.success(
        request,
        f"Quiz submitted! You scored {score}/{total_questions} ({percentage}%). {result_word}."
    )
    return redirect('attempt_detail', attempt_id=attempt.pk)


@login_required
def attempt_detail(request, attempt_id):
    """Shows the full scored result of one QuizAttempt with per-answer feedback."""
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related(
            'student', 'quiz', 'quiz__course', 'quiz__course__teacher'
        ),
        pk=attempt_id,
    )

    if request.user.is_student:
        if attempt.student != request.user:
            raise PermissionDenied
    elif request.user.is_teacher:
        if attempt.quiz.course.teacher != request.user:
            raise PermissionDenied

    answers = (
        attempt.answers
        .select_related('question', 'choice')
        .prefetch_related('question__choices')
        .order_by('question__order')
    )

    context = {'attempt': attempt, 'answers': answers}
    return render(request, 'assessments/attempt_detail.html', context)


@login_required
def teacher_attempts(request):
    """Lists all quiz attempts across the teacher's courses."""
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

    context = {'attempts': attempts}
    return render(request, 'assessments/teacher_attempts.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3C — Teacher Quiz Management
# ─────────────────────────────────────────────────────────────────────────────

# ── Quiz CRUD ─────────────────────────────────────────────────────────────────

@login_required
def teacher_quiz_list(request):
    """
    Lists all quizzes belonging to the logged-in teacher's courses.
    Includes attempt count per quiz for at-a-glance analytics.
    """
    _require_teacher(request.user)

    quizzes = (
        Quiz.objects
        .filter(course__teacher=request.user)
        .select_related('course')
        .order_by('course__title', 'created_at')
    )

    context = {'quizzes': quizzes}
    return render(request, 'assessments/teacher_quiz_list.html', context)


@login_required
def teacher_quiz_create(request):
    """Teacher creates a new Quiz, then is redirected to manage its questions."""
    _require_teacher(request.user)

    if request.method == 'POST':
        form = QuizForm(request.POST, teacher=request.user)
        if form.is_valid():
            quiz = form.save()
            messages.success(request, f"Quiz '{quiz.title}' created successfully.")
            return redirect('teacher_question_list', quiz_id=quiz.pk)
    else:
        form = QuizForm(teacher=request.user)

    context = {'form': form, 'action': 'Create'}
    return render(request, 'assessments/quiz_form.html', context)


@login_required
def teacher_quiz_edit(request, quiz_id):
    """Teacher edits an existing quiz they own."""
    _require_teacher(request.user)

    quiz = get_object_or_404(Quiz.objects.select_related('course'), pk=quiz_id)
    _require_teacher_owns_quiz(request.user, quiz)

    if request.method == 'POST':
        # teacher=request.user keeps the course dropdown scoped to their courses
        form = QuizForm(request.POST, instance=quiz, teacher=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Quiz '{quiz.title}' updated successfully.")
            return redirect('teacher_quiz_list')
    else:
        form = QuizForm(instance=quiz, teacher=request.user)

    context = {'form': form, 'quiz': quiz, 'action': 'Edit'}
    return render(request, 'assessments/quiz_form.html', context)


@login_required
def teacher_quiz_delete(request, quiz_id):
    """
    Confirmation page + DELETE for a quiz.
    Cascade via DB relationships automatically removes:
      Questions → Choices → StudentAnswers; QuizAttempts → StudentAnswers
    """
    _require_teacher(request.user)

    quiz = get_object_or_404(Quiz.objects.select_related('course'), pk=quiz_id)
    _require_teacher_owns_quiz(request.user, quiz)

    if request.method == 'POST':
        title = quiz.title
        quiz.delete()
        messages.success(request, f"Quiz '{title}' and all its data have been deleted.")
        return redirect('teacher_quiz_list')

    context = {'quiz': quiz}
    return render(request, 'assessments/quiz_confirm_delete.html', context)


# ── Question CRUD ──────────────────────────────────────────────────────────────

@login_required
def teacher_question_list(request, quiz_id):
    """Lists all questions for a quiz, with a link to manage each question's choices."""
    _require_teacher(request.user)

    quiz = get_object_or_404(Quiz.objects.select_related('course'), pk=quiz_id)
    _require_teacher_owns_quiz(request.user, quiz)

    questions = (
        quiz.questions
        .prefetch_related('choices')
        .order_by('order')
    )

    context = {'quiz': quiz, 'questions': questions}
    return render(request, 'assessments/question_list.html', context)


@login_required
def teacher_question_create(request, quiz_id):
    """Teacher adds a new question to a quiz they own."""
    _require_teacher(request.user)

    quiz = get_object_or_404(Quiz.objects.select_related('course'), pk=quiz_id)
    _require_teacher_owns_quiz(request.user, quiz)

    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question      = form.save(commit=False)
            question.quiz = quiz
            question.save()
            messages.success(request, f"Question added. Now add the answer choices.")
            return redirect('teacher_choice_list', question_id=question.pk)
    else:
        # Pre-fill order with the next available number
        next_order = quiz.questions.count() + 1
        form = QuestionForm(initial={'order': next_order})

    context = {'form': form, 'quiz': quiz, 'action': 'Add'}
    return render(request, 'assessments/question_form.html', context)


@login_required
def teacher_question_edit(request, question_id):
    """Teacher edits a question they own."""
    _require_teacher(request.user)

    question = get_object_or_404(
        Question.objects.select_related('quiz', 'quiz__course'),
        pk=question_id,
    )
    _require_teacher_owns_question(request.user, question)

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, "Question updated successfully.")
            return redirect('teacher_question_list', quiz_id=question.quiz.pk)
    else:
        form = QuestionForm(instance=question)

    context = {'form': form, 'question': question, 'quiz': question.quiz, 'action': 'Edit'}
    return render(request, 'assessments/question_form.html', context)


@login_required
def teacher_question_delete(request, question_id):
    """
    Confirmation page + DELETE for a question.
    Cascade removes its Choices and any StudentAnswer rows referencing them.
    """
    _require_teacher(request.user)

    question = get_object_or_404(
        Question.objects.select_related('quiz', 'quiz__course'),
        pk=question_id,
    )
    _require_teacher_owns_question(request.user, question)

    if request.method == 'POST':
        quiz_id = question.quiz.pk
        question.delete()
        messages.success(request, "Question deleted.")
        return redirect('teacher_question_list', quiz_id=quiz_id)

    context = {'question': question, 'quiz': question.quiz}
    return render(request, 'assessments/question_confirm_delete.html', context)


# ── Choice CRUD ────────────────────────────────────────────────────────────────

@login_required
def teacher_choice_list(request, question_id):
    """Lists all choices for a question."""
    _require_teacher(request.user)

    question = get_object_or_404(
        Question.objects.select_related('quiz', 'quiz__course')
                        .prefetch_related('choices'),
        pk=question_id,
    )
    _require_teacher_owns_question(request.user, question)

    context = {'question': question, 'quiz': question.quiz, 'choices': question.choices.all()}
    return render(request, 'assessments/choice_list.html', context)


@login_required
def teacher_choice_create(request, question_id):
    """
    Teacher adds a choice to a question.
    If is_correct=True, all other choices on this question are set to False
    automatically so there is always at most one correct answer.
    """
    _require_teacher(request.user)

    question = get_object_or_404(
        Question.objects.select_related('quiz', 'quiz__course'),
        pk=question_id,
    )
    _require_teacher_owns_question(request.user, question)

    if request.method == 'POST':
        form = ChoiceForm(request.POST)
        if form.is_valid():
            choice          = form.save(commit=False)
            choice.question = question
            choice.save()

            # Enforce single-correct rule: unmark all other choices if this one is correct
            if choice.is_correct:
                question.choices.exclude(pk=choice.pk).update(is_correct=False)

            messages.success(request, f"Choice '{choice.choice_text[:40]}' added.")
            return redirect('teacher_choice_list', question_id=question.pk)
    else:
        form = ChoiceForm()

    context = {'form': form, 'question': question, 'quiz': question.quiz, 'action': 'Add'}
    return render(request, 'assessments/choice_form.html', context)


@login_required
def teacher_choice_edit(request, choice_id):
    """
    Teacher edits a choice.
    Same single-correct enforcement as create.
    """
    _require_teacher(request.user)

    choice = get_object_or_404(
        Choice.objects.select_related('question', 'question__quiz', 'question__quiz__course'),
        pk=choice_id,
    )
    _require_teacher_owns_choice(request.user, choice)
    question = choice.question

    if request.method == 'POST':
        form = ChoiceForm(request.POST, instance=choice)
        if form.is_valid():
            choice = form.save()

            # Enforce single-correct rule
            if choice.is_correct:
                question.choices.exclude(pk=choice.pk).update(is_correct=False)

            messages.success(request, "Choice updated successfully.")
            return redirect('teacher_choice_list', question_id=question.pk)
    else:
        form = ChoiceForm(instance=choice)

    context = {
        'form': form,
        'choice': choice,
        'question': question,
        'quiz': question.quiz,
        'action': 'Edit',
    }
    return render(request, 'assessments/choice_form.html', context)


@login_required
def teacher_choice_delete(request, choice_id):
    """
    Confirmation page + DELETE for a choice.
    Cascade removes any StudentAnswer rows that referenced this choice.
    """
    _require_teacher(request.user)

    choice = get_object_or_404(
        Choice.objects.select_related('question', 'question__quiz', 'question__quiz__course'),
        pk=choice_id,
    )
    _require_teacher_owns_choice(request.user, choice)
    question = choice.question

    if request.method == 'POST':
        text = choice.choice_text[:60]
        choice.delete()
        messages.success(request, f"Choice '{text}' deleted.")
        return redirect('teacher_choice_list', question_id=question.pk)

    context = {'choice': choice, 'question': question, 'quiz': question.quiz}
    return render(request, 'assessments/choice_confirm_delete.html', context)
