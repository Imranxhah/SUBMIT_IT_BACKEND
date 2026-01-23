
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables (ensure .env exists on the server or vars are set in the dashboard)
# In PythonAnywhere, you usually set these in the WSGI file or the "Environment variables" section,
# but loading .env is good for consistency if you use it there.
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# CRITICAL: On PythonAnywhere, generate a new random key and set it in your .env or environment variables.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-t_u80fh0gsq)6(*@t33k&9+h*n=wg&e^xtikpcs4-(4k+q$tub')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False 

# PythonAnywhere specific allowed hosts
ALLOWED_HOSTS = [
    'submitit.pythonanywhere.com', 
    'www.submitit.pythonanywhere.com',
    'localhost',
    '127.0.0.1'
]


# Application definition

INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    
    # Local apps
    'users',
    'assignments',
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # Added CORS
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'Submit_it.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Submit_it.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# Note: SQLite works fine on PythonAnywhere for small to medium apps.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

# On PythonAnywhere, you must set up the Static Files mapping in the "Web" tab.
# URL: /static/ -> Directory: /home/submitit/SUBMIT_IT_BACKEND/staticfiles
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Media files (User uploads)
# On PythonAnywhere, add another mapping in the "Web" tab.
# URL: /media/ -> Directory: /home/submitit/SUBMIT_IT_BACKEND/media
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '10000/day',
        'otp': '5/min',
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

OTP_EXPIRATION_MINUTES = 10

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
# Ensure these are set in your PythonAnywhere environment variables or .env file
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f"Submit_it <{os.getenv('EMAIL_HOST_USER', 'noreply@submitit.com')}>"

# CORS
# For production, it is safer to specify exact origins rather than allow all.
# Update this list with your frontend domain(s).
CORS_ALLOWED_ORIGINS = [
    "https://submitit.pythonanywhere.com",
    # Add your frontend domain here, e.g.:
    # "https://my-frontend-app.vercel.app",
]
# Fallback if you want to allow all (not recommended for strict production but useful for testing)
CORS_ALLOW_ALL_ORIGINS = True 
# CORS_ALLOW_CREDENTIALS = True # Uncomment if using cookies/sessions with cross-origin requests

UNFOLD = {
    "SITE_TITLE": "Submit it Admin",
    "SITE_HEADER": "Submit it",
    "SITE_SYMBOL": "speed", # icon from google fonts
    "SHOW_HISTORY": True, # show history button in model admin
    "SHOW_VIEW_ON_SITE": True, # show view on site button in model admin
}

DAILY_SUBMISSION_LIMIT = 3

# Security Settings for Production (HTTPS)
# Uncomment these once you have HTTPS set up (PythonAnywhere provides this by default)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
