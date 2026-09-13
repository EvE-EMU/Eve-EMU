"""Character sheet payload — audit profile, skills, assets, wallet."""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.character_skills import CharacterSkillLevel
from app.models.member_audit import AuditSecurityFlag, CharacterAsset, CharacterWalletJournal
from app.models.tools import AuditProfile, CharacterMarketOrder, LinkedCharacter, SdeSystem, SdeTypeIndex, SsoUser
from app.services.audit_scopes import (
    has_assets_access,
    has_clones_access,
    has_contracts_access,
    has_killmails_access,
    has_location_access,
    has_mail_access,
    has_skill_queue_access,
    has_skills_access,
    has_wallet_access,
    missing_scopes,
    parse_granted_scopes,
    scope_status,
)
from app.services.audit_snapshot import load_snapshot
from app.services.asset_labels import asset_display_name, flag_label, load_type_names, resolve_type_name
from app.services.eve_time import format_eve_time, next_sync_at
from app.services.jump_drive import distance_ly
from app.services.route_planner import system_coords_map
from app.services.skill_ranks import load_skill_ranks
from app.services.skill_sp import cumulative_skill_sp, max_skill_sp
from app.services.universe_locations import ensure_universe_locations


async def _viewer_has_hr_lookup(
    session: AsyncSession,
    *,
    viewer_character_id: int,
    permissions: set[str],
) -> bool:
    if "audit.view" in permissions or "director" in permissions or "admin" in permissions:
        return True
    from app.services.hr_lookup import viewer_has_hr_lookup
    from app.services.rbac import UserAuthContext

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == viewer_character_id))
    if not user:
        return False
    ctx = UserAuthContext(
        character_id=viewer_character_id,
        character_name=user.character_name,
        corporation_id=int(user.corporation_id or 0),
        alliance_id=int(user.alliance_id) if user.alliance_id else None,
        state_name=None,
        state_id=None,
        permissions=permissions,
    )
    return await viewer_has_hr_lookup(session, ctx)


async def _market_orders_for_character(session: AsyncSession, character_id: int) -> list[dict]:
    rows = (
        await session.scalars(
            select(CharacterMarketOrder)
            .where(CharacterMarketOrder.character_id == character_id)
            .order_by(CharacterMarketOrder.issued_at.desc())
            .limit(40)
        )
    ).all()
    return [
        {
            "order_id": r.order_id,
            "type_id": r.type_id,
            "type_name": r.type_name,
            "is_buy_order": r.is_buy_order,
            "price": str(r.price),
            "volume_remain": r.volume_remain,
            "volume_total": r.volume_total,
            "location_name": r.location_name,
            "range_label": r.range_label,
            "issued_at": r.issued_at.isoformat() if r.issued_at else None,
        }
        for r in rows
    ]


async def viewable_character_ids(session: AsyncSession, character_id: int) -> set[int]:
    """Main + linked characters owned by the logged-in pilot."""
    ids = {character_id}
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if not user:
        return ids
    alts = await session.scalars(
        select(LinkedCharacter).where(LinkedCharacter.owner_user_id == user.id)
    )
    for alt in alts.all():
        ids.add(int(alt.character_id))
    return ids


async def can_view_character(
    session: AsyncSession,
    *,
    viewer_character_id: int,
    target_character_id: int,
    permissions: set[str],
) -> bool:
    if await _viewer_has_hr_lookup(
        session, viewer_character_id=viewer_character_id, permissions=permissions
    ):
        return True
    allowed = await viewable_character_ids(session, viewer_character_id)
    return target_character_id in allowed


