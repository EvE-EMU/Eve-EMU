"""Spy-o-meter — rank counterparties as likely alts / intel risks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member_audit import (
    AuditSecurityFlag,
    CharacterInteractionAggregate,
    IntelEntityTag,
)
from app.models.onboarding import CharacterStanding
from app.models.tools import HrAccountFlag, HrBlacklistEntry
from app.services.character_roster import load_roster, resolve_owner_user_id
from app.services.entity_classify import classify_entity_id
from app.services.esi import resolve_universe_names

TAG_TYPES = {
    "spy_alt": {"label": "Spy alt", "score": 55, "tone": "danger"},
    "known_alt": {"label": "Known alt", "score": 50, "tone": "danger"},
    "holding_corp": {"label": "Holding corp", "score": 40, "tone": "warn"},
    "hostile": {"label": "Hostile", "score": 25, "tone": "warn"},
    "watchlist": {"label": "Watchlist", "score": 18, "tone": "warn"},
    "trusted": {"label": "Trusted", "score": -30, "tone": "ok"},
}

# Channel weights: (points per event, hard cap)
CHANNEL_WEIGHTS: dict[str, tuple[float, float]] = {
    "combat_fleet": (12.0, 45.0),  # flew together on zKill — strongest alt signal
    "contract": (10.0, 35.0),
    "wallet": (8.0, 30.0),
    "mail_received": (3.0, 12.0),
    "mail_sent": (3.0, 12.0),
    "contact": (6.0, 15.0),
    "combat_kill": (2.0, 8.0),
    "combat_loss": (2.0, 8.0),
}


def public_intel_links(entity_id: int, entity_kind: str) -> dict[str, str]:
    kind = (entity_kind or "character").lower()
    if kind == "corporation":
        return {
            "evewho": f"https://evewho.com/corporation/{entity_id}",
            "zkill": f"https://zkillboard.com/corporation/{entity_id}/",
            "eve411": f"https://eve411.com/corporation/{entity_id}",
        }
    if kind == "alliance":
        return {
            "evewho": f"https://evewho.com/alliance/{entity_id}",
            "zkill": f"https://zkillboard.com/alliance/{entity_id}/",
            "eve411": f"https://eve411.com/alliance/{entity_id}",
        }
    return {
        "evewho": f"https://evewho.com/character/{entity_id}",
        "zkill": f"https://zkillboard.com/character/{entity_id}/",
        "eve411": f"https://eve411.com/character/{entity_id}",
    }


def _recommendation(score: float) -> tuple[str, str]:
    if score >= 80:
        return "likely_alt", "Likely alt / high risk"
    if score >= 55:
        return "suspicious", "Suspicious — review"
    if score >= 30:
        return "watch", "Watch"
    return "low", "Low signal"


def _score_channels(channel_events: dict[str, int], wallet_isk: float) -> tuple[float, list[dict[str, Any]]]:
    signals: list[dict[str, Any]] = []
    total = 0.0
    for channel, count in channel_events.items():
        if count <= 0:
            continue
        per, cap = CHANNEL_WEIGHTS.get(channel, (1.0, 5.0))
        pts = min(cap, per * count)
        total += pts
        signals.append(
            {
                "key": f"channel:{channel}",
                "label": channel.replace("_", " ").title(),
                "points": round(pts, 1),
                "detail": f"{count} event(s)",
            }
        )
    if abs(wallet_isk) >= 10_000_000:
        bonus = min(15.0, abs(wallet_isk) / 100_000_000 * 10)
        total += bonus
        signals.append(
            {
                "key": "wallet_volume",
                "label": "Wallet volume",
                "points": round(bonus, 1),
                "detail": f"{wallet_isk:,.0f} ISK",
            }
        )
    return total, signals


async def _load_context(session: AsyncSession, owner_id: int) -> dict[str, Any]:
    tags = (
        await session.scalars(
            select(IntelEntityTag).where(
                IntelEntityTag.owner_user_id == owner_id,
                IntelEntityTag.active.is_(True),
            )
        )
    ).all()
    tags_by_entity: dict[int, list[IntelEntityTag]] = defaultdict(list)
    for t in tags:
        tags_by_entity[int(t.entity_id)].append(t)

    blacklist_rows = (
        await session.scalars(select(HrBlacklistEntry).where(HrBlacklistEntry.active.is_(True)))
    ).all()
    blacklist: dict[int, str] = {}
    for b in blacklist_rows:
        if b.character_id:
            blacklist[int(b.character_id)] = b.reason or "blacklisted"

    hr_flags = (
        await session.scalars(select(HrAccountFlag).where(HrAccountFlag.active.is_(True)))
    ).all()
    flags_by_entity: dict[int, list[str]] = defaultdict(list)
    for f in hr_flags:
        flags_by_entity[int(f.target_character_id)].append(f.flag_label or f.flag_key)

    sec_flags = (
        await session.scalars(
            select(AuditSecurityFlag).where(AuditSecurityFlag.resolved.is_(False))
        )
    ).all()
    for f in sec_flags:
        flags_by_entity[int(f.character_id)].append(f.flag_key)

    # Standings from any roster character's synced standings table
    roster_ids = (
        await session.scalars(
            select(CharacterInteractionAggregate.character_id)
            .where(CharacterInteractionAggregate.owner_user_id == owner_id)
            .distinct()
        )
    ).all()
    standings_map: dict[int, float] = {}
    if roster_ids:
        rows = (
            await session.scalars(
                select(CharacterStanding).where(CharacterStanding.character_id.in_(list(roster_ids)))
            )
        ).all()
        # Prefer most extreme standing seen across alts
        for r in rows:
            fid = int(r.from_id)
            val = float(r.standing)
            prev = standings_map.get(fid)
            if prev is None or abs(val) > abs(prev):
                standings_map[fid] = val

    return {
        "tags_by_entity": tags_by_entity,
        "blacklist": blacklist,
        "flags_by_entity": flags_by_entity,
        "standings_map": standings_map,
    }


def score_entity(
    *,
    entity_id: int,
    entity_kind: str,
    entity_name: str,
    channel_events: dict[str, int],
    wallet_isk: float,
    event_count: int,
    alt_count: int,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    score = 0.0

    ch_score, ch_signals = _score_channels(channel_events, wallet_isk)
    score += ch_score
    signals.extend(ch_signals)

    tags: list[IntelEntityTag] = ctx["tags_by_entity"].get(entity_id, [])
    tag_payload = []
    for t in tags:
        meta = TAG_TYPES.get(t.tag_type, {"label": t.tag_type, "score": 10, "tone": "warn"})
        pts = float(meta["score"])
        score += pts
        signals.append(
            {
                "key": f"tag:{t.tag_type}",
                "label": meta["label"],
                "points": pts,
                "detail": t.notes or (
                    f"Linked to {t.linked_character_name}" if t.linked_character_name else "Manual tag"
                ),
            }
        )
        tag_payload.append(
            {
                "id": t.id,
                "tag_type": t.tag_type,
                "label": meta["label"],
                "tone": meta.get("tone", "warn"),
                "linked_character_id": t.linked_character_id,
                "linked_character_name": t.linked_character_name,
                "notes": t.notes,
            }
        )

    if entity_id in ctx["blacklist"]:
        score += 40
        signals.append(
            {
                "key": "blacklist",
                "label": "Blacklisted",
                "points": 40,
                "detail": ctx["blacklist"][entity_id],
            }
        )

    for label in ctx["flags_by_entity"].get(entity_id, []):
        score += 12
        signals.append(
            {
                "key": f"flag:{label}",
                "label": f"Flag: {label}",
                "points": 12,
                "detail": "HR / security flag",
            }
        )

    standing = ctx["standings_map"].get(entity_id)
    if standing is not None:
        if standing <= -5:
            pts = min(20.0, abs(standing) * 2)
            score += pts
            signals.append(
                {
                    "key": "standing_neg",
                    "label": "Hostile standing",
                    "points": round(pts, 1),
                    "detail": f"{standing:+.1f}",
                }
            )
        elif standing >= 5 and not any(t.tag_type == "trusted" for t in tags):
            # High positive standing without trusted tag is mild interest (blue alt?)
            pts = min(8.0, standing)
            score += pts
            signals.append(
                {
                    "key": "standing_pos",
                    "label": "Strong positive standing",
                    "points": round(pts, 1),
                    "detail": f"{standing:+.1f}",
                }
            )

    # Multi-alt contact amplifies alt-network signal
    if alt_count >= 2:
        pts = min(10.0, (alt_count - 1) * 4)
        score += pts
        signals.append(
            {
                "key": "multi_alt",
                "label": "Multiple alts interacted",
                "points": round(pts, 1),
                "detail": f"{alt_count} roster characters",
            }
        )

    # Fleet + money/contracts together is a classic alt pattern
    if channel_events.get("combat_fleet", 0) and (
        channel_events.get("wallet", 0) or channel_events.get("contract", 0)
    ):
        score += 15
        signals.append(
            {
                "key": "fleet_and_money",
                "label": "Fleet + wallet/contracts",
                "points": 15,
                "detail": "Strong alt pattern",
            }
        )

    score = max(0.0, min(100.0, score))
    rec, rec_label = _recommendation(score)
    signals.sort(key=lambda s: s["points"], reverse=True)

    return {
        "entity_id": entity_id,
        "entity_kind": entity_kind,
        "entity_name": entity_name,
        "spy_score": round(score, 1),
        "recommendation": rec,
        "recommendation_label": rec_label,
        "signals": signals[:12],
        "tags": tag_payload,
        "channels": channel_events,
        "event_count": event_count,
        "wallet_isk": wallet_isk,
        "alt_count": alt_count,
        "blacklisted": entity_id in ctx["blacklist"],
        "public_links": public_intel_links(entity_id, entity_kind),
    }


async def build_spy_scores_for_entities(
    session: AsyncSession,
    owner_id: int,
    entity_ids: list[int] | None = None,
) -> dict[int, dict[str, Any]]:
    ctx = await _load_context(session, owner_id)

    q = (
        select(
            CharacterInteractionAggregate.counterparty_id,
            CharacterInteractionAggregate.counterparty_kind,
            func.max(CharacterInteractionAggregate.counterparty_name).label("name"),
            CharacterInteractionAggregate.channel,
            func.sum(CharacterInteractionAggregate.event_count).label("events"),
            func.sum(CharacterInteractionAggregate.total_amount_isk).label("isk"),
            func.count(func.distinct(CharacterInteractionAggregate.character_id)).label("alts"),
        )
        .where(CharacterInteractionAggregate.owner_user_id == owner_id)
        .group_by(
            CharacterInteractionAggregate.counterparty_id,
            CharacterInteractionAggregate.counterparty_kind,
            CharacterInteractionAggregate.channel,
        )
    )
    if entity_ids is not None:
        if not entity_ids:
            return {}
        q = q.where(CharacterInteractionAggregate.counterparty_id.in_(entity_ids))

    rows = (await session.execute(q)).all()

    by_entity: dict[int, dict[str, Any]] = {}
    for r in rows:
        eid = int(r.counterparty_id)
        bucket = by_entity.setdefault(
            eid,
            {
                "kind": r.counterparty_kind or "entity",
                "name": r.name or f"Entity {eid}",
                "channels": {},
                "isk": 0.0,
                "alts": 0,
                "events": 0,
            },
        )
        ch = str(r.channel or "")
        events = int(r.events or 0)
        bucket["channels"][ch] = bucket["channels"].get(ch, 0) + events
        bucket["isk"] += float(r.isk or 0)
        bucket["alts"] = max(bucket["alts"], int(r.alts or 0))
        bucket["events"] += events
        if r.name:
            bucket["name"] = r.name

    # Include tagged entities with no interaction rows yet
    if entity_ids is None:
        for eid, tags in ctx["tags_by_entity"].items():
            if eid not in by_entity and tags:
                t0 = tags[0]
                by_entity[eid] = {
                    "kind": t0.entity_kind or classify_entity_id(eid),
                    "name": t0.entity_name or f"Entity {eid}",
                    "channels": {},
                    "isk": 0.0,
                    "alts": 0,
                    "events": 0,
                }

    scores: dict[int, dict[str, Any]] = {}
    for eid, data in by_entity.items():
        scores[eid] = score_entity(
            entity_id=eid,
            entity_kind=data["kind"],
            entity_name=data["name"],
            channel_events=data["channels"],
            wallet_isk=data["isk"],
            event_count=data["events"],
            alt_count=data["alts"],
            ctx=ctx,
        )
    return scores


async def spy_meter_board(
    session: AsyncSession,
    viewer_character_id: int,
    *,
    min_score: float = 0,
    limit: int = 50,
) -> dict[str, Any]:
    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    if owner_id is None:
        return {"rows": [], "total": 0, "tag_types": TAG_TYPES}

    scores = await build_spy_scores_for_entities(session, int(owner_id))
    rows = sorted(scores.values(), key=lambda r: r["spy_score"], reverse=True)
    if min_score > 0:
        rows = [r for r in rows if r["spy_score"] >= min_score]
    return {
        "rows": rows[:limit],
        "total": len(rows),
        "tag_types": {k: {"label": v["label"], "tone": v["tone"]} for k, v in TAG_TYPES.items()},
        "legend": [
            {"channel": "combat_fleet", "label": "Fleet co-attacker (zKill)", "weight": "highest"},
            {"channel": "contract", "label": "Contracts", "weight": "high"},
            {"channel": "wallet", "label": "Wallet / trades", "weight": "high"},
            {"channel": "contact", "label": "Address book", "weight": "medium"},
            {"channel": "mail", "label": "Mail", "weight": "low"},
        ],
    }


async def list_intel_tags(session: AsyncSession, viewer_character_id: int) -> list[dict]:
    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    if owner_id is None:
        return []
    rows = (
        await session.scalars(
            select(IntelEntityTag)
            .where(IntelEntityTag.owner_user_id == int(owner_id), IntelEntityTag.active.is_(True))
            .order_by(IntelEntityTag.updated_at.desc())
        )
    ).all()
    out = []
    for t in rows:
        meta = TAG_TYPES.get(t.tag_type, {"label": t.tag_type, "tone": "warn"})
        out.append(
            {
                "id": t.id,
                "entity_id": int(t.entity_id),
                "entity_kind": t.entity_kind,
                "entity_name": t.entity_name,
                "tag_type": t.tag_type,
                "label": meta["label"],
                "tone": meta.get("tone", "warn"),
                "linked_character_id": t.linked_character_id,
                "linked_character_name": t.linked_character_name,
                "notes": t.notes,
                "public_links": public_intel_links(int(t.entity_id), t.entity_kind),
            }
        )
    return out


async def upsert_intel_tag(
    session: AsyncSession,
    *,
    viewer_character_id: int,
    viewer_character_name: str,
    entity_id: int,
    entity_kind: str = "",
    entity_name: str = "",
    tag_type: str,
    linked_character_id: int | None = None,
    linked_character_name: str = "",
    notes: str = "",
) -> dict[str, Any]:
    if tag_type not in TAG_TYPES:
        return {"error": f"Unknown tag_type. Use one of: {', '.join(TAG_TYPES)}"}

    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    if owner_id is None:
        owner_id = viewer_character_id

    kind = entity_kind or classify_entity_id(entity_id)
    name = entity_name
    if not name:
        names = await resolve_universe_names([entity_id])
        name = names.get(entity_id, f"Entity {entity_id}")

    linked_name = linked_character_name
    if linked_character_id and not linked_name:
        names = await resolve_universe_names([linked_character_id])
        linked_name = names.get(linked_character_id, f"Character {linked_character_id}")

    existing = await session.scalar(
        select(IntelEntityTag).where(
            IntelEntityTag.owner_user_id == int(owner_id),
            IntelEntityTag.entity_id == int(entity_id),
            IntelEntityTag.tag_type == tag_type,
        )
    )
    if existing:
        existing.active = True
        existing.entity_kind = kind
        existing.entity_name = name
        existing.linked_character_id = linked_character_id
        existing.linked_character_name = linked_name or ""
        existing.notes = notes or existing.notes
        row = existing
    else:
        row = IntelEntityTag(
            owner_user_id=int(owner_id),
            entity_id=int(entity_id),
            entity_kind=kind,
            entity_name=name,
            tag_type=tag_type,
            linked_character_id=linked_character_id,
            linked_character_name=linked_name or "",
            notes=notes or "",
            created_by_character_id=viewer_character_id,
            created_by_character_name=viewer_character_name,
            active=True,
        )
        session.add(row)
    await session.flush()
    meta = TAG_TYPES[tag_type]
    return {
        "id": row.id,
        "entity_id": int(row.entity_id),
        "entity_kind": row.entity_kind,
        "entity_name": row.entity_name,
        "tag_type": row.tag_type,
        "label": meta["label"],
        "tone": meta["tone"],
        "linked_character_id": row.linked_character_id,
        "linked_character_name": row.linked_character_name,
        "notes": row.notes,
        "public_links": public_intel_links(int(row.entity_id), row.entity_kind),
    }


async def remove_intel_tag(
    session: AsyncSession,
    *,
    viewer_character_id: int,
    tag_id: int,
) -> dict[str, Any]:
    owner_id = await resolve_owner_user_id(session, viewer_character_id)
    if owner_id is None:
        return {"error": "No roster"}
    row = await session.get(IntelEntityTag, tag_id)
    if not row or int(row.owner_user_id) != int(owner_id):
        return {"error": "Tag not found"}
    row.active = False
    return {"ok": True, "id": tag_id}
