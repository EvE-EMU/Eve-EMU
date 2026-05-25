"""Persist intel pings, bubbles, tags."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import GateBubble, IntelEntity, IntelPing, SystemTag
from app.parser import ParsedEntity, ParsedIntelLine, portrait_url_for
from app.services import map_data


async def resolve_last_system(session: AsyncSession, line: ParsedIntelLine) -> ParsedIntelLine | None:
    """For 'Character location?' lines, use the most recent active ping for that character."""
    if line.solar_system_id:
        return line

    now = datetime.now(timezone.utc)
    for ent in line.entities:
        if ent.entity_type != "character":
            continue
        result = await session.execute(
            select(IntelPing.solar_system_id, IntelPing.solar_system_name)
            .join(IntelEntity, IntelEntity.ping_id == IntelPing.id)
            .where(
                IntelEntity.entity_type == "character",
                IntelEntity.entity_id == ent.entity_id,
                IntelPing.expires_at >= now,
            )
            .order_by(IntelPing.reported_at.desc())
            .limit(1)
        )
        row = result.first()
        if row:
            line.solar_system_id = int(row[0])
            line.solar_system_name = str(row[1])
            line.inferred_system = True
            return line
    return None


async def store_intel_lines(session: AsyncSession, lines: list[ParsedIntelLine]) -> list[int]:
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=settings.ring_ttl_seconds)
    ping_ids: list[int] = []

    await map_data.ensure_systems(
        session,
        {line.solar_system_id: line.solar_system_name for line in lines},
    )

    for line in lines:
        ping = IntelPing(
            channel=line.channel,
            reported_at=line.reported_at,
            expires_at=now + ttl,
            solar_system_id=line.solar_system_id,
            solar_system_name=line.solar_system_name,
            raw_line=line.raw_line,
        )
        session.add(ping)
        await session.flush()
        ping_ids.append(ping.id)

        for ent in line.entities:
            session.add(
                IntelEntity(
                    ping_id=ping.id,
                    entity_type=ent.entity_type,
                    entity_id=ent.entity_id,
                    name=ent.name,
                    showinfo_type=ent.showinfo_type,
                    portrait_url=portrait_url_for(ent.entity_type, ent.entity_id),
                )
            )
    await session.commit()
    return ping_ids


async def prune_expired(session: AsyncSession) -> list[int]:
    """Delete expired rows; return solar system IDs whose intel just expired."""
    now = datetime.now(timezone.utc)
    from sqlalchemy import select

    expiring = await session.execute(
        select(IntelPing.solar_system_id).where(IntelPing.expires_at < now)
    )
    expired_systems = {row[0] for row in expiring.all()}

    await session.execute(delete(IntelPing).where(IntelPing.expires_at < now))
    await session.execute(
        delete(GateBubble).where(
            GateBubble.expires_at.is_not(None),
            GateBubble.expires_at < now,
        )
    )
    await session.commit()

    if not expired_systems:
        return []

    still_active = await session.execute(
        select(IntelPing.solar_system_id).where(
            IntelPing.expires_at >= now,
            IntelPing.solar_system_id.in_(expired_systems),
        )
    )
    still = {row[0] for row in still_active.all()}
    return sorted(expired_systems - still)


async def active_pings(session: AsyncSession) -> list[IntelPing]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(IntelPing)
        .where(IntelPing.expires_at >= now)
        .order_by(IntelPing.reported_at.desc())
    )
    return list(result.scalars().all())


async def entities_for_pings(session: AsyncSession, ping_ids: list[int]) -> dict[int, list[IntelEntity]]:
    if not ping_ids:
        return {}
    result = await session.execute(
        select(IntelEntity).where(IntelEntity.ping_id.in_(ping_ids))
    )
    grouped: dict[int, list[IntelEntity]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.ping_id, []).append(row)
    return grouped


async def add_gate_bubble(
    session: AsyncSession,
    *,
    from_system_id: int,
    to_system_id: int,
    side: str,
    note: str = "",
    placed_by: str = "",
) -> GateBubble:
    expires_at = None
    if settings.bubble_ttl_seconds > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.bubble_ttl_seconds)
    bubble = GateBubble(
        from_system_id=from_system_id,
        to_system_id=to_system_id,
        side=side,
        note=note,
        placed_by=placed_by,
        expires_at=expires_at,
    )
    session.add(bubble)
    await session.commit()
    await session.refresh(bubble)
    return bubble


async def list_gate_bubbles(session: AsyncSession) -> list[GateBubble]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(GateBubble).where(
            (GateBubble.expires_at.is_(None)) | (GateBubble.expires_at >= now)
        )
    )
    return list(result.scalars().all())


async def add_system_tag(
    session: AsyncSession,
    *,
    solar_system_id: int,
    tag: str,
    source: str = "manual",
) -> SystemTag:
    existing = await session.execute(
        select(SystemTag).where(
            SystemTag.solar_system_id == solar_system_id,
            SystemTag.tag == tag,
            SystemTag.source == source,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        return row
    row = SystemTag(solar_system_id=solar_system_id, tag=tag, source=source)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def remove_system_tag(
    session: AsyncSession,
    *,
    solar_system_id: int,
    tag: str,
    source: str | None = None,
) -> int:
    q = delete(SystemTag).where(
        SystemTag.solar_system_id == solar_system_id,
        SystemTag.tag == tag,
    )
    if source:
        q = q.where(SystemTag.source == source)
    result = await session.execute(q)
    await session.commit()
    return result.rowcount or 0


async def list_system_tags(session: AsyncSession) -> dict[int, list[dict[str, str]]]:
    result = await session.execute(select(SystemTag))
    grouped: dict[int, list[dict[str, str]]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.solar_system_id, []).append(
            {"tag": row.tag, "source": row.source}
        )
    return grouped
