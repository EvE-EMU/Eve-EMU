"""Shared wormhole chain — GET / PUT /penguin/wh.

The whole chain is one JSON blob per (scope, key):
  * personal — key = the caller's AA user pk (always allowed)
  * corp     — key = the caller's main character's corp id
  * alliance — key = the caller's main character's alliance id

GET returns {data, rev, updated_by, updated_at}. PUT takes {scope, data,
base_rev}: if base_rev == the stored rev the blob is replaced and rev bumped;
otherwise 409 with the current {data, rev} so the client can re-merge and retry.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from penguin_bridge.models import PenguinWhMap
from penguin_bridge.views import _main_character_id, _session_user

logger = logging.getLogger("penguin_bridge")

_SCOPES = {"personal", "corp", "alliance"}


def _key_for(user, scope: str) -> int | None:
    if scope == "personal":
        return int(user.pk)
    cid = _main_character_id(user)
    if not cid:
        return None
    from allianceauth.authentication.models import CharacterOwnership

    own = (
        CharacterOwnership.objects.filter(user=user, character__character_id=cid)
        .select_related("character")
        .first()
    )
    if own is None:
        return None
    c = own.character
    if scope == "corp":
        return int(c.corporation_id or 0) or None
    return int(c.alliance_id or 0) or None


@csrf_exempt
@require_http_methods(["GET", "PUT", "POST"])
def wh(request):
    user, _ = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)

    if request.method == "GET":
        scope = request.GET.get("scope", "personal")
        if scope not in _SCOPES:
            return JsonResponse({"error": "bad_scope"}, status=400)
        key = _key_for(user, scope)
        if key is None:
            return JsonResponse({"error": f"not_in_{scope}"}, status=403)
        row = PenguinWhMap.objects.filter(scope=scope, key=key).first()
        if row is None:
            return JsonResponse(
                {"scope": scope, "key": key, "data": {}, "rev": 0, "updated_by": "", "updated_at": ""}
            )
        return JsonResponse(row.as_dict())

    # PUT / POST — replace the blob
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    scope = body.get("scope", "personal")
    if scope not in _SCOPES:
        return JsonResponse({"error": "bad_scope"}, status=400)
    key = _key_for(user, scope)
    if key is None:
        return JsonResponse({"error": f"not_in_{scope}"}, status=403)

    data = body.get("data")
    if not isinstance(data, dict):
        return JsonResponse({"error": "data_must_be_object"}, status=400)
    base_rev = int(body.get("base_rev") or 0)

    row, _created = PenguinWhMap.objects.get_or_create(scope=scope, key=key)
    if row.rev != base_rev:
        return JsonResponse(
            {"error": "stale", "rev": row.rev, "data": row.data or {}}, status=409
        )

    row.data = data
    row.rev = base_rev + 1
    row.updated_by = (body.get("by") or user.username)[:100]
    row.save()
    return JsonResponse({"scope": scope, "key": key, "rev": row.rev, "updated_at": row.updated_at.isoformat()})
