"""
Django settings for CRM Service avec schémas séparés
"""

import os
from pathlib import Path
from decouple import config
from corsheaders.defaults import default_headers

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')


# Application definition

# Configuration django-tenants
SHARED_APPS = [
    'django_tenants',  # Obligatoire en premier
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third party apps
    'rest_framework',
    'corsheaders',
    
    # Apps partagées (contient les modèles Client et Domain)
    'tiers',  # Modèles tenant partagés
]

TENANT_APPS = [
    # Apps spécifiques aux tenants (modèles métier isolés)
    'tenant_metier',  # Modèles métier des tiers (isolés par schéma)
    'opportunites',  # Modèles métier des opportunités
]

INSTALLED_APPS = SHARED_APPS + TENANT_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'tiers.middleware_hybrid.HeaderTenantMiddleware',  # Middleware hybride pour headers (remplace TenantMainMiddleware)
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = "crm_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "crm_service.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# Database avec django-tenants
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',  # Engine django-tenants
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
}

# Configuration pour django-tenants
DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

# Internationalization
LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# API Configuration
API_PORT = config('API_PORT', default=8003, cast=int)
API_HOST = config('API_HOST', default='0.0.0.0')

# CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",  # React frontend
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # API Gateway
] if not DEBUG else []

CORS_ALLOW_HEADERS = list(default_headers) + [
    'X-Tenant-ID',
]

# Créer le dossier logs s'il n'existe pas
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'crm.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': config('LOG_LEVEL', default='INFO'),
    },
    'loggers': {
        'tiers': {
            'handlers': ['console', 'file'],
            'level': config('LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}

# Configuration django-tenants
TENANT_MODEL = 'tiers.Client'
TENANT_DOMAIN_MODEL = 'tiers.Domain'

# Configuration tenant schema (garder pour compatibilité)
TENANT_SCHEMA_PREFIX = 'tenant_'

# Sécurité
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
