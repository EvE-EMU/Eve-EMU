"""Consumer API keys, optional IP allowlist, django-esi token resolution."""

from __future__ import annotations

import ipaddress
import os
from typing import Any

from django.http import HttpRequest, HttpResponseForbidden

from esi.models import Token


def _legacy_secret() -> str:
    return os.environ.get("ESI_FORWARDER_INTERNAL_SECRET", "").strip()


def _api_keys() -> dict[str, str]:
    """
    Per-consumer secrets for external linking.

    Format: ``consumer_id:secret,other_id:othersecret`` or legacy single secret only.
    """
    out: dict[str, str] = {}
    raw = os.environ.get("ESI_FORWARDER_API_KEYS", "").strip()
    if raw:
        for part in raw.split(","):
            piece = part.strip()
            if ":" not in piece:
                continue
            cid, sec = piece.split(":", 1)
            cid, sec = cid.strip(), sec.strip()
            if cid and sec:
                out[cid] = sec
    legacy = _legacy_secret()
    if legacy and "default" not in out:
        out["default"] = legacy
    return out


def _allowed_networks() -> list[Any]:
    raw = os.environ.get("ESI_FORWARDER_ALLOWED_IPS", "").strip()
    if not raw:
        return []
    nets: list[ipaddress._BaseNetwork] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        try:
            nets.append(ipaddress.ip_network(piece, strict=False))
        except ValueError:
            continue
    return nets


def _client_ip(request: HttpRequest) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _ip_allowed(request: HttpRequest) -> bool:
    nets = _allowed_networks()
    if not nets:
        return True
    ip_raw = _client_ip(request)
    if not ip_raw:
        return False
    try:
        ip = ipaddress.ip_address(ip_raw)
    except ValueError:
        return False
    return any(ip in net for net in nets)


def _presented_secret(request: HttpRequest) -> str:
    header = (
        request.headers.get("X-Esi-Forwarder-Secret")
        or request.headers.get("X-Internal-Secret")
        or ""
    ).strip()
    if header:
        return header
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def authenticate_consumer(request: HttpRequest) -> tuple[HttpResponseForbidden | None, str | None]:
    keys = _api_keys()
    if not keys:
        return HttpResponseForbidden("forwarder disabled (no API keys configured)"), None

    if not _ip_allowed(request):
        return HttpResponseForbidden("client IP not allowed"), None

    presented = _presented_secret(request)
    if not presented:
        return HttpResponseForbidden("missing credentials"), None

    for consumer_id, secret in keys.items():
        if presented == secret:
            return None, consumer_id
    return HttpResponseForbidden("forbidden"), None


def require_consumer_auth(request: HttpRequest):
    """Return ``(error_response, consumer_id)`` — *consumer_id* set when allowed."""
    return authenticate_consumer(request)


def _required_scopes() -> list[str]:
    raw = os.environ.get("ESI_FORWARDER_REQUIRED_SCOPES", "").strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def resolve_token(*, token_id: int | None = None) -> Token | None:
    scopes = _required_scopes()
    try:
        if token_id is not None:
            token = Token.objects.get(pk=int(token_id))
        else:
            default_id = os.environ.get("ESI_FORWARDER_DEFAULT_TOKEN_ID", "").strip()
            if default_id:
                token = Token.objects.get(pk=int(default_id))
            else:
                character = (
                    os.environ.get("ESI_FORWARDER_DEFAULT_CHARACTER", "").strip()
                    or "Sevey"
                )
                qs = Token.objects.filter(character_name__iexact=character)
                if scopes:
                    qs = qs.require_scopes(scopes)
                token = qs.first()
    except (Token.DoesNotExist, ValueError):
        return None

    if token is None:
        return None

    if scopes:
        have = {s.name for s in token.scopes.all()}
        if not all(s in have for s in scopes):
            return None
    return token


def user_agent() -> str:
    return (
        os.environ.get("ESI_FORWARDER_USER_AGENT", "").strip()
        or "AA-ESI-Forwarder/1.0 (+https://github.com/eve-emu/aa-esi-forwarder)"
    )
