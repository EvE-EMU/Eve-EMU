"""Directorate administration — infrastructure telemetry and operational actions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import redis.asyncio as aioredis
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_api_key
from app.celery_app import celery_app
from app.config import settings
from app.db.session import get_db
from app.models import StructureTaxRule
from app.models.tools import HrLeaveRequest, HrRoleTitle, IndustrialBuildStructure, SrpLoss, SrpRateRule
from app.models.member_audit import HrAuditAlertRule
from app.models.storefront import (
    StorefrontConfig,
    StorefrontItemOverride,
    StorefrontKit,
    StorefrontKitItem,
    StorefrontOrder,
    StorefrontPickupLocation,
)
from app.schemas.storefront import (
    StorefrontConfigPatch,
    StorefrontKitIn,
    StorefrontKitItemIn,
    StorefrontKitPatch,
    StorefrontLocationIn,
    StorefrontLocationPatch,
    StorefrontOrderStatusPatch,
    StorefrontOverrideIn,
    StorefrontOverridePatch,
)
from app.services.storefront import (
    _config_out,
    _kit_out,
    _location_out,
    _order_out,
    build_catalog,
    ensure_storefront_defaults,
    get_storefront_config,
    list_kits_admin,
    list_orders_admin,
    list_overrides_admin,
    list_pickup_locations_admin,
)
from app.services.service_sync import load_sync_config

router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[Depends(require_api_key)])


class SrpStatusPatch(BaseModel):
    status: Literal["pending", "approved", "rejected", "paid"]


class SrpRateRuleIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)
    ship_type_id: int = Field(default=0, ge=0)
    ship_type_name: str = Field(default="", max_length=128)
    doctrine_slug: str = Field(default="", max_length=64)
    base_srp_isk: Decimal = Field(default=Decimal("0"), ge=0)
    max_percent: Decimal | None = Field(default=None, ge=0, le=100)
    doctrine_multiplier: Decimal = Field(default=Decimal("1"), ge=0, le=2)
    meta_multiplier: Decimal = Field(default=Decimal("0.75"), ge=0, le=2)
    shitfit_multiplier: Decimal = Field(default=Decimal("0"), ge=0, le=2)
    allow_shitfit: bool = False
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=10000)


class SrpRateRulePatch(BaseModel):
    label: str | None = Field(default=None, max_length=128)
    ship_type_id: int | None = Field(default=None, ge=0)
    ship_type_name: str | None = Field(default=None, max_length=128)
    doctrine_slug: str | None = Field(default=None, max_length=64)
    base_srp_isk: Decimal | None = Field(default=None, ge=0)
    max_percent: Decimal | None = Field(default=None, ge=0, le=100)
    doctrine_multiplier: Decimal | None = Field(default=None, ge=0, le=2)
    meta_multiplier: Decimal | None = Field(default=None, ge=0, le=2)
    shitfit_multiplier: Decimal | None = Field(default=None, ge=0, le=2)
    allow_shitfit: bool | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=10000)


class HrLeaveStatusPatch(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class HrRoleTitleIn(BaseModel):
    corporation_id: int = Field(..., gt=0)
    title_id: int = Field(..., gt=0)
    title_name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=256)
    active: bool = True


class HrRoleTitlePatch(BaseModel):
    title_name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=256)
    active: bool | None = None


class HrAuditRuleIn(BaseModel):
    rule_key: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    enabled: bool = True
    severity: Literal["warn", "critical"] = "warn"
    rule_type: Literal[
        "mail_subject",
        "wallet_ref_type",
        "blacklist_contact",
        "wallet_drop",
        "interaction_threshold",
    ]
    match_json: str = "{}"
    webhook_url: str = Field(default="", max_length=512)
    notify_in_app: bool = True
    cooldown_hours: int = Field(default=24, ge=0, le=720)


class HrAuditRulePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    enabled: bool | None = None
    severity: Literal["warn", "critical"] | None = None
    match_json: str | None = None
    webhook_url: str | None = Field(default=None, max_length=512)
    notify_in_app: bool | None = None
    cooldown_hours: int | None = Field(default=None, ge=0, le=720)


class TaxRulePatch(BaseModel):
    r16_pct: Decimal | None = None
    r32_pct: Decimal | None = None
    r64_pct: Decimal | None = None
    pattern: str | None = None
    priority: int | None = None
    active: bool | None = None


class ServiceLockPatch(BaseModel):
    locked: bool
    reason: str = ""


class BuildStructureIn(BaseModel):
    structure_id: int = Field(..., gt=0)
    structure_name: str = Field(..., min_length=1, max_length=256)
    system_name: str = Field(default="", max_length=128)
    location_label: str = Field(default="", max_length=128)
    material_bonus_pct: float = Field(default=0.0, ge=0, le=50)
    time_bonus_pct: float = Field(default=0.0, ge=0, le=50)
    tax_pct: float = Field(default=0.0, ge=0, le=25)
    has_manufacturing: bool = True


class BuildStructurePatch(BaseModel):
    structure_name: str | None = Field(default=None, max_length=256)
    system_name: str | None = Field(default=None, max_length=128)
    location_label: str | None = Field(default=None, max_length=128)
    material_bonus_pct: float | None = Field(default=None, ge=0, le=50)
    time_bonus_pct: float | None = Field(default=None, ge=0, le=50)
    tax_pct: float | None = Field(default=None, ge=0, le=25)
    has_manufacturing: bool | None = None


def _build_structure_out(row: IndustrialBuildStructure) -> dict:
    return {
        "id": row.id,
        "structure_id": int(row.structure_id),
        "structure_name": row.structure_name,
        "system_name": row.system_name,
        "location_label": row.location_label,
        "material_bonus_pct": row.material_bonus_pct,
        "time_bonus_pct": row.time_bonus_pct,
        "tax_pct": row.tax_pct,
        "has_manufacturing": row.has_manufacturing,
    }


@router.get("/build-structures")
async def list_build_structures_admin(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (
        await db.scalars(
            select(IndustrialBuildStructure).order_by(IndustrialBuildStructure.structure_name)
        )
    ).all()
    return [_build_structure_out(r) for r in rows]


@router.post("/build-structures", status_code=201)
async def create_build_structure(body: BuildStructureIn, db: AsyncSession = Depends(get_db)) -> dict:
    exists = await db.scalar(
        select(IndustrialBuildStructure).where(IndustrialBuildStructure.structure_id == body.structure_id)
    )
    if exists:
        raise HTTPException(400, detail="structure_id already configured")
    row = IndustrialBuildStructure(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _build_structure_out(row)


@router.patch("/build-structures/{row_id}")
async def patch_build_structure(
    row_id: int, body: BuildStructurePatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(IndustrialBuildStructure, row_id)
    if not row:
        raise HTTPException(404, detail="Build structure not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return _build_structure_out(row)


@router.delete("/build-structures/{row_id}")
async def delete_build_structure(row_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(IndustrialBuildStructure, row_id)
    if not row:
        raise HTTPException(404, detail="Build structure not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": row_id}


@router.get("/infrastructure")
async def infrastructure_status() -> dict:
    """Celery/Redis telemetry for coalition directors."""
    redis_status: dict = {"reachable": False, "connected_clients": 0, "used_memory_human": ""}
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            pong = await client.ping()
            info = await client.info("memory")
            clients = await client.info("clients")
            redis_status = {
                "reachable": pong is True,
                "connected_clients": int(clients.get("connected_clients", 0)),
                "used_memory_human": str(info.get("used_memory_human", "")),
            }
        finally:
            await client.aclose()
    except Exception as exc:
        redis_status["error"] = str(exc)

    workers: list[str] = []
    active_tasks: dict[str, list] = {}
    scheduled: dict = {}
    try:
        inspect = celery_app.control.inspect(timeout=2.0)
        if inspect:
            ping = inspect.ping() or {}
            workers = sorted(ping.keys())
            active_tasks = inspect.active() or {}
            scheduled = inspect.scheduled() or {}
    except Exception as exc:
        workers = []
        active_tasks = {"error": str(exc)}

    queue_depth = sum(len(v or []) for v in active_tasks.values() if isinstance(v, list))
    beat_schedule = [
        {"name": name, "task": spec.get("task", ""), "schedule": str(spec.get("schedule", ""))}
        for name, spec in (celery_app.conf.beat_schedule or {}).items()
    ]

    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "environment": settings.environment,
        "redis": redis_status,
        "celery": {
            "workers_online": len(workers),
            "worker_names": workers,
            "active_task_count": queue_depth,
            "active_by_worker": {
                k: [{"name": t.get("name"), "id": t.get("id")} for t in (v or [])[:8]]
                for k, v in active_tasks.items()
                if isinstance(v, list)
            },
            "scheduled_count": sum(len(v or []) for v in scheduled.values()),
            "beat_schedule": beat_schedule,
        },
    }


@router.patch("/srp/{loss_id}")
async def patch_srp_loss(
    loss_id: int, body: SrpStatusPatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(SrpLoss, loss_id)
    if not row:
        raise HTTPException(404, detail="SRP loss not found")
    row.status = body.status
    if body.status in ("approved", "paid"):
        row.confirmed_at = datetime.now(UTC)
    await db.commit()
    return {"id": row.id, "status": row.status}


def _srp_rate_out(row: SrpRateRule) -> dict:
    return {
        "id": row.id,
        "label": row.label,
        "ship_type_id": row.ship_type_id,
        "ship_type_name": row.ship_type_name,
        "doctrine_slug": row.doctrine_slug,
        "base_srp_isk": str(row.base_srp_isk),
        "max_percent": str(row.max_percent) if row.max_percent is not None else None,
        "doctrine_multiplier": str(row.doctrine_multiplier),
        "meta_multiplier": str(row.meta_multiplier),
        "shitfit_multiplier": str(row.shitfit_multiplier),
        "allow_shitfit": row.allow_shitfit,
        "enabled": row.enabled,
        "priority": row.priority,
    }


@router.get("/srp/rules")
async def list_srp_rate_rules(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (
        await db.scalars(select(SrpRateRule).order_by(SrpRateRule.priority.desc(), SrpRateRule.label))
    ).all()
    return [_srp_rate_out(r) for r in rows]


@router.post("/srp/rules", status_code=201)
async def create_srp_rate_rule(body: SrpRateRuleIn, db: AsyncSession = Depends(get_db)) -> dict:
    row = SrpRateRule(
        label=body.label,
        ship_type_id=body.ship_type_id,
        ship_type_name=body.ship_type_name,
        doctrine_slug=body.doctrine_slug,
        base_srp_isk=body.base_srp_isk,
        max_percent=body.max_percent,
        doctrine_multiplier=body.doctrine_multiplier,
        meta_multiplier=body.meta_multiplier,
        shitfit_multiplier=body.shitfit_multiplier,
        allow_shitfit=body.allow_shitfit,
        enabled=body.enabled,
        priority=body.priority,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _srp_rate_out(row)


@router.patch("/srp/rules/{rule_id}")
async def patch_srp_rate_rule(
    rule_id: int, body: SrpRateRulePatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(SrpRateRule, rule_id)
    if not row:
        raise HTTPException(404, detail="SRP rate rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return _srp_rate_out(row)


@router.delete("/srp/rules/{rule_id}")
async def delete_srp_rate_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(SrpRateRule, rule_id)
    if not row:
        raise HTTPException(404, detail="SRP rate rule not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": rule_id}


@router.patch("/hr/leaves/{leave_id}")
async def patch_hr_leave(
    leave_id: int, body: HrLeaveStatusPatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(HrLeaveRequest, leave_id)
    if not row:
        raise HTTPException(404, detail="Leave request not found")
    row.status = body.status
    await db.commit()
    return {"id": row.id, "status": row.status}


@router.get("/hr/role-titles")
async def list_hr_role_titles(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.scalars(select(HrRoleTitle).order_by(HrRoleTitle.title_name))).all()
    return [
        {
            "id": r.id,
            "corporation_id": int(r.corporation_id),
            "title_id": int(r.title_id),
            "title_name": r.title_name,
            "description": r.description,
            "active": r.active,
        }
        for r in rows
    ]


@router.post("/hr/role-titles", status_code=201)
async def create_hr_role_title(body: HrRoleTitleIn, db: AsyncSession = Depends(get_db)) -> dict:
    row = HrRoleTitle(
        corporation_id=body.corporation_id,
        title_id=body.title_id,
        title_name=body.title_name,
        description=body.description,
        active=body.active,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "corporation_id": int(row.corporation_id),
        "title_id": int(row.title_id),
        "title_name": row.title_name,
        "description": row.description,
        "active": row.active,
    }


@router.patch("/hr/role-titles/{title_row_id}")
async def patch_hr_role_title(
    title_row_id: int, body: HrRoleTitlePatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(HrRoleTitle, title_row_id)
    if not row:
        raise HTTPException(404, detail="HR role title not found")
    if body.title_name is not None:
        row.title_name = body.title_name
    if body.description is not None:
        row.description = body.description
    if body.active is not None:
        row.active = body.active
    await db.commit()
    return {
        "id": row.id,
        "corporation_id": int(row.corporation_id),
        "title_id": int(row.title_id),
        "title_name": row.title_name,
        "description": row.description,
        "active": row.active,
    }


@router.delete("/hr/role-titles/{title_row_id}")
async def delete_hr_role_title(title_row_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(HrRoleTitle, title_row_id)
    if not row:
        raise HTTPException(404, detail="HR role title not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": title_row_id}


def _rule_out(r: HrAuditAlertRule) -> dict:
    return {
        "id": r.id,
        "rule_key": r.rule_key,
        "name": r.name,
        "description": r.description,
        "enabled": r.enabled,
        "severity": r.severity,
        "rule_type": r.rule_type,
        "match_json": r.match_json,
        "webhook_url": r.webhook_url,
        "notify_in_app": r.notify_in_app,
        "cooldown_hours": r.cooldown_hours,
    }


@router.get("/hr/audit-rules")
async def list_hr_audit_rules(db: AsyncSession = Depends(get_db)) -> list[dict]:
    from app.services.hr_alert_engine import seed_default_hr_rules

    if not await db.scalar(select(HrAuditAlertRule).limit(1)):
        await seed_default_hr_rules(db)
        await db.commit()
    rows = (await db.scalars(select(HrAuditAlertRule).order_by(HrAuditAlertRule.name))).all()
    return [_rule_out(r) for r in rows]


@router.post("/hr/audit-rules", status_code=201)
async def create_hr_audit_rule(body: HrAuditRuleIn, db: AsyncSession = Depends(get_db)) -> dict:
    exists = await db.scalar(select(HrAuditAlertRule).where(HrAuditAlertRule.rule_key == body.rule_key))
    if exists:
        raise HTTPException(400, detail="rule_key already exists")
    row = HrAuditAlertRule(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _rule_out(row)


@router.patch("/hr/audit-rules/{rule_id}")
async def patch_hr_audit_rule(
    rule_id: int, body: HrAuditRulePatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(HrAuditAlertRule, rule_id)
    if not row:
        raise HTTPException(404, detail="Audit rule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return _rule_out(row)


@router.delete("/hr/audit-rules/{rule_id}")
async def delete_hr_audit_rule(rule_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(HrAuditAlertRule, rule_id)
    if not row:
        raise HTTPException(404, detail="Audit rule not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": rule_id}


@router.patch("/tax-rules/{rule_id}")
async def patch_tax_rule(
    rule_id: int, body: TaxRulePatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(StructureTaxRule, rule_id)
    if not row:
        raise HTTPException(404, detail="Tax rule not found")
    if body.r16_pct is not None:
        row.r16_pct = body.r16_pct
    if body.r32_pct is not None:
        row.r32_pct = body.r32_pct
    if body.r64_pct is not None:
        row.r64_pct = body.r64_pct
    if body.pattern is not None:
        row.pattern = body.pattern
    if body.priority is not None:
        row.priority = body.priority
    if body.active is not None:
        row.active = body.active
    await db.commit()
    return {
        "id": row.id,
        "pattern": row.pattern,
        "r16_pct": str(row.r16_pct),
        "r32_pct": str(row.r32_pct),
        "r64_pct": str(row.r64_pct),
    }


@router.patch("/services/lock")
async def emergency_service_lock(body: ServiceLockPatch, db: AsyncSession = Depends(get_db)) -> dict:
    cfg = await load_sync_config(db)
    cfg.enabled = not body.locked
    if body.locked and body.reason:
        cfg.mumble_server_json = json.dumps({"lock_reason": body.reason, "locked_at": datetime.now(UTC).isoformat()})
    await db.commit()
    return {"service_sync_enabled": cfg.enabled, "locked": body.locked}


# --- Storefront ---


@router.get("/storefront/config")
async def get_storefront_config_admin(db: AsyncSession = Depends(get_db)) -> dict:
    await ensure_storefront_defaults(db)
    cfg = await get_storefront_config(db)
    return _config_out(cfg)


@router.patch("/storefront/config")
async def patch_storefront_config(body: StorefrontConfigPatch, db: AsyncSession = Depends(get_db)) -> dict:
    cfg = await get_storefront_config(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    await db.commit()
    await db.refresh(cfg)
    return _config_out(cfg)


@router.get("/storefront/catalog")
async def storefront_catalog_admin(db: AsyncSession = Depends(get_db)) -> dict:
    await ensure_storefront_defaults(db)
    return await build_catalog(db, include_hidden=True)


@router.get("/storefront/locations")
async def list_storefront_locations(db: AsyncSession = Depends(get_db)) -> list[dict]:
    await ensure_storefront_defaults(db)
    return await list_pickup_locations_admin(db)


@router.post("/storefront/locations", status_code=201)
async def create_storefront_location(body: StorefrontLocationIn, db: AsyncSession = Depends(get_db)) -> dict:
    if body.is_default:
        for row in (await db.scalars(select(StorefrontPickupLocation))).all():
            row.is_default = False
    row = StorefrontPickupLocation(**body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _location_out(row)


@router.patch("/storefront/locations/{row_id}")
async def patch_storefront_location(
    row_id: int, body: StorefrontLocationPatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(StorefrontPickupLocation, row_id)
    if not row:
        raise HTTPException(404, detail="Location not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_default"):
        for other in (await db.scalars(select(StorefrontPickupLocation))).all():
            other.is_default = False
    for field, value in data.items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return _location_out(row)


@router.delete("/storefront/locations/{row_id}")
async def delete_storefront_location(row_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(StorefrontPickupLocation, row_id)
    if not row:
        raise HTTPException(404, detail="Location not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": row_id}


@router.get("/storefront/overrides")
async def list_storefront_overrides(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await list_overrides_admin(db)


@router.post("/storefront/overrides", status_code=201)
async def create_storefront_override(body: StorefrontOverrideIn, db: AsyncSession = Depends(get_db)) -> dict:
    exists = await db.scalar(
        select(StorefrontItemOverride).where(StorefrontItemOverride.type_id == body.type_id)
    )
    if exists:
        raise HTTPException(400, detail="Override for type_id already exists")
    row = StorefrontItemOverride(
        type_id=body.type_id,
        type_name=body.type_name,
        price_override_isk=body.price_override_isk,
        fake_qty_add=body.fake_qty_add,
        hidden=body.hidden,
        note=body.note,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "type_id": row.type_id,
        "type_name": row.type_name,
        "price_override_isk": float(row.price_override_isk) if row.price_override_isk is not None else None,
        "fake_qty_add": row.fake_qty_add,
        "hidden": row.hidden,
        "note": row.note,
    }


@router.patch("/storefront/overrides/{row_id}")
async def patch_storefront_override(
    row_id: int, body: StorefrontOverridePatch, db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(StorefrontItemOverride, row_id)
    if not row:
        raise HTTPException(404, detail="Override not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return {
        "id": row.id,
        "type_id": row.type_id,
        "type_name": row.type_name,
        "price_override_isk": float(row.price_override_isk) if row.price_override_isk is not None else None,
        "fake_qty_add": row.fake_qty_add,
        "hidden": row.hidden,
        "note": row.note,
    }


@router.delete("/storefront/overrides/{row_id}")
async def delete_storefront_override(row_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.get(StorefrontItemOverride, row_id)
    if not row:
        raise HTTPException(404, detail="Override not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": row_id}


@router.get("/storefront/kits")
async def list_storefront_kits(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await list_kits_admin(db)


@router.post("/storefront/kits", status_code=201)
async def create_storefront_kit(body: StorefrontKitIn, db: AsyncSession = Depends(get_db)) -> dict:
    kit = StorefrontKit(
        name=body.name,
        description=body.description,
        price_isk=body.price_isk,
        active=body.active,
        sort_order=body.sort_order,
    )
    db.add(kit)
    await db.flush()
    for item in body.items:
        db.add(
            StorefrontKitItem(
                kit_id=kit.id,
                type_id=item.type_id,
                type_name=item.type_name,
                quantity=item.quantity,
            )
        )
    await db.commit()
    kit = await db.scalar(
        select(StorefrontKit).options(selectinload(StorefrontKit.items)).where(StorefrontKit.id == kit.id)
    )
    return _kit_out(kit)


@router.patch("/storefront/kits/{kit_id}")
async def patch_storefront_kit(kit_id: int, body: StorefrontKitPatch, db: AsyncSession = Depends(get_db)) -> dict:
    kit = await db.scalar(
        select(StorefrontKit).options(selectinload(StorefrontKit.items)).where(StorefrontKit.id == kit_id)
    )
    if not kit:
        raise HTTPException(404, detail="Kit not found")
    data = body.model_dump(exclude_unset=True)
    items = data.pop("items", None)
    for field, value in data.items():
        setattr(kit, field, value)
    if items is not None:
        kit.items.clear()
        await db.flush()
        for raw in items:
            item = StorefrontKitItemIn.model_validate(raw)
            db.add(
                StorefrontKitItem(
                    kit_id=kit.id,
                    type_id=item.type_id,
                    type_name=item.type_name or "",
                    quantity=item.quantity,
                )
            )
    await db.commit()
    kit = await db.scalar(
        select(StorefrontKit).options(selectinload(StorefrontKit.items)).where(StorefrontKit.id == kit_id)
    )
    return _kit_out(kit)


@router.delete("/storefront/kits/{kit_id}")
async def delete_storefront_kit(kit_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    kit = await db.get(StorefrontKit, kit_id)
    if not kit:
        raise HTTPException(404, detail="Kit not found")
    await db.delete(kit)
    await db.commit()
    return {"deleted": kit_id}


@router.get("/storefront/orders")
async def list_storefront_orders(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await list_orders_admin(db)


@router.patch("/storefront/orders/{order_id}")
async def patch_storefront_order(
    order_id: int, body: StorefrontOrderStatusPatch, db: AsyncSession = Depends(get_db)
) -> dict:
    order = await db.get(StorefrontOrder, order_id)
    if not order:
        raise HTTPException(404, detail="Order not found")
    order.status = body.status
    await db.commit()
    await db.refresh(order)
    return _order_out(order)
