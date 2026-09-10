"""Fleet pings & shared timers — GET / POST /penguin/pings.

GET  → every non-expired ping for the caller's corp id + alliance id, newest
       first (limit 100).
POST → add a ping. A signed-in user may post to their own corp or alliance.
       A relay forwarder (Discord / Jabber bridge) may post to any corp /
       alliance id by presenting `X-Penguin-Relay-Secret` == env
       PENGUIN_RELAY_SECRET.

Body: {scope: "corp"|"alliance", kind, text, system?, at_unix?, ttl_hours?,
       key? (relay only)}.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from penguin_bridge.models import PenguinPing
from penguin_bridge.views import _main_character_id, _session_user

logger = logging.getLogger("penguin_bridge")

_KINDS = {"fc", "formup", "doctrine", "undock", "timer", "misc"}


def _corp_alliance(user):
    """(corp_id, alliance_id) for the user's main, or (0, 0)."""
    cid = _main_character_id(user)
    if not cid:
        return 0, 0
    from allianceauth.authentication.models import CharacterOwnership

    own = (
        CharacterOwnership.objects.filter(user=user, character__character_id=cid)
        .select_related("character")
        .first()
    )
    if own is None:
        return 0, 0
    c = own.character
    return int(c.corporation_id or 0), int(c.alliance_id or 0)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def pings(request):
    relay_secret = os.environ.get("PENGUIN_RELAY_SECRET", "")
    is_relay = bool(relay_secret) and request.headers.get("X-Penguin-Relay-Secret") == relay_secret

    user = None
    if not is_relay:
        user, _ = _session_user(request)
        if user is None:
            return JsonResponse({"error": "invalid_session"}, status=401)

    now = timezone.now()

    if request.method == "GET":
        PenguinPing.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
        if is_relay:
            return JsonResponse({"pings": []})
        corp_id, alliance_id = _corp_alliance(user)
        rows = PenguinPing.objects.filter(expires_at__gte=now).filter(
            models_q(corp_id, alliance_id)
        )[:100]
        return JsonResponse({"pings": [r.as_dict() for r in rows]})

    # POST
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    scope = body.get("scope", "corp")
    if scope not in ("corp", "alliance"):
        return JsonResponse({"error": "bad_scope"}, status=400)
    kind = body.get("kind", "misc")
    if kind not in _KINDS:
        kind = "misc"
    text = (body.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "empty_text"}, status=400)

    if is_relay:
        key = int(body.get("key") or 0)
        author = (body.get("author") or "relay")[:100]
        if not key:
            return JsonResponse({"error": "relay_needs_key"}, status=400)
    else:
        corp_id, alliance_id = _corp_alliance(user)
        key = corp_id if scope == "corp" else alliance_id
        if not key:
            return JsonResponse({"error": f"not_in_{scope}"}, status=403)
        author = (user.username or "")[:100]

    ttl_hours = max(1, min(int(body.get("ttl_hours") or 12), 168))
    ping = PenguinPing.objects.create(
        scope=scope,
        key=key,
        kind=kind,
        text=text[:4000],
        system=(body.get("system") or "")[:64],
        at_unix=int(body.get("at_unix") or 0),
        author=author,
        expires_at=now + timedelta(hours=ttl_hours),
    )
    return JsonResponse(ping.as_dict(), status=201)


def models_q(corp_id: int, alliance_id: int):
    from django.db.models import Q

    q = Q(pk__in=[])
    if corp_id:
        q |= Q(scope="corp", key=corp_id)
    if alliance_id:
        q |= Q(scope="alliance", key=alliance_id)
    return q
