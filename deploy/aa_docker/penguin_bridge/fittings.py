"""Fittings for the desktop client — GET / POST / DELETE /penguin/fittings.

GET merges two sources:
  * "auth"    — read-only doctrine fits from AllianceAuth's `fittings` app
                (shown when the user has `fittings.access_fittings`), grouped
                by doctrine; ids look like "auth:<pk>".
  * "penguin" — the user's own `PenguinFitting` rows: their private fits plus
                every corp / alliance fit whose stored org id matches one of
                their linked characters' orgs. Editable / deletable.

POST / DELETE only ever touch "penguin" rows, and a user may only write a
corp / alliance scope for an org they belong to.
"""

from __future__ import annotations

import json
import logging

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from penguin_bridge.models import PenguinFitting
from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")

_SCOPES = {PenguinFitting.PRIVATE, PenguinFitting.CORP, PenguinFitting.ALLIANCE}


def _my_orgs(user):
    from allianceauth.authentication.models import CharacterOwnership

    corp_ids: set[int] = set()
    alli_ids: set[int] = set()
    for own in CharacterOwnership.objects.filter(user=user).select_related("character"):
        c = own.character
        if c.corporation_id:
            corp_ids.add(int(c.corporation_id))
        if c.alliance_id:
            alli_ids.add(int(c.alliance_id))
    return corp_ids, alli_ids


def _auth_fittings(user):
    """Read-only doctrine fits from AllianceAuth's `fittings` app."""
    if not user.has_perm("fittings.access_fittings"):
        return []
    try:
        from fittings.models import Fitting
    except Exception:  # app not installed
        return []

    rows = []
    qs = Fitting.objects.select_related("ship_type").prefetch_related("doctrines")
    for f in qs:
        try:
            eft = f.eft
        except Exception:
            logger.warning("penguin fittings: eft() failed for Fitting %s", f.pk)
            continue
        upd = getattr(f, "last_updated", None) or getattr(f, "created", None)
        rows.append(
            {
                "id": f"auth:{f.pk}",
                "name": f.name,
                "ship_type_id": int(getattr(f, "ship_type_type_id", 0) or 0),
                "eft": eft,
                "scope": "auth",
                "source": "auth",
                "mine": False,
                "doctrines": sorted(d.name for d in f.doctrines.all()),
                "updated": upd.isoformat() if upd else "",
            }
        )
    return rows


@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def fittings(request):
    user, payload = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)

    corp_ids, alli_ids = _my_orgs(user)

    if request.method == "GET":
        visible = (
            Q(scope=PenguinFitting.PRIVATE, owner_user_id=user.pk)
            | Q(scope=PenguinFitting.CORP, corp_id__in=list(corp_ids) or [0])
            | Q(scope=PenguinFitting.ALLIANCE, alliance_id__in=list(alli_ids) or [0])
        )
        rows = [
            {**f.as_dict(mine=(f.owner_user_id == user.pk)), "source": "penguin"}
            for f in PenguinFitting.objects.filter(visible)
        ]
        rows.extend(_auth_fittings(user))
        return JsonResponse({"fittings": rows})

    if request.method == "DELETE":
        fid = request.GET.get("id")
        deleted, _ = PenguinFitting.objects.filter(
            id=fid, owner_user_id=user.pk
        ).delete()
        if not deleted:
            return JsonResponse({"error": "not_found_or_not_yours"}, status=404)
        return JsonResponse({"deleted": deleted})

    # POST — create or update one of the caller's fits
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    name = (body.get("name") or "").strip()[:120]
    eft = (body.get("eft") or "").strip()
    if not name or not eft:
        return JsonResponse({"error": "name_and_eft_required"}, status=400)

    scope = body.get("scope")
    if scope not in _SCOPES:
        scope = PenguinFitting.PRIVATE

    corp_id = 0
    alliance_id = 0
    if scope == PenguinFitting.CORP:
        want = int(body.get("corp_id") or 0)
        corp_id = want if want in corp_ids else next(iter(corp_ids), 0)
        if corp_id == 0:
            return JsonResponse({"error": "not_in_a_corp"}, status=403)
    elif scope == PenguinFitting.ALLIANCE:
        want = int(body.get("alliance_id") or 0)
        alliance_id = want if want in alli_ids else next(iter(alli_ids), 0)
        if alliance_id == 0:
            return JsonResponse({"error": "not_in_an_alliance"}, status=403)

    fields = dict(
        name=name,
        ship_type_id=int(body.get("ship_type_id") or 0),
        eft=eft,
        scope=scope,
        corp_id=corp_id,
        alliance_id=alliance_id,
        owner_name=(body.get("owner_name") or "")[:100],
    )

    fid = body.get("id")
    if fid:
        obj = PenguinFitting.objects.filter(id=fid, owner_user_id=user.pk).first()
        if obj is None:
            return JsonResponse({"error": "not_found_or_not_yours"}, status=404)
        for k, v in fields.items():
            setattr(obj, k, v)
        obj.save()
    else:
        obj = PenguinFitting.objects.create(owner_user_id=user.pk, **fields)

    return JsonResponse(obj.as_dict(mine=True))
