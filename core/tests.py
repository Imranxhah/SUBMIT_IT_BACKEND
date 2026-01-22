from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import AppVersion
import time

class AppVersionTests(APITestCase):
    def test_get_app_version(self):
        """
        Ensure we can get the latest app version.
        """
        AppVersion.objects.create(version="1.0.0", force_update=False)
        time.sleep(0.1) # Ensure timestamp difference for SQLite
        AppVersion.objects.create(version="1.1.0", force_update=True)
        
        url = reverse('app-version')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['version'], "1.1.0")
        self.assertEqual(response.data['force_update'], True)

    def test_get_app_version_empty(self):
        """
        Ensure we get 404 if no version exists.
        """
        url = reverse('app-version')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)