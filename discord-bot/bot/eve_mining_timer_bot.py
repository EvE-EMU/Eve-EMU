#!/usr/bin/env python3
"""
Discord mining timer bot for EVE Online anomaly respawns.

Set ``EVE_DISCORD_BOT_TOKEN`` in the process environment, or put ``EVE_DISCORD_BOT_TOKEN=...`` in ``bot/.env`` (gitignored).
Windows: in **cmd.exe** use ``set EVE_DISCORD_BOT_TOKEN=your_token`` (no spaces around ``=``); in **PowerShell** use
``$env:EVE_DISCORD_BOT_TOKEN = 'your_token'``. Do not paste a literal placeholder string.

Commands:
  /miner timer tier:T1|T2|T3 system_name anom_type eve_time
  !miner timer T1|T2|T3 … — same as /miner timer (text; no slash perms needed)
  /miner respawns
  !miner respawns — same as /miner respawns (text; `!miner resawns` typo alias accepted)
  /website
  /structure new_timer … — add structure vulnerability timer (UTC)
  /structure admin_panel … — alert buckets + Discord channel id
  !popejoy (message) — joke reply in channel

Optional remote dashboard (EvE-EMU API + Redis): set MINING_BOT_DASHBOARD_PUSH_URL and
MINING_BOT_DASHBOARD_TOKEN (see ../README.md — browser UI was removed from the main Next app).

Channel @here mining pings: ``EVE_MINING_PING_LEAD_MINUTES`` (default **30**) — the bot posts when this
many minutes remain until respawn, not at respawn (set to **0** for legacy “at respawn time” behavior).

Set EVEEMU_API_BASE_URL to your API origin (e.g. https://eve-emu.com), or omit it and derive the base URL
from the heartbeat URL.

Corporation Projects (ESI) channel feed: set API env ``CORP_PROJECTS_ESI_TOKEN_ID`` (``esi_tokens.id`` with
``esi-corporations.read_corporation_projects.v1``), optional ``CORP_PROJECTS_CORPORATION_ID``, and on the bot
``EVE_CORP_PROJECTS_CHANNEL_ID`` **or** ``EVE_CORP_PROJECTS_GUILD_ID`` + ``EVE_CORP_PROJECTS_CHANNEL_NAME`` (substring
match, default ``corp projects``). Poll interval defaults to 10 hours: ``EVE_CORP_PROJECTS_POLL_SECONDS`` (minimum 300).

Structure timer board: API env ``STRUCTURE_TIMER_SHEET_CSV_URL`` (Google Sheet published CSV),
``STRUCTURE_TIMER_STANDINGS_TOKEN_ID`` (``esi_tokens.id`` with ``esi-corporations.read_standings.v1``),
optional ``STRUCTURE_TIMER_HOME_CORPORATION_ID``. Bot: ``EVE_STRUCTURE_TIMER_CHANNEL_ID`` (fallback if not set via
``/structure admin_panel``), ``EVE_STRUCTURE_TIMER_POLL_SECONDS`` (default 300).

WOMPSTAR market bot: API env ``MARKET_BOT_STOCKER_CHANNEL_ID`` (Discord channel for #stocker-pings-style alerts),
``MARKET_BOT_STOCKER_CONTENT_PREFIX`` (optional ``<@&role_id>`` to ping @Stocker_Pings), ``MARKET_BOT_STATION_MATCH``
(default ``WOMPSTAR``), ``MARKET_BOT_CROSS_BUY_PREMIUM_PCT`` (default 10), ``MARKET_BOT_UNDERCUT_TOKEN_IDS`` (comma
``esi_tokens.id`` with Discord link + ``esi-markets.read_character_orders.v1``). Bot:
``EVE_MARKET_WATCH_CHANNEL_ID`` (fallback channel), ``EVE_MARKET_WATCH_POLL_SECONDS`` (default 600).
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
import shlex
import sys
import time
import threading
import uuid
from urllib.parse import urlsplit
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import aiohttp
import discord
from discord import app_commands

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]
from discord.errors import LoginFailure, PrivilegedIntentsRequired
from discord.ext import commands, tasks


DATE_TOKEN_RE = re.compile(r"^\d{4}[-/]\d{2}[-/]\d{2}$")
TIME_TOKEN_RE = re.compile(r"^\d{1,2}:\d{2}$")

# Lazy-loaded solar system names for slash autocomplete (Fuzzwork CSV by default).
_SYSTEM_NAMES: list[str] | None = None
_SYSTEM_NAMES_GUARD = threading.Lock()
BeltImageMap = dict[str, str]


def _slash_option_strings(interaction: discord.Interaction) -> dict[str, str]:
    """Flatten STRING options from nested slash payload (group → subcommand → args)."""
    data: dict[str, Any] = interaction.data or {}  # type: ignore[assignment]
    out: dict[str, str] = {}

    def walk(opts: list[dict[str, Any]]) -> None:
        for opt in opts or []:
            t = int(opt.get("type", 0))
            if t in (1, 2):
                walk(opt.get("options") or [])
            elif "value" in opt and opt.get("name") is not None:
                out[str(opt["name"])] = str(opt["value"])

    walk(data.get("options") or [])
    return out


def _parse_solar_system_names_csv(text: str) -> list[str]:
    """CPU-heavy CSV parse; run via asyncio.to_thread so slash/autocomplete stays responsive."""
    names: list[str] = []
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return []

    name_idx = 0
    for i, col in enumerate(header):
        c = col.strip().casefold()
        if c == "solarsystemname" or c == "solar_system_name":
            name_idx = i
            break
        if "solarsystem" in c.replace("_", "") and "name" in c:
            name_idx = i
            break
    else:
        name_idx = min(2, len(header) - 1) if len(header) > 2 else 0

    for row in reader:
        if len(row) <= name_idx:
            continue
        n = row[name_idx].strip()
        if n:
            names.append(n)
    names.sort(key=str.casefold)
    return names


async def load_solar_system_names() -> list[str]:
    global _SYSTEM_NAMES
    with _SYSTEM_NAMES_GUARD:
        if _SYSTEM_NAMES is not None:
            return _SYSTEM_NAMES

    local_csv_path = (
        os.getenv("EVE_SYSTEM_NAMES_CSV_PATH", "").strip()
        or str(Path(__file__).resolve().parent / "data" / "mapSolarSystems.csv")
    )
    if local_csv_path:
        p = Path(local_csv_path)
        if p.exists():
            try:
                text = await asyncio.to_thread(p.read_text, "utf-8")
                names = await asyncio.to_thread(_parse_solar_system_names_csv, text)
                if names:
                    with _SYSTEM_NAMES_GUARD:
                        if _SYSTEM_NAMES is None:
                            _SYSTEM_NAMES = names
                            print(f"Solar system autocomplete: loaded {len(names)} names from {p}")
                    return _SYSTEM_NAMES or []
            except Exception as exc:
                print(f"Solar system list local read failed ({p}): {exc}")

    url = os.getenv(
        "EVE_SYSTEM_NAMES_CSV_URL",
        "https://www.fuzzwork.co.uk/dump/latest/mapSolarSystems.csv",
    ).strip()
    text = ""
    try:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"Solar system list: HTTP {resp.status} from {url}")
                    with _SYSTEM_NAMES_GUARD:
                        if _SYSTEM_NAMES is None:
                            _SYSTEM_NAMES = []
                    return _SYSTEM_NAMES or []
                text = await resp.text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        print(f"Solar system list fetch failed: {exc}")
        with _SYSTEM_NAMES_GUARD:
            if _SYSTEM_NAMES is None:
                _SYSTEM_NAMES = []
        return _SYSTEM_NAMES or []

    names = await asyncio.to_thread(_parse_solar_system_names_csv, text)
    if not names:
        with _SYSTEM_NAMES_GUARD:
            if _SYSTEM_NAMES is None:
                _SYSTEM_NAMES = []
        return _SYSTEM_NAMES or []

    with _SYSTEM_NAMES_GUARD:
        if _SYSTEM_NAMES is None:
            _SYSTEM_NAMES = names
            print(f"Solar system autocomplete: loaded {len(names)} names")
    return _SYSTEM_NAMES or []


def _normalize_discord_bot_token(raw: str | None) -> str:
    """Strip whitespace and outer quotes (common .env mistakes). Discord rejects stray quotes as 'Improper token'."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


