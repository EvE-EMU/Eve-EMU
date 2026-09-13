"""zKillboard API helpers."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_ZKB_HEADERS = {
    "Accept-Encoding": "gzip",
    "User-Agent": "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com)",
}


def _parse_zkill_kill_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a zKill Redis killmail payload into a flat dict."""
    if not isinstance(row, dict):
        return None
    km_id = int(row.get("killmail_id") or 0)
    if km_id <= 0:
        return None

    victim = row.get("victim") if isinstance(row.get("victim"), dict) else {}
    zkb = row.get("zkb") if isinstance(row.get("zkb"), dict) else {}
    attackers_raw = row.get("attackers") if isinstance(row.get("attackers"), list) else []
    attackers: list[dict[str, Any]] = []
    for atk in attackers_raw:
        if not isinstance(atk, dict):
            continue
        cid = int(atk.get("character_id") or 0) or None
        attackers.append(
            {
                "character_id": cid,
                "corporation_id": int(atk.get("corporation_id") or 0) or None,
                "alliance_id": int(atk.get("alliance_id") or 0) or None,
                "ship_type_id": int(atk.get("ship_type_id") or 0) or None,
                "damage_done": int(atk.get("damage_done") or 0),
                "final_blow": bool(atk.get("final_blow")),
            }
        )

    return {
        "killmail_id": km_id,
        "killmail_hash": str(row.get("killmail_hash") or zkb.get("hash") or ""),
        "killed_at": row.get("killmail_time"),
        "solar_system_id": int(row.get("solar_system_id") or 0) or None,
        "total_value": float(zkb.get("totalValue") or 0),
        "victim_character_id": int(victim.get("character_id") or 0) or None,
        "victim_corporation_id": int(victim.get("corporation_id") or 0) or None,
        "victim_alliance_id": int(victim.get("alliance_id") or 0) or None,
        "ship_type_id": int(victim.get("ship_type_id") or 0) or None,
        "attackers": attackers,
        "zkill_url": f"https://zkillboard.com/kill/{km_id}/",
    }


async def fetch_alliance_stats(alliance_id: int, *, days: int = 30) -> dict[str, Any]:
    return await fetch_scope_stats("alliance", alliance_id, days=days)


async def fetch_scope_stats(scope: str, scope_id: int, *, days: int = 30) -> dict[str, Any]:
    """Fetch killmail stats for alliance or corporation via zKill REST."""
    key = "allianceID" if scope == "alliance" else "corporationID"
    url = f"{settings.zkill_base_url}/stats/{key}/{scope_id}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=_ZKB_HEADERS)
            if resp.status_code != 200:
                return {"error": "zkill_unavailable", "scope": scope, "scope_id": scope_id}
            data = resp.json()
        except Exception:
            logger.exception("zkill scope stats failed")
            return {"error": "zkill_error", "scope": scope, "scope_id": scope_id}

    return {
        "scope": scope,
        "scope_id": scope_id,
        "period_days": days,
        "isk_destroyed": data.get("iskDestroyed", 0),
        "isk_lost": data.get("iskLost", 0),
        "ships_destroyed": data.get("shipsDestroyed", 0),
        "ships_lost": data.get("shipsLost", 0),
        "raw": data,
    }


async def fetch_character_stats(character_id: int) -> dict[str, Any]:
    """Fetch per-character kill/loss totals from zKill."""
    url = f"{settings.zkill_base_url}/stats/characterID/{character_id}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=_ZKB_HEADERS)
            if resp.status_code != 200:
                return {"error": "zkill_unavailable", "character_id": character_id}
            data = resp.json()
        except Exception:
            logger.exception("zkill character stats failed for %s", character_id)
            return {"error": "zkill_error", "character_id": character_id}

    return {
        "character_id": character_id,
        "isk_destroyed": data.get("iskDestroyed", 0),
        "isk_lost": data.get("iskLost", 0),
        "ships_destroyed": data.get("shipsDestroyed", 0),
        "ships_lost": data.get("shipsLost", 0),
        "raw": data,
    }


async def fetch_scope_recent_kills(
    scope: str,
    scope_id: int,
    *,
    limit: int = 50,
    page: int = 1,
) -> list[dict[str, Any]]:
    """Fetch recent killmails for alliance or corporation from zKill."""
    key = "allianceID" if scope == "alliance" else "corporationID"
    url = f"{settings.zkill_base_url}/kills/{key}/{scope_id}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                url,
                headers=_ZKB_HEADERS,
                params={"limit": limit, "page": page},
            )
            if resp.status_code != 200:
                return []
            rows = resp.json()
        except Exception:
            logger.exception("zkill scope kills failed for %s/%s", scope, scope_id)
            return []

    out: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        parsed = _parse_zkill_kill_row(row)
        if parsed:
            out.append(parsed)
    return out


async def fetch_character_recent_kills(
    character_id: int, *, limit: int = 20
) -> list[dict[str, Any]]:
    url = f"{settings.zkill_base_url}/kills/characterID/{character_id}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=_ZKB_HEADERS, params={"limit": limit})
            if resp.status_code != 200:
                return []
            rows = resp.json()
        except Exception:
            logger.exception("zkill kills failed")
            return []

    out: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        parsed = _parse_zkill_kill_row(row)
        if parsed:
            out.append(parsed)
    return out


async def fetch_killmail_zkb(killmail_id: int) -> dict[str, Any]:
    """Fetch zKillboard metadata (total value) for a killmail."""
    url = f"{settings.zkill_base_url}/killmails/killID/{killmail_id}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=_ZKB_HEADERS)
            if resp.status_code != 200:
                return {"total_value": 0}
            rows = resp.json()
        except Exception:
            logger.exception("zkill killmail fetch failed for %s", killmail_id)
            return {"total_value": 0}

    if isinstance(rows, list) and rows:
        row = rows[0] if isinstance(rows[0], dict) else {}
    elif isinstance(rows, dict):
        row = rows
    else:
        return {"total_value": 0}
    zkb = row.get("zkb") if isinstance(row.get("zkb"), dict) else {}
    return {
        "total_value": zkb.get("totalValue", 0),
        "url": f"https://zkillboard.com/kill/{killmail_id}/",
    }


def leaderboard_from_demo(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: float(r.get("isk_destroyed", 0)), reverse=True)
