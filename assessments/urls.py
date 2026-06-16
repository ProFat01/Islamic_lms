"""
assessments/urls.py

All URLs are mounted at /assessments/ in the root urls.py.

Phase 3B (student-facing, unchanged)
-------------------------------------
  quiz/<id>/           quiz_detail        pre-quiz landing page
  quiz/<id>/take/      quiz_take          quiz form
  quiz/<id>/submit/    quiz_submit        POST submission handler
  attempt/<id>/        attempt_detail     result + answer review
  teacher/attempts/    teacher_attempts   teacher analytics list

Phase 3C (teacher quiz management, new)
----------------------------------------
  teacher/quizzes/                         teacher_quiz_list
  teacher/quizzes/create/                  teacher_quiz_create
  teacher/quizzes/<id>/edit/               teacher_quiz_edit
  teacher/quizzes/<id>/delete/             teacher_quiz_delete
  teacher/quizzes/<id>/questions/          teacher_question_list
  teacher/questions/create/<quiz_id>/      teacher_question_create
  teacher/questions/<id>/edit/             teacher_question_edit
  teacher/questions/<id>/delete/           teacher_question_delete
  teacher/questions/<id>/choices/          teacher_choice_list
  teacher/questions/<id>/choices/create/   teacher_choice_create
  teacher/choices/<id>/edit/               teacher_choice_edit
  teacher/choices/<id>/delete/             teacher_choice_delete

URL design notes
----------------
- All teacher management routes are prefixed with teacher/ to make the
  permission boundary visually obvious.
- question/choice routes use singular nouns matching their model names.
- <int:*_id> is used throughout for clarity over bare <int:pk>.
"""

from django.urls import path
from . import views

urlpatterns = [

    # ── Phase 3B — Student-facing ─────────────────────────────────────────
    path('quiz/<int:quiz_id>/',
         views.quiz_detail,
         name='quiz_detail'),

    path('quiz/<int:quiz_id>/take/',
         views.quiz_take,
         name='quiz_take'),

    path('quiz/<int:quiz_id>/submit/',
         views.quiz_submit,
         name='quiz_submit'),

    path('attempt/<int:attempt_id>/',
         views.attempt_detail,
         name='attempt_detail'),

    path('teacher/attempts/',
         views.teacher_attempts,
         name='teacher_attempts'),

    # ── Phase 3C — Quiz CRUD ──────────────────────────────────────────────
    path('teacher/quizzes/',
         views.teacher_quiz_list,
         name='teacher_quiz_list'),

    path('teacher/quizzes/create/',
         views.teacher_quiz_create,
         name='teacher_quiz_create'),

    path('teacher/quizzes/<int:quiz_id>/edit/',
         views.teacher_quiz_edit,
         name='teacher_quiz_edit'),

    path('teacher/quizzes/<int:quiz_id>/delete/',
         views.teacher_quiz_delete,
         name='teacher_quiz_delete'),

    # ── Phase 3C — Question CRUD ──────────────────────────────────────────
    path('teacher/quizzes/<int:quiz_id>/questions/',
         views.teacher_question_list,
         name='teacher_question_list'),

    path('teacher/questions/create/<int:quiz_id>/',
         views.teacher_question_create,
         name='teacher_question_create'),

    path('teacher/questions/<int:question_id>/edit/',
         views.teacher_question_edit,
         name='teacher_question_edit'),

    path('teacher/questions/<int:question_id>/delete/',
         views.teacher_question_delete,
         name='teacher_question_delete'),

    # ── Phase 3C — Choice CRUD ────────────────────────────────────────────
    path('teacher/questions/<int:question_id>/choices/',
         views.teacher_choice_list,
         name='teacher_choice_list'),

    path('teacher/questions/<int:question_id>/choices/create/',
         views.teacher_choice_create,
         name='teacher_choice_create'),

    path('teacher/choices/<int:choice_id>/edit/',
         views.teacher_choice_edit,
         name='teacher_choice_edit'),

    path('teacher/choices/<int:choice_id>/delete/',
         views.teacher_choice_delete,
         name='teacher_choice_delete'),
]