async def _skills_for_character(
    session: AsyncSession, character_id: int, snapshot: dict
) -> list[dict]:
    training_id = 0
    for row in snapshot.get("skill_queue") or []:
        if isinstance(row, dict) and int(row.get("queue_position") or 0) == 0:
            training_id = int(row.get("skill_type_id") or 0)
            break

    trained_map: dict[int, dict] = {}
    db_rows = (
        await session.scalars(
            select(CharacterSkillLevel).where(CharacterSkillLevel.character_id == character_id)
        )
    ).all()
    if db_rows:
        type_ids = {int(r.skill_type_id) for r in db_rows}
        meta = {
            int(r.type_id): r
            for r in (
                await session.scalars(
                    select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids))
                )
            ).all()
        }
        for r in db_rows:
            sid = int(r.skill_type_id)
            m = meta.get(sid)
            trained_map[sid] = {
                "skill_type_id": sid,
                "skill_name": r.skill_name or (m.name if m else f"Type {sid}"),
                "skill_group": (m.group_name if m else "") or "Other",
                "trained_level": int(r.trained_level or 0),
                "active_level": int(r.trained_level or 0),
                "skillpoints_in_skill": int(getattr(r, "skillpoints_in_skill", 0) or 0),
                "is_training": sid == training_id and training_id > 0,
            }

    catalog = await session.scalars(
        select(SdeTypeIndex)
        .where(SdeTypeIndex.category_name == "Skill")
        .order_by(SdeTypeIndex.group_name, SdeTypeIndex.name)
    )
    catalog_rows = catalog.all()
    rank_map = load_skill_ranks([int(r.type_id) for r in catalog_rows])
    out: list[dict] = []
    for row in catalog_rows:
        sid = int(row.type_id)
        trained = trained_map.get(sid)
        level = int(trained.get("trained_level") or 0) if trained else 0
        active = int(trained.get("active_level") or level) if trained else 0
        rank = rank_map.get(sid, 1)
        sp_in = int(trained.get("skillpoints_in_skill") or 0) if trained and level > 0 else 0
        if level > 0 and sp_in <= 0:
            sp_in = cumulative_skill_sp(level, rank)
        out.append(
            {
                "skill_type_id": sid,
                "skill_name": row.name,
                "skill_group": row.group_name or "Other",
                "trained_level": level,
                "active_level": active,
                "skill_rank": rank,
                "skillpoints_in_skill": sp_in,
                "max_skillpoints": max_skill_sp(rank),
                "is_training": bool(trained.get("is_training")) if trained else False,
            }
        )
    return out


def _recent_skills(snapshot: dict, limit: int = 8) -> list[dict]:
    queue = [q for q in (snapshot.get("skill_queue") or []) if isinstance(q, dict)]
    if queue:
        return [
            {
                "skill_type_id": int(q.get("skill_type_id") or 0),
                "skill_name": q.get("skill_name") or f"Type {q.get('skill_type_id')}",
                "trained_level": int(q.get("finished_level") or 0),
                "active_level": int(q.get("finished_level") or 0),
                "is_training": i == 0,
                "finish_date": q.get("finish_date"),
                "queue_position": int(q.get("queue_position") or 0),
            }
            for i, q in enumerate(queue[:limit])
            if int(q.get("skill_type_id") or 0) > 0
        ]
    skills = [s for s in (snapshot.get("skills") or []) if isinstance(s, dict)]
    skills.sort(key=lambda s: (-int(s.get("trained_level") or 0), str(s.get("skill_name") or "")))
    return skills[:limit]


def _asset_kind(category_name: str, group_name: str, has_children: bool) -> str:
    cat = (category_name or "").strip().lower()
    group = (group_name or "").strip().lower()
    if cat == "ship":
        return "ship"
    if has_children or "container" in group or "freight container" in group:
        return "container"
    return "item"


def _count_asset_nodes(nodes: list[dict]) -> int:
    total = 0
    for node in nodes:
        total += 1
        total += _count_asset_nodes(node.get("children") or [])
    return total


def _build_asset_node(
    asset: CharacterAsset,
    *,
    children_map: dict[int, list[CharacterAsset]],
    type_meta: dict[int, SdeTypeIndex],
) -> dict:
    kids = children_map.get(asset.item_id, [])
    meta = type_meta.get(asset.type_id)
    category = meta.category_name if meta else ""
    group = meta.group_name if meta else ""
    kind = _asset_kind(category, group, bool(kids))
    custom = (getattr(asset, "custom_name", None) or "").strip()
    display = asset_display_name(
        type_id=int(asset.type_id),
        type_name=asset.type_name or "",
        custom_name=custom,
        flag=asset.flag or "",
    )
    child_nodes = [
        _build_asset_node(c, children_map=children_map, type_meta=type_meta)
        for c in sorted(kids, key=lambda a: ((getattr(a, "custom_name", None) or a.type_name or "").lower()))
    ]
    return {
        "item_id": int(asset.item_id),
        "type_id": int(asset.type_id),
        "type_name": display,
        "base_type_name": asset.type_name or f"Type {asset.type_id}",
        "custom_name": custom,
        "quantity": int(asset.quantity or 0),
        "flag": asset.flag or "",
        "flag_label": flag_label(asset.flag or ""),
        "kind": kind,
        "category_name": category,
        "children": child_nodes,
    }


