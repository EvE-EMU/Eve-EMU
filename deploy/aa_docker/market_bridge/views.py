"""Serve a fresh ESI access token from Alliance Auth django-esi (corp tools tokens)."""

from __future__ import annotations

import os

from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from esi.models import Token

_STRUCTURE_MARKETS = "esi-markets.structure_markets.v1"


@require_GET
def access_token_view(request):
    secret = os.environ.get("MARKET_INTERNAL_SECRET", "").strip()
    if not secret or request.headers.get("X-Market-Internal-Secret") != secret:
        return HttpResponseForbidden("forbidden")

    token_id = os.environ.get("MARKET_ESI_TOKEN_ID", "").strip()
    character = os.environ.get("MARKET_ESI_CHARACTER_NAME", "Sevey").strip() or "Sevey"

    try:
        if token_id:
            token = Token.objects.get(pk=int(token_id))
        else:
            token = (
                Token.objects.filter(character_name__iexact=character)
                .require_scopes([_STRUCTURE_MARKETS])
                .first()
            )
    except (Token.DoesNotExist, ValueError):
        token = None

    if token is None:
        return JsonResponse(
            {"error": "no_token", "detail": f"No token with {_STRUCTURE_MARKETS}"},
            status=404,
        )

    scope_names = {s.name for s in token.scopes.all()}
    if _STRUCTURE_MARKETS not in scope_names:
        return JsonResponse(
            {"error": "missing_scope", "detail": _STRUCTURE_MARKETS},
            status=404,
        )

    try:
        access = token.valid_access_token()
    except Exception as exc:  # noqa: BLE001 — return message to market-api logs only
        return JsonResponse({"error": "token_refresh_failed", "detail": str(exc)}, status=502)

    return JsonResponse(
        {
            "access_token": access,
            "character_id": token.character_id,
            "character_name": token.character_name,
            "token_id": token.pk,
        }
    )
