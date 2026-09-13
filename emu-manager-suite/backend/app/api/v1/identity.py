"""Coalition identity — states, groups, RBAC administration."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, is_administrator, require_administrator, require_api_key
from app.db.session import get_db
from app.models.identity import (
    EmumsCharacterGroupJoin,
    EmumsGroup,
    EmumsState,
    EmumsStateRule,
)
from app.schemas.map import (
    GroupAssignRequest,
    GroupCreate,
    GroupJoinRequest,
    GroupUpdate,
    ServiceSyncConfigUpdate,
    StateCreate,
    StateRuleCreate,
    StateRuleUpdate,
)
from app.services.rbac import UserAuthContext, build_auth_context

router = APIRouter(
    prefix="/identity",
    tags=["Identity"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/me")
async def identity_me(
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    return {
        "character_id": auth.character_id,
        "character_name": auth.character_name,
        "corporation_id": auth.corporation_id,
        "alliance_id": auth.alliance_id,
        "state": auth.state_name,
        "groups": auth.groups,
        "permissions": sorted(auth.permissions),
        "is_administrator": is_administrator(auth),
    }


@router.get("/modules")
async def list_permission_modules() -> list[dict]:
    """Coalition permission modules exposed to the client shell."""
    from app.services.rbac import DEFAULT_STATES, MODULE_PERMISSIONS

    return [
        {
            "id": level,
            "label": next((s[0] for s in DEFAULT_STATES if s[0].lower() == level), level.title()),
            "permissions": perms,
        }
        for level, perms in MODULE_PERMISSIONS.items()
    ]


@router.get("/states")
async def list_states(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(EmumsState).order_by(EmumsState.priority_weight.desc()))).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "priority_weight": s.priority_weight,
            "color": s.color,
            "description": s.description,
            "active": s.active,
        }
        for s in rows
    ]


@router.post("/states")
async def create_state(body: StateCreate, db: AsyncSession = Depends(get_db)) -> dict:
    row = EmumsState(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "name": row.name}


@router.get("/state-rules")
async def list_state_rules(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(EmumsStateRule))).all()
    return [
        {
            "id": r.id,
            "state_id": r.state_id,
            "allowed_alliance_ids": json.loads(r.allowed_alliance_ids_json or "[]"),
            "allowed_corporation_ids": json.loads(r.allowed_corporation_ids_json or "[]"),
            "priority": r.priority,
        }
        for r in rows
    ]


@router.post("/state-rules")
async def create_state_rule(body: StateRuleCreate, db: AsyncSession = Depends(get_db)) -> dict:
    row = EmumsStateRule(
        state_id=body.state_id,
        allowed_alliance_ids_json=json.dumps(body.allowed_alliance_ids),
        allowed_corporation_ids_json=json.dumps(body.allowed_corporation_ids),
        priority=body.priority,
    )
    db.add(row)
    await db.commit()
    return {"id": row.id}


@router.get("/groups")
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(EmumsGroup).order_by(EmumsGroup.name))).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "is_hidden": g.is_hidden,
            "is_open": g.is_open,
            "discord_role_id": g.discord_role_id,
            "permissions": json.loads(g.permissions_json or "[]"),
            "active": g.active,
        }
        for g in rows
    ]


@router.post("/groups")
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    row = EmumsGroup(
        name=body.name,
        description=body.description,
        is_hidden=body.is_hidden,
        is_open=body.is_open,
        discord_role_id=body.discord_role_id,
        permissions_json=json.dumps(body.permissions),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "name": row.name}


@router.patch("/groups/{group_id}")
async def update_group(
    group_id: int,
    body: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    row = await db.get(EmumsGroup, group_id)
    if not row:
        raise HTTPException(404, detail="Group not found")
    data = body.model_dump(exclude_unset=True)
    if "permissions" in data and data["permissions"] is not None:
        row.permissions_json = json.dumps(data.pop("permissions"))
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    return {"id": row.id, "name": row.name, "permissions": json.loads(row.permissions_json or "[]")}


@router.patch("/state-rules/{rule_id}")
async def update_state_rule(
    rule_id: int,
    body: StateRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    row = await db.get(EmumsStateRule, rule_id)
    if not row:
        raise HTTPException(404, detail="Rule not found")
    if body.allowed_alliance_ids is not None:
        row.allowed_alliance_ids_json = json.dumps(body.allowed_alliance_ids)
    if body.allowed_corporation_ids is not None:
        row.allowed_corporation_ids_json = json.dumps(body.allowed_corporation_ids)
    if body.priority is not None:
        row.priority = body.priority
    await db.commit()
    return {"id": row.id, "updated": True}


@router.post("/groups/{group_id}/assign")
async def assign_group_member(
    group_id: int,
    body: GroupAssignRequest,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    group = await db.get(EmumsGroup, group_id)
    if not group:
        raise HTTPException(404, detail="Group not found")
    existing = await db.scalar(
        select(EmumsCharacterGroupJoin).where(
            EmumsCharacterGroupJoin.group_id == group_id,
            EmumsCharacterGroupJoin.character_id == body.character_id,
        )
    )
    status = body.status or EmumsCharacterGroupJoin.STATUS_ACTIVE
    if existing:
        existing.status = status
        existing.character_name = body.character_name or existing.character_name
        existing.granted_by_character_id = auth.character_id
    else:
        existing = EmumsCharacterGroupJoin(
            character_id=body.character_id,
            character_name=body.character_name,
            group_id=group_id,
            status=status,
            granted_by_character_id=auth.character_id,
        )
        db.add(existing)
    await db.commit()
    from app.services.service_sync import schedule_user_service_sync

    schedule_user_service_sync(body.character_id)
    return {"id": existing.id, "status": existing.status}


@router.post("/groups/{group_id}/join")
async def join_group(
    group_id: int,
    body: GroupJoinRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    group = await db.get(EmumsGroup, group_id)
    if not group:
        raise HTTPException(404, detail="Group not found")
    if not group.is_open:
        raise HTTPException(403, detail="Group requires director assignment")
    row = EmumsCharacterGroupJoin(
        character_id=body.character_id,
        character_name=body.character_name,
        group_id=group_id,
        status=EmumsCharacterGroupJoin.STATUS_PENDING,
    )
    db.add(row)
    await db.commit()
    from app.services.service_sync import schedule_user_service_sync

    schedule_user_service_sync(body.character_id)
    return {"id": row.id, "status": EmumsCharacterGroupJoin.STATUS_PENDING}


@router.get("/groups/{group_id}/members")
async def group_members(group_id: int, db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = await db.scalars(
        select(EmumsCharacterGroupJoin).where(EmumsCharacterGroupJoin.group_id == group_id)
    )
    return [
        {
            "id": j.id,
            "character_id": j.character_id,
            "character_name": j.character_name,
            "status": j.status,
        }
        for j in rows.all()
    ]


@router.post("/service-sync/{character_id}")
async def trigger_service_sync(character_id: int) -> dict[str, str]:
    from app.tasks.service_sync import sync_user_services_task

    task = sync_user_services_task.delay(character_id)
    return {"task_id": task.id, "status": "queued"}


@router.get("/service-sync/config")
async def get_service_sync_config(db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.service_sync import load_sync_config

    cfg = await load_sync_config(db)
    return {
        "discord_guild_id": cfg.discord_guild_id,
        "discord_nickname_format": cfg.discord_nickname_format,
        "enabled": cfg.enabled,
        "has_bot_token": bool(cfg.discord_bot_token),
    }


@router.patch("/service-sync/config")
async def update_service_sync_config(
    body: ServiceSyncConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    from app.services.service_sync import load_sync_config

    cfg = await load_sync_config(db)
    if body.discord_bot_token:
        cfg.discord_bot_token = body.discord_bot_token
    cfg.discord_guild_id = body.discord_guild_id
    cfg.discord_nickname_format = body.discord_nickname_format
    cfg.mumble_server_json = body.mumble_server_json
    cfg.enabled = body.enabled
    await db.commit()
    return {"updated": True, "enabled": cfg.enabled}


@router.post("/resolve/{character_id}")
async def resolve_character_auth(
    character_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    ctx = await build_auth_context(db, character_id)
    if not ctx:
        raise HTTPException(404, detail="Character not registered")
    return {
        "state": ctx.state_name,
        "groups": ctx.groups,
        "permissions": sorted(ctx.permissions),
    }


@router.get("/admin/users/search")
async def admin_search_users(
    q: str = Query("", min_length=0),
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> list[dict]:
    from app.models.tools import SsoUser

    query = q.strip()
    if len(query) < 2:
        return []
    pattern = f"%{query}%"
    rows = (
        await db.scalars(
            select(SsoUser)
            .where(SsoUser.character_name.ilike(pattern))
            .order_by(SsoUser.character_name)
            .limit(max(1, min(limit, 50)))
        )
    ).all()
    return [
        {
            "character_id": int(r.character_id),
            "character_name": r.character_name,
            "corporation_name": r.corporation_name,
            "alliance_name": r.alliance_name,
        }
        for r in rows
    ]


@router.get("/admin/users/{character_id}")
async def admin_user_detail(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    from app.models.tools import SsoUser

    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    ctx = await build_auth_context(db, character_id)
    joins = (
        await db.execute(
            select(EmumsCharacterGroupJoin, EmumsGroup)
            .join(EmumsGroup, EmumsGroup.id == EmumsCharacterGroupJoin.group_id)
            .where(EmumsCharacterGroupJoin.character_id == character_id)
            .order_by(EmumsGroup.name)
        )
    ).all()
    group_rows = []
    for join, group in joins:
        group_rows.append(
            {
                "join_id": join.id,
                "group_id": group.id,
                "group_name": group.name,
                "status": join.status,
                "permissions": json.loads(group.permissions_json or "[]"),
                "is_open": group.is_open,
            }
        )
    if not user and not ctx:
        raise HTTPException(404, detail="Character not registered on EMUMS")
    return {
        "character_id": character_id,
        "character_name": user.character_name if user else (ctx.character_name if ctx else f"Pilot {character_id}"),
        "corporation_name": user.corporation_name if user else None,
        "alliance_name": user.alliance_name if user else None,
        "registered": user is not None,
        "state": ctx.state_name if ctx else None,
        "groups": ctx.groups if ctx else [],
        "permissions": sorted(ctx.permissions) if ctx else [],
        "group_memberships": group_rows,
    }


@router.post("/admin/users/{character_id}/groups/{group_id}")
async def admin_assign_group(
    character_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    group = await db.get(EmumsGroup, group_id)
    if not group or not group.active:
        raise HTTPException(404, detail="Group not found")
    from app.models.tools import SsoUser

    user = await db.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    character_name = user.character_name if user else f"Character {character_id}"
    existing = await db.scalar(
        select(EmumsCharacterGroupJoin).where(
            EmumsCharacterGroupJoin.character_id == character_id,
            EmumsCharacterGroupJoin.group_id == group_id,
        )
    )
    if existing:
        existing.status = EmumsCharacterGroupJoin.STATUS_ACTIVE
        existing.character_name = character_name
        existing.granted_by_character_id = auth.character_id
    else:
        db.add(
            EmumsCharacterGroupJoin(
                character_id=character_id,
                character_name=character_name,
                group_id=group_id,
                status=EmumsCharacterGroupJoin.STATUS_ACTIVE,
                granted_by_character_id=auth.character_id,
            )
        )
    await db.commit()
    from app.services.service_sync import schedule_user_service_sync

    schedule_user_service_sync(character_id)
    return {"character_id": character_id, "group_id": group_id, "status": "active"}


@router.delete("/admin/users/{character_id}/groups/{group_id}")
async def admin_revoke_group(
    character_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: UserAuthContext = Depends(require_administrator),
) -> dict:
    existing = await db.scalar(
        select(EmumsCharacterGroupJoin).where(
            EmumsCharacterGroupJoin.character_id == character_id,
            EmumsCharacterGroupJoin.group_id == group_id,
        )
    )
    if not existing:
        raise HTTPException(404, detail="Group membership not found")
    existing.status = EmumsCharacterGroupJoin.STATUS_REVOKED
    await db.commit()
    from app.services.service_sync import schedule_user_service_sync

    schedule_user_service_sync(character_id)
    return {"character_id": character_id, "group_id": group_id, "status": "revoked"}
