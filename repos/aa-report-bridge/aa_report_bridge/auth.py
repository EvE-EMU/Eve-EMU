"""API keys and optional IP allowlist (same pattern as aa-esi-forwarder)."""

from __future__ import annotations

import ipaddress
import os
from typing import Any

from django.http import HttpRequest, HttpResponseForbidden


def _legacy_secret() -> str:
    return os.environ.get("REPORT_BRIDGE_INTERNAL_SECRET", "").strip()


def _api_keys() -> dict[str, str]:
    out: dict[str, str] = {}
    raw = os.environ.get("REPORT_BRIDGE_API_KEYS", "").strip()
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
    raw = os.environ.get("REPORT_BRIDGE_ALLOWED_IPS", "").strip()
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
        request.headers.get("X-Report-Bridge-Secret")
        or request.headers.get("X-Esi-Forwarder-Secret")
        or ""
    ).strip()
    if header:
        return header
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def require_consumer_auth(request: HttpRequest):
    keys = _api_keys()
    if not keys:
        return HttpResponseForbidden("report bridge disabled (no API keys)"), None

    if not _ip_allowed(request):
        return HttpResponseForbidden("client IP not allowed"), None

    presented = _presented_secret(request)
    if not presented:
        return HttpResponseForbidden("missing credentials"), None

    for consumer_id, secret in keys.items():
        if presented == secret:
            return None, consumer_id
    return HttpResponseForbidden("forbidden"), None


def site_id() -> str:
    return os.environ.get("REPORT_BRIDGE_SITE_ID", "aa5").strip() or "aa5"
