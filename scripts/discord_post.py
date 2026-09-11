#!/usr/bin/env python3
"""Post a message to a Discord channel via the bot REST API (no gateway
connection needed — a bot token + channel id is enough for a one-shot post).

Used by the EVE-Penguin release pipeline to announce new versions to
#penguin-releases (channel 1546211961744789504) and to push periodic
project-status updates to the status board (channel 1547925925818273882).

Usage:
    python3 scripts/discord_post.py <channel_id> "message text"
    python3 scripts/discord_post.py <channel_id> --file notes.md

Reads DISCORD_BOT_TOKEN from the environment or ../.env (this script's
parent dir). Never prints the token.
"""
import os
import sys
import json
import urllib.request
import urllib.error


def load_token() -> str:
    tok = os.environ.get("DISCORD_BOT_TOKEN")
    if tok:
        return tok
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DISCORD_BOT_TOKEN="):
                    return line.strip().split("=", 1)[1]
    raise SystemExit("DISCORD_BOT_TOKEN not found in env or .env")


def post(channel_id: str, content: str) -> None:
    token = load_token()
    # Discord caps a single message at 2000 chars; trim with a marker rather
    # than let the API 400 on an oversized release-notes blob.
    if len(content) > 1990:
        content = content[:1970] + "\n… (truncated)"
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    body = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "eve-penguin-release-bot (https://eve-emu.com, 1.0)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"posted ok: {resp.status}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"discord post failed: {e.code} {detail}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    channel_id = sys.argv[1]
    if sys.argv[2] == "--file":
        with open(sys.argv[3]) as f:
            text = f.read()
    else:
        text = sys.argv[2]
    post(channel_id, text)
