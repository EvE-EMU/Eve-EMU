"""Mail, combat log, and corporation history for character audit snapshots."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import SdeTypeIndex
from app.services.audit_scopes import has_killmails_access, has_mail_access
from app.services.esi import bearer_token, esi_get, esi_get_paged_list, resolve_universe_names

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; audit)"


async def sync_corp_history(client: httpx.AsyncClient, character_id: int) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{_ESI}/characters/{character_id}/corporationhistory/",
        headers={"Accept": "application/json", "User-Agent": _UA},
    )
    if resp.status_code != 200 or not isinstance(resp.json(), list):
        return []

    rows = sorted(resp.json(), key=lambda r: str(r.get("start_date") or ""))
    corp_ids = {int(r.get("corporation_id") or 0) for r in rows if int(r.get("corporation_id") or 0) > 0}
    names = await resolve_universe_names(list(corp_ids))

    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        corp_id = int(row.get("corporation_id") or 0)
        if corp_id <= 0:
            continue
        joined = row.get("start_date")
        left = rows[i + 1].get("start_date") if i + 1 < len(rows) else None
        out.append(
            {
                "corporation_id": corp_id,
                "corporation_name": names.get(corp_id, f"Corporation {corp_id}"),
                "record_id": int(row.get("record_id") or 0) or None,
                "joined_at": joined,
                "left_at": left,
                "is_current": left is None,
            }
        )
    out.reverse()
    return out


async def sync_mail_headers(
    session: AsyncSession,
    *,
    character_id: int,
    granted: set[str],
) -> list[dict[str, Any]]:
    if not has_mail_access(granted):
        return []

    raw = await esi_get_paged_list(
        f"/characters/{character_id}/mail/",
        auth=True,
        session=session,
        character_id=character_id,
        max_pages=3,
    )
    char_ids: set[int] = set()
    for row in raw:
        if isinstance(row, dict):
            fid = int(row.get("from") or 0)
            if fid > 0:
                char_ids.add(fid)

    names = await resolve_universe_names(list(char_ids))
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        mail_id = int(row.get("mail_id") or 0)
        if mail_id <= 0:
            continue
        from_id = int(row.get("from") or 0)
        recipients = row.get("recipients") or []
        recipient_ids: list[dict] = []
        if isinstance(recipients, list):
            for recip in recipients:
                if not isinstance(recip, dict):
                    continue
                rid = int(recip.get("recipient_id") or 0)
                if rid > 0:
                    recipient_ids.append(
                        {
                            "recipient_id": rid,
                            "recipient_type": str(recip.get("recipient_type") or ""),
                        }
                    )
                    char_ids.add(rid)
        out.append(
            {
                "mail_id": mail_id,
                "subject": str(row.get("subject") or "(no subject)"),
                "from_id": from_id or None,
                "from_name": names.get(from_id) if from_id else None,
                "timestamp": row.get("timestamp"),
                "is_read": bool(row.get("is_read")),
                "labels": row.get("labels") or [],
                "recipient_count": len(recipients) if isinstance(recipients, list) else 0,
                "recipient_ids": recipient_ids,
            }
        )
    out.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
    return out[:80]


async def _fetch_killmail(client: httpx.AsyncClient, killmail_id: int, killmail_hash: str) -> dict | None:
    resp = await client.get(
        f"{_ESI}/killmails/{killmail_id}/{killmail_hash}/",
        headers={"Accept": "application/json", "User-Agent": _UA},
    )
    if resp.status_code != 200:
        return None
    body = resp.json()
    return body if isinstance(body, dict) else None


async def sync_combat_log(
    session: AsyncSession,
    client: httpx.AsyncClient,
    *,
    character_id: int,
    headers: dict[str, str],
    granted: set[str],
) -> list[dict[str, Any]]:
    if not has_killmails_access(granted):
        return []

    resp = await client.get(
        f"{_ESI}/characters/{character_id}/killmails/recent/",
        headers=headers,
    )
    if resp.status_code != 200 or not isinstance(resp.json(), list):
        return []

    refs = [r for r in resp.json() if isinstance(r, dict)][:35]
    events: list[dict[str, Any]] = []
    type_ids: set[int] = set()
    char_ids: set[int] = set()

    for ref in refs:
        km_id = int(ref.get("killmail_id") or 0)
        km_hash = str(ref.get("killmail_hash") or "")
        if km_id <= 0 or not km_hash:
            continue
        km = await _fetch_killmail(client, km_id, km_hash)
        if not km:
            continue

        victim = km.get("victim") if isinstance(km.get("victim"), dict) else {}
        victim_cid = int(victim.get("character_id") or 0) or None
        ship_type_id = int(victim.get("ship_type_id") or 0) or None
        if ship_type_id:
            type_ids.add(ship_type_id)

        is_loss = victim_cid == character_id
        is_kill = False
        attacker_ids: list[int] = []
        for atk in km.get("attackers") or []:
            if not isinstance(atk, dict):
                continue
            ac = int(atk.get("character_id") or 0)
            if ac > 0:
                attacker_ids.append(ac)
            if ac == character_id:
                is_kill = True

        if not is_kill and not is_loss:
            continue

        outcome = "loss" if is_loss else "kill"
        # Resolve names for victim and all attackers (fleet co-attackers on kills).
        if victim_cid:
            char_ids.add(victim_cid)
        for ac in attacker_ids:
            if ac != character_id:
                char_ids.add(ac)
        if is_loss or is_kill:
            char_ids.add(character_id)

        solar_system_id = int(km.get("solar_system_id") or 0) or None
        events.append(
            {
                "killmail_id": km_id,
                "killmail_hash": km_hash,
                "outcome": outcome,
                "killed_at": km.get("killmail_time"),
                "solar_system_id": solar_system_id,
                "ship_type_id": ship_type_id,
                "victim_character_id": victim_cid,
                "attacker_character_ids": sorted(set(attacker_ids)),
                "zkill_url": f"https://zkillboard.com/kill/{km_id}/",
            }
        )

    type_ids_set = {int(t) for t in type_ids if int(t) > 0}
    type_names: dict[int, str] = {}
    if type_ids_set:
        rows = await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids_set)))
        type_names = {int(r.type_id): r.name for r in rows.all()}
    char_names = await resolve_universe_names(list(char_ids))
    system_names = await resolve_universe_names(
        [e["solar_system_id"] for e in events if e.get("solar_system_id")]
    )

    for event in events:
        sid = event.get("ship_type_id")
        if sid:
            event["ship_type_name"] = type_names.get(int(sid), f"Type {sid}")
        vid = event.get("victim_character_id")
        if vid:
            event["victim_character_name"] = char_names.get(int(vid), f"Character {vid}")
        sys_id = event.get("solar_system_id")
        if sys_id:
            event["solar_system_name"] = system_names.get(int(sys_id), f"System {sys_id}")

    events.sort(key=lambda r: str(r.get("killed_at") or ""), reverse=True)
    return events[:50]


async def fetch_mail_body(
    session: AsyncSession,
    *,
    character_id: int,
    mail_id: int,
) -> dict[str, Any]:
    token = await bearer_token(session, character_id=character_id)
    if not token:
        return {"found": False, "error": "ESI token not available"}

    status, body = await esi_get(
        f"/characters/{character_id}/mail/{mail_id}/",
        auth=True,
        session=session,
        character_id=character_id,
    )
    if status != 200 or not isinstance(body, dict):
        return {"found": False, "error": f"Mail fetch failed ({status})"}

    from_id = int(body.get("from") or 0)
    names = await resolve_universe_names([from_id]) if from_id else {}
    return {
        "found": True,
        "mail_id": mail_id,
        "subject": body.get("subject"),
        "from_id": from_id or None,
        "from_name": names.get(from_id) if from_id else None,
        "timestamp": body.get("timestamp"),
        "body": body.get("body") or "",
        "labels": body.get("labels") or [],
    }