@dataclass
class BotConfig:
    token: str
    slash_guild_id: int | None
    t1_respawn_hours: int
    t2_respawn_hours: int
    t3_respawn_hours: int
    state_file: Path
    welcome_channel_id: int | None
    welcome_guild_id: int | None
    welcome_state_file: Path
    website_url: str
    dashboard_push_url: str | None
    dashboard_token: str | None
    eveemu_api_base_url: str | None
    corp_projects_channel_id: int | None
    corp_projects_guild_id: int | None
    corp_projects_channel_name_needle: str
    corp_projects_poll_seconds: int
    structure_timer_poll_seconds: int
    structure_timer_channel_id: int | None
    market_watch_poll_seconds: int
    market_watch_channel_id: int | None
    account_notify_poll_seconds: int
    buyback_admin_alert_poll_seconds: int
    buyback_admin_alert_channel_id: int | None
    mumble_help_image_path: str | None
    belt_ping_images: BeltImageMap
    mining_ping_lead_minutes: int

    def resolved_api_base(self) -> str | None:
        if self.eveemu_api_base_url:
            return self.eveemu_api_base_url.rstrip("/")
        u = self.dashboard_push_url
        if u:
            try:
                parts = urlsplit(u)
                if parts.scheme and parts.netloc:
                    return f"{parts.scheme}://{parts.netloc}".rstrip("/")
            except Exception:
                pass
        return None

    @classmethod
    def from_env(cls) -> "BotConfig":
        token = _normalize_discord_bot_token(os.getenv("EVE_DISCORD_BOT_TOKEN"))
        if not token:
            env_hint = Path(__file__).resolve().parent / ".env"
            raise RuntimeError(
                "EVE_DISCORD_BOT_TOKEN is required.\n"
                "  • cmd.exe:        set EVE_DISCORD_BOT_TOKEN=YourRealTokenFromDiscordPortal\n"
                "                    (no spaces around = ; then run python eve_mining_timer_bot.py in the same window)\n"
                "  • PowerShell:     $env:EVE_DISCORD_BOT_TOKEN = 'YourRealToken'\n"
                f"  • Or file:        {env_hint}\n"
                "                    with one line: EVE_DISCORD_BOT_TOKEN=YourRealToken\n"
                "                    (needs: pip install -r ..\\requirements.txt  including python-dotenv)\n"
                "  Note: $env:... is PowerShell only; in cmd it causes “syntax is incorrect”."
            )

        default_state = Path(__file__).resolve().parent / "data" / "mining_timers.json"
        state_file = Path(os.getenv("EVE_MINING_TIMER_STATE_FILE", str(default_state)))
        guild_id_raw = os.getenv("EVE_DISCORD_GUILD_ID", "").strip()
        slash_guild_id = int(guild_id_raw) if guild_id_raw else None

        wc_raw = os.getenv("EVE_WELCOME_CHANNEL_ID", "").strip()
        welcome_channel_id = int(wc_raw) if wc_raw else None
        wg_raw = os.getenv("EVE_WELCOME_GUILD_ID", "").strip()
        welcome_guild_id = int(wg_raw) if wg_raw else slash_guild_id
        default_welcome = Path(__file__).resolve().parent / "data" / "welcome_seen.json"
        welcome_state_file = Path(os.getenv("EVE_WELCOME_STATE_FILE", str(default_welcome)))
        wu = os.getenv("EVE_WEBSITE_URL", "https://eve-emu.com/").strip() or "https://eve-emu.com/"
        website_url = wu if wu.endswith("/") else wu + "/"
        dash_url = os.getenv("MINING_BOT_DASHBOARD_PUSH_URL", "").strip() or None
        dash_tok = os.getenv("MINING_BOT_DASHBOARD_TOKEN", "").strip() or None
        api_base = os.getenv("EVEEMU_API_BASE_URL", "").strip() or None

        cp_ch = os.getenv("EVE_CORP_PROJECTS_CHANNEL_ID", "").strip()
        corp_projects_channel_id = int(cp_ch) if cp_ch else None
        cp_g = os.getenv("EVE_CORP_PROJECTS_GUILD_ID", "").strip()
        corp_projects_guild_id = int(cp_g) if cp_g else None
        corp_projects_channel_name_needle = (
            os.getenv("EVE_CORP_PROJECTS_CHANNEL_NAME", "corp projects").strip() or "corp projects"
        )
        corp_projects_poll_seconds = max(300, int(os.getenv("EVE_CORP_PROJECTS_POLL_SECONDS", "36000")))
        st_poll = max(60, int(os.getenv("EVE_STRUCTURE_TIMER_POLL_SECONDS", "300")))
        st_ch = os.getenv("EVE_STRUCTURE_TIMER_CHANNEL_ID", "").strip()
        structure_timer_channel_id = int(st_ch) if st_ch else None
        mw_poll = max(300, int(os.getenv("EVE_MARKET_WATCH_POLL_SECONDS", "600")))
        mw_ch = os.getenv("EVE_MARKET_WATCH_CHANNEL_ID", "").strip()
        market_watch_channel_id = int(mw_ch) if mw_ch else None
        account_notify_poll_seconds = max(1800, int(os.getenv("EVE_ACCOUNT_NOTIFY_POLL_SECONDS", "3600")))
        buyback_admin_alert_poll_seconds = max(120, int(os.getenv("EVE_BUYBACK_ADMIN_ALERT_POLL_SECONDS", "300")))
        baa_ch = os.getenv("EVE_BUYBACK_ADMIN_ALERT_CHANNEL_ID", "").strip()
        buyback_admin_alert_channel_id = int(baa_ch) if baa_ch else None
        default_mumble_img = Path(__file__).resolve().parent / "mumble_shout_whisper.gif"
        mumble_help_image_path = (
            os.getenv("EVE_MUMBLE_HELP_IMAGE", "").strip()
            or (str(default_mumble_img) if default_mumble_img.exists() else "")
            or None
        )
        default_belt_ping_images: dict[str, Path] = {
            "large veldspar deposit": Path(__file__).resolve().parent / "large_veldspar_deposit.png",
            "large mordunium deposit": Path(__file__).resolve().parent / "large_mordunium_deposit.png",
            "large kylixium deposit": Path(__file__).resolve().parent / "large_kylixium_deposit.png",
            "large ueganite deposit": Path(__file__).resolve().parent / "large_ueganite_deposit.png",
            "large griemeer deposit": Path(__file__).resolve().parent / "large_griemeer_deposit.png",
            "large hezorime deposit": Path(__file__).resolve().parent / "large_hezorime_deposit.png",
            "large nocxite deposit": Path(__file__).resolve().parent / "large_nocxite_deposit.png",
        }
        belt_ping_images: BeltImageMap = {}
        for belt_name_cf, p in default_belt_ping_images.items():
            env_key = (
                "EVE_BELT_PING_IMAGE_"
                + belt_name_cf.upper().replace(" ", "_")
            )
            raw = os.getenv(env_key, "").strip()
            if raw:
                belt_ping_images[belt_name_cf] = raw
            elif p.exists():
                belt_ping_images[belt_name_cf] = str(p)

        mining_ping_lead_minutes = max(0, int(os.getenv("EVE_MINING_PING_LEAD_MINUTES", "30")))

        return cls(
            token=token,
            slash_guild_id=slash_guild_id,
            t1_respawn_hours=int(os.getenv("EVE_T1_RESPAWN_HOURS", "0")),
            t2_respawn_hours=int(os.getenv("EVE_T2_RESPAWN_HOURS", "0")),
            t3_respawn_hours=int(os.getenv("EVE_T3_RESPAWN_HOURS", "10")),
            state_file=state_file,
            welcome_channel_id=welcome_channel_id,
            welcome_guild_id=welcome_guild_id,
            welcome_state_file=welcome_state_file,
            website_url=website_url,
            dashboard_push_url=dash_url,
            dashboard_token=dash_tok,
            eveemu_api_base_url=api_base,
            corp_projects_channel_id=corp_projects_channel_id,
            corp_projects_guild_id=corp_projects_guild_id,
            corp_projects_channel_name_needle=corp_projects_channel_name_needle,
            corp_projects_poll_seconds=corp_projects_poll_seconds,
            structure_timer_poll_seconds=st_poll,
            structure_timer_channel_id=structure_timer_channel_id,
            market_watch_poll_seconds=mw_poll,
            market_watch_channel_id=market_watch_channel_id,
            account_notify_poll_seconds=account_notify_poll_seconds,
            buyback_admin_alert_poll_seconds=buyback_admin_alert_poll_seconds,
            buyback_admin_alert_channel_id=buyback_admin_alert_channel_id,
            mumble_help_image_path=mumble_help_image_path,
            belt_ping_images=belt_ping_images,
            mining_ping_lead_minutes=mining_ping_lead_minutes,
        )


@dataclass
class TimerEntry:
    timer_id: str
    tier: str
    system_name: str
    belt_type: str
    pop_time_utc: str
    respawn_time_utc: str
    guild_id: int
    channel_id: int
    author_id: int
    fired: bool = False

    @property
    def respawn_dt(self) -> datetime:
        return datetime.fromisoformat(self.respawn_time_utc)


class TimerStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()
        self._timers: list[TimerEntry] = []

    async def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            await self.save()
            return
        raw = (await asyncio.to_thread(lambda: self.path.read_text(encoding="utf-8"))).strip()
        if not raw:
            self._timers = []
            return
        payload = json.loads(raw)
        self._timers = [TimerEntry(**item) for item in payload]

    async def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps([asdict(t) for t in self._timers], indent=2)
        await asyncio.to_thread(self.path.write_text, content, "utf-8")

    async def add(self, entry: TimerEntry) -> None:
        async with self._lock:
            self._timers.append(entry)
            await self.save()

    async def pending_count(self) -> int:
        async with self._lock:
            return sum(1 for t in self._timers if not t.fired)

    async def timer_counts(self) -> tuple[int, int]:
        """Returns (pending_unfired, total)."""
        async with self._lock:
            total = len(self._timers)
            pending = sum(1 for t in self._timers if not t.fired)
            return pending, total

    async def due(self, now_utc: datetime, *, ping_lead: timedelta) -> list[TimerEntry]:
        """Return timers that should fire a channel ping now.

        With ``ping_lead`` > 0, a ping is due when ``now_utc`` has reached
        ``respawn - ping_lead`` (e.g. 30 minutes before respawn), not at respawn itself.
        ``ping_lead`` of zero restores the legacy behavior (ping at/after respawn time).
        """
        async with self._lock:
            due_items = [
                t
                for t in self._timers
                if not t.fired
                and (t.respawn_dt - ping_lead) <= now_utc
            ]
            if due_items:
                for t in due_items:
                    t.fired = True
                await self.save()
            return due_items

    async def belt_types_for_system(self, system: str, limit: int = 22) -> list[str]:
        sys_cf = system.strip().casefold()
        if not sys_cf:
            return []
        async with self._lock:
            seen: set[str] = set()
            out: list[str] = []
            for t in reversed(self._timers):
                if t.system_name.strip().casefold() != sys_cf:
                    continue
                bt = t.belt_type.strip()
                if not bt or bt.casefold() in seen:
                    continue
                seen.add(bt.casefold())
                out.append(bt)
                if len(out) >= limit:
                    break
            return out

    async def respawns_in_window(self, start: datetime, end: datetime) -> list[TimerEntry]:
        """Timers whose respawn time falls in [start, end] (inclusive), fired or not."""
        async with self._lock:
            out = [t for t in self._timers if start <= t.respawn_dt <= end]
            out.sort(key=lambda x: x.respawn_dt)
            return out


