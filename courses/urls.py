from django.urls import path
from . import views

urlpatterns = [
    # ── Public ───────────────────────────────────────────────────────────
    path('', views.course_list, name='course_list'),

    # ── Phase 3D: Lesson completion toggle ───────────────────────────────
    # POST only (enforced in the view).
    # Placed before the bare <slug:slug>/ patterns cannot match "lessons/..."
    # because it lives under course_slug/lessons/, which already works.
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

    path('<slug:slug>/enroll/', views.enroll, name='enroll'),

    # Category pages — must come before bare <slug:slug>/ to avoid collision
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),

    path('<slug:course_slug>/lessons/<int:lesson_id>/', views.lesson_view, name='lesson_view'),
    path('<slug:slug>/', views.course_detail, name='course_detail'),

]