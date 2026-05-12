#!/usr/bin/env python3
"""
Discord mining timer bot for EVE Online anomaly respawns.

**Timer semantics:** ``eve_time`` is when the belt was **popped** (cleared). Respawn = pop + duration; band lengths
follow env ``EVE_T1_RESPAWN_HOURS``, ``EVE_T2_RESPAWN_HOURS``, ``EVE_T3_RESPAWN_HOURS`` (float or ``H:MM``).

**Slash only:** ``/help``, ``/about``, ``/admin`` (``notes`` / optional ``restart`` & ``rebuild`` via Docker Compose), ``/miner timer``, ``/miner respawns``, ``/srp``, ``/auth``, ``/mumble``,
``/intel``, ``/buyback``. Command output uses **ephemeral** replies (visible only to you in the channel where you ran the command).

**Moon timers:** optional Google Sheet CSV (``EVE_MOON_TIMERS_*``). Use ``EVE_MOON_TIMERS_CHANNEL_ID`` for **@here**
(optional) in that channel; set ``EVE_MOON_TIMERS_NOTIFY_USER_ID`` to also DM that user the same alert (plain text in DM).

**Mining reminders:** DM the timer author (``EVE_MINING_PING_LEAD_MINUTES``). Optionally set ``EVE_MINING_PING_CHANNEL_ID``
and ``EVE_MINING_PING_HERE`` to also post an **@here** belt alert in a shared channel.

**Solar system autocomplete:** optional ESI sovereignty map (``EVE_SYSTEM_NAMES_SOV_ALLIANCE_ID`` or ``EVE_SYSTEM_NAMES_SOV_ALLIANCE_NAME``),
refreshed on a timer (default daily). System names are resolved from ``mapSolarSystems`` CSV (local ``EVE_SYSTEM_NAMES_CSV_PATH`` or
``EVE_SYSTEM_NAMES_CSV_URL``). If sovereignty is unset or yields no names, the bot loads the full CSV list as before.

Set ``EVE_DISCORD_BOT_TOKEN`` in the environment or ``bot/.env`` (see ``example.env``).
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
import shlex
import subprocess
import time
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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

# FALSE GODS moon timers (public sheet; tab ``moon_timers`` — see module docstring).
MOON_TIMERS_SPREADSHEET_ID = "1cDtuFQivlumB_HNZGVXWmZaHcPomFZT6r_zAe_G6VhY"
MOON_TIMERS_TAB_NAME = "moon_timers"


def _default_moon_timers_csv_url() -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{MOON_TIMERS_SPREADSHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={MOON_TIMERS_TAB_NAME}"
    )


# Lazy-loaded solar system names for slash autocomplete (optional ESI sovereignty filter; else Fuzzwork CSV).
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


def _parse_map_solar_systems_csv_id_to_name(text: str) -> dict[int, str]:
    """Parse Fuzzwork-style ``mapSolarSystems.csv`` into ``solarSystemID`` → ``solarSystemName``."""
    out: dict[int, str] = {}
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return out
    id_idx = name_idx = 0
    for i, col in enumerate(header):
        c = col.strip().casefold()
        if c == "solarsystemid":
            id_idx = i
        elif c == "solarsystemname":
            name_idx = i
    for row in reader:
        if len(row) <= max(id_idx, name_idx):
            continue
        try:
            sid = int(row[id_idx].strip())
        except ValueError:
            continue
        n = row[name_idx].strip()
        if n:
            out[sid] = n
    return out


def _sov_alliance_id_from_env_sync() -> int | None:
    raw = os.getenv("EVE_SYSTEM_NAMES_SOV_ALLIANCE_ID", "").strip()
    if raw.isdigit():
        return int(raw)
    return None


def _sov_autocomplete_enabled() -> bool:
    return _sov_alliance_id_from_env_sync() is not None or bool(
        os.getenv("EVE_SYSTEM_NAMES_SOV_ALLIANCE_NAME", "").strip()
    )


def _sov_refresh_loop_hours() -> float:
    raw = os.getenv("EVE_SYSTEM_NAMES_SOV_REFRESH_HOURS", "24").strip().replace(",", ".")
    try:
        h = float(raw)
    except ValueError:
        h = 24.0
    return max(1.0, min(168.0, h))


_ESI_SOV_USER_AGENT = "EVE-EMU-DiscordBot/1.0 (+sov-system-names; contact: eve-emu)"


async def _resolve_sov_alliance_id_async(session: aiohttp.ClientSession) -> int | None:
    sid = _sov_alliance_id_from_env_sync()
    if sid is not None:
        return sid
    name = os.getenv("EVE_SYSTEM_NAMES_SOV_ALLIANCE_NAME", "").strip()
    if not name:
        return None
    url = "https://esi.evetech.net/latest/universe/ids/"
    try:
        async with session.post(
            url,
            json=[name],
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        ) as resp:
            if resp.status != 200:
                print(f"ESI universe/ids: HTTP {resp.status} for alliance name lookup")
                return None
            data = await resp.json()
    except Exception as exc:
        print(f"ESI universe/ids failed ({name!r}): {exc}")
        return None
    alliances = data.get("alliances") or []
    if alliances:
        try:
            return int(alliances[0]["id"])
        except (KeyError, TypeError, ValueError):
            return None
    corps = data.get("corporations") or []
    if not corps:
        return None
    try:
        cid = int(corps[0]["id"])
    except (KeyError, TypeError, ValueError):
        return None
    try:
        async with session.get(f"https://esi.evetech.net/latest/corporations/{cid}/") as resp2:
            if resp2.status != 200:
                return None
            cdata = await resp2.json()
    except Exception as exc:
        print(f"ESI corporations/{cid} failed: {exc}")
        return None
    aid = cdata.get("alliance_id")
    if aid is None:
        return None
    try:
        return int(aid)
    except (TypeError, ValueError):
        return None


async def _esi_universe_system_name(session: aiohttp.ClientSession, system_id: int) -> str | None:
    url = f"https://esi.evetech.net/latest/universe/systems/{system_id}/"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except Exception:
        return None
    n = (data.get("name") or "").strip()
    return n or None


async def _load_map_solar_systems_csv_text_for_sov() -> str:
    """Same sources as full autocomplete CSV, for ID→name when using sovereignty filter."""
    local_csv_path = (
        os.getenv("EVE_SYSTEM_NAMES_CSV_PATH", "").strip()
        or str(Path(__file__).resolve().parent / "data" / "mapSolarSystems.csv")
    )
    if local_csv_path:
        p = Path(local_csv_path)
        if p.exists():
            return await asyncio.to_thread(p.read_text, "utf-8")
    url = os.getenv(
        "EVE_SYSTEM_NAMES_CSV_URL",
        "https://www.fuzzwork.co.uk/dump/latest/mapSolarSystems.csv",
    ).strip()
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": _ESI_SOV_USER_AGENT}) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"mapSolarSystems.csv: HTTP {resp.status} from {url}")
            return await resp.text(encoding="utf-8", errors="ignore")


async def _fetch_sov_system_names_for_alliance(session: aiohttp.ClientSession, alliance_id: int) -> list[str]:
    async with session.get("https://esi.evetech.net/latest/sovereignty/map/") as resp:
        if resp.status != 200:
            print(f"ESI sovereignty/map: HTTP {resp.status}")
            return []
        try:
            rows: list[dict[str, Any]] = await resp.json()
        except Exception as exc:
            print(f"ESI sovereignty/map: invalid JSON: {exc}")
            return []
    system_ids: set[int] = set()
    for row in rows:
        aid = row.get("alliance_id")
        if aid is None:
            continue
        try:
            if int(aid) != alliance_id:
                continue
        except (TypeError, ValueError):
            continue
        sid = row.get("system_id")
        if sid is None:
            continue
        try:
            system_ids.add(int(sid))
        except (TypeError, ValueError):
            continue
    if not system_ids:
        return []
    csv_text = await _load_map_solar_systems_csv_text_for_sov()
    id_to_name = await asyncio.to_thread(_parse_map_solar_systems_csv_id_to_name, csv_text)
    names: list[str] = []
    missing: list[int] = []
    for sid in sorted(system_ids):
        n = id_to_name.get(sid)
        if n:
            names.append(n)
        else:
            missing.append(sid)
    for sid in missing:
        n = await _esi_universe_system_name(session, sid)
        if n:
            names.append(n)
        await asyncio.sleep(0.05)
    names.sort(key=str.casefold)
    return names


async def _load_solar_system_names_via_sovereignty() -> list[str] | None:
    """``None`` = sovereignty autocomplete not configured. Otherwise a (possibly empty) name list."""
    if not _sov_autocomplete_enabled():
        return None
    timeout = aiohttp.ClientTimeout(total=120)
    headers = {"User-Agent": _ESI_SOV_USER_AGENT}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        alliance_id = await _resolve_sov_alliance_id_async(session)
        if alliance_id is None:
            print("ESI sovereignty autocomplete: could not resolve alliance id (check env).")
            return []
        names = await _fetch_sov_system_names_for_alliance(session, alliance_id)
        if names:
            print(
                f"Solar system autocomplete (ESI sovereignty): {len(names)} system(s) "
                f"for alliance_id={alliance_id}"
            )
        else:
            print(f"ESI sovereignty autocomplete: no systems with alliance_id={alliance_id} on sovereignty map.")
        return names


async def load_solar_system_names() -> list[str]:
    global _SYSTEM_NAMES
    with _SYSTEM_NAMES_GUARD:
        if _SYSTEM_NAMES is not None:
            return _SYSTEM_NAMES

    sov_names: list[str] | None
    try:
        sov_names = await _load_solar_system_names_via_sovereignty()
    except Exception as exc:
        print(f"ESI sovereignty autocomplete failed: {exc}")
        sov_names = []
    if sov_names is not None:
        if sov_names:
            with _SYSTEM_NAMES_GUARD:
                if _SYSTEM_NAMES is None:
                    _SYSTEM_NAMES = sov_names
            return _SYSTEM_NAMES or []
        print("ESI sovereignty autocomplete: no names; falling back to full CSV sources.")

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


# Default respawn after pop (hours), per ore-site upgrade band — alliance anomaly sheet.
_DEFAULT_T1_RESPAWN_HOURS = 1.0
_DEFAULT_T2_RESPAWN_HOURS = 4.0 + 20.0 / 60.0  # 4 h 20 m
_DEFAULT_T3_RESPAWN_HOURS = 10.0

# Fixed respawn (hours) for sites where the sheet gives one value regardless of T1–T3 band.
_BELT_RESPAWN_OVERRIDE_HOURS_CF: dict[str, float] = {
    "large mercoxit deposit": 8.0,
    "enormous mercoxit deposit": 12.0,
}

_RESPAWN_ENV_HOURS_COLON = re.compile(r"^\s*(\d{1,4})\s*:\s*(\d{1,2})\s*$")


def _parse_env_respawn_hours(env_name: str, default: float) -> float:
    """Parse ``EVE_T*_RESPAWN_HOURS``: empty → default; ``4:20`` → 4h20m; else float hours."""
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    m = _RESPAWN_ENV_HOURS_COLON.match(raw)
    if m:
        hours = int(m.group(1)) + int(m.group(2)) / 60.0
    else:
        hours = float(raw.replace(",", "."))
    return hours if hours > 0 else default


def _normalize_discord_bot_token(raw: str | None) -> str:
    """Strip whitespace and outer quotes (common .env mistakes). Discord rejects stray quotes as 'Improper token'."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def _parse_discord_admin_user_ids(raw: str | None) -> frozenset[int]:
    """Comma- or semicolon-separated Discord user snowflakes for `/admin` when set (see ``EVE_DISCORD_ADMIN_USER_IDS``)."""
    out: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        p = part.strip()
        if p.isdigit():
            out.append(int(p))
    return frozenset(out)


