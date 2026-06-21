"""
islamic_lms URL Configuration

Phase 3E adds exactly one new line: the public certificate verification URL.
Everything else is unchanged.
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
    path('assessments/', include('assessments.urls')),   # Phase 3B

    # Phase 3E — public certificate verification (no login required)
    path(
        'certificate/verify/<str:certificate_id>/',
        course_views.certificate_verify,
        name='certificate_verify',
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)