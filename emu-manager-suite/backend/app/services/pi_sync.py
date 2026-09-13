"""Planetary interaction — ESI sync, colony analysis, roster overview."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import AuditProfile, SdeSystem, SsoUser
from app.services.asset_labels import load_type_names
from app.services.audit_snapshot import load_snapshot, save_snapshot
from app.services.audit_scopes import has_pi_access, parse_granted_scopes
from app.services.character_roster import load_roster
from app.services.esi import bearer_token, resolve_universe_names

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; pi)"

# Common PI pin type IDs (command / storage / launchpad / ECU / processors)
STORAGE_TYPE_IDS = frozenset({2254, 2255, 2256, 2263, 2264})
EXTRACTOR_TYPE_IDS = frozenset({2524, 2525, 2526, 2528, 2529, 2530})
PROCESSOR_TYPE_IDS = frozenset({2536, 2537, 2538})

STORAGE_CAPACITY_BY_TYPE: dict[int, int] = {
    2254: 500,   # Launchpad
    2255: 5000,  # Storage Facility
    2256: 5000,  # Basic Storage
    2263: 10000, # Advanced Storage
    2264: 10000, # High-Tech Storage
    2544: 10000, # Planetary Customs Office (import/export)
}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _pin_category(type_id: int, pin: dict) -> str:
    if type_id in EXTRACTOR_TYPE_IDS or pin.get("expiry_time"):
        return "extractor"
    if int(pin.get("schematic_id") or 0) > 0 or type_id in PROCESSOR_TYPE_IDS:
        return "factory"
    if type_id in STORAGE_TYPE_IDS:
        return "storage"
    return "other"


def _pin_contents(pin: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in pin.get("contents") or []:
        if not isinstance(item, dict):
            continue
        tid = int(item.get("type_id") or 0)
        amt = int(item.get("amount") or 0)
        if tid > 0 and amt > 0:
            rows.append({"type_id": tid, "amount": amt})
    return rows


def _storage_capacity(type_id: int, level: int) -> int:
    base = STORAGE_CAPACITY_BY_TYPE.get(type_id, 5000)
    return int(base * max(1, level + 1))


def analyze_colony(
    *,
    planet_id: int,
    colony_meta: dict,
    layout: dict,
    type_names: dict[int, str],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive per-planet PI status from ESI colony layout."""
    now = now or datetime.now(UTC)
    pins = [p for p in (layout.get("pins") or []) if isinstance(p, dict)]
    pin_rows: list[dict[str, Any]] = []
    active_extractors = 0
    expired_extractors = 0
    next_expiry: datetime | None = None
    storage_used = 0
    storage_capacity = 0
    attention: list[str] = []

    for pin in pins:
        pin_id = int(pin.get("pin_id") or 0)
        type_id = int(pin.get("type_id") or 0)
        category = _pin_category(type_id, pin)
        level = int(pin.get("level") or 0)
        expiry = _parse_ts(pin.get("expiry_time"))
        last_cycle = _parse_ts(pin.get("last_cycle_start"))
        contents = _pin_contents(pin)
        content_total = sum(c["amount"] for c in contents)
        type_name = type_names.get(type_id, f"Pin {type_id}")

        content_labels = [
            f"{type_names.get(c['type_id'], c['type_id'])} ×{c['amount']:,}" for c in contents[:6]
        ]

        pin_rows.append(
            {
                "pin_id": pin_id,
                "type_id": type_id,
                "type_name": type_name,
                "category": category,
                "level": level,
                "expiry_time": expiry.isoformat() if expiry else None,
                "last_cycle_start": last_cycle.isoformat() if last_cycle else None,
                "product_type_id": int(pin.get("product_type_id") or 0) or None,
                "schematic_id": int(pin.get("schematic_id") or 0) or None,
                "contents": contents,
                "contents_label": ", ".join(content_labels) if content_labels else "—",
                "content_total": content_total,
            }
        )

        if category == "extractor":
            if expiry and expiry > now:
                active_extractors += 1
                if next_expiry is None or expiry < next_expiry:
                    next_expiry = expiry
            else:
                expired_extractors += 1
                if expiry and expiry <= now:
                    attention.append(f"Extractor {type_name} head expired — redeploy required")

        if category in {"storage", "other"} and contents:
            cap = _storage_capacity(type_id, level) if type_id in STORAGE_TYPE_IDS else max(content_total, 5000)
            storage_used += content_total
            storage_capacity += cap
            pct = (content_total / cap * 100) if cap else 0
            if pct >= 85:
                attention.append(f"{type_name} storage {pct:.0f}% full")

    if not active_extractors and len(pins) > 1:
        attention.append("No active extractors — planet idle")

    storage_pct = (storage_used / storage_capacity * 100) if storage_capacity else 0
    status = "ok"
    if expired_extractors and not active_extractors:
        status = "idle"
    if attention:
        status = "attention" if active_extractors else "idle"

    hours_to_expiry: float | None = None
    if next_expiry:
        hours_to_expiry = max(0.0, (next_expiry - now).total_seconds() / 3600)

    return {
        "planet_id": planet_id,
        "solar_system_id": int(colony_meta.get("solar_system_id") or 0),
        "planet_type": str(colony_meta.get("planet_type") or "unknown"),
        "upgrade_level": int(colony_meta.get("upgrade_level") or 0),
        "num_pins": len(pins),
        "active_extractors": active_extractors,
        "expired_extractors": expired_extractors,
        "storage_used": storage_used,
        "storage_capacity_est": storage_capacity,
        "storage_fill_pct": round(storage_pct, 1),
        "next_expiry_at": next_expiry.isoformat() if next_expiry else None,
        "hours_to_expiry": round(hours_to_expiry, 2) if hours_to_expiry is not None else None,
        "status": status,
        "attention_reasons": attention,
        "pins": pin_rows,
    }


