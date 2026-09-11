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
INDY_HUB_SITE_URL = os.environ.get("INDY_HUB_SITE_URL", SITE_URL).rstrip("/")

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
    for _extra in (f"auth.{_domain}", f"pm.{_domain}", _domain, f"www.{_domain}"):
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

_cookie_domain = os.environ.get("AA_SESSION_COOKIE_DOMAIN", "").strip()
if not _cookie_domain and _domain:
    _cookie_domain = f".{_domain.lstrip('.')}"
if _cookie_domain:
    SESSION_COOKIE_DOMAIN = _cookie_domain
    CSRF_COOKIE_DOMAIN = _cookie_domain

# Re-save session on each request so a bridge visit re-issues Domain=.eve-emu.com cookies.
# Use Redis-only sessions so CorpTools/Indy Hub API fan-out does not UPDATE django_session
# in Postgres on every XHR (cached_db would write Redis + PG each time).
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_SAVE_EVERY_REQUEST = True

if _domain:
    _public_origin = f"https://{_domain.lstrip('.')}"
    if _public_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_public_origin)

# Caddy terminates TLS and forwards X-Forwarded-Proto. Without this, OIDC discovery
# advertises http:// endpoints; clients POST to http, get a 308 with an empty body,
# and fail token exchange with a JSON parse error.
if os.environ.get("AA_BEHIND_PROXY", "1").strip().lower() in ("1", "true", "yes", "on"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

STATIC_ROOT = os.environ.get("AA_STATIC_ROOT", os.path.join(BASE_DIR, "staticfiles"))
MEDIA_ROOT = os.environ.get("AA_MEDIA_ROOT", os.path.join(BASE_DIR, "media"))
MEDIA_URL = os.environ.get("AA_MEDIA_URL", "/content/uploads/")

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
    # Reuse connections across requests (gunicorn workers + Celery). Default 0 opens a
    # new TCP/auth handshake to Postgres on every request — brutal for CorpTools SPA loads.
    "CONN_MAX_AGE": int(os.environ.get("AA_DB_CONN_MAX_AGE", "600")),
    "CONN_HEALTH_CHECKS": True,
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

# Duplicate csrftoken cookies (host-only + Domain=.eve-emu.com) break Craft AJAX CSRF.
# Prefer the cookie that matches X-CSRFToken / csrfmiddlewaretoken before Django checks.
_csrf_mw = "django.middleware.csrf.CsrfViewMiddleware"
_csrf_fix_mw = "csrf_cookie_cleanup.PreferMatchingCsrfCookieMiddleware"
if _csrf_fix_mw not in MIDDLEWARE:
    try:
        _csrf_idx = MIDDLEWARE.index(_csrf_mw)
    except ValueError:
        MIDDLEWARE.append(_csrf_fix_mw)
    else:
        MIDDLEWARE.insert(_csrf_idx, _csrf_fix_mw)

import importlib

_LOCAL_APPS = [
    "industry_suite",
    "sde_wiki.apps.SdeWikiConfig",
    "buyback_v2.apps.BuybackV2Config",
    "market_bridge.apps.MarketBridgeConfig",
    "freight_bridge.apps.FreightBridgeConfig",
    "penguin_bridge.apps.PenguinBridgeConfig",
    "moon_rental_bridge.apps.MoonRentalBridgeConfig",
    "mfg_projects.apps.MfgProjectsConfig",
    "emu_pi.apps.EmuPiConfig",
    "discord_lookup.apps.DiscordLookupConfig",
    "corptools_asset_export.apps.CorptoolsAssetExportConfig",
    "audit_comms_hub.apps.AuditCommsHubConfig",
    "auth_assets_report.apps.AuthAssetsReportConfig",
    "industry_jobs_report.apps.IndustryJobsReportConfig",
    "false_gods_audit.apps.FalseGodsAuditConfig",
    "logistics_group.apps.LogisticsGroupConfig",
    "marketing_mail.apps.MarketingMailConfig",
    "doctrine_contract_manager.apps.DoctrineContractManagerConfig",
    "winter_coalition_report.apps.WinterCoalitionReportConfig",
    "ffr.apps.FfrConfig",
    "carbon_bridge.apps.CarbonBridgeConfig",
    "permissions_overview.apps.PermissionsOverviewConfig",
    "package_monitor_ops.apps.PackageMonitorOpsConfig",
    "rorqual_status.apps.RorqualStatusConfig",
    "krab_schedule.apps.KrabScheduleConfig",
    "jumpplanner_blues.apps.JumpplannerBluesConfig",
    "stream_watch.apps.StreamWatchConfig",
    "zomboid_service.apps.ZomboidServiceConfig",
]


def _local_app_importable(entry: str) -> bool:
    root = entry.split(".apps.", 1)[0] if ".apps." in entry else entry.split(".", 1)[0]
    try:
        importlib.import_module(root)
        return True
    except ModuleNotFoundError:
        return False


INSTALLED_APPS += [entry for entry in _LOCAL_APPS if _local_app_importable(entry)]

# EVE-Penguin Discord → ping relay cog (aa-discordbot). Harmless if the bot
# profile isn't running; needs PENGUIN_RELAY_SECRET set + channel mappings in
# the admin (penguin_bridge → Penguin ping channels). We can't import
# aadiscordbot.app_settings here (settings not built yet), so restate the
# upstream default cog list and append ours.
DISCORD_BOT_COGS = [
    "aadiscordbot.cogs.about",
    "aadiscordbot.cogs.admin",
    "aadiscordbot.cogs.members",
    "aadiscordbot.cogs.timers",
    "aadiscordbot.cogs.auth",
    "aadiscordbot.cogs.sov",
    "aadiscordbot.cogs.time",
    "aadiscordbot.cogs.eastereggs",
    "aadiscordbot.cogs.remind",
    "aadiscordbot.cogs.reaction_roles",
    "aadiscordbot.cogs.services",
    "aadiscordbot.cogs.price_check",
    "aadiscordbot.cogs.eightball",
    "aadiscordbot.cogs.welcomegoodbye",
    "aadiscordbot.cogs.models",
    "aadiscordbot.cogs.quote",
    "aadiscordbot.cogs.honeypot",
    "penguin_bridge.discord_relay",
]

# Upstream AA permissions audit (permission → users/groups drill-down).
if "allianceauth.permissions_tool" not in INSTALLED_APPS:
    INSTALLED_APPS.append("allianceauth.permissions_tool")

# Built-in HR Applications (recruitment questionnaires / review).
# https://allianceauth.readthedocs.io/en/latest/features/apps/hrapplications.html
if "allianceauth.hrapplications" not in INSTALLED_APPS:
    INSTALLED_APPS.append("allianceauth.hrapplications")

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

# aa-discordbot admin slash commands (e.g. /lookup, /altcorp) require channel allowlist.
_raw_aa_admin_ch = os.environ.get("AA_ADMIN_DISCORD_BOT_CHANNELS", "").strip()
if _raw_aa_admin_ch:
    ADMIN_DISCORD_BOT_CHANNELS = [
        int(x.strip()) for x in _raw_aa_admin_ch.split(",") if x.strip().isdigit()
    ]
else:
    # HR / officer channel — aa-discordbot /lookup is blocked without this.
    ADMIN_DISCORD_BOT_CHANNELS = [1460686353237803244]

LOGGING["loggers"]["django"]["level"] = "INFO"
LOGGING["loggers"]["allianceauth"]["level"] = "INFO"
LOGGING["loggers"]["esi"]["level"] = "INFO"