async def _load_system_coords(session: AsyncSession, system_ids: set[int]) -> dict[int, tuple[float, float, float]]:
    if not system_ids:
        return {}
    rows = await session.scalars(select(SdeSystem).where(SdeSystem.system_id.in_(system_ids)))
    return system_coords_map({int(r.system_id): r for r in rows.all()})


async def _build_asset_locations(
    session: AsyncSession,
    assets: list[CharacterAsset],
    *,
    character_id: int,
    character_name: str,
    main_system_id: int | None = None,
) -> list[dict]:
    if not assets:
        return []

    by_item = {int(a.item_id): a for a in assets if int(a.item_id or 0) > 0}
    children_map: dict[int, list[CharacterAsset]] = defaultdict(list)
    roots_by_location: dict[int, list[CharacterAsset]] = defaultdict(list)

    for asset in assets:
        loc = int(asset.location_id or 0)
        if loc in by_item:
            children_map[loc].append(asset)
        else:
            roots_by_location[loc].append(asset)

    type_ids = {int(a.type_id) for a in assets if int(a.type_id or 0) > 0}
    type_meta: dict[int, SdeTypeIndex] = {}
    if type_ids:
        rows = await session.scalars(
            select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids))
        )
        type_meta = {int(r.type_id): r for r in rows.all()}
        missing_names = await load_type_names(session, {tid for tid in type_ids if tid not in type_meta})
        for asset in assets:
            if asset.type_name.startswith("Type ") and asset.type_id in missing_names:
                asset.type_name = resolve_type_name(
                    int(asset.type_id),
                    missing_names.get(int(asset.type_id), asset.type_name),
                    flag=asset.flag or "",
                )

    location_ids = list(roots_by_location.keys())
    cached = await ensure_universe_locations(
        session, location_ids, character_id=character_id
    )
    location_names: dict[int, str] = {}
    location_systems: dict[int, int | None] = {}
    for loc_id in location_ids:
        row = cached.get(loc_id)
        if row:
            location_names[loc_id] = row.name
            location_systems[loc_id] = int(row.solar_system_id) if row.solar_system_id else None
        elif loc_id == character_id:
            location_names[loc_id] = f"{character_name} — Hangar"
            location_systems[loc_id] = main_system_id
        else:
            location_names[loc_id] = f"Location {loc_id}"
            location_systems[loc_id] = None

    system_ids = {sid for sid in location_systems.values() if sid}
    if main_system_id:
        system_ids.add(main_system_id)
    coords = await _load_system_coords(session, system_ids)

    locations: list[dict] = []
    for loc_id in location_ids:
        roots = roots_by_location[loc_id]
        ships: list[dict] = []
        containers: list[dict] = []
        items: list[dict] = []
        for asset in roots:
            node = _build_asset_node(asset, children_map=children_map, type_meta=type_meta)
            kind = node["kind"]
            if kind == "ship":
                ships.append(node)
            elif kind == "container":
                containers.append(node)
            else:
                items.append(node)
        ships.sort(key=lambda n: n["type_name"].lower())
        containers.sort(key=lambda n: n["type_name"].lower())
        items.sort(key=lambda n: n["type_name"].lower())
        all_nodes = ships + containers + items
        sys_id = location_systems.get(loc_id)
        dist: float | None = None
        if main_system_id and sys_id and main_system_id in coords and sys_id in coords:
            dist = round(distance_ly(main_system_id, sys_id, coords), 2)
        locations.append(
            {
                "location_id": loc_id,
                "location_name": location_names.get(loc_id, f"Location {loc_id}"),
                "solar_system_id": sys_id,
                "distance_ly": dist,
                "ships": ships,
                "containers": containers,
                "items": items,
                "item_count": _count_asset_nodes(all_nodes),
            }
        )

    locations.sort(
        key=lambda loc: (
            loc["distance_ly"] if loc["distance_ly"] is not None else 999999,
            loc["location_name"].lower(),
        )
    )
    return locations


def _group_assets(assets: list[CharacterAsset]) -> list[dict]:
    buckets: dict[str, list[CharacterAsset]] = defaultdict(list)
    for asset in assets:
        flag = asset.flag or "Other"
        buckets[flag].append(asset)
    groups: list[dict] = []
    for flag in sorted(buckets.keys()):
        items = buckets[flag]
        groups.append(
            {
                "location_flag": flag,
                "item_count": len(items),
                "total_quantity": sum(int(a.quantity or 0) for a in items),
                "items": [
                    {
                        "type_id": a.type_id,
                        "type_name": a.type_name or f"Type {a.type_id}",
                        "quantity": a.quantity,
                    }
                    for a in sorted(items, key=lambda x: (x.type_name or "").lower())[:80]
                ],
            }
        )
    return groups