def _extractor_state(colony: dict) -> dict[int, dict]:
    """pin_id -> signature for change detection."""
    out: dict[int, dict] = {}
    for pin in colony.get("pins") or []:
        if not isinstance(pin, dict):
            continue
        pin_id = int(pin.get("pin_id") or 0)
        if pin_id <= 0:
            continue
        out[pin_id] = {
            "expiry_time": str(pin.get("expiry_time") or ""),
            "last_cycle_start": str(pin.get("last_cycle_start") or ""),
            "product_type_id": int(pin.get("product_type_id") or 0),
            "category": pin.get("category") or _pin_category(int(pin.get("type_id") or 0), pin),
        }
    return out


def colony_by_planet(snapshot: dict) -> dict[int, dict]:
    pi = snapshot.get("pi") if isinstance(snapshot.get("pi"), dict) else {}
    colonies = pi.get("colonies") if isinstance(pi.get("colonies"), list) else []
    return {int(c["planet_id"]): c for c in colonies if isinstance(c, dict) and c.get("planet_id")}


async def sync_character_pi(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient,
    character_id: int,
    headers: dict[str, str],
    granted: set[str],
) -> tuple[list[dict], str | None]:
    """Fetch PI colonies from ESI and return analyzed colony list."""
    if not has_pi_access(granted):
        return [], "Missing scope: esi-planets.manage_planets.v1"

    try:
        resp = await client.get(f"{_ESI}/characters/{character_id}/planets/", headers=headers)
    except Exception:
        logger.exception("PI planet list failed for %s", character_id)
        return [], "PI planet list request failed"

    if resp.status_code in (401, 403):
        return [], "Missing scope or token for PI (esi-planets.manage_planets.v1)"
    if resp.status_code != 200:
        return [], f"PI list HTTP {resp.status_code}"

    colonies_raw = resp.json()
    if not isinstance(colonies_raw, list):
        return [], None

    type_ids: set[int] = set()
    colonies_out: list[dict] = []
    now = datetime.now(UTC)

    layout_errors: list[str] = []
    for entry in colonies_raw:
        if not isinstance(entry, dict):
            continue
        planet_id = int(entry.get("planet_id") or 0)
        if planet_id <= 0:
            continue
        try:
            detail_resp = await client.get(
                f"{_ESI}/characters/{character_id}/planets/{planet_id}/",
                headers=headers,
            )
        except Exception:
            logger.exception("PI layout failed for %s planet %s", character_id, planet_id)
            layout_errors.append(f"Planet {planet_id}: layout request failed")
            continue
        if detail_resp.status_code != 200:
            layout_errors.append(f"Planet {planet_id}: HTTP {detail_resp.status_code}")
            continue
        layout = detail_resp.json()
        if not isinstance(layout, dict):
            continue
        for pin in layout.get("pins") or []:
            if isinstance(pin, dict):
                type_ids.add(int(pin.get("type_id") or 0))
                for c in _pin_contents(pin):
                    type_ids.add(int(c["type_id"]))

        type_names = await load_type_names(session, type_ids)
        analyzed = analyze_colony(
            planet_id=planet_id,
            colony_meta=entry,
            layout=layout,
            type_names=type_names,
            now=now,
        )
        system_id = analyzed["solar_system_id"]
        system_name = ""
        if system_id:
            row = await session.scalar(select(SdeSystem).where(SdeSystem.system_id == system_id))
            system_name = row.name if row else ""
            if not system_name:
                resolved = await resolve_universe_names([system_id])
                system_name = resolved.get(system_id, f"System {system_id}")
        analyzed["system_name"] = system_name
        colonies_out.append(analyzed)

    if layout_errors and not colonies_out:
        return [], "; ".join(layout_errors[:3])
    if layout_errors:
        logger.warning("PI partial layout errors for %s: %s", character_id, layout_errors)
    return colonies_out, None


