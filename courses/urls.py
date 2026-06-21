"""
courses/urls.py

All existing URLs are preserved exactly.
Phase 3D added: lessons/<id>/complete/
Phase 3E adds: certificate list/detail/print URLs (mounted under /courses/)
               plus the public verification URL is registered separately
               in the ROOT urls.py as /certificate/verify/<id>/ — see
               root_urls.py output for that single added line.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Public ───────────────────────────────────────────────────────────
    path('', views.course_list, name='course_list'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    # ── Phase 3E: Certificates (placed before bare <slug:slug>/ to avoid
    #    "certificates" being interpreted as a course slug) ──────────────
    path('certificates/', views.certificate_list, name='certificate_list'),
    path('certificates/<int:certificate_id>/', views.certificate_detail, name='certificate_detail'),
    path('certificates/<int:certificate_id>/print/', views.certificate_print, name='certificate_print'),

    path('<slug:slug>/', views.course_detail, name='course_detail'),
    path('<slug:slug>/enroll/', views.enroll, name='enroll'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/', views.lesson_view, name='lesson_view'),

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
]