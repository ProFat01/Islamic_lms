from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model with role field."""

    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Islamic LMS', {
            'fields': ('role', 'profile_picture', 'bio')
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Islamic LMS', {
            'fields': ('role', 'first_name', 'last_name', 'email')
        }),
    )
