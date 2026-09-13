"""Authentication dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session_factory
from app.models.tools import SsoUser
from app.services.auth_session import parse_session_token
from app.services.rbac import UserAuthContext, build_auth_context


async def require_api_key(x_emums_key: str | None = Header(default=None, alias="X-EMUMS-Key")) -> None:
    if not x_emums_key or x_emums_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-EMUMS-Key header",
        )


def is_administrator(auth: UserAuthContext) -> bool:
    return auth.has_permission("director") or auth.has_permission("admin") or auth.has_permission(
        "settings.admin"
    )


async def get_current_user(
    x_emums_key: str | None = Header(default=None, alias="X-EMUMS-Key"),
    x_emums_session: str | None = Header(default=None, alias="X-EMUMS-Session"),
    x_emums_character_id: str | None = Header(default=None, alias="X-EMUMS-Character-Id"),
) -> UserAuthContext:
    """Validate session cookie/header, API key + character id, or API key alone (BFF)."""
    session_character_id = parse_session_token(x_emums_session)
    if session_character_id is not None:
        factory = get_session_factory()
        async with factory() as session:
            ctx = await build_auth_context(session, session_character_id)
            if ctx:
                return ctx
            user = await session.scalar(
                select(SsoUser).where(SsoUser.character_id == session_character_id)
            )
            if not user:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
            return UserAuthContext(
                character_id=session_character_id,
                character_name=user.character_name,
                corporation_id=int(user.corporation_id or 0),
                alliance_id=int(user.alliance_id) if user.alliance_id else None,
                state_name=None,
                state_id=None,
            )

    if x_emums_key and x_emums_key == settings.api_key:
        if x_emums_character_id and x_emums_character_id.isdigit():
            character_id = int(x_emums_character_id)
        else:
            factory = get_session_factory()
            async with factory() as session:
                user = await session.scalar(select(SsoUser).order_by(SsoUser.last_login_at.desc()))
                if not user:
                    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
                character_id = int(user.character_id)
        factory = get_session_factory()
        async with factory() as session:
            ctx = await build_auth_context(session, character_id)
            if ctx:
                return ctx
            user = await session.scalar(select(SsoUser).where(SsoUser.character_id == character_id))
            if not user:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
            return UserAuthContext(
                character_id=character_id,
                character_name=user.character_name,
                corporation_id=int(user.corporation_id or 0),
                alliance_id=int(user.alliance_id) if user.alliance_id else None,
                state_name=None,
                state_id=None,
                permissions={"director", "audit.view", "settings.admin"},
            )

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def require_administrator(
    auth: UserAuthContext = Depends(get_current_user),
) -> UserAuthContext:
    if not is_administrator(auth):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Administrator access required")
    return auth
