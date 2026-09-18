import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'django_apscheduler',
    # JOINIK apps
    'apps.core',
    'apps.accounts',
    'apps.devices',
    'apps.telemetry',
    'apps.alarms',
    'apps.ai_engine',
    'apps.analytics',
    'apps.notifications',
    'apps.audit',
    'apps.scheduler',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.LoginRequiredMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.global_alarm_counts',
                'apps.core.context_processors.joinik_context',
            ],
        },
    },
]

ASGI_APPLICATION = 'config.asgi.application'

# ── Databases ──────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
    },
    'thingsboard': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('TB_DB_NAME'),
        'USER': env('TB_DB_USER'),
        'PASSWORD': env('TB_DB_PASSWORD'),
        'HOST': '172.16.12.223', # env('TB_DB_HOST'),
        'PORT': env('TB_DB_PORT'),
        'OPTIONS': {'options': '-c default_transaction_read_only=on'},
    },
    'analysis_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'joinik_analysis',
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
    }
}

DATABASE_ROUTERS = ['apps.core.db_router.ThingsBoardRouter', 'apps.ai_engine.db_router.AnalysisRouter']

# ── Cache / Channels ────────────────────────────────────────────────────────
REDIS_URL = env('REDIS_URL', default='redis://127.0.0.1:6379/0')

# Use Redis for cache and channel layer (VM Redis at 100.78.208.60)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_URL]},
    }
}

# ── Celery (kept for future production use) ──────────────────────────────────
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = 'Asia/Dhaka'

# ── APScheduler ─────────────────────────────────────────────────────────────
APSCHEDULER_DAEMON = True
APSCHEDULER_RUN_NOW_TIMEOUT = 25  # seconds

# ── Auth ────────────────────────────────────────────────────────────────────
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/auth/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

# ── Static ──────────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# ── ThingsBoard ─────────────────────────────────────────────────────────────
TB_URL = 'http://172.16.12.223:8080' # env('TB_URL')
TB_ADMIN_EMAIL = env('TB_ADMIN_EMAIL')
TB_ADMIN_PASSWORD = env('TB_ADMIN_PASSWORD')
JOINIK_MODULE_01_TB_ID = env('JOINIK_MODULE_01_TB_ID')

# ── Authentication ────────────────────────────────────────────────────────
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/auth/login/'
LOGIN_URL = '/auth/login/'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

