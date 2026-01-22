import os
import django
import json

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Submit_it.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from users.models import User

User = get_user_model()

def run_verification():
    client = APIClient()
    email = "teststudent@university.edu"
    password = "StrongPassword123!"
    
    print("--- 1. Cleaning up old test data ---")
    User.objects.filter(email=email).delete()
    
    print("\n--- 2. Testing Registration ---")
    reg_data = {
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "Student",
        "university_name": "Tech University",
        "department": "CS",
        "registration_number": "CS-2026-001"
    }
    response = client.post('/api/auth/register/', reg_data, format='json')
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code != 201:
        print("❌ Registration Failed")
        return

    print("\n--- 3. Retrieving OTP (Database Check) ---")
    user = User.objects.get(email=email)
    print(f"User Created: {user.email}")
    print(f"Is Active: {user.is_active}")
    print(f"OTP Code: {user.otp_code}")
    
    print("\n--- 4. Testing OTP Verification ---")
    verify_data = {
        "email": email,
        "otp_code": user.otp_code
    }
    response = client.post('/api/auth/verify/', verify_data, format='json')
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    user.refresh_from_db()
    if user.is_active:
        print("✅ User successfully activated")
    else:
        print("❌ User is still inactive")
        return

    print("\n--- 5. Testing Login ---")
    login_data = {
        "email": email,
        "password": password
    }
    response = client.post('/api/auth/login/', login_data, format='json')
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        tokens = response.json()
        access_token = tokens.get('access')
        print("✅ Login Successful")
        print(f"Access Token (truncated): {access_token[:20]}...")
        
        print("\n--- 6. Testing Protected Profile Endpoint ---")
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
        response = client.get('/api/users/profile/')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    else:
        print(f"❌ Login Failed: {response.json()}")

if __name__ == "__main__":
    run_verification()
