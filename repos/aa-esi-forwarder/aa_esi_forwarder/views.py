"""Internal HTTP API: short-lived access token + optional ESI reverse proxy."""

from __future__ import annotations

import json
import logging
import os

import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from aa_esi_forwarder.auth import require_consumer_auth, resolve_token, user_agent

logger = logging.getLogger(__name__)

_ESI_ROOT = "https://esi.evetech.net/latest/"


@require_http_methods(["GET"])
def health_view(request):
    """Connection test for external consumers (no ESI call)."""
    denied, consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied

    token = resolve_token()
    return JsonResponse(
        {
            "status": "ok",
            "consumer_id": consumer_id,
            "default_token_configured": token is not None,
            "default_character": token.character_name if token else None,
            "default_token_id": token.pk if token else None,
        }
    )


@require_http_methods(["GET"])
def access_token_view(request):
    denied, consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied

    token_id = request.GET.get("token_id", "").strip()
    tid = int(token_id) if token_id.isdigit() else None
    token = resolve_token(token_id=tid)
    if token is None:
        return JsonResponse(
            {"error": "no_token", "detail": "No django-esi token matched request"},
            status=404,
        )

    try:
        access = token.valid_access_token()
    except Exception as exc:  # noqa: BLE001
        logger.exception("esi forwarder token refresh failed")
        return JsonResponse(
            {"error": "token_refresh_failed", "detail": str(exc)},
            status=502,
        )

    return JsonResponse(
        {
            "access_token": access,
            "character_id": token.character_id,
            "character_name": token.character_name,
            "token_id": token.pk,
            "scopes": [s.name for s in token.scopes.all()],
            "consumer_id": consumer_id,
        }
    )


@require_http_methods(["GET", "POST", "PUT", "DELETE", "HEAD"])
def esi_proxy_view(request, esi_path: str):
    """
    Forward request to ESI with a django-esi Bearer token.

    Example::
        GET /internal/esi-forwarder/v1/proxy/characters/123/assets/
        Header: X-Esi-Forwarder-Secret: …
    """
    denied, _consumer_id = require_consumer_auth(request)
    if denied is not None:
        return denied

    if ".." in esi_path or esi_path.startswith("/"):
        return JsonResponse({"error": "invalid_path"}, status=400)

    token_id = request.GET.get("token_id", "").strip()
    tid = int(token_id) if token_id.isdigit() else None
    token = resolve_token(token_id=tid)
    if token is None:
        return JsonResponse({"error": "no_token"}, status=404)

    try:
        access = token.valid_access_token()
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": "token_refresh_failed", "detail": str(exc)}, status=502)

    url = _ESI_ROOT + esi_path.lstrip("/")
    headers = {
        "Authorization": f"Bearer {access}",
        "Accept": request.headers.get("Accept", "application/json"),
        "User-Agent": user_agent(),
    }
    compat = os.environ.get("ESI_FORWARDER_COMPATIBILITY_DATE", "").strip()
    if compat:
        headers["X-Compatibility-Date"] = compat
    for hop in ("If-None-Match", "If-Modified-Since"):
        if hop in request.headers:
            headers[hop] = request.headers[hop]

    try:
        resp = requests.request(
            method=request.method,
            url=url,
            params=request.GET,
            data=request.body if request.method not in ("GET", "HEAD") else None,
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as exc:
        return JsonResponse({"error": "esi_upstream_failed", "detail": str(exc)}, status=502)

    out = HttpResponse(
        content=resp.content,
        status=resp.status_code,
        content_type=resp.headers.get("Content-Type", "application/json"),
    )
    for key in (
        "X-Pages",
        "X-Page",
        "X-Esi-Error-Limit-Remain",
        "X-Esi-Error-Limit-Reset",
        "ETag",
        "Last-Modified",
    ):
        if key in resp.headers:
            out[key] = resp.headers[key]
    return out
