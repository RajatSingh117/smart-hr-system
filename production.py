"""
Production settings for Smart HRMS.
Extends base settings with hardened security configuration.
"""

from .base import *
import os

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

if not SECRET_KEY or SECRET_KEY.startswith('django-insecure-'):
    raise ValueError(
        'Production SECRET_KEY must be set via environment variable. '
        'Generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
    )

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')
if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['']:
    raise ValueError('ALLOWED_HOSTS must be set via environment variable')

# Database - PostgreSQL required for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
}

# Security Headers
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Session Security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 28800  # 8 hours

# CSRF Security
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o]
CSRF_USE_SESSIONS = True

# Content Security Policy (django-csp 4.0+ format)
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ["'self'"],
        'script-src': ["'self'", 'csp.constants.NONCE'],
        'style-src': ["'self'", "'unsafe-inline'", 'csp.constants.NONCE'],
        'img-src': ["'self'", "data:"],
        'font-src': ["'self'"],
        'connect-src': ["'self'"],
        'frame-ancestors': ["'none'"],
        'form-action': ["'self'"],
        'base-uri': ["'self'"],
    },
    'INCLUDE_NONCE_IN': ['script-src', 'style-src'],
}

# Referrer Policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Permissions Policy (Feature Policy)
PERMISSIONS_POLICY = {
    'geolocation': [],
    'microphone': [],
    'camera': [],
    'payment': [],
    'usb': [],
    'magnetometer': [],
    'gyroscope': [],
    'accelerometer': [],
}

# Rate Limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_VIEW = 'apps.accounts.views.ratelimited_error'

# Cache configuration for rate limiting
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'smart_hrms',
        'TIMEOUT': 300,
    }
}

# Email - production backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@smarthrms.local')

# Static files - production
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['security_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps.accounts': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps.payroll': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Celery - production
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_ACKS_LATE = True

# Password validation - already strict in base, keep as-is
# AUTH_PASSWORD_VALIDATORS inherited from base settings

# Admin security
ADMIN_URL = os.getenv('ADMIN_URL', 'admin/')

# Secure proxy SSL header (if behind load balancer)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')