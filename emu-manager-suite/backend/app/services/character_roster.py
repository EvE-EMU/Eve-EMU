"""Character roster — main pilot + linked alts for session switching."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tools import LinkedCharacter, SsoUser
from app.services.cache_ttl import cache_get, cache_set


@dataclass
class RosterCharacter:
    character_id: int
    character_name: str
    is_main: bool
    token_valid: bool
    corporation_id: int


async def unified_roster_character_ids(session: AsyncSession, character_id: int) -> set[int]:
    """All pilots reachable via shared link rows (handles alts linked under different mains)."""
    cid = int(character_id)
    char_ids: set[int] = {cid}
    owner_ids: set[int] = set()

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == cid))
    if user:
        owner_ids.add(int(user.id))

    changed = True
    while changed:
        changed = False
        stmt = select(LinkedCharacter)
        if owner_ids and char_ids:
            stmt = stmt.where(
                or_(
                    LinkedCharacter.owner_user_id.in_(owner_ids),
                    LinkedCharacter.character_id.in_(char_ids),
                )
            )
        elif owner_ids:
            stmt = stmt.where(LinkedCharacter.owner_user_id.in_(owner_ids))
        elif char_ids:
            stmt = stmt.where(LinkedCharacter.character_id.in_(char_ids))
        else:
            break

        for row in (await session.scalars(stmt)).all():
            oid = int(row.owner_user_id)
            rcid = int(row.character_id)
            if oid not in owner_ids:
                owner_ids.add(oid)
                changed = True
            if rcid not in char_ids:
                char_ids.add(rcid)
                changed = True

    return char_ids


async def resolve_owner_user_id(session: AsyncSession, character_id: int) -> int | None:
    """Primary SsoUser.id for roster ownership (prefers explicit main row)."""
    linked = await session.scalar(
        select(LinkedCharacter).where(LinkedCharacter.character_id == character_id)
    )
    if linked:
        return int(linked.owner_user_id)
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if user:
        return int(user.id)
    return None


async def roster_character_ids(session: AsyncSession, character_id: int) -> set[int]:
    return await unified_roster_character_ids(session, character_id)


def _roster_from_rows(
    rows: list[LinkedCharacter],
    user_map: dict[int, SsoUser],
) -> list[RosterCharacter]:
    out: list[RosterCharacter] = []
    for row in rows:
        user = user_map.get(int(row.character_id))
        out.append(
            RosterCharacter(
                character_id=int(row.character_id),
                character_name=row.character_name,
                is_main=bool(row.is_main),
                token_valid=bool(row.token_valid and user and user.refresh_token_enc),
                corporation_id=int(row.corporation_id or (user.corporation_id if user else 0)),
            )
        )
    return out


async def load_roster(session: AsyncSession, character_id: int, *, use_cache: bool = True) -> list[RosterCharacter]:
    cache_key = f"roster:unified:{int(character_id)}"

    if use_cache:
        cached = await cache_get(cache_key)
        if cached is not None:
            return [
                RosterCharacter(
                    character_id=int(r["character_id"]),
                    character_name=str(r["character_name"]),
                    is_main=bool(r["is_main"]),
                    token_valid=bool(r["token_valid"]),
                    corporation_id=int(r["corporation_id"]),
                )
                for r in cached
            ]

    char_ids = await unified_roster_character_ids(session, character_id)
    if not char_ids:
        return []

    link_rows = (
        await session.scalars(
            select(LinkedCharacter).where(LinkedCharacter.character_id.in_(char_ids))
        )
    ).all()
    link_by_char: dict[int, LinkedCharacter] = {}
    for row in link_rows:
        existing = link_by_char.get(int(row.character_id))
        if existing is None or (row.is_main and not existing.is_main):
            link_by_char[int(row.character_id)] = row

    users = (
        await session.scalars(select(SsoUser).where(SsoUser.character_id.in_(char_ids)))
    ).all()
    user_map = {int(u.character_id): u for u in users}

    roster: list[RosterCharacter] = []
    for cid in sorted(char_ids):
        link = link_by_char.get(cid)
        user = user_map.get(cid)
        if link:
            roster.append(
                RosterCharacter(
                    character_id=cid,
                    character_name=link.character_name,
                    is_main=bool(link.is_main),
                    token_valid=bool(link.token_valid and user and user.refresh_token_enc),
                    corporation_id=int(link.corporation_id or (user.corporation_id if user else 0)),
                )
            )
        elif user:
            roster.append(
                RosterCharacter(
                    character_id=cid,
                    character_name=user.character_name,
                    is_main=cid == int(character_id),
                    token_valid=bool(user.refresh_token_enc),
                    corporation_id=int(user.corporation_id or 0),
                )
            )

    roster.sort(key=lambda r: (not r.is_main, r.character_name.lower()))

    if use_cache:
        await cache_set(
            cache_key,
            [
                {
                    "character_id": r.character_id,
                    "character_name": r.character_name,
                    "is_main": r.is_main,
                    "token_valid": r.token_valid,
                    "corporation_id": r.corporation_id,
                }
                for r in roster
            ],
            ttl_seconds=30,
        )
    return roster


async def can_switch_to(session: AsyncSession, *, current_character_id: int, target_character_id: int) -> bool:
    allowed = await roster_character_ids(session, current_character_id)
    return target_character_id in allowed