@dataclass
class BotConfig:
    token: str
    slash_guild_id: int | None
    t1_respawn_hours: float
    t2_respawn_hours: float
    t3_respawn_hours: float
    state_file: Path
    mumble_help_image_path: str | None
    belt_ping_images: BeltImageMap
    mining_ping_lead_minutes: int
    mining_ping_channel_id: int | None
    mining_ping_here: bool
    moon_timers_csv_url: str | None
    moon_timers_notify_user_id: int | None
    moon_timers_channel_id: int | None
    moon_timers_poll_seconds: int
    moon_timers_lead_minutes: int
    moon_timers_ping_here: bool
    moon_timers_ping_state_file: Path
    discord_invite_url: str
    presence_activity: str
    product_display_name: str
    miner_slash_group_description: str
    discord_admin_user_ids: frozenset[int]
    docker_admin_enabled: bool
    docker_compose_workdir: Path | None
    docker_compose_file: str | None
    docker_compose_service: str | None
    docker_compose_timeout_sec: int

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

        mining_ping_ch = os.getenv("EVE_MINING_PING_CHANNEL_ID", "").strip()
        mining_ping_channel_id = int(mining_ping_ch) if mining_ping_ch else None
        mining_here_raw = os.getenv("EVE_MINING_PING_HERE", "1").strip().lower()
        mining_ping_here = mining_here_raw not in ("0", "false", "no", "off")

        moon_notify_raw = os.getenv("EVE_MOON_TIMERS_NOTIFY_USER_ID", "").strip()
        moon_timers_notify_user_id = int(moon_notify_raw) if moon_notify_raw else None
        moon_ch = os.getenv("EVE_MOON_TIMERS_CHANNEL_ID", "").strip()
        moon_timers_channel_id = int(moon_ch) if moon_ch else None
        moon_csv = os.getenv("EVE_MOON_TIMERS_CSV_URL", "").strip() or None
        moon_dest = moon_timers_notify_user_id is not None or moon_timers_channel_id is not None
        if moon_dest and not moon_csv:
            moon_csv = _default_moon_timers_csv_url()
        elif not moon_dest:
            moon_csv = None
        moon_timers_poll_seconds = max(120, int(os.getenv("EVE_MOON_TIMERS_POLL_SECONDS", "300")))
        moon_timers_lead_minutes = max(0, int(os.getenv("EVE_MOON_TIMERS_LEAD_MINUTES", "30")))
        moon_here_raw = os.getenv("EVE_MOON_TIMERS_PING_HERE", "1").strip().lower()
        moon_timers_ping_here = moon_here_raw not in ("0", "false", "no", "off")
        default_moon_ping_state = Path(__file__).resolve().parent / "data" / "moon_timer_pings.json"
        moon_timers_ping_state_file = Path(
            os.getenv("EVE_MOON_TIMERS_PING_STATE_FILE", str(default_moon_ping_state))
        )

        _def_discord_invite = "https://discord.gg/DHMTKsMNbp"
        discord_invite_url = os.getenv("EVE_BOT_DISCORD_INVITE_URL", "").strip() or _def_discord_invite
        product_display_name = os.getenv("EVE_BOT_PRODUCT_DISPLAY_NAME", "EVE-EMU").strip() or "EVE-EMU"
        _def_activity = "Never Forget Nov 2, 1932 – Dec 10, 1932 GMW."
        presence_activity = os.getenv("EVE_DISCORD_BOT_ACTIVITY", "").strip() or _def_activity
        if len(presence_activity) > 128:
            presence_activity = presence_activity[:128]

        def _slash_cmd_desc(env_key: str, default: str) -> str:
            return (os.getenv(env_key, "").strip() or default)[:100]

        miner_slash_group_description = _slash_cmd_desc(
            "EVE_BOT_MINER_SLASH_GROUP_DESCRIPTION",
            "Mining timer tools",
        )

        discord_admin_user_ids = _parse_discord_admin_user_ids(os.getenv("EVE_DISCORD_ADMIN_USER_IDS"))

        docker_en = os.getenv("EVE_DOCKER_ADMIN_ENABLED", "").strip().lower()
        docker_admin_enabled = docker_en in ("1", "true", "yes", "on")
        dc_dir_raw = os.getenv("EVE_DOCKER_COMPOSE_DIR", "").strip()
        docker_compose_workdir = Path(dc_dir_raw).resolve() if dc_dir_raw else None
        docker_compose_file = os.getenv("EVE_DOCKER_COMPOSE_FILE", "").strip() or None
        docker_compose_service = os.getenv("EVE_DOCKER_COMPOSE_SERVICE", "").strip() or None
        docker_compose_timeout_sec = max(30, int(os.getenv("EVE_DOCKER_COMPOSE_TIMEOUT_SEC", "900").strip() or "900"))

        return cls(
            token=token,
            slash_guild_id=slash_guild_id,
            t1_respawn_hours=_parse_env_respawn_hours("EVE_T1_RESPAWN_HOURS", _DEFAULT_T1_RESPAWN_HOURS),
            t2_respawn_hours=_parse_env_respawn_hours("EVE_T2_RESPAWN_HOURS", _DEFAULT_T2_RESPAWN_HOURS),
            t3_respawn_hours=_parse_env_respawn_hours("EVE_T3_RESPAWN_HOURS", _DEFAULT_T3_RESPAWN_HOURS),
            state_file=state_file,
            mumble_help_image_path=mumble_help_image_path,
            belt_ping_images=belt_ping_images,
            mining_ping_lead_minutes=mining_ping_lead_minutes,
            mining_ping_channel_id=mining_ping_channel_id,
            mining_ping_here=mining_ping_here,
            moon_timers_csv_url=moon_csv,
            moon_timers_notify_user_id=moon_timers_notify_user_id,
            moon_timers_channel_id=moon_timers_channel_id,
            moon_timers_poll_seconds=moon_timers_poll_seconds,
            moon_timers_lead_minutes=moon_timers_lead_minutes,
            moon_timers_ping_here=moon_timers_ping_here,
            moon_timers_ping_state_file=moon_timers_ping_state_file,
            discord_invite_url=discord_invite_url,
            presence_activity=presence_activity,
            product_display_name=product_display_name,
            miner_slash_group_description=miner_slash_group_description,
            discord_admin_user_ids=discord_admin_user_ids,
            docker_admin_enabled=docker_admin_enabled,
            docker_compose_workdir=docker_compose_workdir,
            docker_compose_file=docker_compose_file,
            docker_compose_service=docker_compose_service,
            docker_compose_timeout_sec=docker_compose_timeout_sec,
        )


