"""Complete EVE SSO callback when ``state`` is a Discord ``link_id`` (pending row)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, select, update

from app.config import settings
from app.db.models import CoreUser, DiscordPendingSsoLink, EveLinkedCharacter
from app.db.session import session_scope
from app.db.token_store import upsert_eve_refresh_token_in_session
from app.services.eve_jwt import character_id_from_payload, character_name_from_payload, owner_hash_from_payload
from app.services.eve_sso_http import exchange_authorization_code


def _html(body: str, *, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><meta charset=\"utf-8\"><title>EVE-EMU Core</title></head>"
            f"<body style=\"font-family:system-ui;max-width:40rem;margin:2rem auto;\">{body}</body></html>"
        ),
        status_code=status,
    )


async def handle_eve_oauth_callback(*, code: str | None, state: str | None) -> HTMLResponse:
    """Exchange code, link Discord + EVE account when ``state`` is a pending ``link_id`` UUID."""
    if not code:
        return _html("<h1>Missing code</h1><p>CCP did not return an authorization code.</p>", status=400)
    if not state or not str(state).strip():
        return _html(
            "<h1>Missing state</h1><p>Start linking from Discord using <code>/settings link</code>.</p>",
            status=400,
        )
    link_key = str(state).strip()
    try:
        link_uuid = uuid.UUID(link_key)
    except ValueError:
        return _html(
            "<h1>Invalid link session</h1><p>Open a fresh link from <code>/settings link</code> in Discord.</p>",
            status=400,
        )

    if not settings.database_url:
        return _html("<h1>Database unavailable</h1><p>CORE_DATABASE_URL is not configured.</p>", status=503)

    try:
        token_payload = await exchange_authorization_code(code=code)
    except Exception as exc:
        return _html(
            f"<h1>SSO token exchange failed</h1><p>Check CORE_SSO_CLIENT_ID / CORE_SSO_CLIENT_SECRET and callback URL.</p>"
            f"<pre>{exc!r}</pre>",
            status=502,
        )

    access = str(token_payload.get("access_token") or "")
    refresh = str(token_payload.get("refresh_token") or "")
    if not access or not refresh:
        return _html("<h1>Invalid token response</h1><p>Missing access or refresh token from CCP.</p>", status=502)

    from app.services.token_cipher import TokenCipher

    try:
        TokenCipher.require()
    except RuntimeError as exc:
        return _html(
            f"<h1>Token encryption not configured</h1><p>Set CORE_TOKEN_ENCRYPTION_KEY on core.</p><pre>{exc}</pre>",
            status=503,
        )

    from app.services.eve_jwt import decode_jwt_payload

    jwt_body = decode_jwt_payload(access)
    character_id = character_id_from_payload(jwt_body)
    owner_hash = owner_hash_from_payload(jwt_body)
    character_name = character_name_from_payload(jwt_body) or ""
    if character_id is None or not owner_hash:
        return _html("<h1>Could not read character from token</h1><p>JWT payload was incomplete.</p>", status=502)

    expires_in = token_payload.get("expires_in")
    access_expires_at: datetime | None = None
    if expires_in is not None:
        try:
            access_expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            access_expires_at = None

    scopes = str(token_payload.get("scope") or settings.sso_scopes)

    now = datetime.now(UTC)
    stale_before = now - timedelta(minutes=30)

    async with session_scope() as session:
        pending = await session.get(DiscordPendingSsoLink, link_uuid)
        if pending is None:
            return _html(
                "<h1>Link expired or unknown</h1><p>Run <code>/settings link</code> again in Discord.</p>",
                status=400,
            )
        if pending.created_at < stale_before:
            await session.execute(delete(DiscordPendingSsoLink).where(DiscordPendingSsoLink.link_id == link_uuid))
            await session.commit()
            return _html(
                "<h1>Link expired</h1><p>Discord link sessions expire after 30 minutes. Use <code>/settings link</code> again.</p>",
                status=400,
            )

        discord_uid = int(pending.discord_user_id)

        existing_user_id: uuid.UUID | None = None
        row = await session.scalar(
            select(CoreUser.id)
            .join(EveLinkedCharacter, EveLinkedCharacter.user_id == CoreUser.id)
            .where(EveLinkedCharacter.owner_hash == owner_hash)
            .limit(1)
        )
        if row is not None:
            existing_user_id = row

        if existing_user_id is not None:
            core_user = await session.get(CoreUser, existing_user_id)
            assert core_user is not None
        else:
            core_user = CoreUser()
            session.add(core_user)
            await session.flush()

        await session.execute(
            update(CoreUser)
            .where(CoreUser.discord_user_id == discord_uid, CoreUser.id != core_user.id)
            .values(discord_user_id=None)
        )

        core_user.discord_user_id = discord_uid
        core_user.updated_at = now

        link_row = await session.get(EveLinkedCharacter, character_id)
        if link_row is None:
            session.add(
                EveLinkedCharacter(
                    character_id=character_id,
                    user_id=core_user.id,
                    owner_hash=owner_hash,
                    character_name=character_name,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            link_row.user_id = core_user.id
            link_row.owner_hash = owner_hash
            if character_name:
                link_row.character_name = character_name
            link_row.updated_at = now

        await session.flush()

        if core_user.main_character_id is None:
            core_user.main_character_id = character_id

        await upsert_eve_refresh_token_in_session(
            session,
            character_id=character_id,
            refresh_token=refresh,
            scopes=scopes,
            owner_user_id=core_user.id,
            access_token=access,
            access_expires_at=access_expires_at,
        )

        await session.execute(delete(DiscordPendingSsoLink).where(DiscordPendingSsoLink.link_id == link_uuid))
        await session.commit()

    redir = (settings.discord_link_success_url or "").strip()
    if redir:
        return RedirectResponse(url=redir, status_code=302)

    return _html(
        "<h1>Linked</h1>"
        "<p>Your EVE character is linked to this Discord account in <strong>eve-emu core</strong>. "
        "You can close this tab and run <code>/settings sync</code> in Discord for roles.</p>"
    )
