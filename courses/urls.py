"""
courses/urls.py

All existing URLs are preserved exactly.
Phase 3D added: lessons/<id>/complete/
Phase 3E added: certificate list/detail/print URLs (mounted under /courses/)
Phase 4B added: review create/edit/delete + teacher reviews analytics
Phase 4B.1 added: teacher/analytics/ — advanced teacher analytics dashboard
Phase 5A added: advisor/ — AI Learning Advisor page
Phase 5B adds: study-planner/ — AI Study Planner page

URL ordering note: review/create/, teacher/reviews/, teacher/analytics/,
advisor/, and study-planner/ are all placed before the bare <slug:slug>/
pattern (same technique already used for certificates/) so Django's URL
resolver tries the more specific literal prefixes first and never mistakes
"review", "teacher", "advisor", or "study-planner" for a course slug.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Public ───────────────────────────────────────────────────────────
    path('', views.course_list, name='course_list'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    # ── Phase 3E: Certificates ────────────────────────────────────────────
    path('certificates/', views.certificate_list, name='certificate_list'),
    path('certificates/<int:certificate_id>/', views.certificate_detail, name='certificate_detail'),
    path('certificates/<int:certificate_id>/print/', views.certificate_print, name='certificate_print'),

    # ── Phase 4B: Reviews ─────────────────────────────────────────────────
    path('review/<int:course_id>/create/', views.review_create, name='review_create'),
    path('review/<int:review_id>/edit/', views.review_edit, name='review_edit'),
    path('review/<int:review_id>/delete/', views.review_delete, name='review_delete'),
    path('teacher/reviews/', views.teacher_reviews, name='teacher_reviews'),

    # ── Phase 4B.1: Advanced Teacher Analytics ───────────────────────────
    path('teacher/analytics/', views.teacher_analytics, name='teacher_analytics'),

    # ── Phase 5A: AI Learning Advisor ─────────────────────────────────────
    path('advisor/', views.advisor_dashboard, name='advisor_dashboard'),

    # ── Phase 5B: AI Study Planner ─────────────────────────────────────────
    path('study-planner/', views.study_planner, name='study_planner'),

    # ── Phase 3D: Lesson completion toggle ───────────────────────────────
    path('lessons/<int:lesson_id>/complete/', views.lesson_complete, name='lesson_complete'),

    # ── Student ───────────────────────────────────────────────────────────
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),

    # ── Teacher ───────────────────────────────────────────────────────────
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('create/', views.course_create, name='course_create'),
    path('<slug:slug>/edit/', views.course_edit, name='course_edit'),
    path('<slug:slug>/manage/', views.course_manage, name='course_manage'),
    path('<slug:course_slug>/lessons/add/', views.lesson_create, name='lesson_create'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/edit/', views.lesson_edit, name='lesson_edit'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),

    path('<slug:slug>/', views.course_detail, name='course_detail'),
    path('<slug:slug>/enroll/', views.enroll, name='enroll'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/', views.lesson_view, name='lesson_view'),
]