from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import AppVersion

@admin.register(AppVersion)
class AppVersionAdmin(ModelAdmin):
    list_display = ('version', 'force_update', 'created_at')
    list_filter = ('force_update',)