async def _enrich_clones(
    session: AsyncSession,
    clones: dict,
    *,
    character_id: int,
) -> dict:
    if not clones:
        return clones
    out = dict(clones)
    loc_ids: list[int] = []
    for jc in out.get("jump_clones") or []:
        if isinstance(jc, dict):
            lid = int(jc.get("location_id") or 0)
            if lid > 0:
                loc_ids.append(lid)
    jump_clones: list[dict] = []
    loc_labels: dict[int, str] = {}
    locs: dict = {}
    sys_names: dict[int, str] = {}
    if loc_ids:
        from app.services.location_display import resolve_location_labels

        loc_labels = await resolve_location_labels(
            session,
            loc_ids,
            character_id=character_id,
        )
        locs = await ensure_universe_locations(session, loc_ids, character_id=character_id, force=True)
        sys_ids = {int(l.solar_system_id) for l in locs.values() if l.solar_system_id}
        if sys_ids:
            rows = await session.scalars(select(SdeSystem).where(SdeSystem.system_id.in_(sys_ids)))
            sys_names = {int(r.system_id): r.name for r in rows.all()}

    for jc in out.get("jump_clones") or []:
        if not isinstance(jc, dict):
            continue
        row = dict(jc)
        lid = int(row.get("location_id") or 0)
        label = loc_labels.get(lid) or row.get("location_name")
        if label:
            row["location_name"] = label
        loc = locs.get(lid)
        if loc and loc.solar_system_id:
            sid = int(loc.solar_system_id)
            row["solar_system_id"] = sid
            row["solar_system_name"] = sys_names.get(sid)
        if not (row.get("name") or "").strip():
            row["name"] = f"Jump clone {int(row.get('jump_clone_id') or 0)}"
        jump_clones.append(row)
    out["jump_clones"] = jump_clones
    for key in (
        "home_location_id",
        "home_location_name",
        "home_solar_system_id",
        "home_solar_system_name",
    ):
        out.pop(key, None)
    return out


