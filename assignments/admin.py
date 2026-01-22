from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import AssignmentSubmission, AdReward

@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')

@admin.register(AdReward)
class AdRewardAdmin(ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')