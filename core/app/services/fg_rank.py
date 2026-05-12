"""Resolve False Gods corp rank for a linked Discord user (ESI + stored refresh tokens)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.db.models import CoreUser, EveLinkedCharacter
from app.db.session import session_scope
from app.db.token_store import get_eve_refresh_token_plain, upsert_eve_refresh_token
from app.services.esi_http import character_corporation_id, character_role_ids, corporation_ceo_id
from app.services.eve_sso_http import refresh_access_token


@dataclass
class FgRankResult:
    linked: bool
    rank_key: str
    detail: str = ""


def _parse_rank_table(raw: str) -> list[tuple[int, str, int]]:
    """Return ``(role_id, slug, weight)`` sorted by weight descending."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[tuple[int, str, int]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item["role_id"])
        except (KeyError, TypeError, ValueError):
            continue
        slug = str(item.get("slug") or "fg_role").strip() or "fg_role"
        try:
            w = int(item.get("weight", 0))
        except (TypeError, ValueError):
            w = 0
        out.append((rid, slug, w))
    out.sort(key=lambda t: t[2], reverse=True)
    return out


async def compute_fg_rank_for_discord(discord_user_id: int) -> FgRankResult:
    if not settings.database_url:
        return FgRankResult(linked=False, rank_key="none", detail="database_unconfigured")

    async with session_scope() as session:
        core_user = await session.scalar(select(CoreUser).where(CoreUser.discord_user_id == discord_user_id))
        if core_user is None:
            return FgRankResult(linked=False, rank_key="none", detail="discord_not_linked")
        core_uid = core_user.id
        linked = (
            await session.scalars(
                select(EveLinkedCharacter.character_id).where(EveLinkedCharacter.user_id == core_user.id)
            )
        ).all()

    fg_corp = int(settings.false_gods_corporation_id or 0)
    if fg_corp <= 0:
        return FgRankResult(linked=True, rank_key="none", detail="false_gods_corporation_id_unset")

    if not linked:
        return FgRankResult(linked=True, rank_key="none", detail="no_characters")

    rank_table = _parse_rank_table(settings.fg_rank_roles_json)

    ceo_id = await corporation_ceo_id(fg_corp)
    best_weight = -1
    best_slug = "fg_member"
    any_in_fg = False
    ceo_hit = False

    for cid in linked:
        corp = await character_corporation_id(int(cid))
        if corp != fg_corp:
            continue
        any_in_fg = True
        if ceo_id is not None and int(cid) == ceo_id:
            ceo_hit = True
            break

        rt = await get_eve_refresh_token_plain(character_id=int(cid))
        if not rt:
            continue
        try:
            tr = await refresh_access_token(refresh_token=rt)
        except Exception:
            continue
        new_access = str(tr.get("access_token") or "")
        new_refresh = str(tr.get("refresh_token") or rt)
        if not new_access:
            continue
        scopes = str(tr.get("scope") or settings.sso_scopes)
        expires_in = tr.get("expires_in")

        access_expires_at = None
        if expires_in is not None:
            try:
                access_expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                access_expires_at = None
        await upsert_eve_refresh_token(
            character_id=int(cid),
            refresh_token=new_refresh,
            scopes=scopes,
            owner_user_id=core_uid,
            access_token=new_access,
            access_expires_at=access_expires_at,
        )

        role_ids = await character_role_ids(character_id=int(cid), bearer=new_access)
        for rid, slug, w in rank_table:
            if rid in role_ids and w > best_weight:
                best_weight = w
                best_slug = slug

    if ceo_hit:
        return FgRankResult(linked=True, rank_key="fg_ceo", detail="ceo_match")
    if not any_in_fg:
        return FgRankResult(linked=True, rank_key="none", detail="not_in_false_gods")
    if best_weight < 0:
        return FgRankResult(linked=True, rank_key="fg_member", detail="no_mapped_roles")
    return FgRankResult(linked=True, rank_key=best_slug, detail="role_match")
