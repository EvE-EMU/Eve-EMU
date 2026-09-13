"""External service sync — Discord roles and Mumble permissions."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import EmumsGroup
from app.models.member_audit import ServiceSyncConfig, UserServiceSyncState
from app.models.tools import SsoUser
from app.services.rbac import build_auth_context

logger = logging.getLogger(__name__)


async def load_sync_config(session: AsyncSession) -> ServiceSyncConfig:
    row = await session.scalar(select(ServiceSyncConfig).limit(1))
    if row:
        return row
    row = ServiceSyncConfig()
    session.add(row)
    await session.flush()
    return row


def _format_nickname(template: str, user: SsoUser) -> str:
    ticker = (user.corporation_name or "???")[:5].upper()
    return (
        template.replace("{ticker}", ticker)
        .replace("{name}", user.character_name)
        .replace("{corp}", user.corporation_name or "")
    )[:32]


async def sync_user_services(session: AsyncSession, character_id: int) -> dict[str, str | bool]:
    cfg = await load_sync_config(session)
    if not cfg.enabled or not cfg.discord_bot_token or not cfg.discord_guild_id:
        return {"skipped": True, "reason": "service sync disabled"}

    user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
    if not user:
        return {"skipped": True, "reason": "user not found"}

    auth = await build_auth_context(session, character_id)
    if not auth:
        return {"skipped": True, "reason": "no auth context"}

    group_rows = await session.scalars(
        select(EmumsGroup).where(
            EmumsGroup.active.is_(True),
            EmumsGroup.discord_role_id != "",
        )
    )
    role_map = {g.name: g.discord_role_id for g in group_rows.all()}
    desired_roles = [role_map[name] for name in auth.groups if name in role_map]

    state = await session.scalar(
        select(UserServiceSyncState).where(UserServiceSyncState.character_id == character_id)
    )
    if not state:
        state = UserServiceSyncState(character_id=character_id)
        session.add(state)

    headers = {"Authorization": f"Bot {cfg.discord_bot_token}"}
    guild_id = cfg.discord_guild_id
    discord_user_id = None  # wired when Discord OAuth link is added to SsoUser

    if discord_user_id and desired_roles:
        async with httpx.AsyncClient(timeout=20.0) as client:
            for role_id in desired_roles:
                url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_user_id}/roles/{role_id}"
                resp = await client.put(url, headers=headers)
                if resp.status_code not in (204, 201):
                    state.last_error = f"Discord role {role_id}: HTTP {resp.status_code}"
                    logger.warning("Discord sync: %s", state.last_error)
            nick = _format_nickname(cfg.discord_nickname_format, user)
            patch_url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{discord_user_id}"
            await client.patch(url=patch_url, headers=headers, json={"nick": nick})

    state.last_sync_at = datetime.now(UTC)
    state.discord_roles_json = json.dumps(desired_roles)
    state.last_error = ""
    return {"synced": True, "roles": len(desired_roles)}


def schedule_user_service_sync(character_id: int) -> None:
    from app.tasks.service_sync import sync_user_services_task

    sync_user_services_task.delay(character_id)
