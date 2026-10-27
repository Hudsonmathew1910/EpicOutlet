"""
Django settings for epicoutlet project.

All secrets and environment-specific values come from environment variables
(loaded from .env in development). See .env.example for the full list.
"""

from pathlib import Path
import os
import sys
import cloudinary
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]


TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

# SECURITY WARNING: keep the secret key used in production secret!
DEBUG = env_bool('DJANGO_DEBUG', False)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG and not TESTING:
        raise RuntimeError('DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.')
    SECRET_KEY = 'dev-insecure-secret-key-change-me'

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', '127.0.0.1,localhost')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

# Render
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

SITE_NAME = 'EpicOutlet'

# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
    'shop.apps.ShopConfig',
    'api.apps.ApiConfig',
    'cloudinary',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'shop.middleware.StreamingSafeGZipMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'epicoutlet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.store',
            ],
        },
    },
]

WSGI_APPLICATION = 'epicoutlet.wsgi.application'


# Database
# Uses DATABASE_URL (e.g. Supabase Postgres) when set, otherwise local SQLite.
# Tests always run on SQLite so they never touch the real database.
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

if DATABASE_URL and not TESTING:
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            ssl_require=DATABASE_URL.startswith('postgres'),  # Supabase requires SSL
        )
    }
    if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
        # Shared connection pool: opening a TLS connection to a remote DB takes seconds,
        # so connections are reused across requests and threads.
        DATABASES['default']['OPTIONS']['pool'] = {
            'min_size': 1,
            'max_size': int(os.environ.get('DB_POOL_MAX', '4')),
            'timeout': 15,
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Cache: used for catalog lookups and rate limiting (per process).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'epicoutlet',
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': (
            'django.contrib.staticfiles.storage.StaticFilesStorage'
            if DEBUG or TESTING
            else 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        ),
    },
}

# Cloudinary (product and category images)
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    api_key=os.environ.get('CLOUDINARY_API_KEY', ''),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', ''),
    secure=True,
)

# Email (password reset, order confirmations). Console backend unless SMTP is configured.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'EpicOutlet <no-reply@epicoutlet.local>')

# Payments (Razorpay). In demo mode, checkout pauses at the payment step.
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
PAYMENT_DEMO_MODE = env_bool('PAYMENT_DEMO_MODE', True)

# Order pricing (whole rupees)
FREE_SHIPPING_THRESHOLD = int(os.environ.get('FREE_SHIPPING_THRESHOLD', '999'))
SHIPPING_FEE = int(os.environ.get('SHIPPING_FEE', '49'))
MAX_QTY_PER_ITEM = 10
DELIVERY_MIN_DAYS = int(os.environ.get('DELIVERY_MIN_DAYS', '3'))
DELIVERY_MAX_DAYS = int(os.environ.get('DELIVERY_MAX_DAYS', '6'))

# AI shop bot. HEROS_API is the primary provider (OpenAI-compatible); Groq is the fallback.
HEROS_API_KEY = os.environ.get('HEROS_API_KEY') or os.environ.get('HEROS_API', '')
HEROS_BASE_URL = os.environ.get('HEROS_BASE_URL', '')
HEROS_MODEL = os.environ.get('HEROS_MODEL', '')
GROQ_API_KEY = os.environ.get('Groq_API_KEY_1', '')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'openai/gpt-oss-120b')
CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get('CHAT_RATE_LIMIT_PER_MINUTE', '15'))

# Security hardening for production
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
if not DEBUG and not TESTING:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '%(asctime)s %(levelname)s [%(name)s] %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'), 'propagate': False},
        'shop': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'api': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

if TESTING:
    # Tests never call real AI providers.
    HEROS_API_KEY = GROQ_API_KEY = ''
    for name in ('django', 'shop', 'api'):
        LOGGING['loggers'][name]['level'] = 'CRITICAL'

# Admin theme
JAZZMIN_SETTINGS = {
    'site_title': 'EpicOutlet Admin',
    'site_header': 'EpicOutlet',
    'site_brand': 'EpicOutlet',
    'site_logo': 'images/EP2.png',
    'login_logo': 'images/EP2.png',
    'site_icon': 'images/EP2.png',
    'welcome_sign': 'Welcome to the EpicOutlet control room',
    'copyright': 'EpicOutlet',
    'search_model': ['shop.Product', 'shop.Order', 'auth.User'],
    'user_avatar': None,
    'topmenu_links': [
        {'name': 'Dashboard', 'url': 'admin_dashboard'},
        {'name': 'View store', 'url': 'home', 'new_window': True},
        {'model': 'shop.Order'},
    ],
    'show_sidebar': True,
    'navigation_expanded': True,
    'order_with_respect_to': ['shop', 'shop.Order', 'shop.Product', 'shop.Catagory', 'auth'],
    'custom_links': {
        'shop': [{'name': 'Sales dashboard', 'url': 'admin_dashboard', 'icon': 'fas fa-chart-line'}],
    },
    'icons': {
        'auth': 'fas fa-users-cog',
        'auth.user': 'fas fa-user',
        'auth.Group': 'fas fa-users',
        'shop.Catagory': 'fas fa-layer-group',
        'shop.Product': 'fas fa-box-open',
        'shop.Order': 'fas fa-receipt',
        'shop.cart': 'fas fa-shopping-cart',
        'shop.fav': 'fas fa-heart',
    },
    'default_icon_parents': 'fas fa-folder',
    'default_icon_children': 'fas fa-circle',
    'related_modal_active': True,
    'changeform_format': 'horizontal_tabs',
    'show_ui_builder': False,
}

JAZZMIN_UI_TWEAKS = {
    'theme': 'flatly',
    'dark_mode_theme': 'darkly',
    'navbar': 'navbar-dark navbar-primary',
    'sidebar': 'sidebar-dark-primary',
    'brand_colour': 'navbar-primary',
    'accent': 'accent-primary',
    'navbar_small_text': False,
    'sidebar_nav_flat_style': True,
    'button_classes': {
        'primary': 'btn-primary',
        'secondary': 'btn-outline-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
