import logging
from datetime import timedelta
from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.exceptions import APIException
from .serializers import (
    UserRegistrationSerializer, 
    VerifyOTPSerializer, 
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer
)
from .utils import generate_otp, send_otp_email

logger = logging.getLogger(__name__)

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def handle_exception(self, exc):
        status_code = getattr(exc, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
        if isinstance(exc, APIException):
            status_code = exc.status_code
        elif isinstance(exc, ValueError):
            status_code = status.HTTP_400_BAD_REQUEST

        error_data = {
            "error_type": exc.__class__.__name__,
            "detail": str(exc),
            "code": getattr(exc, 'default_code', 'unknown_error'),
            "message": "An unexpected error occurred."
        }
        
        if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
            error_data['detail'] = exc.detail.get('detail', str(exc))
            error_data['code'] = exc.detail.get('code', error_data['code'])
            if 'message' in exc.detail:
                error_data['message'] = exc.detail['message']
            elif 'detail' in exc.detail:
                error_data['message'] = exc.detail['detail']

        if getattr(exc, 'default_code', None) == 'unverified_user' or (hasattr(exc, 'detail') and isinstance(exc.detail, dict) and exc.detail.get('code') == 'unverified_user'):
            error_data['code'] = 'unverified_user'
            error_data['detail'] = getattr(exc, 'detail', "User is not active. A new OTP has been sent.")
            error_data['message'] = "User is not active. A new OTP has been sent."
            status_code = status.HTTP_401_UNAUTHORIZED
        
        elif getattr(exc, 'default_code', None) in ['authentication_failed', 'no_active_account'] or \
             (hasattr(exc, 'detail') and isinstance(exc.detail, dict) and exc.detail.get('code') in ['authentication_failed', 'no_active_account']):
            error_data['code'] = 'authentication_failed'
            error_data['detail'] = "No account found with the given credentials."
            error_data['message'] = "No account found with the given credentials."
            status_code = status.HTTP_401_UNAUTHORIZED

        if not isinstance(exc, APIException):
            error_data['message'] = "An unexpected server error occurred."
            error_data['detail'] = "An internal server error occurred."
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
        return Response(error_data, status=status_code)

class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()
                    otp = generate_otp()
                    user.otp_code = otp
                    user.otp_created_at = timezone.now()
                    user.otp_attempts = 0
                    user.save()
                    send_otp_email(user.email, otp)
                    
                return Response({
                    "message": "User registered successfully. Please verify your email.",
                    "email": user.email
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                return Response({
                    "error": "Failed to send verification email. User not created.",
                    "details": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            if 'email' in serializer.errors and 'already exists' in str(serializer.errors['email']):
                email = request.data.get('email')
                user = User.objects.filter(email=email).first()

                if user and not user.is_active:
                    if user.otp_created_at and timezone.now() < user.otp_created_at + timedelta(minutes=1):
                         return Response({
                            "status": "unverified",
                            "message": "Account validation pending. Please check your email for the code."
                        }, status=status.HTTP_409_CONFLICT)

                    try:
                        with transaction.atomic():
                            otp = generate_otp()
                            user.otp_code = otp
                            user.otp_created_at = timezone.now()
                            user.otp_attempts = 0
                            user.save()
                            send_otp_email(user.email, otp)
                        
                        return Response({
                            "status": "unverified",
                            "message": "This account is not verified. A new OTP has been sent to your email."
                        }, status=status.HTTP_409_CONFLICT)

                    except Exception as e:
                        return Response({
                            "error": "Failed to resend verification email.",
                            "details": str(e)
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.is_active = True
            user.otp_code = None
            user.otp_attempts = 0
            user.save()
            return Response({"message": "Account verified successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email'].lower()
            user = User.objects.filter(email=email).first()
            
            if user:
                otp = generate_otp()
                user.otp_code = otp
                user.otp_created_at = timezone.now()
                user.otp_attempts = 0
                user.save()
                
                try:
                    send_otp_email(user.email, otp)
                except Exception:
                    pass 
                
                return Response({"message": "An OTP has been sent to your email address."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "No account found with this email address."}, status=status.HTTP_404_NOT_FOUND)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            new_password = serializer.validated_data['new_password']
            user.set_password(new_password)
            user.otp_code = None
            user.otp_attempts = 0
            user.save()
            return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserRegistrationSerializer

    def get_object(self):
        return self.request.user

class UserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer

class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email'].lower()
            user = User.objects.filter(email=email).first()

            if user:
                if user.is_active:
                    return Response({"message": "User is already verified."}, status=status.HTTP_400_BAD_REQUEST)

                try:
                    with transaction.atomic():
                        otp = generate_otp()
                        user.otp_code = otp
                        user.otp_created_at = timezone.now()
                        user.otp_attempts = 0
                        user.save()
                        send_otp_email(user.email, otp)
                    
                    return Response({
                        "message": "A new verification OTP has been sent to your email address.",
                        "email": user.email
                    }, status=status.HTTP_200_OK)

                except Exception as e:
                    return Response({
                        "error": "Failed to send new OTP. Please try again later.",
                        "details": str(e)
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({"error": "No account found with this email address."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            self.object.set_password(serializer.validated_data['new_password'])
            self.object.save()
            return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)