async def persist_character_pi_snapshot(
    session: AsyncSession,
    character_id: int,
) -> tuple[int, str | None]:
    """Fetch PI from ESI and merge into the character audit snapshot."""
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    granted = parse_granted_scopes(user.scopes_json if user else "")
    if not has_pi_access(granted):
        return 0, "Missing scope: esi-planets.manage_planets.v1"

    token = await bearer_token(session, character_id=character_id)
    if not token:
        return 0, "No valid SSO token — log in again."

    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    if profile is None:
        profile = AuditProfile(
            character_id=character_id,
            character_name=user.character_name if user else f"Character {character_id}",
            corporation_name=user.corporation_name if user else "",
        )
        session.add(profile)
        await session.flush()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": _UA,
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        colonies, pi_err = await sync_character_pi(
            session,
            client=client,
            character_id=character_id,
            headers=headers,
            granted=granted,
        )

    prev_snapshot = load_snapshot(profile)
    snapshot = dict(prev_snapshot)
    scope_errors = dict(snapshot.get("scope_errors") or {})
    if pi_err:
        scope_errors["pi"] = pi_err
    else:
        scope_errors.pop("pi", None)
    if scope_errors:
        snapshot["scope_errors"] = scope_errors
    elif "scope_errors" in snapshot:
        snapshot.pop("scope_errors", None)
    snapshot["pi"] = {
        "colonies": colonies,
        "synced_at": datetime.now(UTC).isoformat(),
    }
    save_snapshot(profile, snapshot)

    try:
        from app.services.webhook_notification_engine import evaluate_webhook_notifications

        char_name = profile.character_name or (user.character_name if user else f"Character {character_id}")
        await evaluate_webhook_notifications(
            session,
            character_id,
            character_name=char_name,
            prev_snapshot=prev_snapshot,
            new_snapshot=snapshot,
            scope_errors=scope_errors if scope_errors else None,
        )
    except Exception:
        logger.exception("PI webhook dispatch failed for %s", character_id)

    return len(colonies), pi_err


