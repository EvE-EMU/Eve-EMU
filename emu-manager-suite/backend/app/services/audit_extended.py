"""Additional ESI scope sync — online, ship, fatigue, roles, standings, contacts, etc."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_scopes import (
    has_calendar_access,
    has_contacts_access,
    has_corp_roles_access,
    has_fatigue_access,
    has_loyalty_access,
    has_notifications_access,
    has_online_access,
    has_ship_type_access,
    has_standings_access,
)
from app.services.asset_labels import load_type_names
from app.services.esi import esi_get_paged_list, resolve_universe_names

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; audit-ext)"


async def sync_audit_extended(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient,
    character_id: int,
    headers: dict[str, str],
    granted: set[str],
    snapshot: dict[str, Any],
    scope_errors: dict[str, str],
) -> None:
    if has_online_access(granted):
        try:
            resp = await client.get(f"{_ESI}/characters/{character_id}/online/", headers=headers)
            if resp.status_code == 200 and isinstance(resp.json(), dict):
                body = resp.json()
                snapshot["online"] = {
                    "online": bool(body.get("online")),
                    "last_login": body.get("last_login"),
                    "last_logout": body.get("last_logout"),
                    "logins": body.get("logins"),
                }
            elif resp.status_code in (401, 403):
                scope_errors["online"] = resp.text[:200]
        except Exception:
            logger.exception("audit online sync failed for %s", character_id)
    else:
        scope_errors["online"] = "Missing scope: esi-location.read_online.v1"

    if has_ship_type_access(granted):
        try:
            resp = await client.get(f"{_ESI}/characters/{character_id}/ship/", headers=headers)
            if resp.status_code == 200 and isinstance(resp.json(), dict):
                body = resp.json()
                ship_type_id = int(body.get("ship_type_id") or 0)
                names = await load_type_names(session, {ship_type_id} if ship_type_id else set())
                snapshot["active_ship"] = {
                    "ship_item_id": int(body.get("ship_item_id") or 0) or None,
                    "ship_type_id": ship_type_id or None,
                    "ship_type_name": names.get(ship_type_id, f"Type {ship_type_id}")
                    if ship_type_id
                    else None,
                    "ship_name": str(body.get("ship_name") or "").strip() or None,
                }
            elif resp.status_code in (401, 403):
                scope_errors["ship"] = resp.text[:200]
        except Exception:
            logger.exception("audit ship sync failed for %s", character_id)
    else:
        scope_errors["ship"] = "Missing scope: esi-location.read_ship_type.v1"

    if has_fatigue_access(granted):
        try:
            resp = await client.get(f"{_ESI}/characters/{character_id}/fatigue/", headers=headers)
            if resp.status_code == 200 and isinstance(resp.json(), dict):
                body = resp.json()
                snapshot["fatigue"] = {
                    "jump_fatigue_expire_date": body.get("jump_fatigue_expire_date"),
                    "last_jump_date": body.get("last_jump_date"),
                    "last_update_date": body.get("last_update_date"),
                }
            elif resp.status_code in (401, 403):
                scope_errors["fatigue"] = resp.text[:200]
        except Exception:
            logger.exception("audit fatigue sync failed for %s", character_id)
    else:
        scope_errors["fatigue"] = "Missing scope: esi-characters.read_fatigue.v1"

    if has_corp_roles_access(granted):
        try:
            resp = await client.get(f"{_ESI}/characters/{character_id}/roles/", headers=headers)
            if resp.status_code == 200 and isinstance(resp.json(), dict):
                body = resp.json()
                snapshot["corp_roles"] = {
                    "roles": list(body.get("roles") or []),
                    "roles_at_hq": list(body.get("roles_at_hq") or []),
                    "roles_at_base": list(body.get("roles_at_base") or []),
                    "roles_at_other": list(body.get("roles_at_other") or []),
                }
            elif resp.status_code in (401, 403):
                scope_errors["corp_roles"] = resp.text[:200]
        except Exception:
            logger.exception("audit corp roles sync failed for %s", character_id)
    else:
        scope_errors["corp_roles"] = "Missing scope: esi-characters.read_corporation_roles.v1"

    if has_standings_access(granted):
        try:
            rows = await esi_get_paged_list(
                f"/characters/{character_id}/standings/",
                auth=True,
                session=session,
                character_id=character_id,
                max_pages=5,
            )
            entity_ids = {
                int(r.get("from_id") or 0)
                for r in rows
                if isinstance(r, dict) and int(r.get("from_id") or 0) > 0
            }
            names = await resolve_universe_names(list(entity_ids))
            snapshot["standings"] = [
                {
                    "from_id": int(r.get("from_id") or 0),
                    "from_type": r.get("from_type"),
                    "from_name": names.get(int(r.get("from_id") or 0)),
                    "standing": float(r.get("standing") or 0),
                }
                for r in rows
                if isinstance(r, dict) and int(r.get("from_id") or 0) > 0
            ][:120]
        except Exception:
            logger.exception("audit standings sync failed for %s", character_id)
    else:
        scope_errors["standings"] = "Missing scope: esi-characters.read_standings.v1"

    if has_contacts_access(granted):
        try:
            rows = await esi_get_paged_list(
                f"/characters/{character_id}/contacts/",
                auth=True,
                session=session,
                character_id=character_id,
                max_pages=10,
            )
            contact_ids = {
                int(r.get("contact_id") or 0)
                for r in rows
                if isinstance(r, dict) and int(r.get("contact_id") or 0) > 0
            }
            names = await resolve_universe_names(list(contact_ids))
            snapshot["contacts"] = [
                {
                    "contact_id": int(r.get("contact_id") or 0),
                    "contact_type": r.get("contact_type"),
                    "contact_name": names.get(int(r.get("contact_id") or 0)),
                    "label": str(r.get("label") or ""),
                    "standing": float(r.get("standing") or 0),
                    "is_blocked": bool(r.get("is_blocked")),
                    "is_watched": bool(r.get("is_watched")),
                }
                for r in rows
                if isinstance(r, dict) and int(r.get("contact_id") or 0) > 0
            ][:200]
        except Exception:
            logger.exception("audit contacts sync failed for %s", character_id)
    else:
        scope_errors["contacts"] = "Missing scope: esi-characters.read_contacts.v1"

    if has_notifications_access(granted):
        try:
            rows = await esi_get_paged_list(
                f"/characters/{character_id}/notifications/",
                auth=True,
                session=session,
                character_id=character_id,
                max_pages=5,
            )
            snapshot["eve_notifications"] = [
                {
                    "notification_id": int(r.get("notification_id") or 0),
                    "type": r.get("type"),
                    "sender_id": r.get("sender_id"),
                    "sender_type": r.get("sender_type"),
                    "timestamp": r.get("timestamp"),
                    "is_read": bool(r.get("is_read")),
                }
                for r in rows
                if isinstance(r, dict) and int(r.get("notification_id") or 0) > 0
            ][:80]
        except Exception:
            logger.exception("audit notifications sync failed for %s", character_id)
    else:
        scope_errors["eve_notifications"] = "Missing scope: esi-characters.read_notifications.v1"

    if has_loyalty_access(granted):
        try:
            resp = await client.get(
                f"{_ESI}/characters/{character_id}/loyalty/points/", headers=headers
            )
            if resp.status_code == 200 and isinstance(resp.json(), list):
                corp_ids = {int(r.get("corporation_id") or 0) for r in resp.json() if isinstance(r, dict)}
                names = await resolve_universe_names(list(corp_ids))
                snapshot["loyalty_points"] = [
                    {
                        "corporation_id": int(r.get("corporation_id") or 0),
                        "corporation_name": names.get(int(r.get("corporation_id") or 0)),
                        "loyalty_points": int(r.get("loyalty_points") or 0),
                    }
                    for r in resp.json()
                    if isinstance(r, dict) and int(r.get("corporation_id") or 0) > 0
                ]
            elif resp.status_code in (401, 403):
                scope_errors["loyalty"] = resp.text[:200]
        except Exception:
            logger.exception("audit loyalty sync failed for %s", character_id)
    else:
        scope_errors["loyalty"] = "Missing scope: esi-characters.read_loyalty.v1"

    if has_calendar_access(granted):
        try:
            resp = await client.get(f"{_ESI}/characters/{character_id}/calendar/", headers=headers)
            if resp.status_code == 200 and isinstance(resp.json(), list):
                snapshot["calendar_events"] = [
                    {
                        "event_id": int(r.get("event_id") or 0),
                        "title": str(r.get("title") or ""),
                        "importance": int(r.get("importance") or 0),
                        "event_date": r.get("event_date"),
                        "duration": int(r.get("duration") or 0),
                    }
                    for r in resp.json()
                    if isinstance(r, dict) and int(r.get("event_id") or 0) > 0
                ][:60]
            elif resp.status_code in (401, 403):
                scope_errors["calendar"] = resp.text[:200]
        except Exception:
            logger.exception("audit calendar sync failed for %s", character_id)
    else:
        scope_errors["calendar"] = "Missing scope: esi-calendar.read_calendar_events.v1"

    snapshot["extended_synced_at"] = datetime.now(UTC).isoformat()
