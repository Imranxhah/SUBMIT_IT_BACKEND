import datetime
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from .models import AssignmentSubmission, AdReward
from django.conf import settings

User = get_user_model()

class AssignmentLimitTests(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        self.client.force_authenticate(user=self.user)
        
        # URLs
        self.generate_url = reverse('generate_assignment')
        self.reward_url = reverse('assignment_reward')
        
        # Dummy file for upload
        self.pdf_content = b'%PDF-1.4 mock content'
        self.upload_file = SimpleUploadedFile(
            "test_assignment.pdf", 
            self.pdf_content, 
            content_type="application/pdf"
        )
        
        self.valid_payload = {
            'assignment_number': '1',
            'subject_name': 'Math',
            'teacher_name': 'Mr. Smith',
            'assignment_file': self.upload_file
        }

    @patch('assignments.views.extract_content_from_file')
    @patch('assignments.views.HTML.write_pdf')
    def test_submission_limit_enforcement(self, mock_write_pdf, mock_extract):
        """Test that the user cannot exceed the daily limit."""
        mock_extract.return_value = "Mocked Extracted Content"
        mock_write_pdf.return_value = b"Mock PDF Byte String"
        
        # Ensure default limit is 3 (as per settings)
        # We can override setting for test stability if needed, but assuming 3 is fine
        limit = getattr(settings, 'DAILY_SUBMISSION_LIMIT', 3)
        
        # 1. Submit up to the limit
        for i in range(limit):
            # We need to create a new file object for each request because it gets closed
            file_obj = SimpleUploadedFile("test.pdf", b"content", "application/pdf")
            payload = self.valid_payload.copy()
            payload['assignment_file'] = file_obj
            
            response = self.client.post(self.generate_url, payload, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_200_OK, f"Submission {i+1} failed")
            
        # Verify db count
        self.assertEqual(AssignmentSubmission.objects.filter(user=self.user).count(), limit)

        # 2. Try to submit one more
        file_obj = SimpleUploadedFile("test_fail.pdf", b"content", "application/pdf")
        payload = self.valid_payload.copy()
        payload['assignment_file'] = file_obj
        
        response = self.client.post(self.generate_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Daily submission limit reached", response.data['error'])

    @patch('assignments.views.extract_content_from_file')
    @patch('assignments.views.HTML.write_pdf')
    def test_rolling_window_logic(self, mock_write_pdf, mock_extract):
        """Test that old submissions don't count towards the limit."""
        mock_extract.return_value = "Content"
        mock_write_pdf.return_value = b"PDF"

        limit = getattr(settings, 'DAILY_SUBMISSION_LIMIT', 3)
        
        # Create 'limit' number of submissions in the past (25 hours ago)
        past_time = timezone.now() - datetime.timedelta(hours=25)
        for _ in range(limit):
            sub = AssignmentSubmission.objects.create(user=self.user)
            sub.created_at = past_time
            sub.save() # Save to persist override of auto_now_add

        # Verify they exist but are old
        self.assertEqual(AssignmentSubmission.objects.filter(user=self.user).count(), limit)
        
        # Now try to submit a new one (should succeed because old ones are expired)
        file_obj = SimpleUploadedFile("test_new.pdf", b"content", "application/pdf")
        payload = self.valid_payload.copy()
        payload['assignment_file'] = file_obj
        
        response = self.client.post(self.generate_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('assignments.views.extract_content_from_file')
    @patch('assignments.views.HTML.write_pdf')
    def test_reward_increases_limit(self, mock_write_pdf, mock_extract):
        """Test that claiming a reward allows extra submissions."""
        mock_extract.return_value = "Content"
        mock_write_pdf.return_value = b"PDF"
        
        limit = getattr(settings, 'DAILY_SUBMISSION_LIMIT', 3)
        
        # 1. Fill the limit manually to save time
        for _ in range(limit):
            AssignmentSubmission.objects.create(user=self.user)
            
        # 2. Verify next submission fails
        file_obj = SimpleUploadedFile("test_fail.pdf", b"content", "application/pdf")
        payload = self.valid_payload.copy()
        payload['assignment_file'] = file_obj
        response = self.client.post(self.generate_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # 3. Claim a reward
        reward_response = self.client.post(self.reward_url)
        self.assertEqual(reward_response.status_code, status.HTTP_200_OK)
        self.assertEqual(AdReward.objects.filter(user=self.user).count(), 1)
        
        # 4. Verify submission now succeeds
        file_obj_2 = SimpleUploadedFile("test_success.pdf", b"content", "application/pdf")
        payload['assignment_file'] = file_obj_2
        response = self.client.post(self.generate_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 5. Verify limit is hit again (now limit + 1)
        file_obj_3 = SimpleUploadedFile("test_fail_again.pdf", b"content", "application/pdf")
        payload['assignment_file'] = file_obj_3
        response = self.client.post(self.generate_url, payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access these endpoints."""
        self.client.logout()
        
        # Try generate
        response = self.client.post(self.generate_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Try reward
        response = self.client.post(self.reward_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
