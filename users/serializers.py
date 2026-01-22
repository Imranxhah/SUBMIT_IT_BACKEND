import logging
from rest_framework import serializers
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from .utils import generate_otp, send_otp_email

logger = logging.getLogger(__name__)

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Normalize email to lowercase to match stored users
        if 'email' in attrs:
            attrs['email'] = attrs['email'].lower()
        email = attrs.get('email')
        
        try:
            validated_data = super().validate(attrs)
            return validated_data
        except AuthenticationFailed as e:
            if e.default_code == 'no_active_account':
                user = User.objects.filter(email__iexact=email).first()
                
                if user and not user.is_active:
                    if not user.check_password(attrs.get('password')):
                        raise AuthenticationFailed('No account found with the given credentials.', 'authentication_failed')

                    # Resend OTP logic
                    otp = generate_otp()
                    user.otp_code = otp
                    user.otp_created_at = timezone.now()
                    user.otp_attempts = 0
                    user.save()

                    try:
                        send_otp_email(user.email, otp)
                    except Exception as email_exc:
                        logger.error(f"Failed to send OTP email to {user.email}: {email_exc}")
                    
                    raise AuthenticationFailed(
                        'User is not active. A new OTP has been sent.',
                        'unverified_user'
                    )
                else:
                    raise e 
            else:
                raise e 

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'university_name', 'department', 'registration_number')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            university_name=validated_data.get('university_name', ''),
            department=validated_data.get('department', ''),
            registration_number=validated_data.get('registration_number', ''),
            is_active=False  # Inactive until OTP verified
        )
        return user

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(
        max_length=6, 
        error_messages={"blank": "The OTP code cannot be blank."}
    )

    def validate(self, attrs):
        email = attrs.get('email', '').lower()
        otp_code = attrs.get('otp_code')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or OTP.")

        if user.is_active:
             raise serializers.ValidationError("User is already active.")

        if user.otp_attempts > 5:
            raise serializers.ValidationError("Too many failed attempts. Account locked.")

        if user.otp_created_at and timezone.now() > user.otp_created_at + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES):
            raise serializers.ValidationError("OTP has expired.")
        
        if user.otp_code != otp_code:
            user.otp_attempts += 1
            user.save()
            raise serializers.ValidationError("Invalid OTP.")

        attrs['user'] = user
        return attrs

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate(self, attrs):
        email = attrs.get('email', '').lower()
        otp_code = attrs.get('otp_code')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid request.")

        if user.otp_attempts > 5:
            user.otp_attempts += 1
            user.save()
            raise serializers.ValidationError("Too many failed attempts. Account locked.")

        if user.otp_code != otp_code:
             user.otp_attempts += 1
             user.save()
             raise serializers.ValidationError("Invalid OTP.")
             
        if user.otp_created_at and timezone.now() > user.otp_created_at + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES):
            raise serializers.ValidationError("OTP has expired.")

        attrs['user'] = user
        return attrs

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct.")
        return value
