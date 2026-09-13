"""Member audit and character sheet endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_api_key
from app.db.session import get_db
from app.models.member_audit import AuditSecurityFlag, CharacterAsset
from app.models.tools import AuditProfile
from app.services.character_sheet import build_character_sheet, can_view_character
from app.services.character_roster import load_roster
from app.services.hr_lookup import search_pilots, viewer_has_hr_lookup
from app.services.roster_overview import build_roster_overview
from app.services.roster_interactions import build_roster_interactions
from app.services.pi_sync import build_roster_pi_overview, refresh_roster_pi_snapshots
from app.services.audit_extras import fetch_mail_body
from app.services.member_audit import sync_character_audit
from app.services.rbac import UserAuthContext


class IntelTagBody(BaseModel):
    entity_id: int
    entity_kind: str = ""
    entity_name: str = ""
    tag_type: str
    linked_character_id: int | None = None
    linked_character_name: str = ""
    notes: str = ""


router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
    dependencies=[Depends(require_api_key)],
)


def _require_audit_access(auth: UserAuthContext) -> None:
    if not auth.has_permission("audit.view") and not auth.has_permission("director"):
        raise HTTPException(403, detail="Audit access required")


async def _require_character_access(
    db: AsyncSession,
    auth: UserAuthContext,
    character_id: int,
) -> bool:
    allowed = await can_view_character(
        db,
        viewer_character_id=auth.character_id,
        target_character_id=character_id,
        permissions=auth.permissions,
    )
    if not allowed:
        raise HTTPException(403, detail="You can only view your own character sheet")
    return "audit.view" in auth.permissions or "director" in auth.permissions or "admin" in auth.permissions or await viewer_has_hr_lookup(db, auth)


@router.get("/me")
async def my_character_sheet(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    return await build_character_sheet(
        db,
        auth.character_id,
        viewer_character_id=auth.character_id,
        director_view=False,
    )


@router.post("/me/sync")
async def sync_my_character_sheet(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    result = await sync_character_audit(db, auth.character_id)
    await db.commit()
    sheet = await build_character_sheet(
        db,
        auth.character_id,
        viewer_character_id=auth.character_id,
        director_view=False,
    )
    return {"sync": result, "sheet": sheet}


@router.get("/profiles")
async def list_audit_profiles(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    limit: int = Query(100, le=500),
) -> list[dict]:
    _require_audit_access(auth)
    rows = (await db.scalars(select(AuditProfile).limit(limit))).all()
    return [
        {
            "character_id": p.character_id,
            "character_name": p.character_name,
            "corporation_name": p.corporation_name,
            "wallet_balance_isk": str(p.wallet_balance_isk),
            "skill_points": p.skill_points,
            "assets_value_isk": str(p.assets_value_isk),
            "last_sync_at": p.last_sync_at.isoformat() if p.last_sync_at else None,
        }
        for p in rows
    ]


@router.get("/roster/overview")
async def roster_overview(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    """Combined summary for all linked characters — no session switch required."""
    return await build_roster_overview(db, auth.character_id)


@router.post("/roster/sync")
async def sync_roster(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    background: bool = Query(default=True),
) -> dict:
    """Refresh ESI audit data for every linked alt with a valid token."""
    roster = await load_roster(db, auth.character_id)
    if background and len(roster) > 1:
        from app.tasks.member_audit import sync_roster_alts_task

        task = sync_roster_alts_task.delay(int(auth.character_id))
        return {
            "status": "queued",
            "task_id": task.id,
            "character_count": len(roster),
            "synced_count": 0,
            "skipped_count": sum(1 for r in roster if not r.token_valid),
        }

    synced: list[int] = []
    skipped: list[int] = []
    errors: dict[str, str] = {}
    for row in roster:
        cid = int(row.character_id)
        if not row.token_valid:
            skipped.append(cid)
            continue
        try:
            await sync_character_audit(db, cid)
            synced.append(cid)
        except Exception as exc:
            errors[str(cid)] = str(exc)[:200]
    await db.commit()
    overview = await build_roster_overview(db, auth.character_id)
    return {
        "status": "completed",
        "synced_count": len(synced),
        "skipped_count": len(skipped),
        "errors": errors,
        "overview": overview,
    }


@router.get("/roster/pi")
async def roster_pi_overview(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    refresh: bool = Query(default=True),
) -> dict:
    """Combined planetary interaction overview across linked alts."""
    data = await build_roster_pi_overview(db, auth.character_id, refresh=refresh)
    if refresh:
        await db.commit()
    return data


@router.post("/roster/pi/sync")
async def roster_pi_sync(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    """Force PI colony refresh from ESI for all linked characters with PI scope."""
    stats = await refresh_roster_pi_snapshots(db, auth.character_id, force=True)
    await db.commit()
    overview = await build_roster_pi_overview(db, auth.character_id, refresh=False)
    return {"sync": stats, **overview}


@router.get("/characters/{character_id}/pi")
async def character_pi_overview(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    await _require_character_access(db, auth, character_id)
    data = await build_roster_pi_overview(db, auth.character_id)
    colonies = [c for c in data.get("colonies", []) if int(c.get("character_id") or 0) == character_id]
    return {
        "character_id": character_id,
        "colony_count": len(colonies),
        "attention_count": sum(1 for c in colonies if c.get("status") in {"attention", "idle"}),
        "colonies": colonies,
        "scope_note": data.get("scope_note"),
    }


@router.get("/roster/interactions")
async def roster_interactions(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    q: str = Query(default=""),
    kind: str = Query(default=""),
    counterparty_id: int | None = Query(default=None),
    rollup: bool = Query(default=True),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """Combined interaction counts across all linked alts, with spy-o-meter scores."""
    return await build_roster_interactions(
        db,
        auth.character_id,
        q=q,
        kind=kind,
        counterparty_id=counterparty_id,
        limit=limit,
        offset=offset,
        rollup=rollup,
    )


@router.get("/roster/spy-meter")
async def roster_spy_meter(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    min_score: float = Query(0, ge=0, le=100),
    limit: int = Query(50, le=200),
) -> dict:
    """Rank counterparties by likely-alt / intel risk (spy-o-meter)."""
    from app.services.spy_meter import spy_meter_board

    return await spy_meter_board(
        db, auth.character_id, min_score=min_score, limit=limit
    )


@router.get("/intel/tags")
async def get_intel_tags(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.spy_meter import TAG_TYPES, list_intel_tags

    return {
        "tags": await list_intel_tags(db, auth.character_id),
        "tag_types": {k: {"label": v["label"], "tone": v["tone"]} for k, v in TAG_TYPES.items()},
    }


@router.post("/intel/tags")
async def post_intel_tag(
    body: IntelTagBody,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.spy_meter import upsert_intel_tag

    result = await upsert_intel_tag(
        db,
        viewer_character_id=auth.character_id,
        viewer_character_name=auth.character_name,
        entity_id=body.entity_id,
        entity_kind=body.entity_kind,
        entity_name=body.entity_name,
        tag_type=body.tag_type,
        linked_character_id=body.linked_character_id,
        linked_character_name=body.linked_character_name,
        notes=body.notes,
    )
    if result.get("error"):
        raise HTTPException(400, detail=result["error"])
    await db.commit()
    return result


@router.delete("/intel/tags/{tag_id}")
async def delete_intel_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    from app.services.spy_meter import remove_intel_tag

    result = await remove_intel_tag(
        db, viewer_character_id=auth.character_id, tag_id=tag_id
    )
    if result.get("error"):
        raise HTTPException(404, detail=result["error"])
    await db.commit()
    return result



@router.post("/roster/rebuild-interactions")
async def rebuild_roster_interactions(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    background: bool = Query(default=True),
) -> dict:
    """Rebuild interaction aggregates from DB/snapshot without full ESI sync."""
    roster = await load_roster(db, auth.character_id)
    if background and len(roster) > 3:
        from app.tasks.member_audit import rebuild_roster_interactions_task

        task = rebuild_roster_interactions_task.delay(int(auth.character_id))
        return {
            "status": "queued",
            "task_id": task.id,
            "characters": len(roster),
        }

    from app.services.interaction_sync import sync_character_interactions

    rebuilt = 0
    for row in roster:
        rebuilt += await sync_character_interactions(db, int(row.character_id))
    await db.commit()
    return {
        "status": "completed",
        "characters": len(roster),
        "aggregate_rows": rebuilt,
        "interactions": await build_roster_interactions(db, auth.character_id, limit=50),
    }


@router.get("/search")
async def search_characters(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    limit: int = Query(25, le=50),
) -> list[dict]:
    if not await viewer_has_hr_lookup(db, auth):
        raise HTTPException(403, detail="HR lookup access required")
    return await search_pilots(db, q, limit=limit)


@router.get("/characters/{character_id}")
async def character_audit_detail(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    director_view = await _require_character_access(db, auth, character_id)
    return await build_character_sheet(
        db,
        character_id,
        viewer_character_id=auth.character_id,
        director_view=director_view,
    )


@router.get("/characters/{character_id}/mail/{mail_id}")
async def character_mail_detail(
    character_id: int,
    mail_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    await _require_character_access(db, auth, character_id)
    return await fetch_mail_body(db, character_id=character_id, mail_id=mail_id)


@router.get("/assets/search")
async def search_assets(
    q: str = Query("", min_length=1),
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    limit: int = Query(50, le=200),
) -> list[dict]:
    _require_audit_access(auth)
    needle = f"%{q.strip()}%"
    rows = await db.scalars(
        select(CharacterAsset)
        .where(CharacterAsset.type_name.ilike(needle))
        .limit(limit)
    )
    return [
        {
            "character_id": a.character_id,
            "type_id": a.type_id,
            "type_name": a.type_name,
            "quantity": a.quantity,
            "location_id": a.location_id,
        }
        for a in rows.all()
    ]


@router.get("/flags")
async def list_security_flags(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> list[dict]:
    _require_audit_access(auth)
    rows = await db.scalars(
        select(AuditSecurityFlag)
        .where(AuditSecurityFlag.resolved.is_(False))
        .order_by(AuditSecurityFlag.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": f.id,
            "character_id": f.character_id,
            "character_name": f.character_name,
            "flag_key": f.flag_key,
            "severity": f.severity,
            "detail": f.detail,
        }
        for f in rows.all()
    ]


@router.post("/sync/{character_id}")
async def trigger_character_sync(
    character_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    await _require_character_access(db, auth, character_id)
    if character_id != auth.character_id and not (
        auth.has_permission("audit.view") or auth.has_permission("director")
    ):
        raise HTTPException(403, detail="Only directors can sync other characters")
    result = await sync_character_audit(db, character_id)
    await db.commit()
    return result


@router.post("/sync-all/enqueue")
async def enqueue_full_audit_sync(
    auth: UserAuthContext = Depends(get_current_user),
) -> dict[str, str]:
    _require_audit_access(auth)
    from app.tasks.member_audit import sync_all_characters_audit

    task = sync_all_characters_audit.delay()
    return {"task_id": task.id, "status": "queued"}
