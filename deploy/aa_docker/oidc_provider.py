"""Alliance Auth OIDC provider (for YouTrack, Grafana, etc.)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

OIDC_APPS: tuple[str, ...] = ("oauth2_provider", "allianceauth_oidc")


def oidc_enabled() -> bool:
    return os.environ.get("AA_OIDC_ENABLED", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def oidc_rsa_key_path() -> Path:
    raw = os.environ.get("AA_OIDC_RSA_KEY_PATH", "/app/site/oidc/oidc_rsa.pem").strip()
    return Path(raw)


def ensure_oidc_rsa_key() -> Path | None:
    """Create an RSA private key PEM if missing (for django-oauth-toolkit OIDC)."""
    if not oidc_enabled():
        return None

    key_path = oidc_rsa_key_path()
    if key_path.is_file():
        return key_path

    inline = os.environ.get("AA_OIDC_RSA_PRIVATE_KEY", "").strip()
    if inline:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(inline if inline.endswith("\n") else f"{inline}\n", encoding="utf-8")
        key_path.chmod(0o600)
        return key_path

    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError:
        logger.warning("oidc_provider: cryptography not installed; cannot generate RSA key")
        return None

    key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.write_bytes(pem)
    key_path.chmod(0o600)
    logger.info("oidc_provider: generated OIDC RSA key at %s", key_path)
    return key_path


def ensure_oidc_app_algorithms() -> int:
    """OIDC id_tokens require RS256; allianceauth_oidc admin omits algorithm by default."""
    if not oidc_enabled():
        return 0

    try:
        import django

        django.setup()
        from allianceauth_oidc.models import AllianceAuthApplication
        from oauth2_provider.models import AbstractApplication
    except Exception as exc:
        logger.debug("oidc_provider: algorithm repair skipped (%s)", exc)
        return 0

    updated = AllianceAuthApplication.objects.filter(algorithm="").update(
        algorithm=AbstractApplication.RS256_ALGORITHM
    )
    if updated:
        logger.info("oidc_provider: set RS256 on %s OIDC application(s)", updated)
    return updated


def apply_oidc_settings(settings: dict) -> None:
    if not oidc_enabled():
        return

    key_path = ensure_oidc_rsa_key()
    key_text = os.environ.get("AA_OIDC_RSA_PRIVATE_KEY", "").strip()
    if not key_text and key_path and key_path.is_file():
        key_text = key_path.read_text(encoding="utf-8")
    if not key_text:
        logger.warning("oidc_provider: no OIDC RSA key; OIDC endpoints will not work")
        return

    site_url = str(settings.get("SITE_URL", "")).rstrip("/")
    settings["OAUTH2_PROVIDER_APPLICATION_MODEL"] = (
        "allianceauth_oidc.AllianceAuthApplication"
    )
    oidc_issuer = os.environ.get("AA_OIDC_ISSUER", "").strip() or (
        f"{site_url}/o/" if site_url else ""
    )
    settings["OAUTH2_PROVIDER"] = {
        "OIDC_ENABLED": True,
        "OIDC_ISS_ENDPOINT": oidc_issuer,
        "OIDC_RSA_PRIVATE_KEY": key_text,
        "OAUTH2_VALIDATOR_CLASS": (
            "allianceauth_oidc.auth_provider.AllianceAuthOAuth2Validator"
        ),
        "SCOPES": {
            "openid": "OpenID Connect",
            "email": "Registered email",
            "profile": "Main character name and Auth groups claim",
            # YouTrack / Hub may request these even when groups come from profile claim.
            "groups": "Group membership claim",
            "offline_access": "Refresh token",
            "address": "Address claim",
            "phone": "Phone claim",
        },
        "PKCE_REQUIRED": os.environ.get("AA_OIDC_PKCE_REQUIRED", "0").strip().lower()
        in ("1", "true", "yes", "on"),
        "APPLICATION_ADMIN_CLASS": "allianceauth_oidc.admin.ApplicationAdmin",
        "ACCESS_TOKEN_EXPIRE_SECONDS": int(
            os.environ.get("AA_OIDC_ACCESS_TOKEN_SECONDS", "3600")
        ),
        "REFRESH_TOKEN_EXPIRE_SECONDS": int(
            os.environ.get("AA_OIDC_REFRESH_TOKEN_SECONDS", str(24 * 60 * 60))
        ),
        "ROTATE_REFRESH_TOKEN": True,
    }
    if site_url:
        settings.setdefault("AA_OIDC_ISSUER", f"{site_url}/o/")

    allowed = os.environ.get("AA_CSRF_TRUSTED_ORIGINS", "").strip()
    pm_url = os.environ.get("YOUTRACK_URL", "").strip()
    if pm_url and pm_url not in settings.get("CSRF_TRUSTED_ORIGINS", []):
        csrf = list(settings.get("CSRF_TRUSTED_ORIGINS", []))
        if pm_url not in csrf:
            csrf.append(pm_url)
            settings["CSRF_TRUSTED_ORIGINS"] = csrf

    logger.info("oidc_provider: OIDC enabled (issuer %s/o/)", site_url or "?")


def patch_oidc_urls() -> None:
    if not oidc_enabled():
        return

    try:
        from django.urls import include, path

        import eve_auth.urls as root_urls
    except Exception as exc:
        logger.debug("oidc_provider: url patch skipped (%s)", exc)
        return

    for entry in root_urls.urlpatterns:
        namespace = getattr(entry, "namespace", None)
        if namespace == "oauth2_provider":
            return
        app_name = getattr(entry, "app_name", None)
        if app_name == "oauth2_provider":
            return

    root_urls.urlpatterns.insert(
        0,
        path("o/", include("allianceauth_oidc.urls", namespace="oauth2_provider")),
    )
    logger.info("oidc_provider: mounted /o/ OIDC routes")
