"""aa-discordbot cog: relay messages from configured Discord channels into the
EVE-Penguin ping feed.

Configure targets in the admin (penguin_bridge → Penguin ping channels):
`discord_channel_id → (scope, key, kind, label, ttl_hours)`. Every non-bot
message posted in a mapped channel is forwarded to `POST /penguin/pings` with
`X-Penguin-Relay-Secret: $PENGUIN_RELAY_SECRET`. Only clients whose main is in
that corp / alliance ever receive it.

Enable by adding "penguin_bridge.discord_relay" to `DISCORD_BOT_COGS`.
"""

from __future__ import annotations

import logging
import os

import requests
from discord.ext import commands

logger = logging.getLogger("penguin_bridge.discord_relay")

_BRIDGE_URL = os.environ.get(
    "PENGUIN_BRIDGE_URL", "http://aa-web:8080"
).rstrip("/") + "/penguin/pings"
_SECRET = os.environ.get("PENGUIN_RELAY_SECRET", "")


def _targets() -> dict:
    """`{channel_id: row}` for enabled mappings. Read fresh each message so admin
    edits take effect without a bot restart."""
    from penguin_bridge.models import PenguinPingChannel

    out = {}
    for r in PenguinPingChannel.objects.filter(enabled=True):
        out[int(r.discord_channel_id)] = r
    return out


class PenguinRelay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if not _SECRET:
            return
        try:
            row = _targets().get(int(message.channel.id))
        except Exception:
            logger.exception("penguin relay: target lookup failed")
            return
        if row is None:
            return

        text = (message.content or "").strip()
        if not text:
            return
        if row.label:
            text = f"[{row.label}] {text}"
        payload = {
            "scope": row.scope,
            "key": int(row.key),
            "kind": row.kind,
            "text": text[:3500],
            "author": str(message.author.display_name)[:100],
            "ttl_hours": int(row.ttl_hours or 6),
        }
        try:
            resp = requests.post(
                _BRIDGE_URL,
                json=payload,
                headers={"X-Penguin-Relay-Secret": _SECRET},
                timeout=8,
            )
            if resp.status_code >= 300:
                logger.warning("penguin relay: %s → %s %s", message.channel.id, resp.status_code, resp.text[:200])
        except Exception:
            logger.exception("penguin relay: POST failed")


def setup(bot):
    bot.add_cog(PenguinRelay(bot))
