import random
import string
from django.core.mail import send_mail
from django.conf import settings

def generate_otp(length=6):
    """Generate a numeric OTP of given length."""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(email, otp):
    """
    Send OTP via email.
    Raises Exception if sending fails (critical for transaction rollback).
    """
    subject = 'Your Verification Code'
    message = f'Your verification code is: {otp}. It expires in {settings.OTP_EXPIRATION_MINUTES} minutes.'
    email_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@submitit.com')
    
    send_mail(
        subject,
        message,
        email_from,
        [email],
        fail_silently=False, 
    )
