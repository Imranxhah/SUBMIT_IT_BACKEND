from django.urls import path
from .views import (
    StartAssignmentTaskView, 
    GetAssignmentProgressView, 
    DownloadAssignmentResultView, 
    RewardView, 
    AssignmentStatusView
)

urlpatterns = [
    # Starts the task -> returns {task_id, ...}
    path('generate/', StartAssignmentTaskView.as_view(), name='generate_assignment'),
    
    # Poll this: /assignments/progress/<task_id>/
    path('progress/<str:task_id>/', GetAssignmentProgressView.as_view(), name='assignment_progress'),
    
    # Download final result: /assignments/download/<task_id>/
    path('download/<str:task_id>/', DownloadAssignmentResultView.as_view(), name='assignment_download'),
    
    path('reward/', RewardView.as_view(), name='assignment_reward'),
    path('status/', AssignmentStatusView.as_view(), name='assignment_status'),
]