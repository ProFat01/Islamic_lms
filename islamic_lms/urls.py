"""
islamic_lms URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from courses import views as course_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', course_views.home, name='home'),
    path('about/', course_views.about, name='about'),
    path('accounts/', include('accounts.urls')),
    path('courses/', include('courses.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