def _pi_snapshot_stale(snapshot: dict, *, max_age_minutes: int = 30) -> bool:
    pi = snapshot.get("pi") if isinstance(snapshot.get("pi"), dict) else {}
    synced_at = pi.get("synced_at")
    if not synced_at:
        return True
    try:
        ts = datetime.fromisoformat(str(synced_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    return datetime.now(UTC) - ts > timedelta(minutes=max(5, max_age_minutes))


async def refresh_roster_pi_snapshots(
    session: AsyncSession,
    viewer_character_id: int,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Ensure linked characters with PI scope have colony data in audit snapshots."""
    roster = await load_roster(session, viewer_character_id)
    if not roster:
        return {"refreshed": 0, "skipped": 0, "colonies": 0}

    ids = [int(r.character_id) for r in roster if r.token_valid]
    profiles = (
        await session.scalars(select(AuditProfile).where(AuditProfile.character_id.in_(ids)))
    ).all()
    profile_map = {int(p.character_id): p for p in profiles}

    refreshed = 0
    skipped = 0
    colonies = 0
    for cid in ids:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == cid))
        granted = parse_granted_scopes(user.scopes_json if user else "")
        if not has_pi_access(granted):
            skipped += 1
            continue
        profile = profile_map.get(cid)
        snap = load_snapshot(profile)
        if not force and not _pi_snapshot_stale(snap):
            colonies += len((snap.get("pi") or {}).get("colonies") or [])
            skipped += 1
            continue
        count, _err = await persist_character_pi_snapshot(session, cid)
        refreshed += 1
        colonies += count

    return {"refreshed": refreshed, "skipped": skipped, "colonies": colonies}


async def build_roster_pi_overview(
    session: AsyncSession,
    viewer_character_id: int,
    *,
    refresh: bool = True,
) -> dict:
    if refresh:
        await refresh_roster_pi_snapshots(session, viewer_character_id)

    roster = await load_roster(session, viewer_character_id)
    if not roster:
        return {"character_count": 0, "colony_count": 0, "colonies": [], "attention_count": 0}

    ids = [int(r.character_id) for r in roster]
    profiles = (
        await session.scalars(select(AuditProfile).where(AuditProfile.character_id.in_(ids)))
    ).all()
    profile_map = {int(p.character_id): p for p in profiles}
    name_map = {int(r.character_id): r.character_name for r in roster}

    colonies: list[dict] = []
    for cid in ids:
        profile = profile_map.get(cid)
        snap = load_snapshot(profile)
        pi = snap.get("pi") if isinstance(snap.get("pi"), dict) else {}
        for colony in pi.get("colonies") or []:
            if not isinstance(colony, dict):
                continue
            colonies.append(
                {
                    **colony,
                    "character_id": cid,
                    "character_name": name_map.get(cid, f"Char {cid}"),
                }
            )

    attention = sum(1 for c in colonies if c.get("status") in {"attention", "idle"})
    scope_errors: dict[str, str] = {}
    scope_error_details: list[dict[str, Any]] = []
    pi_scope_count = 0
    for cid in ids:
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == cid))
        granted = parse_granted_scopes(user.scopes_json if user else "")
        if not has_pi_access(granted):
            continue
        pi_scope_count += 1
        profile = profile_map.get(cid)
        snap = load_snapshot(profile)
        err = (snap.get("scope_errors") or {}).get("pi")
        if err:
            scope_errors[str(cid)] = err
            scope_error_details.append(
                {
                    "character_id": cid,
                    "character_name": name_map.get(cid, f"Character {cid}"),
                    "message": err,
                }
            )

    return {
        "character_count": len(roster),
        "colony_count": len(colonies),
        "attention_count": attention,
        "pi_scope_character_count": pi_scope_count,
        "scope_errors": scope_errors,
        "scope_error_details": scope_error_details,
        "colonies": sorted(
            colonies,
            key=lambda c: (
                0 if c.get("status") == "attention" else 1 if c.get("status") == "idle" else 2,
                c.get("hours_to_expiry") if c.get("hours_to_expiry") is not None else 9999,
            ),
        ),
        "scope_note": (
            "PI data updates when colonies are viewed in-game and on audit sync. "
            "Requires esi-planets.manage_planets.v1 scope."
        ),
    }


def detect_pi_webhook_events(
    *,
    match_json: str,
    event_type: str,
    character_id: int,
    character_name: str,
    prev_snapshot: dict,
    new_snapshot: dict,
) -> list[dict[str, Any]]:
    """Return event dicts for webhook engine (title, body, event_key, payload)."""
    import json

    try:
        cfg = json.loads(match_json or "{}")
        if not isinstance(cfg, dict):
            cfg = {}
    except json.JSONDecodeError:
        cfg = {}

    planet_filter = {int(x) for x in cfg.get("planet_ids") or []}
    hours_before = float(cfg.get("hours_before") or 4)
    storage_pct_threshold = float(cfg.get("storage_pct") or 85)
    now = datetime.now(UTC)

    prev_colonies = colony_by_planet(prev_snapshot)
    new_colonies = colony_by_planet(new_snapshot)
    events: list[dict[str, Any]] = []

    for planet_id, colony in new_colonies.items():
        if planet_filter and planet_id not in planet_filter:
            continue
        prev = prev_colonies.get(planet_id, {})
        system = colony.get("system_name") or f"Planet {planet_id}"
        label = f"{system} ({colony.get('planet_type', '?')})"

        if event_type == "pi_planet_idle":
            prev_active = int(prev.get("active_extractors") or 0)
            new_active = int(colony.get("active_extractors") or 0)
            if new_active == 0 and int(colony.get("num_pins") or 0) > 1 and prev_active > 0:
                events.append(
                    {
                        "event_key": f"pi_idle:{planet_id}",
                        "title": f"{character_name}: PI planet idle",
                        "body": f"{label} — no active extractors",
                        "payload": {"character_id": character_id, "planet_id": planet_id, "colony": colony},
                    }
                )
            elif new_active == 0 and int(colony.get("num_pins") or 0) > 1 and not prev:
                events.append(
                    {
                        "event_key": f"pi_idle:{planet_id}",
                        "title": f"{character_name}: PI planet idle",
                        "body": f"{label} — colony has no running extractors",
                        "payload": {"character_id": character_id, "planet_id": planet_id, "colony": colony},
                    }
                )

        elif event_type == "pi_extraction_complete":
            prev_pins = _extractor_state(prev)
            new_pins = _extractor_state(colony)
            for pin_id, sig in new_pins.items():
                if sig["category"] != "extractor":
                    continue
                old = prev_pins.get(pin_id)
                if not old:
                    continue
                cycle_changed = (
                    sig["last_cycle_start"]
                    and old.get("last_cycle_start")
                    and sig["last_cycle_start"] != old.get("last_cycle_start")
                )
                old_exp = _parse_ts(old.get("expiry_time"))
                new_exp = _parse_ts(sig.get("expiry_time"))
                head_depleted = old_exp and old_exp > now and new_exp and new_exp <= now
                if cycle_changed or head_depleted:
                    reason = "extractor head depleted" if head_depleted else "extraction cycle completed"
                    events.append(
                        {
                            "event_key": f"pi_extract:{planet_id}:{pin_id}:{sig.get('last_cycle_start')}",
                            "title": f"{character_name}: PI extraction complete",
                            "body": f"{label} — pin {pin_id}: {reason}",
                            "payload": {
                                "character_id": character_id,
                                "planet_id": planet_id,
                                "pin_id": pin_id,
                                "reason": reason,
                            },
                        }
                    )

        elif event_type == "pi_extractor_expiring":
            hours_to = colony.get("hours_to_expiry")
            if hours_to is not None and float(hours_to) <= hours_before:
                prev_hours = prev.get("hours_to_expiry")
                if prev_hours is None or float(prev_hours) > hours_before:
                    events.append(
                        {
                            "event_key": f"pi_expiring:{planet_id}:{colony.get('next_expiry_at')}",
                            "title": f"{character_name}: PI extractor expiring",
                            "body": f"{label} — head expires in {float(hours_to):.1f}h",
                            "payload": {
                                "character_id": character_id,
                                "planet_id": planet_id,
                                "hours_to_expiry": hours_to,
                            },
                        }
                    )

        elif event_type == "pi_storage_attention":
            pct = float(colony.get("storage_fill_pct") or 0)
            prev_pct = float(prev.get("storage_fill_pct") or 0)
            if pct >= storage_pct_threshold and prev_pct < storage_pct_threshold:
                events.append(
                    {
                        "event_key": f"pi_storage:{planet_id}:{int(pct)}",
                        "title": f"{character_name}: PI storage filling up",
                        "body": f"{label} — storage ~{pct:.0f}% full",
                        "payload": {
                            "character_id": character_id,
                            "planet_id": planet_id,
                            "storage_fill_pct": pct,
                        },
                    }
                )

    return events
