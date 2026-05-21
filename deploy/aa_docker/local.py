# Docker / compose overrides for an `allianceauth start eve_auth` project tree.
# Copied over `eve_auth/settings/local.py` at image build time.
# Upstream template lives in the allianceauth submodule; keep this file aligned when bumping AA.

from __future__ import annotations

import os
from urllib.parse import urlparse

from celery.schedules import crontab

from .base import *  # noqa: F403

import sys as _sys

_aa_docker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _aa_docker_root not in _sys.path:
    _sys.path.insert(0, _aa_docker_root)

from esi_clients_compat import install_esi_clients_shim  # noqa: E402

install_esi_clients_shim()

ROOT_URLCONF = "eve_auth.urls"
WSGI_APPLICATION = "eve_auth.wsgi.application"

SECRET_KEY = os.environ.get("AA_DJANGO_SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "unsafe-dev-only-change-me"

SITE_URL = os.environ.get("AA_SITE_URL", "http://127.0.0.1:8080").rstrip("/")
SITE_NAME = os.environ.get("AA_SITE_NAME", "EVE-EMU Alliance Auth")

DEBUG = os.environ.get("AA_DEBUG", "0").strip().lower() in ("1", "true", "yes", "on")

_raw_hosts = os.environ.get("AA_ALLOWED_HOSTS", "*").strip()
if _raw_hosts == "*":
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

_host = urlparse(SITE_URL).hostname
if _host and _host not in ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_host)

# When auth is on auth.<DOMAIN_NAME> but AA_ALLOWED_HOSTS was not updated yet.
_domain = os.environ.get("DOMAIN_NAME", "").strip().lstrip(".")
if _domain and "*" not in ALLOWED_HOSTS:
    for _extra in (f"auth.{_domain}", _domain, f"www.{_domain}"):
        if _extra not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_extra)

# Docker service names (market-api → aa-web token bridge, health checks).
if "*" not in ALLOWED_HOSTS:
    for _internal in ("aa-web", "market-api", "localhost", "127.0.0.1"):
        if _internal not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_internal)

CSRF_TRUSTED_ORIGINS = []
_extra_csrf = os.environ.get("AA_CSRF_TRUSTED_ORIGINS", "").strip()
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS.extend(o.strip() for o in _extra_csrf.split(",") if o.strip())
if SITE_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.insert(0, SITE_URL)

_site = urlparse(SITE_URL)
if _site.scheme == "http":
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

STATIC_ROOT = os.environ.get("AA_STATIC_ROOT", os.path.join(BASE_DIR, "staticfiles"))

# Optional deployment branding (login / menu logo via templates/bundles/image-auth-logo.html).
_aa_static = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "deploy", "aa_docker", "static")
)
if os.path.isdir(_aa_static):
    _sfd = list(globals().get("STATICFILES_DIRS", []))
    if _aa_static not in _sfd:
        STATICFILES_DIRS = [*_sfd, _aa_static]


def _redis_with_db(url: str, db: int) -> str:
    url = url.strip().rstrip("/")
    scheme_sep = url.find("://")
    if scheme_sep == -1:
        return f"{url}/{db}"
    path_start = url.find("/", scheme_sep + 3)
    if path_start == -1:
        return f"{url}/{db}"
    tail = url[path_start + 1 :]
    if tail.isdigit():
        return f"{url[:path_start]}/{db}"
    return f"{url}/{db}"


_broker = os.environ.get("REDIS_URL", "redis://redis:6379/0").strip()
BROKER_URL = _broker
CELERY_BROKER_URL = _broker
CELERY_RESULT_BACKEND = _broker

_cache_url = os.environ.get("AA_REDIS_CACHE_URL", "").strip() or _redis_with_db(_broker, 1)
CACHES["default"]["LOCATION"] = _cache_url

DATABASES["default"] = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("POSTGRES_DB_AA", "eve_emu_aa"),
    "USER": os.environ.get("POSTGRES_USER", "eve"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "eve"),
    "HOST": os.environ.get("POSTGRES_HOST", "db"),
    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
}

# Must match your CCP developer app callback URL exactly (django-esi: /sso/callback).
# Alliance Auth upstream uses no trailing slash; normalize so .env typos do not break SSO.
_esi_callback = os.environ.get("ESI_CALLBACK_URL", "").strip().rstrip("/")
ESI_SSO_CALLBACK_URL = _esi_callback or f"{SITE_URL}/sso/callback"
ESI_SSO_CLIENT_ID = os.environ.get("AA_ESI_SSO_CLIENT_ID", os.environ.get("ESI_CLIENT_ID", ""))
ESI_SSO_CLIENT_SECRET = os.environ.get("AA_ESI_SSO_CLIENT_SECRET", os.environ.get("ESI_CLIENT_SECRET", ""))
ESI_USER_CONTACT_EMAIL = os.environ.get("AA_ESI_USER_CONTACT_EMAIL", os.environ.get("ESI_USER_CONTACT_EMAIL", ""))
if not str(ESI_USER_CONTACT_EMAIL).strip():
    # Alliance Auth system checks require a non-empty maintainer email (replace in production).
    ESI_USER_CONTACT_EMAIL = "eve-emu-placeholder@example.com"

if os.environ.get("AA_SKIP_EMAIL_VERIFY", "0").strip().lower() in ("1", "true", "yes", "on"):
    REGISTRATION_VERIFY_EMAIL = False

if "whitenoise.middleware.WhiteNoiseMiddleware" not in MIDDLEWARE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

INSTALLED_APPS += [
    "industry_suite.apps.IndustrySuiteConfig",
    "buyback_v2.apps.BuybackV2Config",
    "corp_orders.apps.CorpOrdersConfig",
    "standing_fleet_tracker",
    "sde_wiki.apps.SdeWikiConfig",
    "market_bridge.apps.MarketBridgeConfig",
]

# Community apps: deploy/aa_docker/extensions/ + requirements-aa-extensions.txt
import sys

_aa_docker = os.environ.get("AA_DOCKER_EXTENSIONS_ROOT", "").strip()
if not _aa_docker or not os.path.isdir(_aa_docker):
    _aa_docker = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "deploy", "aa_docker")
    )
if _aa_docker not in sys.path:
    sys.path.insert(0, _aa_docker)

from extensions import configure_extensions  # noqa: E402

_configure = dict(globals())
configure_extensions(_configure)
globals().update(_configure)

LOGGING["loggers"]["django"]["level"] = "INFO"
LOGGING["loggers"]["allianceauth"]["level"] = "INFO"
LOGGING["loggers"]["esi"]["level"] = "INFO"
