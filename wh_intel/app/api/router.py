"""HTTP API for intel ingest and map overlays."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.parser import parse_log_chunk
from app.services import intel_store, map_data, sov, wanderer_bridge

router = APIRouter(prefix="/api/v1")


class IngestBody(BaseModel):
    text: str = Field(..., description="Raw chat log chunk (one or more lines)")
    log_date: datetime | None = None


class BubbleBody(BaseModel):
    from_system_id: int
    to_system_id: int
    side: str = Field(..., pattern="^(from|to)$")
    note: str = ""
    placed_by: str = ""


class TagBody(BaseModel):
    solar_system_id: int
    tag: str
    source: str = "manual"


@router.post("/ingest")
async def ingest_chat(body: IngestBody, session: AsyncSession = Depends(get_db)):
    lines = parse_log_chunk(
        body.text,
        allowed_channels=settings.channel_set(),
        log_date=body.log_date,
    )
    if not lines:
        return {"accepted": 0, "ping_ids": [], "wanderer": []}

    resolved: list = []
    for line in lines:
        if line.solar_system_id:
            resolved.append(line)
        else:
            inferred = await intel_store.resolve_last_system(session, line)
            if inferred:
                resolved.append(inferred)
    if not resolved:
        return {"accepted": 0, "ping_ids": [], "wanderer": [], "skipped": len(lines)}

    ping_ids = await intel_store.store_intel_lines(session, resolved)
    wanderer_results = []
    for line in resolved:
        wanderer_results.append(await wanderer_bridge.sync_intel_line(line))
    return {"accepted": len(ping_ids), "ping_ids": ping_ids, "wanderer": wanderer_results}


@router.get("/overlay")
async def get_overlay(session: AsyncSession = Depends(get_db)):
    await intel_store.prune_expired(session)
    pings = await intel_store.active_pings(session)
    ping_ids = [p.id for p in pings]
    entities = await intel_store.entities_for_pings(session, ping_ids)

    system_ids = {p.solar_system_id for p in pings}
    bubble_rows = await intel_store.list_gate_bubbles(session)
    for b in bubble_rows:
        system_ids.add(b.from_system_id)
        system_ids.add(b.to_system_id)

    systems, jumps = await map_data.fetch_map_subset(session, system_ids, hop=1)
    tags = await intel_store.list_system_tags(session)

    now = datetime.now(timezone.utc)
    rings = []
    for p in pings:
        remaining = max(0, int((p.expires_at - now).total_seconds()))
        rings.append(
            {
                "system_id": p.solar_system_id,
                "system_name": p.solar_system_name,
                "channel": p.channel,
                "reported_at": p.reported_at.isoformat(),
                "expires_at": p.expires_at.isoformat(),
                "remaining_seconds": remaining,
                "entities": [
                    {
                        "type": e.entity_type,
                        "id": e.entity_id,
                        "name": e.name,
                        "portrait_url": e.portrait_url,
                    }
                    for e in entities.get(p.id, [])
                ],
                "raw_line": p.raw_line,
            }
        )

    return {
        "ring_ttl_seconds": settings.ring_ttl_seconds,
        "rings": rings,
        "systems": [
            {
                "id": s.solar_system_id,
                "name": s.name,
                "security": s.security,
                "x": s.x,
                "y": s.y,
                "tags": tags.get(s.solar_system_id, []),
            }
            for s in systems
        ],
        "jumps": [
            {"from": j.from_system_id, "to": j.to_system_id} for j in jumps
        ],
        "bubbles": [
            {
                "id": b.id,
                "from_system_id": b.from_system_id,
                "to_system_id": b.to_system_id,
                "side": b.side,
                "note": b.note,
                "placed_by": b.placed_by,
            }
            for b in bubble_rows
        ],
    }


@router.post("/bubbles")
async def create_bubble(body: BubbleBody, session: AsyncSession = Depends(get_db)):
    bubble = await intel_store.add_gate_bubble(
        session,
        from_system_id=body.from_system_id,
        to_system_id=body.to_system_id,
        side=body.side,
        note=body.note,
        placed_by=body.placed_by,
    )
    w = await wanderer_bridge.sync_gate_bubble(
        body.from_system_id,
        body.to_system_id,
        side=body.side,
        note=body.note,
    )
    return {"id": bubble.id, "wanderer": w}


@router.delete("/bubbles/{bubble_id}")
async def delete_bubble(bubble_id: int, session: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    from app.models import GateBubble

    result = await session.execute(delete(GateBubble).where(GateBubble.id == bubble_id))
    await session.commit()
    if not result.rowcount:
        raise HTTPException(status_code=404, detail="Bubble not found")
    return {"deleted": bubble_id}


@router.post("/tags")
async def add_tag(body: TagBody, session: AsyncSession = Depends(get_db)):
    row = await intel_store.add_system_tag(
        session,
        solar_system_id=body.solar_system_id,
        tag=body.tag,
        source=body.source,
    )
    return {"id": row.id, "tag": row.tag}


@router.delete("/tags")
async def remove_tag(
    solar_system_id: int,
    tag: str,
    source: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    n = await intel_store.remove_system_tag(
        session,
        solar_system_id=solar_system_id,
        tag=tag,
        source=source,
    )
    return {"removed": n}


@router.post("/sov/refresh")
async def refresh_sov(session: AsyncSession = Depends(get_db)):
    count = await sov.refresh_sov_tags(session)
    return {"tagged_systems": count}
