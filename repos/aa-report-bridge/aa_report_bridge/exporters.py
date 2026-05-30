"""Curated read-only snapshots — not raw SQL or full schema dumps."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterator

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Model, QuerySet
from django.utils import timezone


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return dt.isoformat()
    return timezone.make_aware(dt, timezone.utc).isoformat()


def _paginate(qs: QuerySet, *, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    total = qs.count()
    rows = list(qs[offset : offset + limit])
    return rows, total


def export_auth_users(*, limit: int, offset: int, since: datetime | None) -> dict[str, Any]:
    User = get_user_model()
    from django.db.models import Q

    qs = User.objects.all().order_by("pk")
    if since is not None:
        qs = qs.filter(Q(date_joined__gte=since) | Q(last_login__gte=since))
    users, total = _paginate(qs, limit=limit, offset=offset)
    items = []
    for u in users:
        items.append(
            {
                "id": u.pk,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "is_staff": u.is_staff,
                "date_joined": _iso(u.date_joined),
                "last_login": _iso(u.last_login),
                "group_ids": list(u.groups.values_list("pk", flat=True)),
            }
        )
    return {"resource": "auth.user", "items": items, "total": total, "limit": limit, "offset": offset}


def export_auth_groups(*, limit: int, offset: int, since: datetime | None) -> dict[str, Any]:
    qs = Group.objects.all().order_by("pk")
    groups, total = _paginate(qs, limit=limit, offset=offset)
    items = [{"id": g.pk, "name": g.name} for g in groups]
    return {"resource": "auth.group", "items": items, "total": total, "limit": limit, "offset": offset}


def export_eve_characters(*, limit: int, offset: int, since: datetime | None) -> dict[str, Any]:
    try:
        EveCharacter = apps.get_model("eveonline", "EveCharacter")
    except LookupError:
        return {"resource": "eveonline.evecharacter", "items": [], "total": 0, "error": "eveonline not installed"}

    qs = EveCharacter.objects.all().order_by("character_id")
    if since is not None and hasattr(EveCharacter, "updated_at"):
        qs = qs.filter(updated_at__gte=since)
    chars, total = _paginate(qs, limit=limit, offset=offset)
    items = []
    for c in chars:
        items.append(
            {
                "character_id": c.character_id,
                "character_name": getattr(c, "character_name", None),
                "corporation_id": getattr(c, "corporation_id", None),
                "corporation_name": getattr(c, "corporation_name", None),
                "alliance_id": getattr(c, "alliance_id", None),
                "alliance_name": getattr(c, "alliance_name", None),
                "user_id": getattr(c, "user_id", None),
            }
        )
    return {
        "resource": "eveonline.evecharacter",
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _generic_model_export(
    app_label: str,
    model_name: str,
    *,
    limit: int,
    offset: int,
    since: datetime | None,
    fields: list[str],
) -> dict[str, Any]:
    resource = f"{app_label}.{model_name.lower()}"
    try:
        ModelClass = apps.get_model(app_label, model_name)
    except LookupError:
        return {"resource": resource, "items": [], "total": 0, "error": "model not installed"}

    qs: QuerySet = ModelClass.objects.all().order_by("pk")
    if since is not None:
        for candidate in ("updated_at", "modified", "last_update"):
            if hasattr(ModelClass, candidate):
                qs = qs.filter(**{f"{candidate}__gte": since})
                break

    page, total = _paginate(qs, limit=limit, offset=offset)
    items = []
    for row in page:
        item: dict[str, Any] = {"pk": row.pk}
        for name in fields:
            if hasattr(row, name):
                val = getattr(row, name)
                if isinstance(val, datetime):
                    val = _iso(val)
                elif hasattr(val, "pk"):
                    val = val.pk
                item[name] = val
        items.append(item)
    return {"resource": resource, "items": items, "total": total, "limit": limit, "offset": offset}


ExporterFn = Callable[..., dict[str, Any]]

EXPORTERS: dict[str, ExporterFn] = {
    "auth.user": export_auth_users,
    "auth.group": export_auth_groups,
    "eveonline.evecharacter": export_eve_characters,
    "memberaudit.character": lambda **kw: _generic_model_export(
        "memberaudit",
        "Character",
        fields=[
            "character_id",
            "character_name",
            "corporation_id",
            "corporation_name",
            "main_character",
            "is_active",
        ],
        **kw,
    ),
    "miningtaxes.character": lambda **kw: _generic_model_export(
        "miningtaxes",
        "Character",
        fields=[
            "character_id",
            "character_name",
            "corp_id",
            "monthly_taxes",
            "monthly_credits",
            "life_taxes",
            "life_credits",
        ],
        **kw,
    ),
}


def list_resources() -> list[dict[str, str]]:
    return [
        {"id": key, "description": fn.__doc__ or "read-only export"}
        for key, fn in sorted(EXPORTERS.items())
    ]


def run_export(
    resource: str,
    *,
    limit: int = 500,
    offset: int = 0,
    since: datetime | None = None,
) -> dict[str, Any]:
    fn = EXPORTERS.get(resource)
    if fn is None:
        return {"error": "unknown_resource", "resource": resource, "available": list(EXPORTERS)}
    return fn(limit=limit, offset=offset, since=since)


def serialize_instance(instance: Model, *, action: str) -> dict[str, Any]:
    """Small webhook payload for a single row."""
    label = f"{instance._meta.app_label}.{instance._meta.model_name}"
    data: dict[str, Any] = {"pk": instance.pk, "action": action, "model": label}
    if label == "auth.user":
        data["record"] = {
            "id": instance.pk,
            "username": instance.username,
            "is_active": instance.is_active,
            "group_ids": list(instance.groups.values_list("pk", flat=True)),
        }
    elif label == "auth.group":
        data["record"] = {"id": instance.pk, "name": instance.name}
    elif label == "eveonline.evecharacter":
        data["record"] = {
            "character_id": instance.character_id,
            "character_name": getattr(instance, "character_name", None),
            "corporation_id": getattr(instance, "corporation_id", None),
            "user_id": getattr(instance, "user_id", None),
        }
    else:
        data["record"] = {"pk": instance.pk}
    return data
