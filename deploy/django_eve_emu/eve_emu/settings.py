"""Django settings for EvE-EMU stack (industry_suite + future Alliance Auth merge).

Secrets: keep in root ``.env`` (see repository ``.env.example``). Operational constants
(tax %, logistics fees) can later move to DB via admin — env values here are defaults.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# industry_suite lives at repository root in Docker: /app/industry_suite ; site at /app/site
_SITE_ROOT = Path(__file__).resolve().parent.parent
_APP_ROOT = _SITE_ROOT.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

SECRET_KEY = os.environ.get("AA_DJANGO_SECRET_KEY", "unsafe-dev-key-change-me")

DEBUG = os.environ.get("AA_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("AA_ALLOWED_HOSTS", "*").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "industry_suite.apps.IndustrySuiteConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "eve_emu.urls"
WSGI_APPLICATION = "eve_emu.wsgi.application"

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

_db_name = os.environ.get("POSTGRES_DB_AA", "eve_emu_aa")
_db_user = os.environ.get("POSTGRES_USER", "eve")
_db_pass = os.environ.get("POSTGRES_PASSWORD", "eve")
_db_host = os.environ.get("POSTGRES_HOST", "db")
_db_port = os.environ.get("POSTGRES_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _db_name,
        "USER": _db_user,
        "PASSWORD": _db_pass,
        "HOST": _db_host,
        "PORT": _db_port,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = _SITE_ROOT / "staticfiles"
# Serve admin static assets under Gunicorn without a separate nginx static mount.
WHITENOISE_USE_FINDERS = True

# --- Celery ---
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TIMEZONE = TIME_ZONE
# Populated when you add periodic tasks (used by ``aa-beat``).
CELERY_BEAT_SCHEDULE: dict[str, object] = {}

# --- Industrial defaults (override in DB later via admin / custom models) ---
MINING_TAX_RATE = float(os.environ.get("MINING_TAX_RATE", "0") or "0")
LOGISTICS_COST_PER_M3 = float(os.environ.get("LOGISTICS_COST_PER_M3", "0") or "0")
BPC_DEPOSIT_REQUIRED = float(os.environ.get("BPC_DEPOSIT_REQUIRED", "0") or "0")
