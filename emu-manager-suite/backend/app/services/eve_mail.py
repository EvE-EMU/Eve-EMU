"""Send EVE mail via ESI (service account refresh token)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import OrgSettings
from app.services.esi import bearer_token

logger = logging.getLogger(__name__)

_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; mail)"


async def _mail_sender_character_id(session: AsyncSession) -> int | None:
    row = await session.scalar(select(OrgSettings).limit(1))
    name = (row.mail_sender_character if row else "") or ""
    if not name.strip():
        return None
    status, body = await _esi_search_character(name.strip())
    if status == 200 and isinstance(body, list) and body:
        return int(body[0].get("id") or 0) or None
    return None


async def _esi_search_character(name: str) -> tuple[int, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{_ESI}/search/",
            params={"categories": "character", "search": name, "strict": "true"},
            headers={"Accept": "application/json", "User-Agent": _UA},
        )
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def send_character_mail(
    session: AsyncSession,
    *,
    recipient_character_id: int,
    subject: str,
    body: str,
    approved_cost: int = 1_000_000,
) -> tuple[bool, str]:
    row = await session.scalar(select(OrgSettings).limit(1))
    if row and not row.mail_enabled:
        return False, "EVE mail is disabled in org settings"

    sender_id = await _mail_sender_character_id(session)
    if not sender_id:
        return False, "No mail sender character configured in Settings"

    token = await bearer_token(session)
    if not token:
        return False, "ESI mail token not available — configure EMUMS_ESI_REFRESH_TOKEN"

    payload = {
        "approved_cost": approved_cost,
        "body": body[:8000],
        "recipients": [{"recipient_id": int(recipient_character_id), "recipient_type": "character"}],
        "subject": subject[:1000],
    }

    last_err = ""
    for attempt in range(4):
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_ESI}/characters/{sender_id}/mail/",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": _UA,
                },
                json=payload,
            )
        if resp.status_code in (200, 201):
            return True, ""
        try:
            last_err = resp.text[:500]
        except Exception:
            last_err = f"HTTP {resp.status_code}"
        if "MailStopSpamming" in last_err and attempt < 3:
            match = re.search(r'"remainingTime":\s*(\d+)', last_err)
            if match:
                import asyncio

                wait_s = min(int(match.group(1)) / 1_000_000.0 + 1.0, 120.0)
                await asyncio.sleep(wait_s)
                continue
        break

    logger.warning("EMUMS mail failed to %s: %s", recipient_character_id, last_err)
    return False, last_err
