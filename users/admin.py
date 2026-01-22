from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    # Use email instead of username
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'university_name', 'department', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'department')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'university_name', 'department', 'registration_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('OTP Info', {'fields': ('otp_code', 'otp_created_at', 'otp_attempts')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password', 'university_name', 'department', 'registration_number'),
        }),
    )
    
    search_fields = ('email', 'first_name', 'last_name', 'registration_number')