async def build_character_sheet(
    session: AsyncSession,
    character_id: int,
    *,
    viewer_character_id: int | None = None,
    director_view: bool = False,
) -> dict:
    profile = await session.scalar(
        select(AuditProfile).where(AuditProfile.character_id == character_id)
    )
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    from app.services.character_roster import load_roster

    roster = await load_roster(session, character_id)
    alts = [
        {
            "character_id": r.character_id,
            "character_name": r.character_name,
            "is_main": r.is_main,
        }
        for r in roster
    ]

    journals = await session.scalars(
        select(CharacterWalletJournal)
        .where(CharacterWalletJournal.character_id == character_id)
        .order_by(CharacterWalletJournal.recorded_at.desc())
        .limit(40)
    )
    assets = await session.scalars(
        select(CharacterAsset).where(CharacterAsset.character_id == character_id)
    )
    asset_rows = assets.all()

    type_ids = {a.type_id for a in asset_rows if a.type_id and not a.type_name}
    if type_ids:
        name_rows = await session.scalars(
            select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(type_ids))
        )
        type_names = {int(r.type_id): r.name for r in name_rows.all()}
        for asset in asset_rows:
            if not asset.type_name and asset.type_id in type_names:
                asset.type_name = type_names[asset.type_id]

    flags = await session.scalars(
        select(AuditSecurityFlag)
        .where(AuditSecurityFlag.character_id == character_id, AuditSecurityFlag.resolved.is_(False))
        .order_by(AuditSecurityFlag.created_at.desc())
        .limit(20)
    )

    snapshot = load_snapshot(profile)
    granted = parse_granted_scopes(user.scopes_json if user else "")
    skills = await _skills_for_character(session, character_id, snapshot)

    character_name = (
        profile.character_name
        if profile
        else user.character_name
        if user
        else f"Character {character_id}"
    )
    corporation_name = profile.corporation_name if profile else (user.corporation_name if user else "")
    wallet = profile.wallet_balance_isk if profile else Decimal("0")
    skill_points = profile.skill_points if profile else 0
    last_sync = profile.last_sync_at if profile else None
    next_sync = next_sync_at(last_sync, settings.audit_sync_interval_minutes)

    is_self = viewer_character_id is not None and character_id == viewer_character_id
    location = snapshot.get("location") if isinstance(snapshot.get("location"), dict) else {}
    main_system_id = int(location.get("solar_system_id") or 0) or None
    asset_locations = await _build_asset_locations(
        session,
        asset_rows,
        character_id=character_id,
        character_name=character_name,
        main_system_id=main_system_id,
    )

    clones = snapshot.get("clones") if isinstance(snapshot.get("clones"), dict) else {}
    if clones and has_clones_access(granted):
        clones = await _enrich_clones(session, clones, character_id=character_id)
    contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), list) else []
    recent_skills = _recent_skills(snapshot)

    corp_id = int(user.corporation_id or 0) if user else 0
    alliance_id = int(user.alliance_id or 0) if user and user.alliance_id else None

    return {
        "character_id": character_id,
        "character_name": character_name,
        "corporation_id": corp_id,
        "corporation_name": corporation_name,
        "alliance_id": alliance_id,
        "alliance_name": user.alliance_name if user else None,
        "wallet_balance_isk": str(wallet),
        "skill_points": int(skill_points or 0),
        "current_location": location.get("location_name"),
        "main_system_id": main_system_id,
        "location_detail": location,
        "skills_trained": len([s for s in skills if s["trained_level"] > 0]),
        "last_sync_at": last_sync.isoformat() if last_sync else None,
        "last_sync_eve": format_eve_time(last_sync),
        "next_sync_at": next_sync.isoformat() if next_sync else None,
        "next_sync_eve": format_eve_time(next_sync),
        "sync_interval_minutes": settings.audit_sync_interval_minutes,
        "scopes": sorted(granted),
        "missing_scopes": missing_scopes(granted),
        "scope_status": scope_status(granted),
        "has_wallet_access": has_wallet_access(granted),
        "has_assets_access": has_assets_access(granted),
        "has_skills_access": has_skills_access(granted),
        "has_skill_queue_access": has_skill_queue_access(granted),
        "has_location_access": has_location_access(granted),
        "has_clones_access": has_clones_access(granted),
        "has_contracts_access": has_contracts_access(granted),
        "has_mail_access": has_mail_access(granted),
        "has_killmails_access": has_killmails_access(granted),
        "sync_errors": snapshot.get("scope_errors") if isinstance(snapshot.get("scope_errors"), dict) else {},
        "reauthorize_url": "/api/auth/sso/login",
        "skills": skills,
        "recent_skills": recent_skills,
        "skill_queue": snapshot.get("skill_queue") or [],
        "asset_locations": asset_locations,
        "asset_groups": _group_assets(asset_rows),
        "clones": clones,
        "contracts": contracts,
        "mail": snapshot.get("mail") or [],
        "combat_log": snapshot.get("combat_log") or [],
        "corp_history": snapshot.get("corp_history") or [],
        "online": snapshot.get("online") if isinstance(snapshot.get("online"), dict) else None,
        "active_ship": snapshot.get("active_ship") if isinstance(snapshot.get("active_ship"), dict) else None,
        "fatigue": snapshot.get("fatigue") if isinstance(snapshot.get("fatigue"), dict) else None,
        "corp_roles": snapshot.get("corp_roles") if isinstance(snapshot.get("corp_roles"), dict) else None,
        "corp_titles": snapshot.get("corp_titles") or [],
        "standings": snapshot.get("standings") or [],
        "contacts": snapshot.get("contacts") or [],
        "eve_notifications": snapshot.get("eve_notifications") or [],
        "loyalty_points": snapshot.get("loyalty_points") or [],
        "calendar_events": snapshot.get("calendar_events") or [],
        "market_orders": await _market_orders_for_character(session, character_id),
        "wallet_journal": [
            {
                "ref_type": j.ref_type,
                "amount": str(j.amount),
                "balance": str(j.balance),
                "reason": j.reason,
                "second_party_id": j.second_party_id,
                "recorded_at": j.recorded_at.isoformat(),
            }
            for j in journals.all()
        ],
        "flags": [
            {"flag_key": f.flag_key, "severity": f.severity, "detail": f.detail}
            for f in flags.all()
        ],
        "linked_characters": alts,
        "view_mode": "director" if director_view else ("self" if is_self else "alt"),
        "can_sync": False,
    }
