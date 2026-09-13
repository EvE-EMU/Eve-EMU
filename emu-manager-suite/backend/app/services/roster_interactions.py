"""Roster-wide interaction rollups — optimized for large alt lists."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import CharacterInteractionAggregate
from app.services.character_roster import load_roster, resolve_owner_user_id
from app.services.esi import resolve_universe_names


async def build_roster_interactions(
    session: AsyncSession,
    viewer_character_id: int,
    *,
    q: str = "",
    kind: str = "",
    counterparty_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    rollup: bool = False,
) -> dict:
    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    if owner_id is None:
        roster = await load_roster(session, viewer_character_id)
        if not roster:
            return {"total": 0, "rows": [], "by_character": []}
        owner_id = viewer_character_id

    base = select(
        CharacterInteractionAggregate.counterparty_id,
        CharacterInteractionAggregate.counterparty_kind,
        *([] if rollup else [CharacterInteractionAggregate.channel]),
        func.max(CharacterInteractionAggregate.counterparty_name).label("counterparty_name"),
        func.sum(CharacterInteractionAggregate.event_count).label("event_count"),
        func.sum(CharacterInteractionAggregate.total_amount_isk).label("total_amount_isk"),
        func.min(CharacterInteractionAggregate.first_seen_at).label("first_seen_at"),
        func.max(CharacterInteractionAggregate.last_seen_at).label("last_seen_at"),
        func.max(CharacterInteractionAggregate.last_detail).label("last_detail"),
        func.count(func.distinct(CharacterInteractionAggregate.character_id)).label("alt_count"),
    ).where(CharacterInteractionAggregate.owner_user_id == int(owner_id))

    if counterparty_id is not None:
        base = base.where(CharacterInteractionAggregate.counterparty_id == int(counterparty_id))
    if kind:
        base = base.where(CharacterInteractionAggregate.counterparty_kind == kind)
    if q.strip():
        pattern = f"%{q.strip()}%"
        base = base.where(
            or_(
                CharacterInteractionAggregate.counterparty_name.ilike(pattern),
                CharacterInteractionAggregate.last_detail.ilike(pattern),
            )
        )

    grouped = base.group_by(
        CharacterInteractionAggregate.counterparty_id,
        CharacterInteractionAggregate.counterparty_kind,
        *([] if rollup else [CharacterInteractionAggregate.channel]),
    ).subquery()

    total = await session.scalar(select(func.count()).select_from(grouped)) or 0

    rows_q = (
        select(grouped)
        .order_by(grouped.c.event_count.desc(), grouped.c.last_seen_at.desc())
        .limit(min(limit, 500))
        .offset(max(offset, 0))
    )
    rows = (await session.execute(rows_q)).all()

    out_rows = [
        {
            "counterparty_id": int(r.counterparty_id),
            "counterparty_kind": r.counterparty_kind,
            "counterparty_name": r.counterparty_name or f"Entity {r.counterparty_id}",
            "channel": getattr(r, "channel", None) if not rollup else None,
            "event_count": int(r.event_count or 0),
            "total_amount_isk": str(r.total_amount_isk or 0),
            "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
            "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
            "last_detail": r.last_detail or "",
            "alt_count": int(r.alt_count or 0),
        }
        for r in rows
    ]

    by_character: list[dict] = []
    if counterparty_id is not None:
        detail_rows = (
            await session.scalars(
                select(CharacterInteractionAggregate)
                .where(
                    CharacterInteractionAggregate.owner_user_id == int(owner_id),
                    CharacterInteractionAggregate.counterparty_id == int(counterparty_id),
                )
                .order_by(CharacterInteractionAggregate.event_count.desc())
                .limit(200)
            )
        ).all()
        char_ids = {int(d.character_id) for d in detail_rows}
        roster = await load_roster(session, viewer_character_id)
        names = {r.character_id: r.character_name for r in roster}
        for d in detail_rows:
            by_character.append(
                {
                    "character_id": int(d.character_id),
                    "character_name": names.get(int(d.character_id), f"Char {d.character_id}"),
                    "channel": d.channel,
                    "event_count": int(d.event_count),
                    "total_amount_isk": str(d.total_amount_isk),
                    "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
                    "last_detail": d.last_detail,
                }
            )
        missing_names = [cid for cid in char_ids if cid not in names]
        if missing_names:
            resolved = await resolve_universe_names(missing_names)
            for item in by_character:
                if item["character_name"].startswith("Char "):
                    item["character_name"] = resolved.get(item["character_id"], item["character_name"])

    # Attach spy-o-meter scores for the page of counterparties
    from app.services.spy_meter import TAG_TYPES, build_spy_scores_for_entities

    entity_ids = list({int(r["counterparty_id"]) for r in out_rows})
    scores = await build_spy_scores_for_entities(session, int(owner_id), entity_ids)
    for row in out_rows:
        scored = scores.get(int(row["counterparty_id"]))
        if scored:
            row["spy_score"] = scored["spy_score"]
            row["recommendation"] = scored["recommendation"]
            row["recommendation_label"] = scored["recommendation_label"]
            row["signals"] = scored["signals"]
            row["tags"] = scored["tags"]
            row["channels"] = scored["channels"]
            row["blacklisted"] = scored["blacklisted"]
            row["public_links"] = scored["public_links"]
        else:
            row["spy_score"] = 0
            row["recommendation"] = "low"
            row["recommendation_label"] = "Low signal"
            row["signals"] = []
            row["tags"] = []
            row["channels"] = {}
            row["blacklisted"] = False
            row["public_links"] = {}

    detail_score = None
    if counterparty_id is not None:
        detail_score = scores.get(int(counterparty_id))

    return {
        "total": int(total),
        "rows": out_rows,
        "by_character": by_character,
        "rollup": rollup,
        "detail": detail_score,
        "tag_types": {k: {"label": v["label"], "tone": v["tone"]} for k, v in TAG_TYPES.items()},
    }



async def build_roster_interaction_summary(
    session: AsyncSession,
    viewer_character_id: int,
) -> dict:
    """Top counterparty totals for dashboard strip — single query."""
    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    if owner_id is None:
        return {"counterparty_count": 0, "interaction_events": 0, "top_counterparties": []}

    grouped = (
        select(
            CharacterInteractionAggregate.counterparty_id,
            func.max(CharacterInteractionAggregate.counterparty_name).label("name"),
            func.max(CharacterInteractionAggregate.counterparty_kind).label("kind"),
            func.sum(CharacterInteractionAggregate.event_count).label("events"),
        )
        .where(CharacterInteractionAggregate.owner_user_id == int(owner_id))
        .group_by(CharacterInteractionAggregate.counterparty_id)
        .order_by(func.sum(CharacterInteractionAggregate.event_count).desc())
        .limit(12)
    )
    rows = (await session.execute(grouped)).all()
    counterparty_count = await session.scalar(
        select(func.count(func.distinct(CharacterInteractionAggregate.counterparty_id))).where(
            CharacterInteractionAggregate.owner_user_id == int(owner_id)
        )
    )
    total_events = await session.scalar(
        select(func.coalesce(func.sum(CharacterInteractionAggregate.event_count), 0)).where(
            CharacterInteractionAggregate.owner_user_id == int(owner_id)
        )
    )
    return {
        "counterparty_count": int(counterparty_count or 0),
        "interaction_events": int(total_events or 0),
        "top_counterparties": [
            {
                "counterparty_id": int(r.counterparty_id),
                "counterparty_name": r.name or f"Entity {r.counterparty_id}",
                "counterparty_kind": r.kind,
                "event_count": int(r.events or 0),
            }
            for r in rows
        ],
    }
