"""
assessments/urls.py

All URLs are namespaced under /assessments/ (registered in the root urls.py).

quiz_detail      GET   quiz/<id>/            — pre-quiz landing page
quiz_take        GET   quiz/<id>/take/       — render quiz form
quiz_submit      POST  quiz/<id>/submit/     — process submission
attempt_detail   GET   attempt/<id>/         — result + answer review
teacher_attempts GET   teacher/attempts/     — teacher analytics
"""

from django.urls import path
from . import views

urlpatterns = [
    path('quiz/<int:quiz_id>/',          views.quiz_detail,      name='quiz_detail'),
    path('quiz/<int:quiz_id>/take/',     views.quiz_take,        name='quiz_take'),
    path('quiz/<int:quiz_id>/submit/',   views.quiz_submit,      name='quiz_submit'),
    path('attempt/<int:attempt_id>/',    views.attempt_detail,   name='attempt_detail'),
    path('teacher/attempts/',            views.teacher_attempts, name='teacher_attempts'),
]
