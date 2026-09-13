"""Persist character audit snapshot (skills, location, clones, contracts)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.character_skills import CharacterSkillLevel
from app.models.tools import AuditProfile, SdeSystem, SdeTypeIndex, SsoUser
from app.services.audit_scopes import (
    has_clones_access,
    has_contracts_access,
    has_killmails_access,
    has_location_access,
    has_mail_access,
    has_pi_access,
    has_skill_queue_access,
    has_skills_access,
)
from app.services.audit_extras import sync_combat_log, sync_corp_history, sync_mail_headers
from app.services.audit_extended import sync_audit_extended
from app.services.esi import esi_get_paged_list, resolve_universe_names
from app.services.location_display import resolve_location_labels
from app.services.skill_ranks import load_skill_ranks
from app.services.skill_sp import cumulative_skill_sp
from app.services.universe_locations import ensure_universe_locations

logger = logging.getLogger(__name__)
_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; audit)"


def load_snapshot(profile: AuditProfile | None) -> dict[str, Any]:
    if not profile or not profile.snapshot_json:
        return {}
    try:
        data = json.loads(profile.snapshot_json)
        return data if isinstance(data, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def save_snapshot(profile: AuditProfile, snapshot: dict[str, Any]) -> None:
    snapshot.pop("skills", None)
    contracts = snapshot.get("contracts")
    if isinstance(contracts, list) and len(contracts) > 40:
        snapshot["contracts"] = contracts[:40]
    mail = snapshot.get("mail")
    if isinstance(mail, list) and len(mail) > 80:
        snapshot["mail"] = mail[:80]
    combat = snapshot.get("combat_log")
    if isinstance(combat, list) and len(combat) > 50:
        snapshot["combat_log"] = combat[:50]
    pi = snapshot.get("pi")
    if isinstance(pi, dict):
        colonies = pi.get("colonies")
        if isinstance(colonies, list) and len(colonies) > 25:
            pi["colonies"] = colonies[:25]
    for key, limit in (
        ("standings", 120),
        ("contacts", 200),
        ("eve_notifications", 80),
        ("calendar_events", 60),
        ("loyalty_points", 40),
    ):
        chunk = snapshot.get(key)
        if isinstance(chunk, list) and len(chunk) > limit:
            snapshot[key] = chunk[:limit]
    snapshot["wallet_balance_isk"] = str(profile.wallet_balance_isk)
    snapshot["synced_at"] = datetime.now(UTC).isoformat()
    profile.snapshot_json = json.dumps(snapshot)


async def _type_names(session: AsyncSession, type_ids: set[int]) -> dict[int, str]:
    if not type_ids:
        return {}
    rows = await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))
    return {int(r.type_id): r.name for r in rows.all()}


async def _persist_skills(
    session: AsyncSession,
    *,
    character_id: int,
    character_name: str,
    skills_body: dict,
    training_skill_id: int | None,
) -> list[dict]:
    await session.execute(
        delete(CharacterSkillLevel).where(CharacterSkillLevel.character_id == character_id)
    )
    type_ids = {
        int(row.get("skill_id") or 0)
        for row in skills_body.get("skills") or []
        if isinstance(row, dict) and int(row.get("skill_id") or 0) > 0
    }
    names = await _type_names(session, type_ids)
    meta_rows = (
        await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids)))
    ).all() if type_ids else []
    groups = {int(r.type_id): r.group_name for r in meta_rows}
    rank_map = load_skill_ranks(list(type_ids))

    out: list[dict] = []
    for row in skills_body.get("skills") or []:
        if not isinstance(row, dict):
            continue
        sid = int(row.get("skill_id") or 0)
        if sid <= 0:
            continue
        trained = int(row.get("trained_skill_level") or 0)
        active = int(row.get("active_skill_level") or trained)
        sp_in_skill = int(row.get("skillpoints_in_skill") or 0)
        if trained > 0 and sp_in_skill <= 0:
            sp_in_skill = cumulative_skill_sp(trained, rank_map.get(sid, 1))
        session.add(
            CharacterSkillLevel(
                character_id=character_id,
                character_name=character_name,
                skill_type_id=sid,
                skill_name=names.get(sid, f"Type {sid}"),
                trained_level=trained,
                skillpoints_in_skill=sp_in_skill,
            )
        )
        out.append(
            {
                "skill_type_id": sid,
                "skill_name": names.get(sid, f"Type {sid}"),
                "skill_group": groups.get(sid) or "Other",
                "trained_level": trained,
                "active_level": active,
                "skillpoints_in_skill": sp_in_skill,
                "is_training": training_skill_id == sid,
            }
        )
    out.sort(key=lambda r: (-r["trained_level"], r["skill_name"].lower()))
    return out


async def _location_meta_for_ids(
    session: AsyncSession,
    entity_ids: list[int],
    *,
    character_id: int,
    access_token: str | None = None,
) -> dict[int, dict[str, Any]]:
    unique = [i for i in sorted({int(i) for i in entity_ids if int(i) > 0})]
    if not unique:
        return {}

    from app.services.location_display import resolve_location_labels

    labels = await resolve_location_labels(
        session,
        unique,
        character_id=character_id,
        access_token=access_token,
    )
    locs = await ensure_universe_locations(
        session,
        unique,
        character_id=character_id,
        access_token=access_token,
        force=True,
    )
    sys_ids = {int(l.solar_system_id) for l in locs.values() if l.solar_system_id}
    sys_names: dict[int, str] = {}
    if sys_ids:
        rows = await session.scalars(select(SdeSystem).where(SdeSystem.system_id.in_(sys_ids)))
        sys_names = {int(r.system_id): r.name for r in rows.all()}

    out: dict[int, dict[str, Any]] = {}
    for eid in unique:
        row = locs.get(eid)
        sid = int(row.solar_system_id) if row and row.solar_system_id else None
        out[eid] = {
            "location_name": labels.get(eid) or (row.name if row else f"Location {eid}"),
            "solar_system_id": sid,
            "solar_system_name": sys_names.get(sid) if sid else None,
        }
    return out


async def _resolve_location(session: AsyncSession, body: dict, *, character_id: int) -> dict:
    solar_system_id = int(body.get("solar_system_id") or 0)
    station_id = body.get("station_id")
    structure_id = body.get("structure_id")
    loc_entity_ids: list[int] = []
    if station_id:
        loc_entity_ids.append(int(station_id))
    if structure_id:
        loc_entity_ids.append(int(structure_id))
    meta = await _location_meta_for_ids(session, loc_entity_ids, character_id=character_id)
    names = await resolve_universe_names([solar_system_id])
    parts: list[str] = []
    if station_id:
        sid = int(station_id)
        parts.append(meta.get(sid, {}).get("location_name") or names.get(sid) or f"Station {sid}")
    elif structure_id:
        stid = int(structure_id)
        parts.append(meta.get(stid, {}).get("location_name") or names.get(stid) or f"Structure {stid}")
    if solar_system_id and solar_system_id in names:
        parts.append(names[solar_system_id])
    label = " — ".join(parts) if parts else "Unknown location"
    station_meta = meta.get(int(station_id)) if station_id else None
    structure_meta = meta.get(int(structure_id)) if structure_id else None
    return {
        "solar_system_id": solar_system_id or None,
        "station_id": int(station_id) if station_id else None,
        "structure_id": int(structure_id) if structure_id else None,
        "system_name": names.get(solar_system_id),
        "location_name": label,
        "station_name": station_meta.get("location_name") if station_meta else None,
        "structure_name": structure_meta.get("location_name") if structure_meta else None,
    }


async def sync_audit_snapshot(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient,
    character_id: int,
    headers: dict[str, str],
    granted: set[str],
    user: SsoUser | None,
    profile: AuditProfile,
    scope_errors: dict[str, str],
) -> dict[str, Any]:
    snapshot = load_snapshot(profile)
    character_name = profile.character_name or (user.character_name if user else f"Character {character_id}")

    if has_skills_access(granted):
        try:
            sk_resp = await client.get(f"{_ESI}/characters/{character_id}/skills/", headers=headers)
            if sk_resp.status_code == 200:
                body = sk_resp.json()
                profile.skill_points = int(body.get("total_sp") or 0)
                queue: list[dict] = []
                if has_skill_queue_access(granted):
                    q_resp = await client.get(
                        f"{_ESI}/characters/{character_id}/skillqueue/", headers=headers
                    )
                    if q_resp.status_code == 200 and isinstance(q_resp.json(), list):
                        queue = [r for r in q_resp.json() if isinstance(r, dict)]
                    elif q_resp.status_code in (401, 403):
                        scope_errors["skill_queue"] = "Missing scope: esi-skills.read_skillqueue.v1"
                    elif q_resp.status_code == 420:
                        scope_errors["skill_queue"] = "ESI rate limit — retry on next sync"
                else:
                    scope_errors["skill_queue"] = "Missing scope: esi-skills.read_skillqueue.v1"
                training_skill_id: int | None = None
                if queue:
                    training_skill_id = int(queue[0].get("skill_id") or 0) or None
                await _persist_skills(
                    session,
                    character_id=character_id,
                    character_name=character_name,
                    skills_body=body,
                    training_skill_id=training_skill_id,
                )
                snapshot.pop("skills", None)
                skill_ids = {int(q.get("skill_id") or 0) for q in queue}
                q_names = await _type_names(session, skill_ids)
                snapshot["skill_queue"] = [
                    {
                        "skill_type_id": int(q.get("skill_id") or 0),
                        "skill_name": q_names.get(int(q.get("skill_id") or 0), f"Type {q.get('skill_id')}"),
                        "finished_level": int(q.get("finished_level") or 0),
                        "queue_position": int(q.get("queue_position") or 0),
                        "finish_date": q.get("finish_date"),
                        "start_date": q.get("start_date"),
                    }
                    for q in queue
                    if int(q.get("skill_id") or 0) > 0
                ]
            elif sk_resp.status_code in (401, 403):
                scope_errors["skills"] = sk_resp.text[:200]
            elif sk_resp.status_code == 420:
                scope_errors["skills"] = "ESI rate limit — retry on next sync"
        except Exception:
            logger.exception("audit skills snapshot failed for %s", character_id)
    else:
        scope_errors["skills"] = "Missing scope: esi-skills.read_skills.v1"

    if has_location_access(granted):
        try:
            loc_resp = await client.get(f"{_ESI}/characters/{character_id}/location/", headers=headers)
            if loc_resp.status_code == 200 and isinstance(loc_resp.json(), dict):
                snapshot["location"] = await _resolve_location(session, loc_resp.json(), character_id=character_id)
            elif loc_resp.status_code in (401, 403):
                scope_errors["location"] = loc_resp.text[:200]
        except Exception:
            logger.exception("audit location sync failed for %s", character_id)
    else:
        scope_errors["location"] = "Missing scope: esi-location.read_location.v1"

    if has_clones_access(granted):
        try:
            clone_resp = await client.get(f"{_ESI}/characters/{character_id}/clones/", headers=headers)
            imp_resp = await client.get(f"{_ESI}/characters/{character_id}/implants/", headers=headers)
            clones_body = clone_resp.json() if clone_resp.status_code == 200 else {}
            implants_body = imp_resp.json() if imp_resp.status_code == 200 else []
            if isinstance(clones_body, dict):
                jump_clones = clones_body.get("jump_clones") or []
                loc_ids: list[int] = []
                for jc in jump_clones:
                    if isinstance(jc, dict):
                        loc_ids.append(int(jc.get("location_id") or 0))
                auth = str(headers.get("Authorization") or "")
                access_token = auth[7:].strip() if auth.startswith("Bearer ") else None
                loc_meta = await _location_meta_for_ids(
                    session,
                    loc_ids,
                    character_id=character_id,
                    access_token=access_token,
                )
                implant_ids = {
                    int(i.get("type_id") or 0)
                    for i in (implants_body if isinstance(implants_body, list) else [])
                    if isinstance(i, dict)
                }
                imp_names = await _type_names(session, implant_ids)
                implants_list = [
                    {
                        "type_id": int(i.get("type_id") or 0),
                        "type_name": imp_names.get(int(i.get("type_id") or 0), f"Type {i.get('type_id')}"),
                    }
                    for i in (implants_body if isinstance(implants_body, list) else [])
                    if isinstance(i, dict) and int(i.get("type_id") or 0) > 0
                ]
                snapshot["clones"] = {
                    "last_clone_jump_date": clones_body.get("last_clone_jump_date"),
                    "last_station_change_date": clones_body.get("last_station_change_date"),
                    "active_implants": implants_list,
                    "jump_clones": [
                        {
                            "jump_clone_id": int(jc.get("jump_clone_id") or 0),
                            "location_id": int(jc.get("location_id") or 0),
                            "location_name": loc_meta.get(int(jc.get("location_id") or 0), {}).get("location_name"),
                            "solar_system_id": loc_meta.get(int(jc.get("location_id") or 0), {}).get("solar_system_id"),
                            "solar_system_name": loc_meta.get(int(jc.get("location_id") or 0), {}).get("solar_system_name"),
                            "name": (jc.get("name") or "").strip() or f"Clone {int(jc.get('jump_clone_id') or 0)}",
                            "implants": [
                                int(tid)
                                for tid in (jc.get("implants") or [])
                                if int(tid or 0) > 0
                            ],
                        }
                        for jc in jump_clones
                        if isinstance(jc, dict)
                    ],
                }
                all_imp_ids = set(implant_ids)
                for jc in snapshot["clones"]["jump_clones"]:
                    all_imp_ids.update(jc.get("implants") or [])
                imp_all_names = await _type_names(session, all_imp_ids)
                for jc in snapshot["clones"]["jump_clones"]:
                    jc["implant_details"] = [
                        {"type_id": tid, "type_name": imp_all_names.get(tid, f"Type {tid}")}
                        for tid in jc.get("implants") or []
                    ]
            elif clone_resp.status_code in (401, 403):
                scope_errors["clones"] = clone_resp.text[:200]
        except Exception:
            logger.exception("audit clones sync failed for %s", character_id)
    else:
        scope_errors["clones"] = "Missing scope: esi-clones.read_clones.v1"

    if has_contracts_access(granted):
        try:
            contracts = await esi_get_paged_list(
                f"/characters/{character_id}/contracts/",
                auth=True,
                session=session,
                character_id=character_id,
                max_pages=10,
            )
            issuer_ids = {
                int(c.get("issuer_corporation_id") or 0)
                for c in contracts
                if isinstance(c, dict)
            }
            issuer_names = await resolve_universe_names([i for i in issuer_ids if i > 0])
            location_ids = {
                int(c.get("start_location_id") or 0)
                for c in contracts
                if isinstance(c, dict) and int(c.get("start_location_id") or 0) > 0
            }
            location_names = await resolve_location_labels(
                session,
                list(location_ids),
                character_id=character_id,
            )
            snapshot["contracts"] = [
                {
                    "contract_id": int(c.get("contract_id") or 0),
                    "type": c.get("type"),
                    "status": c.get("status"),
                    "title": c.get("title") or "",
                    "for_corporation": bool(c.get("for_corporation")),
                    "issuer_corporation_id": int(c.get("issuer_corporation_id") or 0),
                    "issuer_corporation_name": issuer_names.get(int(c.get("issuer_corporation_id") or 0)),
                    "issuer_id": int(c.get("issuer_id") or 0),
                    "assignee_id": c.get("assignee_id"),
                    "acceptor_id": c.get("acceptor_id"),
                    "start_date": c.get("date_issued"),
                    "date_expired": c.get("date_expired"),
                    "date_completed": c.get("date_completed"),
                    "price": c.get("price"),
                    "reward": c.get("reward"),
                    "collateral": c.get("collateral"),
                    "buyout": c.get("buyout"),
                    "volume": c.get("volume"),
                    "location_id": c.get("start_location_id"),
                    "location_name": location_names.get(int(c.get("start_location_id") or 0)),
                }
                for c in contracts
                if isinstance(c, dict) and int(c.get("contract_id") or 0) > 0
            ]
            snapshot["contracts"].sort(
                key=lambda r: str(r.get("start_date") or ""),
                reverse=True,
            )
            snapshot["contracts"] = snapshot["contracts"][:40]
        except Exception:
            logger.exception("audit contracts sync failed for %s", character_id)
    else:
        scope_errors["contracts"] = "Missing scope: esi-contracts.read_character_contracts.v1"

    try:
        snapshot["corp_history"] = await sync_corp_history(client, character_id)
    except Exception:
        logger.exception("audit corp history sync failed for %s", character_id)
        snapshot.setdefault("corp_history", [])

    if has_mail_access(granted):
        try:
            snapshot["mail"] = await sync_mail_headers(
                session,
                character_id=character_id,
                granted=granted,
            )
        except Exception:
            logger.exception("audit mail sync failed for %s", character_id)
            snapshot.setdefault("mail", [])
    else:
        scope_errors["mail"] = "Missing scope: esi-mail.read_mail.v1"

    if has_killmails_access(granted):
        try:
            snapshot["combat_log"] = await sync_combat_log(
                session,
                client,
                character_id=character_id,
                headers=headers,
                granted=granted,
            )
        except Exception:
            logger.exception("audit combat sync failed for %s", character_id)
            snapshot.setdefault("combat_log", [])
    else:
        scope_errors["combat"] = "Missing scope: esi-killmails.read_killmails.v1"

    if has_pi_access(granted):
        try:
            from app.services.pi_sync import sync_character_pi

            colonies, pi_err = await sync_character_pi(
                session,
                client=client,
                character_id=character_id,
                headers=headers,
                granted=granted,
            )
            snapshot["pi"] = {
                "colonies": colonies,
                "synced_at": datetime.now(UTC).isoformat(),
            }
            if pi_err:
                scope_errors["pi"] = pi_err
        except Exception:
            logger.exception("audit PI sync failed for %s", character_id)
            scope_errors["pi"] = "PI sync failed"
    else:
        scope_errors["pi"] = "Missing scope: esi-planets.manage_planets.v1"

    if user:
        try:
            from app.services.character_titles import sync_character_corp_titles

            titles = await sync_character_corp_titles(
                session,
                character_id=character_id,
                corporation_id=int(user.corporation_id or 0),
                scopes_json=user.scopes_json or "[]",
            )
            if titles:
                snapshot["corp_titles"] = titles
        except Exception:
            logger.exception("audit titles sync failed for %s", character_id)

    await sync_audit_extended(
        session,
        client=client,
        character_id=character_id,
        headers=headers,
        granted=granted,
        snapshot=snapshot,
        scope_errors=scope_errors,
    )

    if scope_errors:
        snapshot["scope_errors"] = dict(scope_errors)
    save_snapshot(profile, snapshot)
    return snapshot
