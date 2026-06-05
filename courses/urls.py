from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.course_list, name='course_list'),
    
    # Student
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),

    # Teacher
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('create/', views.course_create, name='course_create'),
    path('<slug:course_slug>/lessons/add/', views.lesson_create, name='lesson_create'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/edit/', views.lesson_edit, name='lesson_edit'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),


    path('<slug:slug>/edit/', views.course_edit, name='course_edit'),
    path('<slug:slug>/manage/', views.course_manage, name='course_manage'),
    
    path('<slug:slug>/enroll/', views.enroll, name='enroll'),
    path('<slug:course_slug>/lessons/<int:lesson_id>/', views.lesson_view, name='lesson_view'),

    path('<slug:slug>/', views.course_detail, name='course_detail'),
    
    
    
]
