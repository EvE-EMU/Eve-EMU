"""Coalition RBAC — state resolution and permission matrix."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.identity import EmumsCharacterGroupJoin, EmumsGroup, EmumsState, EmumsStateRule
from app.models.tools import SsoUser

logger = logging.getLogger(__name__)

ACCESS_LEVELS = ("public", "guest", "friendly", "blue", "member", "red")

DEFAULT_STATES: list[tuple[str, int, str, str]] = [
    ("Public", 0, "gray", "Unauthenticated visitors"),
    ("Red", 10, "red", "Hostile — restricted to public tools"),
    ("Guest", 100, "gray", "Logged-in pilots without coalition standing"),
    ("Friendly", 200, "teal", "Friendly standings — limited intel access"),
    ("Blue", 300, "blue", "Coalition blues and allied corps"),
    ("Member", 500, "green", "Full coalition member access"),
]

MODULE_PERMISSIONS: dict[str, list[str]] = {
    "public": ["tools.public"],
    "guest": ["tools.public", "tools.guest", "map.bookmarks"],
    "friendly": ["tools.public", "tools.guest", "tools.friendly", "intel.read"],
    "blue": ["tools.public", "tools.guest", "tools.friendly", "tools.blue", "industrial.storefront"],
    "member": [
        "tools.public",
        "tools.guest",
        "tools.friendly",
        "tools.blue",
        "tools.member",
        "industrial.storefront",
        "moons.view",
        "hr.view",
        "srp.submit",
    ],
    "red": ["tools.public", "state.red"],
}


@dataclass
class UserAuthContext:
    character_id: int
    character_name: str
    corporation_id: int
    alliance_id: int | None
    state_name: str | None
    state_id: int | None
    state_color: str | None = None
    groups: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def has_permission(self, perm: str) -> bool:
        if "admin" in self.permissions or "director" in self.permissions:
            return True
        return perm in self.permissions


def normalize_access_level(state_name: str | None, *, authenticated: bool) -> str:
    if not authenticated:
        return "public"
    if not state_name:
        return "guest"
    key = state_name.lower().replace(" ", "_")
    if key in ACCESS_LEVELS:
        return key
    return "guest"


def permissions_for_access_level(level: str) -> set[str]:
    return set(MODULE_PERMISSIONS.get(level, MODULE_PERMISSIONS["guest"]))


async def resolve_state_for_character(
    session: AsyncSession,
    *,
    corporation_id: int,
    alliance_id: int | None,
) -> tuple[int | None, str | None]:
    rule_rows = await session.execute(
        select(EmumsStateRule, EmumsState)
        .join(EmumsState, EmumsState.id == EmumsStateRule.state_id)
        .where(EmumsState.active.is_(True))
        .order_by(EmumsState.priority_weight.desc(), EmumsStateRule.priority)
    )
    for rule, state in rule_rows.all():
        corps = {
            int(x)
            for x in json.loads(rule.allowed_corporation_ids_json or "[]")
            if str(x).isdigit()
        }
        alliances = {
            int(x)
            for x in json.loads(rule.allowed_alliance_ids_json or "[]")
            if str(x).isdigit()
        }
        if corporation_id in corps or (alliance_id and alliance_id in alliances):
            return state.id, state.name
    return None, None


async def build_auth_context(session: AsyncSession, character_id: int) -> UserAuthContext | None:
    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if not user:
        return None

    state_id, state_name = await resolve_state_for_character(
        session,
        corporation_id=int(user.corporation_id or 0),
        alliance_id=int(user.alliance_id) if user.alliance_id else None,
    )

    joins = await session.execute(
        select(EmumsGroup)
        .join(EmumsCharacterGroupJoin, EmumsCharacterGroupJoin.group_id == EmumsGroup.id)
        .where(
            EmumsCharacterGroupJoin.character_id == character_id,
            EmumsCharacterGroupJoin.status == EmumsCharacterGroupJoin.STATUS_ACTIVE,
            EmumsGroup.active.is_(True),
        )
    )
    groups: list[str] = []
    permissions: set[str] = set()
    for group in joins.scalars().all():
        groups.append(group.name)
        for perm in json.loads(group.permissions_json or "[]"):
            if perm:
                permissions.add(str(perm))

    if state_name:
        permissions.add(f"state.{state_name.lower().replace(' ', '_')}")

    state_color = None
    if state_id:
        state_row = await session.scalar(select(EmumsState).where(EmumsState.id == state_id))
        if state_row:
            state_color = state_row.color

    access_level = normalize_access_level(state_name, authenticated=True)
    permissions |= permissions_for_access_level(access_level)

    return UserAuthContext(
        character_id=character_id,
        character_name=user.character_name,
        corporation_id=int(user.corporation_id or 0),
        alliance_id=int(user.alliance_id) if user.alliance_id else None,
        state_name=state_name,
        state_id=state_id,
        state_color=state_color,
        groups=groups,
        permissions=permissions,
    )


async def ensure_default_states(session: AsyncSession) -> None:
    """Upsert coalition access states and default Member alliance rule."""
    state_ids: dict[str, int] = {}
    for name, weight, color, description in DEFAULT_STATES:
        row = await session.scalar(select(EmumsState).where(EmumsState.name == name))
        if row:
            row.priority_weight = weight
            row.color = color
            row.description = description
            row.active = True
        else:
            row = EmumsState(
                name=name,
                priority_weight=weight,
                color=color,
                description=description,
            )
            session.add(row)
            await session.flush()
        state_ids[name] = row.id

    member_id = state_ids.get("Member")
    if member_id:
        existing_rule = await session.scalar(
            select(EmumsStateRule).where(EmumsStateRule.state_id == member_id).limit(1)
        )
        alliance_ids = [settings.killboard_alliance_id] if settings.killboard_alliance_id else []
        corp_ids = [settings.killboard_corporation_id] if settings.killboard_corporation_id else []
        payload_alliances = json.dumps(alliance_ids)
        payload_corps = json.dumps(corp_ids)
        if existing_rule:
            if alliance_ids or corp_ids:
                existing_rule.allowed_alliance_ids_json = payload_alliances
                existing_rule.allowed_corporation_ids_json = payload_corps
        else:
            session.add(
                EmumsStateRule(
                    state_id=member_id,
                    allowed_alliance_ids_json=payload_alliances,
                    allowed_corporation_ids_json=payload_corps,
                )
            )

    director = await session.scalar(select(EmumsGroup).where(EmumsGroup.name == "Directors"))
    if not director:
        director = EmumsGroup(
            name="Directors",
            description="Coalition directors — full audit and administration access",
            is_hidden=False,
            is_open=False,
            permissions_json=json.dumps(["director", "audit.view", "settings.admin"]),
        )
        session.add(director)
        await session.flush()

    await ensure_bootstrap_admins(session, director_group=director)


async def ensure_bootstrap_admins(session: AsyncSession, *, director_group: EmumsGroup) -> None:
    """Grant coalition Directors group to configured bootstrap administrators."""
    import os

    raw_ids = os.environ.get("EMUMS_BOOTSTRAP_ADMIN_CHARACTER_IDS", "715529239")
    raw_names = os.environ.get("EMUMS_BOOTSTRAP_ADMIN_USERNAMES", "sevey")
    character_ids = {int(x.strip()) for x in raw_ids.split(",") if x.strip().isdigit()}
    usernames = {n.strip().lower() for n in raw_names.split(",") if n.strip()}

    if usernames:
        rows = await session.scalars(select(SsoUser))
        for user in rows.all():
            if user.character_name.lower() in usernames:
                character_ids.add(int(user.character_id))

    for character_id in sorted(character_ids):
        user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
        character_name = user.character_name if user else f"Character {character_id}"
        existing = await session.scalar(
            select(EmumsCharacterGroupJoin).where(
                EmumsCharacterGroupJoin.character_id == character_id,
                EmumsCharacterGroupJoin.group_id == director_group.id,
            )
        )
        if existing:
            if existing.status != EmumsCharacterGroupJoin.STATUS_ACTIVE:
                existing.status = EmumsCharacterGroupJoin.STATUS_ACTIVE
                existing.character_name = character_name
            continue
        session.add(
            EmumsCharacterGroupJoin(
                character_id=character_id,
                character_name=character_name,
                group_id=director_group.id,
                status=EmumsCharacterGroupJoin.STATUS_ACTIVE,
            )
        )
        logger.info("EMUMS: granted Directors to %s (%s)", character_name, character_id)
