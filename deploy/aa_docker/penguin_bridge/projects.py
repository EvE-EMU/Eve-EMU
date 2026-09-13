"""Persisted build projects for the desktop client — a thin CRUD layer
directly over Auth Indy Hub's own `ProductionProject`/`ProductionProjectItem`
models (the same tables Indy Hub's own web UI reads and writes), so a
project saved from EVE-Penguin is a genuine Indy Hub project, not a
disconnected copy of the idea living only in the desktop app.

Gated the same way Indy Hub gates itself (`user.has_perm(
"indy_hub.can_access_indy_hub")`) rather than a separate permission scheme —
whoever can already use the real Indy Hub can use this.

- GET|POST /penguin/projects              list mine / create one
- GET|PATCH|DELETE /penguin/projects/<ref> read, update (name/notes/status/
                                           items), or delete one of mine

`status` is Indy Hub's own three-value lifecycle (draft/saved/archived) —
"saved" is the closest existing concept to "approved" without inventing a
fourth state Indy Hub itself doesn't have and its own UI wouldn't recognise.
Each item's `inclusion_mode` (produce/buy/skip) is Indy Hub's own field too,
not a new one — the desktop client's buy-vs-produce advisor writes into it
directly. `metadata` is a free JSON blob per item where the client stores
its own computed cost breakdown (materials, structure used, freight) — Indy
Hub doesn't need to understand that shape, just carry it.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")


def _require_indy_hub(request):
    user, _ = _session_user(request)
    if user is None:
        return None, JsonResponse({"error": "invalid_session"}, status=401)
    try:
        allowed = user.has_perm("indy_hub.can_access_indy_hub") or getattr(
            user, "is_superuser", False
        )
    except Exception:
        logger.warning("penguin projects: permission check failed", exc_info=True)
        return None, JsonResponse({"error": "indy_hub_unavailable"}, status=502)
    if not allowed:
        return None, JsonResponse({"error": "indy_hub_required"}, status=403)
    return user, None


def _item_payload(item) -> dict:
    return {
        "id": item.id,
        "type_id": item.type_id,
        "type_name": item.type_name,
        "quantity_requested": item.quantity_requested,
        "inclusion_mode": item.inclusion_mode,
        "blueprint_type_id": item.blueprint_type_id,
        "is_selected": bool(item.is_selected),
        "metadata": item.metadata or {},
    }


def _project_payload(project, *, with_items: bool) -> dict:
    data = {
        "project_ref": project.project_ref,
        "name": project.name,
        "status": project.status,
        "notes": project.notes,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }
    if with_items:
        data["items"] = [_item_payload(i) for i in project.items.all()]
    else:
        data["item_count"] = project.items.count()
    return data


def _write_items(project, items: list) -> None:
    from indy_hub.models import ProductionProjectItem

    for order, raw in enumerate(items):
        if not isinstance(raw, dict):
            continue
        mode = str(raw.get("inclusion_mode") or "produce")
        if mode not in ProductionProjectItem.InclusionMode.values:
            mode = ProductionProjectItem.InclusionMode.PRODUCE
        try:
            qty = int(raw.get("quantity_requested") or 1)
        except (TypeError, ValueError):
            qty = 1
        type_id = raw.get("type_id")
        bp_id = raw.get("blueprint_type_id")
        ProductionProjectItem.objects.create(
            project=project,
            type_id=int(type_id) if type_id is not None else None,
            type_name=str(raw.get("type_name") or "")[:255],
            quantity_requested=max(1, qty),
            category_order=order,
            inclusion_mode=mode,
            is_craftable=bp_id is not None,
            blueprint_type_id=int(bp_id) if bp_id is not None else None,
            metadata=raw.get("metadata") or {},
        )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def projects(request):
    user, err = _require_indy_hub(request)
    if err:
        return err
    from indy_hub.models import ProductionProject

    if request.method == "GET":
        rows = ProductionProject.objects.filter(user=user).order_by("-updated_at")[:200]
        return JsonResponse({"projects": [_project_payload(p, with_items=False) for p in rows]})

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)
    name = str(body.get("name") or "").strip()[:255] or "Untitled build"
    items = body.get("items") or []
    if not isinstance(items, list):
        return JsonResponse({"error": "bad_items"}, status=400)

    project = ProductionProject.objects.create(
        user=user,
        name=name,
        notes=str(body.get("notes") or ""),
        source_kind=ProductionProject.SourceKind.MANUAL,
        source_name="EVE-Penguin",
        status=ProductionProject.Status.DRAFT,
    )
    _write_items(project, items)
    project.refresh_from_db()
    return JsonResponse(_project_payload(project, with_items=True), status=201)


@csrf_exempt
@require_http_methods(["GET", "POST", "PATCH", "DELETE"])
def project_detail(request, project_ref: str):
    # POST is accepted as a PATCH alias: the desktop client's bridge helper
    # only speaks GET/POST/DELETE (no generic PATCH-with-body), matching
    # this app's existing write convention (`bridge_post` is the one write
    # verb with a body everywhere else too) rather than adding a PATCH-only
    # code path nothing else here uses.
    user, err = _require_indy_hub(request)
    if err:
        return err
    from indy_hub.models import ProductionProject

    try:
        project = ProductionProject.objects.prefetch_related("items").get(
            project_ref=project_ref, user=user
        )
    except ProductionProject.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_project_payload(project, with_items=True))

    if request.method == "DELETE":
        project.delete()
        return JsonResponse({}, status=204)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    if "name" in body:
        cleaned = str(body["name"]).strip()[:255]
        if cleaned:
            project.name = cleaned
    if "notes" in body:
        project.notes = str(body["notes"])
    if "status" in body:
        new_status = str(body["status"])
        from indy_hub.models import ProductionProject as PP

        if new_status in PP.Status.values:
            project.status = new_status
    project.save()

    if "items" in body and isinstance(body["items"], list):
        project.items.all().delete()
        _write_items(project, body["items"])

    project.refresh_from_db()
    return JsonResponse(_project_payload(project, with_items=True))
