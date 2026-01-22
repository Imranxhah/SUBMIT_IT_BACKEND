from django.urls import path
from .views import AppVersionView

urlpatterns = [
    path('app-version/', AppVersionView.as_view(), name='app-version'),
]