@dataclass
class TimerEntry:
    timer_id: str
    tier: str  # Display band: inferred T1/T2/T3, fixed 8h/12h for special mercoxit, or user override
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
        """Return timers that should fire a reminder DM to the author now.

        With ``ping_lead`` > 0, a reminder is due when ``now_utc`` has reached
        ``respawn - ping_lead`` (e.g. 30 minutes before respawn), not at respawn itself.
        ``ping_lead`` of zero restores the legacy behavior (remind at/after respawn time).
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


class MoonTimerPingStore:
    """Dedupe moon timer @here pings (one ping per moon + event instant)."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()
        self._keys: set[str] = set()

    async def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            async with self._lock:
                self._keys = set()
            return
        raw = (await asyncio.to_thread(lambda: self.path.read_text(encoding="utf-8"))).strip()
        async with self._lock:
            if not raw:
                self._keys = set()
                return
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                self._keys = set()
                return
            if isinstance(data, list):
                self._keys = {str(x) for x in data if isinstance(x, str)}
            elif isinstance(data, dict) and isinstance(data.get("keys"), list):
                self._keys = {str(x) for x in data["keys"] if isinstance(x, str)}
            else:
                self._keys = set()

    def _prune_locked(self, now_utc: datetime, *, max_age_hours: int = 72) -> None:
        now = now_utc.astimezone(UTC) if now_utc.tzinfo else now_utc.replace(tzinfo=UTC)
        cutoff = now - timedelta(hours=max_age_hours)
        to_remove: list[str] = []
        for k in self._keys:
            if "\x1f" not in k:
                to_remove.append(k)
                continue
            _, iso_part = k.split("\x1f", 1)
            try:
                dt_e = datetime.fromisoformat(iso_part.replace("Z", "+00:00"))
                if dt_e.tzinfo is None:
                    dt_e = dt_e.replace(tzinfo=UTC)
                else:
                    dt_e = dt_e.astimezone(UTC)
                if dt_e < cutoff:
                    to_remove.append(k)
            except ValueError:
                to_remove.append(k)
        for k in to_remove:
            self._keys.discard(k)

    async def prune(self, now_utc: datetime) -> None:
        async with self._lock:
            self._prune_locked(now_utc)
            await self._save_locked()

    async def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"keys": sorted(self._keys)}
        content = json.dumps(payload, indent=2)
        await asyncio.to_thread(lambda: self.path.write_text(content, encoding="utf-8"))

    async def should_send(self, key: str) -> bool:
        async with self._lock:
            return key not in self._keys

    async def mark(self, key: str, now_utc: datetime) -> None:
        async with self._lock:
            self._keys.add(key)
            self._prune_locked(now_utc)
            await self._save_locked()


