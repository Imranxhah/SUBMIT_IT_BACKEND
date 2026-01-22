from django.urls import path
from .views import GenerateAssignmentView, RewardView, AssignmentStatusView

urlpatterns = [
    path('generate/', GenerateAssignmentView.as_view(), name='generate_assignment'),
    path('reward/', RewardView.as_view(), name='assignment_reward'),
    path('status/', AssignmentStatusView.as_view(), name='assignment_status'),
]
