#!/usr/bin/env python3
"""
Create Discord guild scheduled events for moon pops (EVE time = UTC).

Requires bot token with MANAGE_EVENTS on the guild.

  set DISCORD_BOT_TOKEN=…
  set DISCORD_GUILD_ID=…
  set MOON_POP_DISCORD_VOICE_CHANNEL=corp 2   # voice channel name (substring match)

  python deploy/aa_docker/scripts/moon_pop_discord_scheduled_events.py --dry-run
  python deploy/aa_docker/scripts/moon_pop_discord_scheduled_events.py --apply
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DEFAULT_DATA = Path(__file__).resolve().parent / "data" / "moon_pops_jun_jul_2026.txt"
EVENT_DESCRIPTION = "Pay Yo Taxes Fool, Mine it up!"
EVENT_SUFFIX = "Alliance Moon Mining OP - MOON POPS AT THIS TIME"
DEFAULT_DURATION_HOURS = 2

DISCORD_API = "https://discord.com/api/v10"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "EveEmu-MoonPopScheduler/1.0",
    }


def parse_pop_at(date_str: str, time_str: str) -> datetime:
    """EVE server time is UTC."""
    date_str = date_str.strip()
    time_str = time_str.strip()
    dt = datetime.strptime(date_str, "%Y-%b-%d")
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    second = int(parts[2]) if len(parts) > 2 else 0
    if hour == 24 and minute == 0 and second == 0:
        dt = dt + timedelta(days=1)
        hour, minute, second = 0, 0, 0
    return dt.replace(hour=hour, minute=minute, second=second, tzinfo=timezone.utc)


def parse_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\t+|\s{2,}", line)
        if len(parts) < 4:
            parts = line.split()
            if len(parts) < 4:
                continue
        location, ore_type, date_s, time_s = parts[0], parts[1], parts[2], parts[3]
        rows.append(
            {
                "location": location.strip(),
                "ore_type": ore_type.strip(),
                "date": date_s.strip(),
                "time": time_s.strip(),
            }
        )
    return rows


def event_name(location: str) -> str:
    base = f"{location} / {EVENT_SUFFIX}"
    return base[:100]


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
    if len(voices) > 1:
        print(
            f"Multiple voice channels match {name_match!r}; using {voices[0]['name']!r}",
            file=sys.stderr,
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


def create_scheduled_event(
    token: str,
    guild_id: str,
    *,
    channel_id: str,
    name: str,
    start: datetime,
    description: str,
    duration_hours: int,
    max_retries: int = 8,
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
    for attempt in range(max_retries):
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--apply", action="store_true", help="Create events (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Print only (default)")
    parser.add_argument(
        "--voice-channel",
        default=os.environ.get("MOON_POP_DISCORD_VOICE_CHANNEL", "corp 2"),
        help="Substring match for voice channel name",
    )
    parser.add_argument("--duration-hours", type=int, default=DEFAULT_DURATION_HOURS)
    args = parser.parse_args()
    dry_run = not args.apply or args.dry_run

    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
    if not token or not guild_id:
        print("Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID", file=sys.stderr)
        return 1

    text = args.file.read_text(encoding="utf-8")
    rows = parse_rows(text)
    if not rows:
        print(f"No rows in {args.file}", file=sys.stderr)
        return 1

    channel = find_voice_channel(token, guild_id, args.voice_channel)
    print(f"Voice channel: {channel['name']} ({channel['id']})")

    existing: set[tuple[str, str]] = set()
    if not dry_run:
        try:
            existing = existing_event_keys(list_scheduled_events(token, guild_id))
            print(f"Existing scheduled events on guild: {len(existing)}")
        except Exception as exc:
            print(f"Warning: could not list existing events: {exc}", file=sys.stderr)

    created = 0
    skipped = 0
    errors = 0
    seen: set[tuple[str, str]] = set()

    for row in rows:
        key = (row["location"], f"{row['date']} {row['time']}")
        if key in seen:
            print(f"SKIP duplicate: {row['location']} @ {row['date']} {row['time']}")
            continue
        seen.add(key)

        try:
            pop_at = parse_pop_at(row["date"], row["time"])
        except ValueError as exc:
            print(f"SKIP parse error {row}: {exc}", file=sys.stderr)
            errors += 1
            continue

        name = event_name(row["location"])
        desc = f"{EVENT_DESCRIPTION}\n\nOre: {row['ore_type']}\nPop: {pop_at:%Y-%m-%d %H:%M} EVE (UTC)"

        start_iso = pop_at.isoformat().replace("+00:00", "Z")
        if (name, _start_key(start_iso)) in existing:
            print(f"SKIP exists: {pop_at:%Y-%m-%d %H:%M} | {name}")
            skipped += 1
            continue

        if dry_run:
            print(f"[dry-run] {pop_at:%Y-%m-%d %H:%M} UTC | {name}")
            created += 1
            continue

        try:
            ev = create_scheduled_event(
                token,
                guild_id,
                channel_id=str(channel["id"]),
                name=name,
                start=pop_at,
                description=desc,
                duration_hours=args.duration_hours,
            )
            print(f"OK {ev.get('id')} | {pop_at:%Y-%m-%d %H:%M} | {name}")
            created += 1
            existing.add((name, _start_key(start_iso)))
            time.sleep(1.2)
        except Exception as exc:
            print(f"FAIL {row['location']} @ {pop_at}: {exc}", file=sys.stderr)
            errors += 1

    mode = "dry-run" if dry_run else "applied"
    print(f"\n{mode}: {created} created, {skipped} skipped (already exist), {errors} error(s)")
    if dry_run:
        print("Re-run with --apply to create on Discord.")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