class WelcomeStore:
    """Tracks users who already received a join welcome (per guild)."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()
        self._by_guild: dict[str, set[int]] = {}

    async def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            async with self._lock:
                self._by_guild = {}
            return
        raw = (await asyncio.to_thread(lambda: self.path.read_text(encoding="utf-8"))).strip()
        async with self._lock:
            if not raw:
                self._by_guild = {}
                return
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self._by_guild = {}
                return
            self._by_guild = {}
            for k, v in data.items():
                if not isinstance(v, list):
                    continue
                self._by_guild[str(k)] = {int(x) for x in v}

    async def has_seen(self, guild_id: int, user_id: int) -> bool:
        async with self._lock:
            return user_id in self._by_guild.get(str(guild_id), set())

    async def mark_seen(self, guild_id: int, user_id: int) -> None:
        async with self._lock:
            self._by_guild.setdefault(str(guild_id), set()).add(user_id)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {k: sorted(v) for k, v in sorted(self._by_guild.items(), key=lambda x: int(x[0]))}
            content = json.dumps(payload, indent=2)
            await asyncio.to_thread(lambda: self.path.write_text(content, encoding="utf-8"))


def _parse_time_input(raw: str, now_utc: datetime) -> datetime:
    raw = raw.strip().upper().replace("EVE", "").strip()
    formats = ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%H:%M")
    parsed: datetime | None = None

    for fmt in formats:
        try:
            base = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            parsed = datetime(
                year=now_utc.year,
                month=now_utc.month,
                day=now_utc.day,
                hour=base.hour,
                minute=base.minute,
                tzinfo=UTC,
            )
            if parsed <= now_utc:
                parsed += timedelta(days=1)
        else:
            parsed = datetime(
                year=base.year,
                month=base.month,
                day=base.day,
                hour=base.hour,
                minute=base.minute,
                tzinfo=UTC,
            )
        break

    if parsed is None:
        raise ValueError(
            "Invalid EVE time. Use HH:MM or YYYY-MM-DD HH:MM (UTC/EVE)."
        )
    return parsed


def _parse_command_payload(raw: str) -> tuple[str, str, str]:
    candidate = raw.strip()
    if not candidate:
        raise ValueError("Missing arguments.")

    if "|" in candidate:
        parts = [p.strip() for p in candidate.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError("With | separators use: SYSTEM | ANOM TYPE | EVE_TIME")
        return parts[0], parts[1], parts[2]

    tokens = shlex.split(candidate)
    if len(tokens) < 3:
        raise ValueError("Expected: SYSTEM ANOM_TYPE EVE_TIME")

    if len(tokens) >= 4 and DATE_TOKEN_RE.match(tokens[-2]) and TIME_TOKEN_RE.match(tokens[-1]):
        eve_time = f"{tokens[-2]} {tokens[-1]}"
        core = tokens[:-2]
    else:
        eve_time = tokens[-1]
        core = tokens[:-1]

    if len(core) < 2:
        raise ValueError("Expected: SYSTEM ANOM_TYPE EVE_TIME")

    system_name = core[0]
    belt_type = " ".join(core[1:])
    return system_name, belt_type, eve_time


def _format_eve_time(dt_utc: datetime) -> str:
    return dt_utc.astimezone(UTC).strftime("%Y-%m-%d %H:%M EVE")


def _format_local_time(dt_utc: datetime) -> str:
    return dt_utc.astimezone().strftime("%Y-%m-%d %I:%M %p %Z")


def _respawn_hours_for_tier(cfg: BotConfig, tier: str) -> int:
    table = {"T1": cfg.t1_respawn_hours, "T2": cfg.t2_respawn_hours, "T3": cfg.t3_respawn_hours}
    return table[tier]


def _normalize_anomaly_label(s: str) -> str:
    return " ".join(s.strip().split())


# Matches modulated-crystal style belt labels used in null (e.g. "Type C Mercoxit Belt").
_TYPE_ABC_BELT_RE = re.compile(r"^Type\s+[ABC]\s+.+\sBelt$", re.IGNORECASE)


def _type_abc_belt_variants() -> list[str]:
    simple = ("Veldspar", "Plagioclase", "Scordite", "Pyroxeres", "Mordunium")
    coherent = ("Kernite", "Omber", "Jaspet", "Hemorphite", "Hedbergite", "Ytirium", "Griemeer", "Nocxite")
    variegated = ("Gneiss", "Dark Ochre", "Crokite", "Kylixium")
    complex_ = ("Arkonor", "Bistot", "Spodumain", "Eifyrium", "Ducinium", "Hezorime", "Ueganite")
    abyssal = ("Bezdnacine", "Rakovene", "Talassonite")
    out: list[str] = []
    for letter in ("A", "B", "C"):
        for ore in simple + coherent + variegated + complex_ + abyssal + ("Mercoxit",):
            out.append(f"Type {letter} {ore} Belt")
    return out


# Cosmic ore anomaly names (EVE Online) — EVE University wiki "Ore sites" category + common size variants.
_ORE_ANOMALY_STATIC_LINES = """
Small Asteroid Cluster
Medium Asteroid Cluster
Average Asteroid Cluster
Large Asteroid Cluster
Enormous Asteroid Cluster
Colossal Asteroid Cluster
Small Arkonor and Bistot Deposit
Medium Arkonor and Bistot Deposit
Average Arkonor and Bistot Deposit
Large Arkonor and Bistot Deposit
Small Crokite and Dark Ochre Deposit
Medium Crokite and Dark Ochre Deposit
Average Crokite and Dark Ochre Deposit
Large Crokite and Dark Ochre Deposit
Small Crokite, Dark Ochre and Gneiss Deposit
Medium Crokite, Dark Ochre and Gneiss Deposit
Average Crokite, Dark Ochre and Gneiss Deposit
Large Crokite, Dark Ochre and Gneiss Deposit
Small Dark Ochre and Gneiss Deposit
Medium Dark Ochre and Gneiss Deposit
Average Dark Ochre and Gneiss Deposit
Large Dark Ochre and Gneiss Deposit
Small Gneiss Deposit
Medium Gneiss Deposit
Average Gneiss Deposit
Large Gneiss Deposit
Small Hedbergite, Hemorphite and Jaspet Deposit
Medium Hedbergite, Hemorphite and Jaspet Deposit
Average Hedbergite, Hemorphite and Jaspet Deposit
Large Hedbergite, Hemorphite and Jaspet Deposit
Small Jaspet Deposit
Medium Jaspet Deposit
Average Jaspet Deposit
Large Jaspet Deposit
Small Kernite and Omber Deposit
Medium Kernite and Omber Deposit
Average Kernite and Omber Deposit
Large Kernite and Omber Deposit
Small Mercoxit Deposit
Medium Mercoxit Deposit
Average Mercoxit Deposit
Large Mercoxit Deposit
Enormous Mercoxit Deposit
Small Omber Deposit
Medium Omber Deposit
Average Omber Deposit
Large Omber Deposit
Small Griemeer Deposit
Medium Griemeer Deposit
Average Griemeer Deposit
Large Griemeer Deposit
Small Omber, Dark Ochre and Gneiss Deposit
Medium Omber, Dark Ochre and Gneiss Deposit
Average Omber, Dark Ochre and Gneiss Deposit
Large Omber, Dark Ochre and Gneiss Deposit
Average Frontier Deposit
Unexceptional Frontier Deposit
Common Perimeter Deposit
Infrequent Core Deposit
Uncommon Core Deposit
Unusual Core Deposit
Exceptional Core Deposit
Isolated Core Deposit
Interstitial Ore Deposit
Hidden Omber Deposit
Hidden Gneiss Deposit
Hidden Dark Ochre and Gneiss Deposit
Veiled Asteroid Field
Shattered Debris Field
Veldspar Deposit
Mordunium Deposit
Nocxite Deposit
Hezorime Deposit
Ueganite Deposit
Small Hezorime Deposit
Small Ueganite Deposit
Empire Border Rare Asteroids
Nullsec Border Rare Asteroids
Nullsec Blue A0 Rare Asteroids
W-Space Blue A0 Rare Asteroids
""".strip()


def _build_ore_anomaly_canonical_map() -> dict[str, str]:
    """casefold -> canonical display string for known EVE ore cosmic anomalies."""
    m: dict[str, str] = {}
    for raw in _ORE_ANOMALY_STATIC_LINES.splitlines():
        c = _normalize_anomaly_label(raw)
        if c:
            m[c.casefold()] = c
    for raw in _type_abc_belt_variants():
        c = _normalize_anomaly_label(raw)
        m[c.casefold()] = c
    extra_path = Path(__file__).resolve().parent / "data" / "ore_anomaly_names.txt"
    if extra_path.exists():
        try:
            for raw in extra_path.read_text(encoding="utf-8").splitlines():
                s = raw.strip()
                if s and not s.startswith("#"):
                    c = _normalize_anomaly_label(s)
                    m[c.casefold()] = c
        except OSError:
            pass
    return m


_ORE_ANOMALY_CF_TO_CANONICAL: dict[str, str] = _build_ore_anomaly_canonical_map()
_ORE_ANOMALY_CANONICAL_SORTED: tuple[str, ...] = tuple(sorted(set(_ORE_ANOMALY_CF_TO_CANONICAL.values()), key=str.casefold))
def _canonicalize_anomaly_type(raw: str) -> str | None:
    s = _normalize_anomaly_label(raw)
    if not s:
        return None
    if _TYPE_ABC_BELT_RE.match(s):
        return s
    return _ORE_ANOMALY_CF_TO_CANONICAL.get(s.casefold())


def _chunk_discord_message(text: str, limit: int = 1950) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= limit:
        return [t]
    return [t[i : i + limit] for i in range(0, len(t), limit)]


def _resolve_corp_projects_channel(
    bot: discord.Client, cfg: BotConfig
) -> discord.TextChannel | discord.Thread | None:
    if cfg.corp_projects_channel_id:
        ch = bot.get_channel(cfg.corp_projects_channel_id)
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            return ch
        return None
    needle = (cfg.corp_projects_channel_name_needle or "").strip().casefold()
    gid = cfg.corp_projects_guild_id
    if not needle or gid is None:
        return None
    guild = bot.get_guild(int(gid))
    if not guild:
        return None
    for tc in guild.text_channels:
        if needle in tc.name.casefold():
            return tc
    return None


def build_bot(cfg: BotConfig) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.messages = True
    intents.message_content = True

    bot = commands.Bot(
        command_prefix=commands.when_mentioned,
        intents=intents,
        help_command=None,
        status=discord.Status.online,
        activity=discord.Game(name="Never Forget Nov 2, 1932 – Dec 10, 1932 GMW."),
    )
    store = TimerStore(cfg.state_file)
    welcome_store = WelcomeStore(cfg.welcome_state_file)
    slash_synced = False
    bot_started_at: datetime | None = None

    async def ensure_online_presence() -> None:
        """Discord sometimes shows bots as idle/offline after reconnect; force green + activity."""
        try:
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Game(name="Never Forget Nov 2, 1932 – Dec 10, 1932 GMW."),
            )
        except Exception:
            pass

    async def create_timer(
        tier: str,
        raw: str,
        guild_id: int,
        channel_id: int,
        author_id: int,
    ) -> tuple[TimerEntry, datetime, datetime]:
        system_name, belt_type, eve_input = _parse_command_payload(raw)
        canon_anom = _canonicalize_anomaly_type(belt_type)
        if canon_anom is None:
            raise ValueError(
                "Unknown anomaly type. Choose a name from the autocomplete list, "
                'or a modulated label like "Type C Mercoxit Belt".'
            )
        now_utc = datetime.now(UTC)
        pop_time = _parse_time_input(eve_input, now_utc)
        respawn_hours = _respawn_hours_for_tier(cfg, tier)
        respawn = pop_time + timedelta(hours=respawn_hours)

        timer = TimerEntry(
            timer_id=uuid.uuid4().hex[:10],
            tier=tier,
            system_name=system_name,
            belt_type=canon_anom,
            pop_time_utc=pop_time.isoformat(),
            respawn_time_utc=respawn.isoformat(),
            guild_id=guild_id,
            channel_id=channel_id,
            author_id=author_id,
            fired=False,
        )
        await store.add(timer)
        return timer, pop_time, respawn

    _MINING_PING_ALLOWED = discord.AllowedMentions(everyone=True)

    def _build_mining_ping_message(
        *,
        belt_type: str,
        system_name: str,
        when_utc: datetime,
        minutes_until_respawn: int,
    ) -> str:
        belt_cf = belt_type.strip().casefold()
        approx = f"~{minutes_until_respawn} min" if minutes_until_respawn >= 2 else "imminently"
        if belt_cf == "large griemeer deposit":
            return (
                "@here\n\n"
                "🚨 A Large Griemeer Deposit (ISOGEN) is coming up 🚨\n\n"
                f"SYSTEM:{system_name}\n\n"
                f"TIME: {_format_eve_time(when_utc)} | {_format_local_time(when_utc)} ({approx})\n\n"
                "Ore Breakdown:\n\n"
            )
        return (
            f'Hey @here The "{belt_type}" anomaly in "{system_name}" is due to respawn in {approx} '
            f"(at {_format_eve_time(when_utc)} | {_format_local_time(when_utc)})"
        )

    async def _send_mining_ping(
        channel: discord.abc.Messageable,
        *,
        belt_type: str,
        system_name: str,
        when_utc: datetime,
    ) -> None:
        now = datetime.now(UTC)
        minutes_until = max(0, int((when_utc - now).total_seconds() // 60))
        msg = _build_mining_ping_message(
            belt_type=belt_type,
            system_name=system_name,
            when_utc=when_utc,
            minutes_until_respawn=minutes_until,
        )
        belt_cf = belt_type.strip().casefold()
        await channel.send(msg, allowed_mentions=_MINING_PING_ALLOWED)
        img_path = cfg.belt_ping_images.get(belt_cf)
        if img_path and Path(img_path).exists():
            await channel.send(file=discord.File(img_path))
        else:
            if img_path:
                print(f"belt ping image path not found for '{belt_type}': {img_path}")
        if belt_cf == "large griemeer deposit":
            await channel.send("💡 Tip: Sell your ore back to the corp today! Use the !Buyback command to learn how.")

    _MINER_TIMER_PREFIX_RE = re.compile(r"^\s*!miner\s+timer(?:\s+|$)", re.IGNORECASE)
    _MINER_RESPAWNS_STRICT_RE = re.compile(r"^\s*!miner\s+(?:respawns|resawns)\s*$", re.IGNORECASE)

    async def _miner_respawns_message_parts() -> list[str]:
        """Same output chunks as /miner respawns (for slash followups or channel messages)."""
        now = datetime.now(UTC)
        win_start = now - timedelta(hours=10)
        win_end = now + timedelta(hours=10)
        items = await store.respawns_in_window(win_start, win_end)
        if not items:
            return [
                "No anomaly timers in the **±10 hour** respawn window "
                f"({_format_eve_time(win_start)} → {_format_eve_time(win_end)})."
            ]

        header = (
            f"**Anomaly respawns ±10h (EVE/UTC)** — {len(items)} timer(s)\n"
            f"_Window: {_format_eve_time(win_start)} → {_format_eve_time(win_end)}_\n\n"
        )
        lines: list[str] = []
        for t in items:
            status = "**pinged**" if t.fired else "**pending**"
            when = "respawned" if t.respawn_dt <= now else "respawns"
            belt = t.belt_type.strip()
            if len(belt) > 120:
                belt = belt[:117] + "..."
            lines.append(
                f"**{t.tier}** `{t.timer_id}` · **{t.system_name}** · *{belt}*\n"
                f"  {when.capitalize()}: {_format_eve_time(t.respawn_dt)} | {_format_local_time(t.respawn_dt)} — {status}"
            )
        body = "\n\n".join(lines)
        max_len = 1900
        if len(header) + len(body) <= max_len:
            return [header + body]

        parts: list[str] = []
        chunk = header
        for line in lines:
            addition = ("\n\n" if chunk and not chunk.endswith("\n\n") else "") + line
            if len(chunk) + len(addition) > max_len:
                parts.append(chunk)
                chunk = line
            else:
                chunk += addition
        if chunk:
            parts.append(chunk)
        return parts

    async def _register_timer_core(
        *,
        tier: str,
        system_name: str,
        belt_type: str,
        eve_time: str,
        guild_id: int,
        channel_id: int,
        author_id: int,
    ) -> tuple[TimerEntry, datetime, datetime]:
        raw = f"{system_name.strip()} | {belt_type.strip()} | {eve_time.strip()}"
        return await create_timer(
            tier=tier,
            raw=raw,
            guild_id=guild_id,
            channel_id=channel_id,
            author_id=author_id,
        )

    async def register_timer_slash(
        interaction: discord.Interaction,
        tier: str,
        system_name: str,
        belt_type: str,
        eve_time: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            timer, pop_time, respawn = await _register_timer_core(
                tier=tier,
                system_name=system_name,
                belt_type=belt_type,
                eve_time=eve_time,
                guild_id=interaction.guild.id if interaction.guild else 0,
                channel_id=interaction.channel_id or 0,
                author_id=interaction.user.id,
            )
        except ValueError as exc:
            await interaction.followup.send(
                "\n".join(
                    [
                        str(exc),
                        "Slash format:",
                        "`/miner timer tier:T1|T2|T3 system_name:<name> anom_type:<EVE anomaly> eve_time:<HH:MM>`",
                        "Example: `/miner timer tier:T3 system_name:Jita anom_type:Type C Mercoxit Belt eve_time:19:30`",
                        "Text format: `!miner timer T3 Jita | Type C Mercoxit Belt | 19:30` (same fields after tier).",
                    ]
                ),
                ephemeral=True,
            )
            return

        ping_note = (
            f"Channel @here ping: ~{cfg.mining_ping_lead_minutes} min before respawn "
            f"({_format_eve_time(respawn)} | {_format_local_time(respawn)})"
            if cfg.mining_ping_lead_minutes > 0
            else f"Channel @here ping at respawn: {_format_eve_time(respawn)} | {_format_local_time(respawn)}"
        )
        await interaction.followup.send(
            "\n".join(
                [
                    f"Saved {tier} timer `{timer.timer_id}`.",
                    f"Pop (EVE): {_format_eve_time(pop_time)}",
                    ping_note,
                ]
            ),
            ephemeral=True,
        )

    @bot.event
    async def on_ready() -> None:
        nonlocal slash_synced, bot_started_at
        try:
            if bot_started_at is None:
                bot_started_at = datetime.now(UTC)
            await ensure_online_presence()
            await store.load()
            await welcome_store.load()
            if not timer_loop.is_running():
                timer_loop.start()
            if not presence_refresh_loop.is_running():
                presence_refresh_loop.start()
            if cfg.dashboard_push_url and cfg.dashboard_token and not dashboard_push_loop.is_running():
                dashboard_push_loop.start()
            if cfg.resolved_api_base() and cfg.dashboard_token and not industry_dm_loop.is_running():
                industry_dm_loop.start()
            if cfg.resolved_api_base() and cfg.dashboard_token and not structure_timers_loop.is_running():
                structure_timers_loop.start()
            if cfg.resolved_api_base() and cfg.dashboard_token and not market_watch_loop.is_running():
                market_watch_loop.start()
            if cfg.resolved_api_base() and cfg.dashboard_token and not account_notifications_loop.is_running():
                account_notifications_loop.start()
            if (
                cfg.resolved_api_base()
                and cfg.dashboard_token
                and cfg.buyback_admin_alert_channel_id is not None
                and not buyback_admin_alert_loop.is_running()
            ):
                buyback_admin_alert_loop.start()
            if (
                cfg.resolved_api_base()
                and cfg.dashboard_token
                and not corp_projects_loop.is_running()
                and (
                    cfg.corp_projects_channel_id is not None
                    or (
                        cfg.corp_projects_guild_id is not None
                        and bool((cfg.corp_projects_channel_name_needle or "").strip())
                    )
                )
            ):
                corp_projects_loop.start()
            if not slash_synced:
                try:
                    if cfg.slash_guild_id:
                        guild_obj = discord.Object(id=cfg.slash_guild_id)
                        bot.tree.copy_global_to(guild=guild_obj)
                        synced = await bot.tree.sync(guild=guild_obj)
                        print(f"Synced {len(synced)} guild slash commands to {cfg.slash_guild_id}")
                    else:
                        synced = await bot.tree.sync()
                        print(f"Synced {len(synced)} global slash commands")
                        # Global command propagation can be delayed; sync to current guilds for immediate updates.
                        for g in bot.guilds:
                            try:
                                guild_obj = discord.Object(id=g.id)
                                bot.tree.copy_global_to(guild=guild_obj)
                                gs = await bot.tree.sync(guild=guild_obj)
                                print(f"Synced {len(gs)} guild slash commands to {g.id} ({g.name})")
                            except Exception as exc:
                                print(f"Guild slash sync failed for {g.id} ({g.name}): {exc}")
                    slash_synced = True
                except Exception as exc:
                    print(f"Slash command sync failed: {exc}")
            await load_solar_system_names()
            pending = await store.pending_count()
            print(f"Logged in as {bot.user} | pending timers: {pending}")
        except Exception as exc:
            print(f"on_ready: non-fatal error (bot stays connected): {exc}")

    @bot.event
    async def on_resumed() -> None:
        await ensure_online_presence()

    @tasks.loop(seconds=3600)
    async def presence_refresh_loop() -> None:
        await ensure_online_presence()

    @presence_refresh_loop.before_loop
    async def before_presence_refresh_loop() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=20)
    async def timer_loop() -> None:
        lead = timedelta(minutes=cfg.mining_ping_lead_minutes)
        due = await store.due(datetime.now(UTC), ping_lead=lead)
        for timer in due:
            channel = bot.get_channel(timer.channel_id)
            if channel is None:
                try:
                    channel = await bot.fetch_channel(timer.channel_id)
                except Exception:
                    continue

            try:
                await _send_mining_ping(
                    channel,
                    belt_type=timer.belt_type,
                    system_name=timer.system_name,
                    when_utc=timer.respawn_dt,
                )
            except Exception:
                pass

    @timer_loop.before_loop
    async def before_timer_loop() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=30)
    async def dashboard_push_loop() -> None:
        if not cfg.dashboard_push_url or not cfg.dashboard_token:
            return
        if bot.user is None:
            return
        pending, total = await store.timer_counts()
        guild_payload = [{"id": str(g.id), "name": g.name} for g in list(bot.guilds)[:40]]
        payload = {
            "bot": {
                "username": bot.user.name,
                "id": bot.user.id,
                "discriminator": getattr(bot.user, "discriminator", "0"),
            },
            "guild_count": len(bot.guilds),
            "guilds": guild_payload,
            "latency_ms": round(bot.latency * 1000, 1),
            "pending_timers": pending,
            "total_timers": total,
            "uptime_seconds": int((datetime.now(UTC) - bot_started_at).total_seconds())
            if bot_started_at
            else None,
            "python": sys.version.split()[0],
            "discord_py": getattr(discord, "__version__", "unknown"),
        }
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    cfg.dashboard_push_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        print(f"Mining dashboard push HTTP {resp.status}: {body[:300]}")
        except Exception as exc:
            print(f"Mining dashboard push failed: {exc}")

    @dashboard_push_loop.before_loop
    async def before_dashboard_push() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=90)
    async def industry_dm_loop() -> None:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            return
        url = f"{base}/integrations/mining-discord-bot/industry-watches/run"
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        print(f"Industry watch HTTP {resp.status}: {raw[:400]}")
                        return
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        print(f"Industry watch: non-JSON response: {raw[:200]}")
                        return
        except Exception as exc:
            print(f"Industry watch request failed: {exc}")
            return

        dms = payload.get("dms") if isinstance(payload, dict) else None
        if not isinstance(dms, list) or not dms:
            return
        for item in dms:
            if not isinstance(item, dict):
                continue
            try:
                uid = int(item["discord_user_id"])
                msg = str(item.get("message") or "")
            except (KeyError, TypeError, ValueError):
                continue
            if not msg:
                continue
            try:
                user = await bot.fetch_user(uid)
                await user.send(msg)
            except discord.Forbidden:
                print(f"Industry DM: cannot DM user {uid} (closed DMs or blocked bot).")
            except Exception as exc:
                print(f"Industry DM failed for user {uid}: {exc}")

    @industry_dm_loop.before_loop
    async def before_industry_dm_loop() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=cfg.corp_projects_poll_seconds)
    async def corp_projects_loop() -> None:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            return
        url = f"{base}/integrations/mining-discord-bot/corp-projects/run"
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        print(f"Corp projects watch HTTP {resp.status}: {raw[:400]}")
                        return
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        print(f"Corp projects watch: non-JSON response: {raw[:200]}")
                        return
        except Exception as exc:
            print(f"Corp projects watch request failed: {exc}")
            return

        ch = _resolve_corp_projects_channel(bot, cfg)
        if ch is None:
            return

        posts = payload.get("posts") if isinstance(payload, dict) else None
        if not isinstance(posts, list) or not posts:
            return
        for raw in posts:
            if not isinstance(raw, str) or not raw.strip():
                continue
            for part in _chunk_discord_message(raw):
                try:
                    await ch.send(part)
                except discord.Forbidden:
                    print(
                        "Corp projects: bot cannot post in the configured channel "
                        "(missing Send Messages / View Channel)."
                    )
                    return
                except Exception as exc:
                    print(f"Corp projects channel post failed: {exc}")

    @corp_projects_loop.before_loop
    async def before_corp_projects_loop() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=max(60, cfg.structure_timer_poll_seconds))
    async def structure_timers_loop() -> None:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            return
        url = f"{base}/integrations/mining-discord-bot/structure-timers/tick"
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                    params={"sync_sheet": "true", "force_sheet": "false"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        print(f"Structure timers tick HTTP {resp.status}: {raw[:400]}")
                        return
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        print(f"Structure timers tick: non-JSON response: {raw[:200]}")
                        return
        except Exception as exc:
            print(f"Structure timers tick failed: {exc}")
            return

        embed_dicts = payload.get("embeds") if isinstance(payload, dict) else None
        if not isinstance(embed_dicts, list) or not embed_dicts:
            return
        conf = payload.get("config") if isinstance(payload, dict) else {}
        ch_id = None
        if isinstance(conf, dict) and conf.get("discord_channel_id") is not None:
            try:
                ch_id = int(conf["discord_channel_id"])
            except (TypeError, ValueError):
                ch_id = None
        if ch_id is None:
            ch_id = cfg.structure_timer_channel_id
        if ch_id is None:
            return
        ch = bot.get_channel(int(ch_id))
        if not isinstance(ch, (discord.TextChannel, discord.Thread)):
            return
        batch: list[discord.Embed] = []
        for ed in embed_dicts:
            if not isinstance(ed, dict):
                continue
            try:
                batch.append(discord.Embed.from_dict(ed))
            except Exception:
                batch.append(
                    discord.Embed(
                        title=str(ed.get("title") or "Structure timer"),
                        description=str(ed.get("description") or "")[:4000],
                        color=ed.get("color"),
                    )
                )
            if len(batch) >= 10:
                try:
                    await ch.send(embeds=batch)
                except discord.Forbidden:
                    print("Structure timers: missing permission to post embeds in alert channel.")
                    return
                except Exception as exc:
                    print(f"Structure timers channel post failed: {exc}")
                batch = []
        if batch:
            try:
                await ch.send(embeds=batch)
            except Exception as exc:
                print(f"Structure timers channel post failed: {exc}")

    @structure_timers_loop.before_loop
    async def before_structure_timers_loop() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=max(300, cfg.market_watch_poll_seconds))
    async def market_watch_loop() -> None:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            return
        url = f"{base}/integrations/mining-discord-bot/market-watch/tick"
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        print(f"Market watch tick HTTP {resp.status}: {raw[:400]}")
                        return
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        print(f"Market watch tick: non-JSON response: {raw[:200]}")
                        return
        except Exception as exc:
            print(f"Market watch tick failed: {exc}")
            return

        ch_id = None
        if isinstance(payload, dict):
            raw_ch = payload.get("market_watch_channel_id")
            if raw_ch is not None:
                try:
                    ch_id = int(raw_ch)
                except (TypeError, ValueError):
                    ch_id = None
        if not ch_id:
            ch_id = cfg.market_watch_channel_id
        if ch_id is None:
            return
        ch = bot.get_channel(int(ch_id))
        if not isinstance(ch, (discord.TextChannel, discord.Thread)):
            return

        embed_dicts = payload.get("market_watch_embeds") if isinstance(payload, dict) else None
        content_raw = payload.get("market_watch_content") if isinstance(payload, dict) else None
        content = str(content_raw).strip() if isinstance(content_raw, str) else None
        if content == "":
            content = None

        if isinstance(embed_dicts, list) and embed_dicts:
            batch: list[discord.Embed] = []
            for ed in embed_dicts:
                if not isinstance(ed, dict):
                    continue
                try:
                    batch.append(discord.Embed.from_dict(ed))
                except Exception:
                    batch.append(
                        discord.Embed(
                            title=str(ed.get("title") or "Market watch"),
                            description=str(ed.get("description") or "")[:4000],
                            color=ed.get("color"),
                        )
                    )
                if len(batch) >= 10:
                    try:
                        await ch.send(content=content, embeds=batch)
                    except discord.Forbidden:
                        print("Market watch: missing permission to post in stocker channel.")
                        return
                    except Exception as exc:
                        print(f"Market watch channel post failed: {exc}")
                    batch = []
                    content = None
            if batch:
                try:
                    await ch.send(content=content, embeds=batch)
                except discord.Forbidden:
                    print("Market watch: missing permission to post in stocker channel.")
                except Exception as exc:
                    print(f"Market watch channel post failed: {exc}")

        dms = payload.get("market_watch_dms") if isinstance(payload, dict) else None
        if isinstance(dms, list):
            for item in dms:
                if not isinstance(item, dict):
                    continue
                try:
                    uid = int(item["discord_user_id"])
                    msg = str(item.get("message") or "")
                except (KeyError, TypeError, ValueError):
                    continue
                if not msg:
                    continue
                try:
                    user = await bot.fetch_user(uid)
                    await user.send(msg)
                except discord.Forbidden:
                    print(f"Market watch DM: cannot DM user {uid}.")
                except Exception as exc:
                    print(f"Market watch DM failed for user {uid}: {exc}")

    @market_watch_loop.before_loop
    async def before_market_watch_loop() -> None:
        await bot.wait_until_ready()

    async def _link_code_via_api(discord_user_id: int, discord_username: str | None, code: str) -> tuple[bool, str]:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            return False, "Bot API bridge is not configured by admins."
        url = f"{base}/api/integrations/mining-discord-bot/link"
        payload = {
            "discord_user_id": str(discord_user_id),
            "discord_username": discord_username or "",
            "code": code.strip(),
        }
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        return False, f"Link failed (HTTP {resp.status}): {raw[:180]}"
            return True, "Discord account linked to EvE-EMU."
        except Exception as exc:
            return False, f"Link request failed: {exc}"

    @tasks.loop(seconds=max(1800, cfg.account_notify_poll_seconds))
    async def account_notifications_loop() -> None:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            return
        url = f"{base}/api/integrations/mining-discord-bot/account-notifications/tick"
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        print(f"Account notifications tick HTTP {resp.status}: {raw[:400]}")
                        return
                    payload = json.loads(raw)
        except Exception as exc:
            print(f"Account notifications tick failed: {exc}")
            return

        dms = payload.get("dms") if isinstance(payload, dict) else None
        if not isinstance(dms, list) or not dms:
            return
        for item in dms:
            if not isinstance(item, dict):
                continue
            try:
                uid = int(item["discord_user_id"])
                msg = str(item.get("message") or "")
            except (KeyError, TypeError, ValueError):
                continue
            if not msg:
                continue
            try:
                user = await bot.fetch_user(uid)
                await user.send(msg)
            except discord.Forbidden:
                print(f"Account notify DM: cannot DM user {uid}.")
            except Exception as exc:
                print(f"Account notify DM failed for user {uid}: {exc}")

    @account_notifications_loop.before_loop
    async def before_account_notifications_loop() -> None:
        await bot.wait_until_ready()

    @tasks.loop(seconds=max(120, cfg.buyback_admin_alert_poll_seconds))
    async def buyback_admin_alert_loop() -> None:
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token or cfg.buyback_admin_alert_channel_id is None:
            return
        ch = bot.get_channel(int(cfg.buyback_admin_alert_channel_id))
        if not isinstance(ch, (discord.TextChannel, discord.Thread)):
            return
        url = f"{base}/api/integrations/mining-discord-bot/buyback-admin-alerts/tick"
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        print(f"Buyback admin alerts tick HTTP {resp.status}: {raw[:300]}")
                        return
                    payload = json.loads(raw)
        except Exception as exc:
            print(f"Buyback admin alerts tick failed: {exc}")
            return

        alerts = payload.get("admin_alerts") if isinstance(payload, dict) else None
        if not isinstance(alerts, list) or not alerts:
            return
        for msg in alerts:
            if not isinstance(msg, str) or not msg.strip():
                continue
            try:
                await ch.send(f"**Buyback admin update**\n{msg[:1800]}")
            except discord.Forbidden:
                print("Buyback admin alerts: bot cannot post in configured channel.")
                return
            except Exception as exc:
                print(f"Buyback admin alerts channel post failed: {exc}")

    @buyback_admin_alert_loop.before_loop
    async def before_buyback_admin_alert_loop() -> None:
        await bot.wait_until_ready()

    @bot.event
    async def on_member_join(member: discord.Member) -> None:
        if member.bot:
            return
        if cfg.welcome_channel_id is None:
            return
        guild = member.guild
        if cfg.welcome_guild_id is not None and guild.id != cfg.welcome_guild_id:
            return
        if len(member.roles) > 1:
            return
        if await welcome_store.has_seen(guild.id, member.id):
            return
        channel = guild.get_channel(cfg.welcome_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        msg = (
            f"Welcome {member.mention} to the INDEX Alliance Discord server. Please read the rules and "
            "familiarize yourself with the services we have to offer. If you need assistance, feel free to ask "
            "in the public channels or open a support ticket."
        )
        try:
            await channel.send(msg)
        except Exception as exc:
            print(f"Welcome DM/channel post failed for user {member.id}: {exc}")
            return
        await welcome_store.mark_seen(guild.id, member.id)

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return
        # Guild threads, forum posts, voice/stage text, and DMs are not discord.TextChannel;
        # only checking TextChannel caused !popejoy to no-op in those places.
        content = (message.content or "").strip()
        raw = content.casefold()
        if raw == "!popejoy":
            try:
                await message.channel.send("Popejoy is a bitch.")
            except Exception as exc:
                print(f"!popejoy: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw == "!srp":
            try:
                await message.channel.send("WOMP SRP Link https://auth.wompa.space/ship-replacement/")
            except Exception as exc:
                print(f"!srp: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw == "!auth":
            try:
                await message.channel.send(
                    "WOMP Alliance Auth: https://auth.wompa.space/ — False Gods SEAT: https://seat.false-gods.space/home"
                )
            except Exception as exc:
                print(f"!auth: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw == "!mumble":
            msg = (
                "🚀 Alliance Setup Guide (Follow Carefully!)\n\n"
                "🔐 1. Authenticate Services\n"
                "Head to: https://auth.wompa.space/services/\n"
                "- Navigate: Left Menu → Services → Discord → ✅ Enable\n\n"
                "🎤 2. Install Mumble\n"
                "Download here: https://www.mumble.info/\n\n"
                "🔊 3. Connect Mumble to Alliance Auth\n"
                "- Navigate: Left Menu → Services → Mumble → ✅ Enable\n\n"
                "⚠️ 4. Set Your Push-to-Talk (REQUIRED)\n"
                "- Follow the GIF instructions below to configure your talk hotkeys\n"
                "- ❗ If you skip this, you’ll broadcast to all channels and get kicked from comms\n\n"
                "---\n"
                "💡 Take a minute to double-check everything before joining comms!"
            )
            img_path = cfg.mumble_help_image_path
            try:
                if img_path and Path(img_path).exists():
                    await message.channel.send(msg, file=discord.File(img_path))
                else:
                    await message.channel.send(msg)
                    if img_path:
                        print(f"!mumble: image path not found: {img_path}")
            except Exception as exc:
                print(f"!mumble: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw == "!intel":
            try:
                await message.channel.send(
                    "See this post for the intel channel & fleet reporting guide "
                    "https://discord.com/channels/1446458381945667586/1492283337186738286"
                )
            except Exception as exc:
                print(f"!intel: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw == "!buyback":
            try:
                await message.channel.send(
                    "False Gods buyback: https://discord.com/channels/1446458381945667586/1494398530239074486"
                )
            except Exception as exc:
                print(f"!buyback: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw.startswith("!eve-link"):
            code = content[len("!eve-link") :].strip()
            if not code:
                try:
                    await message.channel.send("Usage: `!eve-link 123456` (generate code on the EvE-EMU Discord page).")
                except Exception as exc:
                    print(f"!eve-link usage: failed in channel {getattr(message.channel, 'id', '?')}: {exc}")
            else:
                ok, msg = await _link_code_via_api(message.author.id, getattr(message.author, "name", None), code)
                try:
                    await message.channel.send(msg)
                except Exception as exc:
                    print(f"!eve-link: failed in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif (mt_miner := _MINER_TIMER_PREFIX_RE.match(content)):
            try:
                rest = content[mt_miner.end() :].strip()
                if not rest:
                    await message.channel.send(
                        "**Usage:** `!miner timer T1|T2|T3 <same fields as /miner timer after tier>`\n"
                        "Examples:\n"
                        "`!miner timer T3 Jita | Type C Mercoxit Belt | 19:30`\n"
                        "`!miner timer T2 MySystem \"Large Mercoxit Deposit\" 2026-05-03 19:30`"
                    )
                else:
                    m_tier = re.match(r"^(T[123])\s+(.+)$", rest, re.IGNORECASE | re.DOTALL)
                    if not m_tier:
                        await message.channel.send(
                            "First argument after `!miner timer` must be **T1**, **T2**, or **T3**, then system, anomaly, and EVE time. "
                            "Example: `!miner timer T3 Jita | Type C Mercoxit Belt | 19:30`"
                        )
                    else:
                        tier = m_tier.group(1).upper()
                        payload = m_tier.group(2).strip()
                        try:
                            system_name, belt_type, eve_time = _parse_command_payload(payload)
                        except ValueError as exc:
                            await message.channel.send(str(exc))
                        else:
                            try:
                                timer, pop_time, respawn = await _register_timer_core(
                                    tier=tier,
                                    system_name=system_name,
                                    belt_type=belt_type,
                                    eve_time=eve_time,
                                    guild_id=message.guild.id if message.guild else 0,
                                    channel_id=message.channel.id,
                                    author_id=message.author.id,
                                )
                            except ValueError as exc:
                                await message.channel.send(
                                    "\n".join(
                                        [
                                            str(exc),
                                            "Try: `!miner timer T3 Jita | Type C Mercoxit Belt | 19:30` "
                                            '(pipe separators) or quoted anomaly name — same rules as `/miner timer`).',
                                        ]
                                    )
                                )
                            else:
                                ping_note = (
                                    f"Channel @here ping: ~{cfg.mining_ping_lead_minutes} min before respawn "
                                    f"({_format_eve_time(respawn)} | {_format_local_time(respawn)})"
                                    if cfg.mining_ping_lead_minutes > 0
                                    else f"Channel @here ping at respawn: {_format_eve_time(respawn)} | {_format_local_time(respawn)}"
                                )
                                await message.reply(
                                    "\n".join(
                                        [
                                            f"Saved {tier} timer `{timer.timer_id}`.",
                                            f"Pop (EVE): {_format_eve_time(pop_time)}",
                                            ping_note,
                                        ]
                                    ),
                                    mention_author=False,
                                )
            except Exception as exc:
                print(f"!miner timer: failed in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif _MINER_RESPAWNS_STRICT_RE.match(content):
            try:
                parts = await _miner_respawns_message_parts()
                await message.reply(parts[0], mention_author=False)
                for extra in parts[1:10]:
                    await message.channel.send(extra)
                if len(parts) > 10:
                    await message.channel.send(f"_…and {len(parts) - 10} more chunk(s) omitted._")
            except Exception as exc:
                print(f"!miner respawns: failed in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw == "!help":
            try:
                await message.channel.send(
                    "**Available text commands**\n"
                    "`!help` — show this list\n"
                    "`!miner timer` — same as `/miner timer` (T1|T2|T3 + system, anomaly, EVE/UTC time)\n"
                    "`!miner respawns` — same as `/miner respawns` (also `!miner resawns`, typo)\n"
                    "`!srp` — SRP link\n"
                    "`!auth` — alliance auth + SEAT links\n"
                    "`!mumble` — comms setup guide + hotkey GIF\n"
                    "`!intel` — intel/fleet reporting guide post\n"
                    "`!buyback` — buyback channel link\n"
                    "`!eve-link 123456` — link your EvE-EMU account to this Discord bot"
                )
            except Exception as exc:
                print(f"!help: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        elif raw.startswith("!testping"):
            try:
                belt_input = content[len("!testping") :].strip()
                if not belt_input:
                    await message.channel.send(
                        "Usage: `!testping <belt type>` (example: `!testping Large Griemeer Deposit`)."
                    )
                    await bot.process_commands(message)
                    return
                canonical = _canonicalize_anomaly_type(belt_input) or _normalize_anomaly_label(belt_input)
                now = datetime.now(UTC)
                test_dt = now.replace(hour=4, minute=20, second=0, microsecond=0)
                if test_dt <= now:
                    test_dt += timedelta(days=1)
                await _send_mining_ping(
                    message.channel,
                    belt_type=canonical,
                    system_name="TESTING",
                    when_utc=test_dt,
                )
            except Exception as exc:
                print(f"!testping: failed to send in channel {getattr(message.channel, 'id', '?')}: {exc}")
        await bot.process_commands(message)

    miner_group = app_commands.Group(name="miner", description="Mining timer tools")

    async def autocomplete_eve_time(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        now = datetime.now(UTC)
        full = now.strftime("%Y-%m-%d %H:%M")
        hm = now.strftime("%H:%M")
        soon = (now + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M")
        plus1h = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        plus2h = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        pairs = [
            (f"EVE now — {full} UTC", full),
            (f"EVE today — {hm} (calendar day UTC)", hm),
            (f"EVE +15m — {soon} UTC", soon),
            (f"EVE +1h — {plus1h} UTC", plus1h),
            (f"EVE +2h — {plus2h} UTC", plus2h),
        ]
        cur = current.strip().casefold()
        out: list[app_commands.Choice[str]] = []
        for label, val in pairs:
            if len(out) >= 25:
                break
            if not cur or cur in label.casefold() or cur in val.casefold():
                out.append(app_commands.Choice(name=label[:100], value=val[:100]))
        return out

    async def autocomplete_anom_type(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            merged: list[str] = []
            seen_cf: set[str] = set()
            for b in list(_ORE_ANOMALY_CANONICAL_SORTED):
                c = _canonicalize_anomaly_type(b)
                if not c:
                    continue
                k = c.casefold()
                if k in seen_cf:
                    continue
                seen_cf.add(k)
                merged.append(c)
            cur = current.strip().casefold()
            if cur:
                merged = [b for b in merged if cur in b.casefold()]
            starts = [b for b in merged if b.casefold().startswith(cur)]
            rest = [b for b in merged if b not in starts]
            ordered = starts + rest
            return [app_commands.Choice(name=b[:100], value=b[:100]) for b in ordered[:25]]
        except Exception as exc:
            print(f"anom_type autocomplete failed: {exc}")
            return []

    async def autocomplete_system_name(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cur = current.strip()
        if len(cur) < 2:
            return []
        all_names = _SYSTEM_NAMES or []
        if not all_names:
            fallback = ["Jita", "Amarr", "Dodixie", "Hek", "Rens"]
            ccf_fb = cur.casefold()
            out_fb = [x for x in fallback if ccf_fb in x.casefold()][:25]
            return [app_commands.Choice(name=n[:100], value=n[:100]) for n in out_fb]
        try:
            ccf = cur.casefold()
            starts: list[str] = []
            for name in all_names:
                if name.casefold().startswith(ccf):
                    starts.append(name)
                    if len(starts) >= 25:
                        break
            if len(starts) >= 25:
                return [app_commands.Choice(name=n[:100], value=n[:100]) for n in starts]
            have = {x.casefold() for x in starts}
            rest: list[str] = []
            for name in all_names:
                if name.casefold() in have:
                    continue
                if ccf in name.casefold():
                    rest.append(name)
                    if len(starts) + len(rest) >= 25:
                        break
            picked = (starts + rest)[:25]
            return [app_commands.Choice(name=n[:100], value=n[:100]) for n in picked]
        except Exception as exc:
            print(f"system_name autocomplete failed: {exc}")
            return []

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        # Keep this broad so autocomplete and command exceptions always land in logs.
        print(f"app command error: type={type(error).__name__} detail={error}")

    @miner_group.command(name="timer", description="Create an ore anomaly respawn timer (T1, T2, or T3)")
    @app_commands.describe(
        tier="Anomaly tier: T1, T2, or T3",
        system_name="System name, e.g. Jita",
        belt_type='EVE cosmic anomaly name, e.g. "Type C Mercoxit Belt" or "Large Mercoxit Deposit"',
        eve_time="EVE time (UTC): HH:MM or YYYY-MM-DD HH:MM",
    )
    async def miner_timer(
        interaction: discord.Interaction,
        tier: Literal["T1", "T2", "T3"],
        system_name: str,
        belt_type: str,
        eve_time: str,
    ) -> None:
        await register_timer_slash(interaction, tier, system_name, belt_type, eve_time)

    @miner_group.command(
        name="respawns",
        description="List anomaly timers that respawned in the last 10h or will respawn in the next 10h (EVE/UTC).",
    )
    async def miner_respawns(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        parts = await _miner_respawns_message_parts()
        await interaction.followup.send(parts[0], ephemeral=True)
        for extra in parts[1:10]:
            await interaction.followup.send(extra, ephemeral=True)
        if len(parts) > 10:
            await interaction.followup.send(
                f"_…and {len(parts) - 10} more chunk(s) omitted._",
                ephemeral=True,
            )

    miner_timer.autocomplete("eve_time")(autocomplete_eve_time)
    miner_timer.autocomplete("system_name")(autocomplete_system_name)
    miner_timer.autocomplete("belt_type")(autocomplete_anom_type)

    @bot.tree.command(name="website", description="INDEX Alliance EvE-EMU main website URL.")
    async def website_slash(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"**INDEX Alliance (EvE-EMU)**\n{cfg.website_url}",
            ephemeral=False,
        )

    @bot.tree.command(name="help", description="Show available bot commands and links.")
    async def help_slash(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "**Available commands**\n"
            "`/website` — show alliance website URL\n"
            "`/eve-link <code>` — link your EvE-EMU account for DM notifications\n"
            "\n"
            "**Text commands**\n"
            "`!help`, `!miner timer`, `!miner respawns`, `!srp`, `!auth`, `!mumble`, `!intel`, `!buyback`, `!eve-link 123456`",
            ephemeral=True,
        )

    @bot.tree.command(name="eve-link", description="Link this Discord account to your EvE-EMU profile.")
    @app_commands.describe(code="6-digit one-time code from EvE-EMU → Social → Discord.")
    async def eve_link_slash(interaction: discord.Interaction, code: str) -> None:
        await interaction.response.defer(ephemeral=True)
        ok, msg = await _link_code_via_api(interaction.user.id, getattr(interaction.user, "name", None), code)
        await interaction.followup.send(msg, ephemeral=True)

    structure_group = app_commands.Group(
        name="structure",
        description="Upwell structure vulnerability timers (sheet + Discord, standings via corp ESI).",
    )

    _STRUCTURE_REF_TYPES: tuple[str, ...] = (
        "Shield vulnerability",
        "Armor vulnerability",
        "Hull / final timer",
        "Structure deployment / anchoring",
        "Other",
    )

    async def structure_ref_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        cur = current.strip().casefold()
        out: list[app_commands.Choice[str]] = []
        for label in _STRUCTURE_REF_TYPES:
            if not cur or cur in label.casefold():
                out.append(app_commands.Choice(name=label[:100], value=label[:100]))
            if len(out) >= 25:
                break
        return out

    @structure_group.command(
        name="new_timer",
        description="Add a structure vulnerability timer (UTC). Standings use alliance id, then owner corp id.",
    )
    @app_commands.describe(
        solar_system="Solar system name",
        alliance_id="EVE alliance id of the structure owner (for standings lookup)",
        alliance_name="Alliance display name (optional)",
        owner_corporation_id="Owner corporation id if known (improves corp-level standings match)",
        structure_name="Structure name as you want it shown",
        ref_type="Timer type (autocomplete)",
        event_utc="Event time in UTC, e.g. 2026-04-23 19:30 or 2026-04-23T19:30:00Z",
        notes="Optional notes",
    )
    async def structure_new_timer(
        interaction: discord.Interaction,
        solar_system: str,
        alliance_id: int,
        alliance_name: str | None,
        owner_corporation_id: int | None,
        structure_name: str,
        ref_type: str,
        event_utc: str,
        notes: str | None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            await interaction.followup.send(
                "EvE-EMU API is not configured (set **EVEEMU_API_BASE_URL** and **MINING_BOT_DASHBOARD_TOKEN**).",
                ephemeral=True,
            )
            return
        s = event_utc.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            await interaction.followup.send(
                "Could not parse **event_utc**. Use ISO UTC like `2026-04-23T19:30:00Z` or `2026-04-23 19:30`.",
                ephemeral=True,
            )
            return
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        url = f"{base}/integrations/mining-discord-bot/structure-timers/create"
        body = {
            "solar_system_name": solar_system.strip(),
            "alliance_id": int(alliance_id),
            "alliance_name": (alliance_name or "").strip() or None,
            "corporation_id": int(owner_corporation_id) if owner_corporation_id is not None else None,
            "structure_name": structure_name.strip(),
            "ref_type": ref_type.strip(),
            "event_at_iso": dt.isoformat() + "Z",
            "notes": (notes or "").strip() or None,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    json=body,
                    headers={"Authorization": f"Bearer {cfg.dashboard_token}"},
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        await interaction.followup.send(f"Create failed: HTTP {resp.status} — {raw[:500]}", ephemeral=True)
                        return
        except Exception as exc:
            await interaction.followup.send(f"API error: `{exc}`", ephemeral=True)
            return
        await interaction.followup.send("Timer saved on EvE-EMU. Alerts use `/structure admin_panel`.", ephemeral=True)

    structure_new_timer.autocomplete("ref_type")(structure_ref_autocomplete)

    @structure_group.command(
        name="admin_panel",
        description="Configure Discord alert channel and reminder buckets (minutes before UTC event).",
    )
    @app_commands.describe(
        alert_minutes_csv="Comma-separated minutes, e.g. 720,360,180,60 (12h,6h,3h,1h). Leave empty to only view.",
        discord_channel_id="Numeric channel id for alert embeds. Leave empty to keep current.",
    )
    async def structure_admin_panel(
        interaction: discord.Interaction,
        alert_minutes_csv: str | None = None,
        discord_channel_id: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        base = cfg.resolved_api_base()
        if not base or not cfg.dashboard_token:
            await interaction.followup.send(
                "EvE-EMU API is not configured (set **EVEEMU_API_BASE_URL** and **MINING_BOT_DASHBOARD_TOKEN**).",
                ephemeral=True,
            )
            return
        headers = {"Authorization": f"Bearer {cfg.dashboard_token}"}
        if not (alert_minutes_csv or "").strip() and not (discord_channel_id or "").strip():
            try:
                timeout = aiohttp.ClientTimeout(total=20)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        f"{base}/integrations/mining-discord-bot/structure-timers/config",
                        headers=headers,
                    ) as resp:
                        raw = await resp.text()
                        if resp.status >= 400:
                            await interaction.followup.send(f"Could not read config: HTTP {resp.status}", ephemeral=True)
                            return
                        payload = json.loads(raw)
            except Exception as exc:
                await interaction.followup.send(f"Config read failed: `{exc}`", ephemeral=True)
                return
            conf = payload.get("config") if isinstance(payload, dict) else {}
            await interaction.followup.send(
                "**Current structure timer board config**\n```json\n"
                + json.dumps(conf, indent=2)[:1800]
                + "\n```\n"
                "Set **alert_minutes_csv** and/or **discord_channel_id** on this command to update.",
                ephemeral=True,
            )
            return
        patch: dict[str, Any] = {}
        csv = (alert_minutes_csv or "").strip()
        if csv:
            mins: list[int] = []
            for part in csv.split(","):
                p = part.strip()
                if p.isdigit():
                    mins.append(int(p))
            if mins:
                patch["alert_minutes_before"] = mins
        ch = (discord_channel_id or "").strip()
        if ch.isdigit():
            patch["discord_channel_id"] = int(ch)
        if not patch:
            await interaction.followup.send("Nothing to update — provide at least one field.", ephemeral=True)
            return
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.patch(
                    f"{base}/integrations/mining-discord-bot/structure-timers/config",
                    json=patch,
                    headers=headers,
                ) as resp:
                    raw = await resp.text()
                    if resp.status >= 400:
                        await interaction.followup.send(f"Update failed: HTTP {resp.status} — {raw[:500]}", ephemeral=True)
                        return
                    payload = json.loads(raw)
        except Exception as exc:
            await interaction.followup.send(f"API error: `{exc}`", ephemeral=True)
            return
        conf = payload.get("config") if isinstance(payload, dict) else {}
        await interaction.followup.send(
            "**Updated.**\n```json\n" + json.dumps(conf, indent=2)[:1800] + "\n```", ephemeral=True
        )

    # /structure commands temporarily disabled.
    bot.tree.add_command(miner_group)

    return bot


def _login_backoff_seconds(attempt: int) -> float:
    """Exponential backoff so Docker/crash loops do not hammer Discord (token reset risk)."""
    base = float(os.getenv("EVE_DISCORD_LOGIN_BACKOFF_BASE_SEC", "30").strip() or "30")
    cap = float(os.getenv("EVE_DISCORD_LOGIN_BACKOFF_MAX_SEC", "900").strip() or "900")
    return min(cap, base * (2 ** min(attempt - 1, 8)))


def main() -> None:
    env_file = Path(__file__).resolve().parent / ".env"
    if load_dotenv is not None:
        load_dotenv(env_file)
    cfg = BotConfig.from_env()
    attempt = 0
    while True:
        attempt += 1
        bot = build_bot(cfg)
        try:
            bot.run(cfg.token)
            return
        except LoginFailure as exc:
            print(
                f"Discord LoginFailure (attempt {attempt}): {exc}\n"
                "Common causes for “Improper token”:\n"
                "  • Wrong value: use the **Bot** token (Developer Portal → Bot → Token / Reset Token), "
                "not the OAuth2 **Client Secret** and not the **Public Key**.\n"
                "  • .env formatting: `EVE_DISCORD_BOT_TOKEN=xxx` with no spaces around `=`; avoid wrapping the token in quotes "
                "(or use matching pairs only). No line breaks inside the token.\n"
                "  • After changing .env, restart the bot; if the token was leaked, reset it in the portal.\n"
                "Waiting before retry to avoid connection abuse..."
            )
            time.sleep(_login_backoff_seconds(attempt))
        except PrivilegedIntentsRequired as exc:
            print(
                f"Discord PrivilegedIntentsRequired (attempt {attempt}): {exc}\n"
                "Enable required intents in the Developer Portal (Bot → Privileged Gateway Intents), "
                "then restart. Waiting before retry..."
            )
            time.sleep(_login_backoff_seconds(attempt))
        except KeyboardInterrupt:
            raise
        except SystemExit as exc:
            code = exc.code
            if code in (0, None):
                return
            print(f"Bot exited with code {code}; backing off before reconnect...")
            time.sleep(min(300.0, 15.0 * min(attempt, 20)))
        except Exception as exc:
            print(f"Bot.run ended unexpectedly: {exc!r}; backing off...")
            time.sleep(min(300.0, 15.0 * min(attempt, 20)))


if __name__ == "__main__":
    main()