_MOON_SHEET_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
)


def _try_parse_sheet_datetime(cell: str, now_utc: datetime) -> datetime | None:
    s = (cell or "").strip().strip('"').strip()
    if not s or s.startswith("£") or s.startswith("$") or s.startswith("€"):
        return None
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", s):
        return None
    if re.fullmatch(r"\d+(\.\d+)?", s):
        try:
            n = float(s)
            if 20000 < n < 80000:
                base = datetime(1899, 12, 30, tzinfo=UTC) + timedelta(days=n)
                return base
        except (OverflowError, OSError, ValueError):
            pass
    s_iso = s.replace("Z", "+00:00")
    if re.search(r"\d{4}-\d{2}-\d{2}", s_iso):
        try:
            dt = datetime.fromisoformat(s_iso)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            pass
    for fmt in _MOON_SHEET_DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _moon_sheet_time_column_order(header: list[str]) -> tuple[int, list[int]]:
    hcf = [h.strip().casefold() for h in header]
    moon_i = next((i for i, h in enumerate(hcf) if h == "moon"), 0)
    front: list[int] = []
    rest: list[int] = []
    for i, h in enumerate(hcf):
        if i == moon_i:
            continue
        if any(x in h for x in ("renter", "monthly rent", "monthly value")):
            continue
        if h in ("next timer", "next_timer", "timer", "when", "due", "event", "next"):
            front.append(i)
        elif "reset to" in h or h == "reset to":
            continue
        else:
            rest.append(i)
    seen: set[int] = set()
    out: list[int] = []
    for i in front + rest:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return moon_i, out


def _moon_event_key(moon: str, when_utc: datetime) -> str:
    w = when_utc.astimezone(UTC).replace(microsecond=0)
    iso = w.isoformat().replace("+00:00", "Z")
    return f"{moon.strip().casefold()}\x1f{iso}"


def _moon_rows_from_sheet_csv(csv_text: str, now_utc: datetime) -> list[tuple[str, datetime]]:
    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    moon_i, col_order = _moon_sheet_time_column_order(header)
    out: list[tuple[str, datetime]] = []
    for parts in rows[1:]:
        if len(parts) <= moon_i:
            continue
        moon = parts[moon_i].strip()
        if not moon or moon.casefold() in ("moon", "total"):
            continue
        found: list[datetime] = []
        for j in col_order:
            if j >= len(parts):
                continue
            dt = _try_parse_sheet_datetime(parts[j], now_utc)
            if dt is not None:
                found.append(dt.astimezone(UTC))
        if not found:
            continue
        when = min(found)
        if when < now_utc - timedelta(hours=12):
            continue
        out.append((moon, when))
    return out


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
            "Invalid time. Use HH:MM or YYYY-MM-DD HH:MM (UTC/EVE — when the belt was popped)."
        )
    return parsed


