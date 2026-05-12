"""Bearer auth for Discord bot → core plugin routes."""

from __future__ import annotations

from fastapi import HTTPException

from app.config import settings


def require_discord_bot_secret(authorization: str | None) -> None:
    secret = (settings.discord_bot_secret or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="CORE_DISCORD_BOT_SECRET is not set.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Expected Authorization: Bearer <secret>.")
    got = authorization.removeprefix("Bearer ").strip()
    if got != secret:
        raise HTTPException(status_code=403, detail="Invalid bearer token.")
