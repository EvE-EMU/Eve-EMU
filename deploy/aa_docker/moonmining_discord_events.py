"""
Sync aa-moonmining extractions to Discord guild scheduled events (deduplicated).

Environment:
  DISCORD_BOT_TOKEN
  DISCORD_GUILD_ID
  MOON_POP_DISCORD_VOICE_CHANNEL (default: corp 2)
  MOON_POP_DISCORD_EVENT_SUFFIX (optional override)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
from django.utils.timezone import now

logger = logging.getLogger(__name__)

EVENT_DESCRIPTION = "Pay Yo Taxes Fool, Mine it up!"
EVENT_SUFFIX = "Alliance Moon Mining OP - MOON POPS AT THIS TIME"
DEFAULT_DURATION_HOURS = 2
DISCORD_API = "https://discord.com/api/v10"


@dataclass
class SyncResult:
    created: int = 0
    skipped: int = 0
    errors: int = 0
    examined: int = 0
    messages: list[str] | None = None

    def __post_init__(self) -> None:
        if self.messages is None:
            self.messages = []


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "EveEmu-MoonminingDiscordSync/1.0",
    }


def event_name(location: str) -> str:
    suffix = os.environ.get("MOON_POP_DISCORD_EVENT_SUFFIX", EVENT_SUFFIX).strip() or EVENT_SUFFIX
    return f"{location} / {suffix}"[:100]


def _start_key(iso: str) -> str:
    return iso.replace("+00:00", "Z")[:16]


def existing_event_keys(events: list[dict]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for ev in events:
        name = (ev.get("name") or "").strip()
        start = ev.get("scheduled_start_time") or ""
        if name and start:
            out.add((name, _start_key(start)))
    return out


def find_voice_channel(token: str, guild_id: str, name_match: str) -> dict:
    resp = requests.get(
        f"{DISCORD_API}/guilds/{guild_id}/channels",
        headers=_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    needle = name_match.lower()
    voices = [
        ch
        for ch in resp.json()
        if ch.get("type") == 2 and needle in (ch.get("name") or "").lower()
    ]
    if not voices:
        names = [ch.get("name") for ch in resp.json() if ch.get("type") == 2]
        raise RuntimeError(
            f"No voice channel matching {name_match!r}. Voice channels: {names[:30]}"
        )
    return voices[0]


def list_scheduled_events(token: str, guild_id: str) -> list[dict]:
    resp = requests.get(
        f"{DISCORD_API}/guilds/{guild_id}/scheduled-events",
        headers=_headers(token),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def create_scheduled_event(
    token: str,
    guild_id: str,
    *,
    channel_id: str,
    name: str,
    start: datetime,
    description: str,
    duration_hours: int = DEFAULT_DURATION_HOURS,
) -> dict:
    end = start + timedelta(hours=duration_hours)
    payload = {
        "name": name[:100],
        "description": description[:1000],
        "scheduled_start_time": start.isoformat().replace("+00:00", "Z"),
        "scheduled_end_time": end.isoformat().replace("+00:00", "Z"),
        "privacy_level": 2,
        "entity_type": 2,
        "channel_id": channel_id,
    }
    for attempt in range(8):
        resp = requests.post(
            f"{DISCORD_API}/guilds/{guild_id}/scheduled-events",
            headers=_headers(token),
            json=payload,
            timeout=30,
        )
        if resp.status_code == 429:
            try:
                wait = float(resp.json().get("retry_after", 2))
            except Exception:
                wait = 2.0
            time.sleep(wait + 0.5)
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        return resp.json()
    raise RuntimeError("rate limited after retries")


def extractions_for_discord_sync():
    """Upcoming moonmining extractions (same pool as Extractions → Upcoming tab)."""
    import datetime as dt

    from moonmining.app_settings import MOONMINING_COMPLETED_EXTRACTIONS_HOURS_UNTIL_STALE
    from moonmining.models import Extraction

    stale_cutoff = now() - dt.timedelta(hours=MOONMINING_COMPLETED_EXTRACTIONS_HOURS_UNTIL_STALE)
    return (
        Extraction.objects.exclude(refinery__moon__isnull=True)
        .filter(auto_fracture_at__gte=stale_cutoff)
        .exclude(status=Extraction.Status.CANCELED)
        .exclude(chunk_arrival_at__isnull=True)
        .select_related("refinery", "refinery__moon")
        .order_by("chunk_arrival_at")
    )


def _pop_at_utc(extraction) -> datetime:
    when = extraction.chunk_arrival_at
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def sync_extractions_to_discord(*, dry_run: bool = False) -> SyncResult:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
    voice = os.environ.get("MOON_POP_DISCORD_VOICE_CHANNEL", "corp 2").strip() or "corp 2"

    if not token or not guild_id:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set on the server."
        )

    result = SyncResult()
    channel = find_voice_channel(token, guild_id, voice)
    result.messages.append(f"Voice channel: {channel['name']}")

    existing: set[tuple[str, str]] = set()
    try:
        existing = existing_event_keys(list_scheduled_events(token, guild_id))
        result.messages.append(f"Guild scheduled events: {len(existing)}")
    except Exception as exc:
        logger.warning("Could not list Discord events: %s", exc)
        result.messages.append(f"Warning: could not list existing events ({exc})")

    seen_local: set[tuple[str, str]] = set()

    min_start = now()
    if min_start.tzinfo is None:
        min_start = min_start.replace(tzinfo=timezone.utc)
    else:
        min_start = min_start.astimezone(timezone.utc)

    for extraction in extractions_for_discord_sync():
        result.examined += 1
        location = (extraction.refinery.name or "").strip() or f"Extraction #{extraction.pk}"
        pop_at = _pop_at_utc(extraction)
        if pop_at < min_start:
            result.skipped += 1
            continue
        name = event_name(location)
        start_iso = pop_at.isoformat().replace("+00:00", "Z")
        dedupe_key = (name, _start_key(start_iso))

        if dedupe_key in seen_local:
            result.skipped += 1
            continue
        seen_local.add(dedupe_key)

        if dedupe_key in existing:
            result.skipped += 1
            continue

        moon = extraction.refinery.moon
        rarity = ""
        try:
            rarity = moon.get_rarity_class_display() or ""
        except Exception:
            pass

        desc = (
            f"{EVENT_DESCRIPTION}\n\n"
            f"Moon: {moon}\n"
            f"Rarity: {rarity}\n"
            f"Pop: {pop_at:%Y-%m-%d %H:%M} EVE (UTC)\n"
            f"Extraction ID: {extraction.pk}"
        )

        if dry_run:
            result.messages.append(f"[dry-run] {pop_at:%Y-%m-%d %H:%M} UTC | {name}")
            result.created += 1
            continue

        try:
            ev = create_scheduled_event(
                token,
                guild_id,
                channel_id=str(channel["id"]),
                name=name,
                start=pop_at,
                description=desc,
            )
            result.messages.append(f"Created {ev.get('id')} | {pop_at:%Y-%m-%d %H:%M} | {name}")
            result.created += 1
            existing.add(dedupe_key)
            time.sleep(1.2)
        except Exception as exc:
            logger.exception("Discord event create failed for extraction %s", extraction.pk)
            result.messages.append(f"FAIL {location} @ {pop_at}: {exc}")
            result.errors += 1

    return result


def discord_sync_configured() -> bool:
    return bool(
        os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        and os.environ.get("DISCORD_GUILD_ID", "").strip()
    )
