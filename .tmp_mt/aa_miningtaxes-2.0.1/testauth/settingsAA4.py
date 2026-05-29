# flake8: noqa
import os

from celery.schedules import crontab

from django.contrib import messages

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)
SITE_URL = "http://localhost:8000"
CSRF_TRUSTED_ORIGINS = [SITE_URL]
ESI_USER_CONTACT_EMAIL = "devnull@example.com"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_celery_beat",
    "django_celery_results",
    "bootstrapform",
    "sortedm2m",
    "esi",
    "eve_sde",
    "allianceauth",
    "allianceauth.authentication",
    "allianceauth.services",
    "allianceauth.eveonline",
    "allianceauth.groupmanagement",
    "allianceauth.notifications",
    "allianceauth.thirdparty.navhelper",
    "miningtaxes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
]

ROOT_URLCONF = "testauth.urls"
WSGI_APPLICATION = "testauth.wsgi.application"

SECRET_KEY = "testauth-aa4-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["*"]
SITE_NAME = "testauth"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = []
LOCALE_PATHS = (os.path.join(BASE_DIR, "locale/"),)
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
SILENCED_SYSTEM_CHECKS = ["allianceauth.checks.B003", "allianceauth.checks.B004"]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(PROJECT_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "allianceauth.context_processors.auth_settings",
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    "allianceauth.authentication.backends.StateBackend",
    "django.contrib.auth.backends.ModelBackend",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(os.path.join(BASE_DIR, "alliance_auth.sqlite3")),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/15",
        "OPTIONS": {
            "IGNORE_EXCEPTIONS": True,
        },
    }
}

MESSAGE_TAGS = {messages.ERROR: "danger"}

LOGIN_URL = "auth_login_user"
LOGIN_REDIRECT_URL = "authentication:dashboard"
LOGOUT_REDIRECT_URL = "authentication:dashboard"
LOGIN_TOKEN_SCOPES = ["publicData"]
ACCOUNT_ACTIVATION_DAYS = 1

ESI_API_URL = "https://esi.evetech.net/"
ESI_SSO_CLIENT_ID = "dummy"
ESI_SSO_CLIENT_SECRET = "dummy"
ESI_SSO_CALLBACK_URL = "http://localhost:8000"

REGISTRATION_VERIFY_EMAIL = False
EMAIL_HOST = ""
EMAIL_PORT = 587
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = ""

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "django-db"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers.DatabaseScheduler"
broker_transport_options = {
    "priority_steps": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "queue_order_strategy": "priority",
}
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "priority_steps": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "queue_order_strategy": "priority",
}
broker_connection_retry_on_startup = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "esi_cleanup_callbackredirect": {
        "task": "esi.tasks.cleanup_callbackredirect",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "esi_cleanup_token": {
        "task": "esi.tasks.cleanup_token",
        "schedule": crontab(minute=0, hour=0),
    },
    "run_model_update": {
        "task": "allianceauth.eveonline.tasks.run_model_update",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "check_all_character_ownership": {
        "task": "allianceauth.authentication.tasks.check_all_character_ownership",
        "schedule": crontab(minute=0, hour="*/4"),
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            "datefmt": "%d/%b/%Y %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "level": "CRITICAL",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "allianceauth": {"handlers": ["console"], "level": "DEBUG"},
        "django": {"handlers": ["console"], "level": "ERROR"},
        "esi": {"handlers": ["console"], "level": "DEBUG"},
    },
}
