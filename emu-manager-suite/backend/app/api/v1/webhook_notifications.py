"""User webhook notification rule CRUD."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.member_audit import WebhookNotificationDelivery, WebhookNotificationRule
from app.services.character_roster import resolve_owner_user_id, roster_character_ids
from app.services.rbac import UserAuthContext
from app.services.webhook_notification_engine import DELIVERY_MODES, EVENT_CATALOG

router = APIRouter(prefix="/webhook-notifications", tags=["Webhook Notifications"])


class WebhookRuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(default="", max_length=2000)
    enabled: bool = True
    event_type: str = Field(..., min_length=2, max_length=64)
    match_json: str = "{}"
    webhook_url: str = Field(default="", max_length=512)
    notify_in_app: bool = True
    delivery_mode: Literal["instant", "hourly", "4h", "8h", "daily", "weekly"] = "instant"
    all_characters: bool = True
    target_character_id: int | None = None


class WebhookRulePatch(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    enabled: bool | None = None
    match_json: str | None = None
    webhook_url: str | None = Field(default=None, max_length=512)
    notify_in_app: bool | None = None
    delivery_mode: Literal["instant", "hourly", "4h", "8h", "daily", "weekly"] | None = None
    all_characters: bool | None = None
    target_character_id: int | None = None


def _rule_out(r: WebhookNotificationRule) -> dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "enabled": r.enabled,
        "event_type": r.event_type,
        "match_json": r.match_json,
        "webhook_url": r.webhook_url,
        "notify_in_app": r.notify_in_app,
        "delivery_mode": r.delivery_mode,
        "all_characters": r.all_characters,
        "target_character_id": r.target_character_id,
        "last_digest_at": r.last_digest_at.isoformat() if r.last_digest_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


async def _require_owner(session: AsyncSession, auth: UserAuthContext) -> int:
    owner_id = await resolve_owner_user_id(session, auth.character_id)
    if owner_id is None:
        raise HTTPException(401, detail="Login required")
    return int(owner_id)


@router.get("/catalog")
async def webhook_notification_catalog() -> dict[str, Any]:
    return {
        "events": EVENT_CATALOG,
        "delivery_modes": [
            {"id": k, "label": v["label"], "seconds": v["seconds"]} for k, v in DELIVERY_MODES.items()
        ],
    }


@router.get("/rules")
async def list_webhook_rules(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> list[dict]:
    owner_id = await _require_owner(db, auth)
    rows = (
        await db.scalars(
            select(WebhookNotificationRule)
            .where(WebhookNotificationRule.owner_user_id == owner_id)
            .order_by(WebhookNotificationRule.name)
        )
    ).all()
    return [_rule_out(r) for r in rows]


@router.post("/rules", status_code=201)
async def create_webhook_rule(
    body: WebhookRuleIn,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    owner_id = await _require_owner(db, auth)
    valid_events = {e["event_type"] for e in EVENT_CATALOG}
    if body.event_type not in valid_events:
        raise HTTPException(400, detail="Unknown event_type")
    if not body.all_characters and not body.target_character_id:
        raise HTTPException(400, detail="Select a target character or enable all characters")
    if body.target_character_id:
        roster = await roster_character_ids(db, auth.character_id)
        if int(body.target_character_id) not in roster:
            raise HTTPException(403, detail="Target character not in your roster")

    row = WebhookNotificationRule(
        owner_user_id=owner_id,
        created_by_character_id=int(auth.character_id),
        **body.model_dump(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _rule_out(row)


@router.patch("/rules/{rule_id}")
async def patch_webhook_rule(
    rule_id: int,
    body: WebhookRulePatch,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    owner_id = await _require_owner(db, auth)
    row = await db.get(WebhookNotificationRule, rule_id)
    if not row or int(row.owner_user_id) != owner_id:
        raise HTTPException(404, detail="Rule not found")
    if body.target_character_id is not None:
        roster = await roster_character_ids(db, auth.character_id)
        if int(body.target_character_id) not in roster:
            raise HTTPException(403, detail="Target character not in your roster")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    return _rule_out(row)


@router.delete("/rules/{rule_id}")
async def delete_webhook_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
) -> dict:
    owner_id = await _require_owner(db, auth)
    row = await db.get(WebhookNotificationRule, rule_id)
    if not row or int(row.owner_user_id) != owner_id:
        raise HTTPException(404, detail="Rule not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": rule_id}


@router.get("/deliveries")
async def list_webhook_deliveries(
    db: AsyncSession = Depends(get_db),
    auth: UserAuthContext = Depends(get_current_user),
    limit: int = 50,
) -> list[dict]:
    owner_id = await _require_owner(db, auth)
    rule_ids = [
        int(r.id)
        for r in (
            await db.scalars(
                select(WebhookNotificationRule.id).where(
                    WebhookNotificationRule.owner_user_id == owner_id
                )
            )
        ).all()
    ]
    if not rule_ids:
        return []
    rows = (
        await db.scalars(
            select(WebhookNotificationDelivery)
            .where(WebhookNotificationDelivery.rule_id.in_(rule_ids))
            .order_by(WebhookNotificationDelivery.created_at.desc())
            .limit(min(limit, 100))
        )
    ).all()
    return [
        {
            "id": d.id,
            "rule_id": d.rule_id,
            "character_id": int(d.character_id),
            "delivery_mode": d.delivery_mode,
            "event_count": d.event_count,
            "webhook_status": d.webhook_status,
            "detail": d.detail,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ]
