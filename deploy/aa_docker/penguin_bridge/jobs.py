"""Corp-project and divisional-manufacturing build jobs — a shared,
org-scoped job board distinct from `projects.py`'s *personal* Indy Hub
projects. See `PenguinBuildJob`'s own doc comment for why this is a new,
EVE-Penguin-owned model rather than another use of Indy Hub's.

- GET  /penguin/jobs                 list, scoped to the caller's own
                                      corp/alliance, filterable by
                                      mode/tier/status/mine
- POST /penguin/jobs                 create (manager permission required)
- GET  /penguin/jobs/<id>            detail
- POST /penguin/jobs/<id>            update, or an action: `{"action":
                                      "claim"|"release"|"start"|"deliver"|
                                      "cancel"}` — claim/release/start/
                                      deliver are for any False Gods member
                                      (claim/release/start/deliver only ever
                                      act on your own claim); field edits and
                                      cancel need the manager permission.

Manager gate is a real Django permission
(`penguin_bridge.can_manage_build_jobs`), not corp membership alone — grant
it to whichever AA group represents directors via the normal Django admin,
the same `default_permissions=()` + custom-permission pattern Indy Hub's own
`can_access_indy_hub` already uses. Deliberately not tied to any existing
"director" flag from the separate `mfg_projects`/`freight_bridge` session
system (see `indy_calc_plugin.rs`'s doc comment for why this bridge avoids
that system entirely) — this is its own, independently grantable permission.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from penguin_bridge.models import PenguinBuildJob
from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")

_MODES = {c[0] for c in PenguinBuildJob.MODE_CHOICES}
_TIERS = {c[0] for c in PenguinBuildJob.TIER_CHOICES}


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


def _main_character_name(user) -> str:
    try:
        return str(user.profile.main_character.character_name)
    except Exception:
        return user.username


def _require_session(request):
    user, _ = _session_user(request)
    if user is None:
        return None, JsonResponse({"error": "invalid_session"}, status=401)
    return user, None


def _is_manager(user) -> bool:
    try:
        return user.has_perm("penguin_bridge.can_manage_build_jobs") or bool(
            getattr(user, "is_superuser", False)
        )
    except Exception:
        return bool(getattr(user, "is_superuser", False))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def jobs(request):
    user, err = _require_session(request)
    if err:
        return err
    corp_ids, alli_ids = _my_orgs(user)

    if request.method == "GET":
        qs = PenguinBuildJob.objects.filter(
            corp_id__in=corp_ids
        ) | PenguinBuildJob.objects.filter(alliance_id__in=alli_ids)
        mode = request.GET.get("mode")
        if mode in _MODES:
            qs = qs.filter(mode=mode)
        tier = request.GET.get("tier")
        if tier in _TIERS:
            qs = qs.filter(tier=tier)
        status = request.GET.get("status")
        if status == "mine":
            qs = qs.filter(claimed_by_user_id=user.pk)
        elif status:
            qs = qs.filter(status=status)
        rows = list(qs.order_by("-created_at")[:500])
        return JsonResponse({"jobs": [j.as_dict() for j in rows]})

    # POST: create
    if not _is_manager(user):
        return JsonResponse({"error": "manager_permission_required"}, status=403)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    mode = str(body.get("mode") or "corp")
    if mode not in _MODES:
        return JsonResponse({"error": "bad_mode"}, status=400)
    tier = str(body.get("tier") or "d0")
    if tier not in _TIERS:
        return JsonResponse({"error": "bad_tier"}, status=400)
    type_name = str(body.get("type_name") or "").strip()
    if not type_name:
        return JsonResponse({"error": "type_name_required"}, status=400)
    try:
        quantity = max(1, int(body.get("quantity") or 1))
    except (TypeError, ValueError):
        quantity = 1

    corp_id = int(body.get("corp_id") or 0)
    alliance_id = int(body.get("alliance_id") or 0)
    if corp_id and corp_id not in corp_ids:
        return JsonResponse({"error": "not_your_corp"}, status=403)
    if alliance_id and alliance_id not in alli_ids:
        return JsonResponse({"error": "not_your_alliance"}, status=403)
    if not corp_id and not alliance_id:
        return JsonResponse({"error": "corp_id_or_alliance_id_required"}, status=400)

    job = PenguinBuildJob.objects.create(
        owner_user_id=user.pk,
        owner_name=_main_character_name(user),
        corp_id=corp_id,
        alliance_id=alliance_id,
        mode=mode,
        tier=tier,
        type_id=int(body.get("type_id") or 0),
        type_name=type_name[:255],
        quantity=quantity,
        blueprint_type_id=body.get("blueprint_type_id"),
        source_kind=str(body.get("source_kind") or "manual"),
        source_ref=str(body.get("source_ref") or "")[:255],
        notes=str(body.get("notes") or ""),
        metadata=body.get("metadata") or {},
        corp_profit_margin_pct=body.get("corp_profit_margin_pct") or 0,
    )
    return JsonResponse(job.as_dict(), status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def job_detail(request, job_id: int):
    user, err = _require_session(request)
    if err:
        return err
    corp_ids, alli_ids = _my_orgs(user)

    try:
        job = PenguinBuildJob.objects.get(pk=job_id)
    except PenguinBuildJob.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)
    if job.corp_id not in corp_ids and job.alliance_id not in alli_ids:
        return JsonResponse({"error": "not_found"}, status=404)

    if request.method == "GET":
        return JsonResponse(job.as_dict())

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    action = body.get("action")
    if action:
        return _apply_action(job, user, str(action))

    if not _is_manager(user):
        return JsonResponse({"error": "manager_permission_required"}, status=403)
    if "tier" in body and body["tier"] in _TIERS:
        job.tier = body["tier"]
    if "notes" in body:
        job.notes = str(body["notes"])
    if "corp_profit_margin_pct" in body:
        job.corp_profit_margin_pct = body["corp_profit_margin_pct"] or 0
    if "builder_share_isk" in body:
        job.builder_share_isk = body["builder_share_isk"]
    if "corp_share_isk" in body:
        job.corp_share_isk = body["corp_share_isk"]
    if "expected_delivery_at" in body:
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(str(body["expected_delivery_at"])) if body["expected_delivery_at"] else None
        job.expected_delivery_at = parsed
    job.save()
    return JsonResponse(job.as_dict())


def _apply_action(job: PenguinBuildJob, user, action: str) -> JsonResponse:
    now = timezone.now()
    if action == "claim":
        if job.status != "open":
            return JsonResponse({"error": "not_open"}, status=409)
        job.status = "claimed"
        job.claimed_by_user_id = user.pk
        job.claimed_by_name = _main_character_name(user)
        job.claimed_at = now
        job.save()
        return JsonResponse(job.as_dict())

    is_claimant = job.claimed_by_user_id == user.pk
    is_manager = _is_manager(user)

    if action == "release":
        if not (is_claimant or is_manager):
            return JsonResponse({"error": "not_your_claim"}, status=403)
        job.status = "open"
        job.claimed_by_user_id = None
        job.claimed_by_name = ""
        job.claimed_at = None
        job.save()
        return JsonResponse(job.as_dict())

    if action == "start":
        if not is_claimant:
            return JsonResponse({"error": "not_your_claim"}, status=403)
        if job.status != "claimed":
            return JsonResponse({"error": "not_claimed"}, status=409)
        job.status = "in_progress"
        job.save()
        return JsonResponse(job.as_dict())

    if action == "deliver":
        if not (is_claimant or is_manager):
            return JsonResponse({"error": "not_your_claim"}, status=403)
        job.status = "delivered"
        job.delivered_at = now
        job.save()
        return JsonResponse(job.as_dict())

    if action == "cancel":
        if not is_manager:
            return JsonResponse({"error": "manager_permission_required"}, status=403)
        job.status = "cancelled"
        job.save()
        return JsonResponse(job.as_dict())

    return JsonResponse({"error": "bad_action"}, status=400)