def _parse_command_payload(raw: str) -> tuple[str, str, str]:
    candidate = raw.strip()
    if not candidate:
        raise ValueError("Missing arguments.")

    if "|" in candidate:
        parts = [p.strip() for p in candidate.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError("With | separators use: SYSTEM | ANOM TYPE | POP_TIME_UTC")
        return parts[0], parts[1], parts[2]

    tokens = shlex.split(candidate)
    if len(tokens) < 3:
        raise ValueError("Expected: SYSTEM ANOM_TYPE POP_TIME_UTC")

    if len(tokens) >= 4 and DATE_TOKEN_RE.match(tokens[-2]) and TIME_TOKEN_RE.match(tokens[-1]):
        eve_time = f"{tokens[-2]} {tokens[-1]}"
        core = tokens[:-2]
    else:
        eve_time = tokens[-1]
        core = tokens[:-1]

    if len(core) < 2:
        raise ValueError("Expected: SYSTEM ANOM_TYPE POP_TIME_UTC")

    system_name = core[0]
    belt_type = " ".join(core[1:])
    return system_name, belt_type, eve_time


def _format_eve_time(dt_utc: datetime) -> str:
    return dt_utc.astimezone(UTC).strftime("%Y-%m-%d %H:%M EVE")


def _format_local_time(dt_utc: datetime) -> str:
    return dt_utc.astimezone().strftime("%Y-%m-%d %I:%M %p %Z")


def _respawn_hours_for_tier(cfg: BotConfig, tier: str) -> float:
    table = {"T1": cfg.t1_respawn_hours, "T2": cfg.t2_respawn_hours, "T3": cfg.t3_respawn_hours}
    return float(table[tier.upper()])


_TYPE_LETTER_TO_TIER = {"a": "T1", "b": "T2", "c": "T3"}


def _infer_tier_from_anomaly(canonical: str) -> str:
    """Map anomaly name to T1/T2/T3 duration band when the user does not pass a tier (alliance sheet bands)."""
    s = canonical.strip()
    cf = s.casefold()
    m_type = re.match(r"^type\s+([abc])\s+", s, re.IGNORECASE)
    if m_type:
        return _TYPE_LETTER_TO_TIER[m_type.group(1).lower()]
    for prefix, tier in (
        ("small ", "T1"),
        ("medium ", "T1"),
        ("average ", "T2"),
        ("large ", "T3"),
        ("enormous ", "T3"),
        ("colossal ", "T3"),
    ):
        if cf.startswith(prefix):
            return tier
    return "T2"


def _respawn_hours_for_anomaly(cfg: BotConfig, belt_canonical: str, explicit_tier: str | None) -> float:
    """Hours from pop until respawn: fixed sheet overrides, else explicit or inferred T1–T3 band."""
    cf = belt_canonical.strip().casefold()
    if cf in _BELT_RESPAWN_OVERRIDE_HOURS_CF:
        return _BELT_RESPAWN_OVERRIDE_HOURS_CF[cf]
    ex = (explicit_tier or "").strip().upper()
    if ex in ("T1", "T2", "T3"):
        return _respawn_hours_for_tier(cfg, ex)
    return _respawn_hours_for_tier(cfg, _infer_tier_from_anomaly(belt_canonical))


def _timer_display_band(belt_canonical: str, explicit_tier: str | None) -> str:
    """Short label stored on the timer row (respawn list / saved confirmation)."""
    cf = belt_canonical.strip().casefold()
    if cf == "large mercoxit deposit":
        return "8h"
    if cf == "enormous mercoxit deposit":
        return "12h"
    ex = (explicit_tier or "").strip().upper()
    if ex in ("T1", "T2", "T3"):
        return ex
    return _infer_tier_from_anomaly(belt_canonical)


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
Kylixium Deposit
Griemeer Deposit
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


def build_bot(cfg: BotConfig) -> commands.Bot:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = False
    intents.messages = False
    intents.message_content = False

    bot = commands.Bot(
        command_prefix=lambda _bot, _message: [],
        intents=intents,
        help_command=None,
        status=discord.Status.online,
        activity=discord.Game(name=cfg.presence_activity),
    )
    store = TimerStore(cfg.state_file)
    moon_ping_store = MoonTimerPingStore(cfg.moon_timers_ping_state_file)
    slash_synced = False
    bot_started_at: datetime | None = None

    async def ensure_online_presence() -> None:
        """Discord sometimes shows bots as idle/offline after reconnect; force green + activity."""
        try:
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Game(name=cfg.presence_activity),
            )
        except Exception:
            pass

    async def create_timer(
        raw: str,
        guild_id: int,
        channel_id: int,
        author_id: int,
        *,
        explicit_tier: str | None = None,
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
        respawn_hours = _respawn_hours_for_anomaly(cfg, canon_anom, explicit_tier)
        respawn = pop_time + timedelta(minutes=round(respawn_hours * 60.0))
        display_band = _timer_display_band(canon_anom, explicit_tier)

        timer = TimerEntry(
            timer_id=uuid.uuid4().hex[:10],
            tier=display_band,
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

    def _build_mining_reminder_dm_text(
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
                "🚨 **Mining timer** — Large Griemeer Deposit (ISOGEN) is coming up 🚨\n\n"
                f"**System:** {system_name}\n\n"
                f"**Time:** {_format_eve_time(when_utc)} | {_format_local_time(when_utc)} ({approx})\n\n"
                "Ore breakdown (in-game) follows your overview — undock prepared.\n"
            )
        return (
            f'**Mining timer:** your "{belt_type}" anomaly in **{system_name}** is due to respawn in {approx} '
            f"(at {_format_eve_time(when_utc)} | {_format_local_time(when_utc)})"
        )

    async def _send_mining_reminder_dm(
        user: discord.abc.User,
        *,
        belt_type: str,
        system_name: str,
        when_utc: datetime,
    ) -> None:
        now = datetime.now(UTC)
        minutes_until = max(0, int((when_utc - now).total_seconds() // 60))
        msg = _build_mining_reminder_dm_text(
            belt_type=belt_type,
            system_name=system_name,
            when_utc=when_utc,
            minutes_until_respawn=minutes_until,
        )
        belt_cf = belt_type.strip().casefold()
        await user.send(msg[:2000])
        img_path = cfg.belt_ping_images.get(belt_cf)
        if img_path and Path(img_path).exists():
            await user.send(file=discord.File(img_path))
        elif img_path:
            print(f"belt ping image path not found for '{belt_type}': {img_path}")
        if belt_cf == "large griemeer deposit":
            await user.send(
                "💡 Tip: Sell your ore back to the corp today — use **`/buyback`** in this server for the link."
            )

    _MINING_HERE_ALLOWED = discord.AllowedMentions(everyone=True)

    def _build_mining_channel_here_text(
        *,
        belt_type: str,
        system_name: str,
        when_utc: datetime,
        minutes_until_respawn: int,
        ping_here: bool,
    ) -> str:
        belt_cf = belt_type.strip().casefold()
        approx = f"~{minutes_until_respawn} min" if minutes_until_respawn >= 2 else "imminently"
        prefix = "@here\n\n" if ping_here else ""
        if belt_cf == "large griemeer deposit":
            return (
                f"{prefix}"
                "🚨 A Large Griemeer Deposit (ISOGEN) is coming up 🚨\n\n"
                f"SYSTEM:{system_name}\n\n"
                f"TIME: {_format_eve_time(when_utc)} | {_format_local_time(when_utc)} ({approx})\n\n"
                "Ore Breakdown:\n\n"
            )
        here_bit = 'Hey @here ' if ping_here else ""
        return (
            f'{here_bit}The "{belt_type}" anomaly in "{system_name}" is due to respawn in {approx} '
            f"(at {_format_eve_time(when_utc)} | {_format_local_time(when_utc)})"
        )

    async def _send_mining_channel_here_ping(
        channel: discord.abc.Messageable,
        *,
        belt_type: str,
        system_name: str,
        when_utc: datetime,
        ping_here: bool,
    ) -> None:
        now = datetime.now(UTC)
        minutes_until = max(0, int((when_utc - now).total_seconds() // 60))
        msg = _build_mining_channel_here_text(
            belt_type=belt_type,
            system_name=system_name,
            when_utc=when_utc,
            minutes_until_respawn=minutes_until,
            ping_here=ping_here,
        )
        belt_cf = belt_type.strip().casefold()
        mentions = _MINING_HERE_ALLOWED if ping_here else discord.AllowedMentions(everyone=False)
        await channel.send(msg[:2000], allowed_mentions=mentions)
        img_path = cfg.belt_ping_images.get(belt_cf)
        if img_path and Path(img_path).exists():
            await channel.send(file=discord.File(img_path))
        elif img_path:
            print(f"belt ping image path not found for '{belt_type}': {img_path}")
        if belt_cf == "large griemeer deposit":
            await channel.send(
                "💡 Tip: Sell your ore back to the corp today! Use **`/buyback`** for the link.",
                allowed_mentions=discord.AllowedMentions(everyone=False),
            )

    async def _defer_ephemeral_followups(
        interaction: discord.Interaction,
        parts: list[str],
        *,
        first_message_file: discord.File | None = None,
    ) -> None:
        """Defer ephemerally, then send each chunk as an ephemeral followup (only you see it)."""
        await interaction.response.defer(ephemeral=True)
        for i, part in enumerate(parts):
            chunk = part[:2000]
            if i == 0 and first_message_file is not None:
                await interaction.followup.send(chunk, file=first_message_file, ephemeral=True)
            else:
                await interaction.followup.send(chunk, ephemeral=True)

    async def _miner_respawns_message_parts() -> list[str]:
        """Output chunks for ``/miner respawns`` (ephemeral followups)."""
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
        system_name: str,
        belt_type: str,
        eve_time: str,
        guild_id: int,
        channel_id: int,
        author_id: int,
        explicit_tier: str | None = None,
    ) -> tuple[TimerEntry, datetime, datetime]:
        raw = f"{system_name.strip()} | {belt_type.strip()} | {eve_time.strip()}"
        return await create_timer(
            raw,
            guild_id=guild_id,
            channel_id=channel_id,
            author_id=author_id,
            explicit_tier=explicit_tier,
        )

    async def register_timer_slash(
        interaction: discord.Interaction,
        system_name: str,
        belt_type: str,
        eve_time: str,
    ) -> None:
        try:
            timer, pop_time, respawn = await _register_timer_core(
                system_name=system_name,
                belt_type=belt_type,
                eve_time=eve_time,
                guild_id=interaction.guild.id if interaction.guild else 0,
                channel_id=interaction.channel_id or 0,
                author_id=interaction.user.id,
                explicit_tier=None,
            )
        except ValueError as exc:
            err_parts = [
                "\n".join(
                    [
                        str(exc),
                        "Slash format:",
                        "`/miner timer` with **system**, **belt_type** (anomaly name), and **eve_time** (pop / clear time, UTC).",
                        "Example: `/miner timer` → Jita, Type C Mercoxit Belt, `19:30`",
                    ]
                )
            ]
            await _defer_ephemeral_followups(interaction, err_parts)
            return

        dm_line = (
            f"You will get a **DM** ~{cfg.mining_ping_lead_minutes} min before respawn "
            f"({_format_eve_time(respawn)} | {_format_local_time(respawn)})"
            if cfg.mining_ping_lead_minutes > 0
            else f"You will get a **DM** at respawn: {_format_eve_time(respawn)} | {_format_local_time(respawn)}"
        )
        lines = [
            f"Saved ({timer.tier}) timer `{timer.timer_id}`.",
            f"Pop (EVE): {_format_eve_time(pop_time)}",
            dm_line,
        ]
        if cfg.mining_ping_channel_id is not None:
            cref = f"<#{cfg.mining_ping_channel_id}>"
            if cfg.mining_ping_here:
                lines.append(f"An **@here** mining alert will also be posted in {cref}.")
            else:
                lines.append(f"A mining alert (no @here) will also be posted in {cref}.")
        body = "\n".join(lines)
        await _defer_ephemeral_followups(interaction, [body])

    @bot.event
    async def on_ready() -> None:
        nonlocal slash_synced, bot_started_at
        try:
            if bot_started_at is None:
                bot_started_at = datetime.now(UTC)
            await ensure_online_presence()
            await store.load()
            await moon_ping_store.load()
            if not timer_loop.is_running():
                timer_loop.start()
            if not presence_refresh_loop.is_running():
                presence_refresh_loop.start()
            if (
                cfg.moon_timers_csv_url
                and (
                    cfg.moon_timers_notify_user_id is not None or cfg.moon_timers_channel_id is not None
                )
                and not moon_timers_loop.is_running()
            ):
                moon_timers_loop.start()
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
            if _sov_autocomplete_enabled() and not sovereignty_system_names_loop.is_running():
                sovereignty_system_names_loop.start()
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

    @tasks.loop(hours=24)
    async def sovereignty_system_names_loop() -> None:
        global _SYSTEM_NAMES
        if not _sov_autocomplete_enabled():
            return
        try:
            names = await _load_solar_system_names_via_sovereignty()
        except Exception as exc:
            print(f"sovereignty_system_names_loop: {exc}")
            return
        if not names:
            print("sovereignty_system_names_loop: empty result; keeping previous autocomplete list")
            return
        with _SYSTEM_NAMES_GUARD:
            _SYSTEM_NAMES = names

    @sovereignty_system_names_loop.before_loop
    async def before_sovereignty_system_names_loop() -> None:
        await bot.wait_until_ready()
        sovereignty_system_names_loop.change_interval(hours=_sov_refresh_loop_hours())

    @tasks.loop(seconds=20)
    async def timer_loop() -> None:
        lead = timedelta(minutes=cfg.mining_ping_lead_minutes)
        due = await store.due(datetime.now(UTC), ping_lead=lead)
        for timer in due:
            user = bot.get_user(timer.author_id)
            if user is None:
                try:
                    user = await bot.fetch_user(timer.author_id)
                except Exception:
                    continue
            try:
                await _send_mining_reminder_dm(
                    user,
                    belt_type=timer.belt_type,
                    system_name=timer.system_name,
                    when_utc=timer.respawn_dt,
                )
            except Exception:
                pass
            if cfg.mining_ping_channel_id is not None:
                alert_ch = bot.get_channel(cfg.mining_ping_channel_id)
                if alert_ch is None:
                    try:
                        fetched = await bot.fetch_channel(cfg.mining_ping_channel_id)
                        if isinstance(fetched, (discord.TextChannel, discord.Thread)):
                            alert_ch = fetched
                    except Exception:
                        alert_ch = None
                if alert_ch is not None:
                    try:
                        await _send_mining_channel_here_ping(
                            alert_ch,
                            belt_type=timer.belt_type,
                            system_name=timer.system_name,
                            when_utc=timer.respawn_dt,
                            ping_here=cfg.mining_ping_here,
                        )
                    except Exception:
                        pass

    @timer_loop.before_loop
    async def before_timer_loop() -> None:
        await bot.wait_until_ready()

    _MOON_PING_ALLOWED = discord.AllowedMentions(everyone=True)

    @tasks.loop(seconds=max(120, cfg.moon_timers_poll_seconds))
    async def moon_timers_loop() -> None:
        if not cfg.moon_timers_csv_url:
            return
        notify_user: discord.User | None = None
        uid = cfg.moon_timers_notify_user_id
        if uid is not None:
            notify_user = bot.get_user(uid)
            if notify_user is None:
                try:
                    notify_user = await bot.fetch_user(uid)
                except Exception:
                    print(f"Moon timers: could not fetch notify user id {uid}")
                    notify_user = None

        ch: discord.TextChannel | discord.Thread | None = None
        if cfg.moon_timers_channel_id is not None:
            raw_ch = bot.get_channel(int(cfg.moon_timers_channel_id))
            if isinstance(raw_ch, (discord.TextChannel, discord.Thread)):
                ch = raw_ch

        if notify_user is None and ch is None:
            return
        now = datetime.now(UTC)
        await moon_ping_store.prune(now)
        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(cfg.moon_timers_csv_url) as resp:
                    if resp.status != 200:
                        print(f"Moon timers CSV HTTP {resp.status}")
                        return
                    raw = await resp.text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            print(f"Moon timers CSV fetch failed: {exc}")
            return
        head = raw[:800].lstrip().lower()
        if head.startswith("<!doctype") or head.startswith("<html"):
            print("Moon timers: response looks like HTML (publish sheet or fix EVE_MOON_TIMERS_CSV_URL).")
            return
        try:
            events = _moon_rows_from_sheet_csv(raw, now)
        except Exception as exc:
            print(f"Moon timers CSV parse failed: {exc}")
            return
        lead = timedelta(minutes=cfg.moon_timers_lead_minutes)
        slack = timedelta(minutes=25)
        channel_mentions = (
            _MOON_PING_ALLOWED if cfg.moon_timers_ping_here else discord.AllowedMentions(everyone=False)
        )
        sheet_link = f"https://docs.google.com/spreadsheets/d/{MOON_TIMERS_SPREADSHEET_ID}/edit"
        for moon, when in events:
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            else:
                when = when.astimezone(UTC)
            if when < now - timedelta(minutes=10):
                continue
            if not ((when - lead) <= now < when + slack):
                continue
            key = _moon_event_key(moon, when)
            if not await moon_ping_store.should_send(key):
                continue
            body = (
                f"**Moon timer** — {moon}\n"
                f"Next: {_format_eve_time(when)} | {_format_local_time(when)}\n"
                f"_([Moon Timers sheet]({sheet_link}))_"
            )
            prefix_ch = "@here\n" if (ch is not None and cfg.moon_timers_ping_here) else ""
            msg_ch = f"{prefix_ch}{body}"
            msg_dm = body
            any_ok = False
            if notify_user is not None:
                try:
                    await notify_user.send(msg_dm)
                    any_ok = True
                except Exception as exc:
                    print(f"Moon timers DM failed: {exc}")
            if ch is not None:
                try:
                    await ch.send(msg_ch, allowed_mentions=channel_mentions)
                    any_ok = True
                except discord.Forbidden:
                    print("Moon timers: bot cannot post in configured channel (or missing @here permission).")
                except Exception as exc:
                    print(f"Moon timers channel post failed: {exc}")
            if any_ok:
                await moon_ping_store.mark(key, now)

    @moon_timers_loop.before_loop
    async def before_moon_timers_loop() -> None:
        await bot.wait_until_ready()

    @bot.tree.command(name="help", description="Command list and Discord invite (ephemeral).")
    async def slash_help(interaction: discord.Interaction) -> None:
        text = (
            f"**{cfg.product_display_name} Discord:** {cfg.discord_invite_url}\n\n"
            "**Slash commands**\n"
            "`/help` — this list\n"
            "`/about` — credits + invite\n"
            "`/admin notes` — operator manual; `/admin restart` & `/admin rebuild` if Docker is configured\n"
            "`/miner timer` — ore anomaly timer (**pop** time, UTC)\n"
            "`/miner respawns` — timers in ±10h window\n"
            "`/srp` `/auth` `/mumble` `/intel` `/buyback` — quick links / guides\n\n"
            "_Slash replies are **ephemeral** (only you see them in this channel)._"
        )
        await _defer_ephemeral_followups(interaction, [text])

    @bot.tree.command(name="about", description="Credits and Discord invite (ephemeral).")
    async def slash_about(interaction: discord.Interaction) -> None:
        text = (
            "Created by **Sevey**.\n"
            f"**{cfg.product_display_name} Discord:** {cfg.discord_invite_url}"
        )
        await _defer_ephemeral_followups(interaction, [text])

    @bot.tree.command(name="srp", description="WOMP SRP link (ephemeral).")
    async def slash_srp(interaction: discord.Interaction) -> None:
        await _defer_ephemeral_followups(
            interaction,
            ["WOMP SRP Link https://auth.wompa.space/ship-replacement/"],
        )

    @bot.tree.command(name="auth", description="Alliance auth links (ephemeral).")
    async def slash_auth(interaction: discord.Interaction) -> None:
        await _defer_ephemeral_followups(
            interaction,
            [
                "WOMP Alliance Auth: https://auth.wompa.space/ — False Gods SEAT: https://seat.false-gods.space/home"
            ],
        )

    @bot.tree.command(name="mumble", description="Mumble + auth setup guide (ephemeral; optional GIF).")
    async def slash_mumble(interaction: discord.Interaction) -> None:
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
        fobj: discord.File | None = None
        if img_path and Path(img_path).exists():
            fobj = discord.File(img_path)
        elif img_path:
            print(f"/mumble: image path not found: {img_path}")
        await _defer_ephemeral_followups(interaction, [msg], first_message_file=fobj)

    @bot.tree.command(name="intel", description="Intel channel guide link (ephemeral).")
    async def slash_intel(interaction: discord.Interaction) -> None:
        await _defer_ephemeral_followups(
            interaction,
            [
                "See this post for the intel channel & fleet reporting guide "
                "https://discord.com/channels/1446458381945667586/1492283337186738286"
            ],
        )

    @bot.tree.command(name="buyback", description="False Gods buyback link (ephemeral).")
    async def slash_buyback(interaction: discord.Interaction) -> None:
        await _defer_ephemeral_followups(
            interaction,
            [
                "False Gods buyback: https://discord.com/channels/1446458381945667586/1494398530239074486"
            ],
        )

    def _slash_admin_allowed(member: discord.Member) -> bool:
        if cfg.discord_admin_user_ids:
            return member.id in cfg.discord_admin_user_ids
        return bool(member.guild_permissions.administrator)

    def _docker_compose_ready() -> bool:
        return bool(
            cfg.docker_admin_enabled
            and cfg.docker_compose_workdir is not None
            and cfg.docker_compose_workdir.is_dir()
            and (cfg.docker_compose_service or "").strip()
        )

    def _compose_base_cmd() -> list[str]:
        cmd: list[str] = ["docker", "compose"]
        cf = cfg.docker_compose_file
        if cf:
            p = Path(cf)
            if not p.is_absolute():
                base = cfg.docker_compose_workdir
                p = (base / p).resolve() if base is not None else p.resolve()
            else:
                p = p.resolve()
            cmd.extend(["-f", str(p)])
        return cmd

    async def _admin_must_be_operator(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        m = interaction.user
        if not isinstance(m, discord.Member):
            await interaction.response.send_message(
                "Could not resolve your server membership; run this from a channel in this server.",
                ephemeral=True,
            )
            return False
        if not _slash_admin_allowed(m):
            await interaction.response.send_message(
                "You don’t have permission to use `/admin`. "
                "Requires **Administrator**, or your user id in **`EVE_DISCORD_ADMIN_USER_IDS`** in the bot `.env`. "
                "A server admin may need to allow this command under **Server Settings → Integrations**.",
                ephemeral=True,
            )
            return False
        return True

    async def _admin_reply_compose_result(
        interaction: discord.Interaction,
        *,
        title: str,
        code: int,
        stdout: str,
        stderr: str,
    ) -> None:
        blob = f"{stdout}\n{stderr}".strip() or "(no output)"
        if len(blob) > 1700:
            blob = "…(truncated)\n" + blob[-1700:]
        inner = f"{title} — exit **{code}**\n```\n{blob}\n```"
        if len(inner) > 1950:
            inner = inner[:1940] + "\n```"
        tail = (
            "\n_If this service is the bot container, Discord may disconnect before you see this; "
            "check `docker compose logs`._"
        )
        msg = inner + tail
        if len(msg) > 2000:
            msg = msg[:1997] + "…"
        await interaction.followup.send(msg, ephemeral=True)

    async def _run_compose_restart() -> tuple[int, str, str]:
        assert cfg.docker_compose_workdir is not None
        assert cfg.docker_compose_service is not None
        svc = cfg.docker_compose_service.strip()
        wd = str(cfg.docker_compose_workdir)
        full = _compose_base_cmd() + ["restart", svc]

        def sync_run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                full,
                cwd=wd,
                capture_output=True,
                text=True,
                timeout=cfg.docker_compose_timeout_sec,
                shell=False,
            )

        try:
            proc = await asyncio.to_thread(sync_run)
            return proc.returncode, proc.stdout or "", proc.stderr or ""
        except FileNotFoundError:
            return 127, "", "docker: executable not found in PATH"
        except subprocess.TimeoutExpired:
            return 124, "", "docker compose restart exceeded EVE_DOCKER_COMPOSE_TIMEOUT_SEC"

    async def _run_compose_rebuild() -> tuple[int, str, str]:
        assert cfg.docker_compose_workdir is not None
        assert cfg.docker_compose_service is not None
        svc = cfg.docker_compose_service.strip()
        wd = str(cfg.docker_compose_workdir)
        base = _compose_base_cmd()

        def sync_rebuild() -> tuple[int, str, str]:
            r1 = subprocess.run(
                base + ["build", "--no-cache", svc],
                cwd=wd,
                capture_output=True,
                text=True,
                timeout=cfg.docker_compose_timeout_sec,
                shell=False,
            )
            o1, e1 = r1.stdout or "", r1.stderr or ""
            if r1.returncode != 0:
                return r1.returncode, o1, e1
            r2 = subprocess.run(
                base + ["up", "-d", svc],
                cwd=wd,
                capture_output=True,
                text=True,
                timeout=min(300, cfg.docker_compose_timeout_sec),
                shell=False,
            )
            return r2.returncode, o1 + (r2.stdout or ""), e1 + (r2.stderr or "")

        try:
            return await asyncio.to_thread(sync_rebuild)
        except FileNotFoundError:
            return 127, "", "docker: executable not found in PATH"
        except subprocess.TimeoutExpired:
            return 124, "", "docker compose build/up exceeded EVE_DOCKER_COMPOSE_TIMEOUT_SEC"

    admin_group = app_commands.Group(
        name="admin",
        description="Operator notes and optional Docker Compose restart/rebuild (restricted).",
    )

    @admin_group.command(name="notes", description="Manual restart/rebuild instructions (ephemeral).")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def admin_notes(interaction: discord.Interaction) -> None:
        if not await _admin_must_be_operator(interaction):
            return
        bot_py = Path(__file__).resolve()
        bot_dir = bot_py.parent
        part_a = (
            "**Bot operator — manual restart / rebuild**\n\n"
            "If Docker is configured in `.env`, use **`/admin restart`** or **`/admin rebuild`**.\n\n"
            f"**Bot directory:** `{bot_dir}`\n"
            f"**Script:** `{bot_py.name}`\n\n"
            "**Bare Python (venv)**\n"
            "1. Stop the bot (**Ctrl+C** or stop the service).\n"
            "2. `cd` to the folder with `eve_mining_timer_bot.py` and `.env`.\n"
            "3. Optional: `pip install -r ../requirements.txt` (or `..\\\\requirements.txt` on Windows).\n"
            "4. Start: `python eve_mining_timer_bot.py`\n\n"
            "**Docker Compose (manual)**\n"
            "`docker compose restart <service>`\n"
            "`docker compose build --no-cache <service> && docker compose up -d <service>`\n\n"
            "**systemd**\n"
            "`sudo systemctl restart <your-unit>`\n"
        )
        part_b = (
            "For slash-triggered Compose: `EVE_DOCKER_ADMIN_ENABLED=1`, `EVE_DOCKER_COMPOSE_DIR`, "
            "`EVE_DOCKER_COMPOSE_SERVICE` (optional `EVE_DOCKER_COMPOSE_FILE`, `EVE_DOCKER_COMPOSE_TIMEOUT_SEC`). "
            "The host needs `docker` on PATH with permission to manage that compose project.\n"
            "**Slash sync:** set `EVE_DISCORD_GUILD_ID` for faster guild sync during development (see `example.env`)."
        )
        await _defer_ephemeral_followups(interaction, [part_a, part_b])

    @admin_group.command(
        name="restart",
        description="Runs docker compose restart for EVE_DOCKER_COMPOSE_SERVICE (env-gated).",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def admin_restart(interaction: discord.Interaction) -> None:
        if not await _admin_must_be_operator(interaction):
            return
        if not _docker_compose_ready():
            await interaction.response.send_message(
                "Docker Compose is not enabled or `.env` is incomplete. Set **`EVE_DOCKER_ADMIN_ENABLED=1`**, "
                "**`EVE_DOCKER_COMPOSE_DIR`** (directory that contains your compose project), and "
                "**`EVE_DOCKER_COMPOSE_SERVICE`**. See **`example.env`**.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            code, out, err = await _run_compose_restart()
        except Exception as exc:
            await interaction.followup.send(f"`docker compose restart` failed: `{exc!r}`", ephemeral=True)
            return
        await _admin_reply_compose_result(
            interaction, title="docker compose restart", code=code, stdout=out, stderr=err
        )

    @admin_group.command(
        name="rebuild",
        description="docker compose build --no-cache then up -d (env-gated; may take minutes).",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def admin_rebuild(interaction: discord.Interaction) -> None:
        if not await _admin_must_be_operator(interaction):
            return
        if not _docker_compose_ready():
            await interaction.response.send_message(
                "Docker Compose is not enabled or `.env` is incomplete. Set **`EVE_DOCKER_ADMIN_ENABLED=1`**, "
                "**`EVE_DOCKER_COMPOSE_DIR`**, and **`EVE_DOCKER_COMPOSE_SERVICE`**. See **`example.env`**.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            code, out, err = await _run_compose_rebuild()
        except Exception as exc:
            await interaction.followup.send(f"`docker compose` rebuild failed: `{exc!r}`", ephemeral=True)
            return
        await _admin_reply_compose_result(
            interaction, title="docker compose build && up -d", code=code, stdout=out, stderr=err
        )

    miner_group = app_commands.Group(name="miner", description=cfg.miner_slash_group_description)

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
            (f"Belt popped ~now — {full} UTC", full),
            (f"Belt popped today — {hm} UTC (same calendar day)", hm),
            (f"Belt popped ~15m ago — {soon} UTC", soon),
            (f"Belt popped ~1h ago — {plus1h} UTC", plus1h),
            (f"Belt popped ~2h ago — {plus2h} UTC", plus2h),
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

    @miner_group.command(
        name="timer",
        description="Ore anomaly respawn from pop time (duration inferred from anomaly name).",
    )
    @app_commands.describe(
        system_name="System name, e.g. Jita",
        belt_type='EVE cosmic anomaly name, e.g. "Type C Mercoxit Belt" or "Large Mercoxit Deposit"',
        eve_time="UTC/EVE when the belt was popped (cleared): HH:MM or YYYY-MM-DD HH:MM",
    )
    async def miner_timer(
        interaction: discord.Interaction,
        system_name: str,
        belt_type: str,
        eve_time: str,
    ) -> None:
        await register_timer_slash(interaction, system_name, belt_type, eve_time)

    @miner_group.command(
        name="respawns",
        description="List anomaly timers that respawned in the last 10h or will respawn in the next 10h (EVE/UTC).",
    )
    async def miner_respawns(interaction: discord.Interaction) -> None:
        parts = await _miner_respawns_message_parts()
        if len(parts) > 10:
            parts = parts[:10] + [f"_…and {len(parts) - 10} more chunk(s) omitted._"]
        await _defer_ephemeral_followups(interaction, parts)

    miner_timer.autocomplete("eve_time")(autocomplete_eve_time)
    miner_timer.autocomplete("system_name")(autocomplete_system_name)
    miner_timer.autocomplete("belt_type")(autocomplete_anom_type)

    bot.tree.add_command(admin_group)
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
        except discord.PrivilegedIntentsRequired as exc:
            print(
                f"Discord PrivilegedIntentsRequired (attempt {attempt}): {exc}\n"
                "This build does not require Message Content intent. If you still see this, "
                "check the Developer Portal (Bot → Privileged Gateway Intents) and restart. Waiting before retry..."
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
