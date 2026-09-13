"""Combined awesome-eve style tools — live ESI / zKill / market / audit DB only."""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.character_skills import CharacterSkillLevel
from app.models.tools import SdeTypeIndex
from app.services.market_prices import hub_prices_for_types
from app.services.zkill import fetch_character_stats

logger = logging.getLogger(__name__)

_ESI = (settings.esi_base_url or "https://esi.evetech.net/latest").rstrip("/")
_UA = "EVE-EMU-EMUMS/1.0 (+https://emums.eve-emu.com; awesome-suite)"
_ZKB = (settings.zkill_base_url or "https://zkillboard.com/api").rstrip("/")

# Catalog of awesome-eve categories mapped to EMUMS windows (combined features).
AWESOME_CATALOG: list[dict[str, Any]] = [
    {
        "category": "Intel",
        "sources": ["PySpy", "Eve411", "Eve Squadron", "RIFT", "EveWho"],
        "window_id": "suite-intel",
        "label": "Intel Paste",
        "description": "Paste local / D-scan / pilot lists — ESI affiliations + zKill stats.",
    },
    {
        "category": "Market",
        "sources": ["EVE Trade", "EveMarketTool", "Priceall", "Adam4EVE", "EVE Tycoon"],
        "window_id": "suite-trade",
        "label": "Trade Margins",
        "description": "Hub buy/sell spreads and haul margins from live market data.",
    },
    {
        "category": "Manufacturing",
        "sources": ["Eve Cost", "EVE Cookbook", "EVE Guru", "Fuzzworks", "ISK Per Hour"],
        "window_id": "ip-planner",
        "label": "Build Planner",
        "description": "Production plans, warehouse stock, max stock, Janice pricing.",
    },
    {
        "category": "Maps",
        "sources": ["Dotlan", "EVE Route", "Eveeye", "Eden Navigator"],
        "window_id": "map-visual",
        "label": "Route & Jump Map",
        "description": "Stargate routes, jump range, bookmarks.",
    },
    {
        "category": "Wormholes",
        "sources": ["Pathfinder", "anoik.is", "GalaxyFinder", "EVEMetro"],
        "window_id": "wh-map",
        "label": "Wormhole Map",
        "description": "Chain mapping and WH intel.",
    },
    {
        "category": "Killboards",
        "sources": ["zKillboard", "brcat", "EVE-KILL"],
        "window_id": "suite-br",
        "label": "Battle Report",
        "description": "System kill aggregation and battle reports from zKill.",
    },
    {
        "category": "Character",
        "sources": ["Cerebral", "EveMonk", "SkillQ", "EVE Buddy"],
        "window_id": "char-audit",
        "label": "Character Audit",
        "description": "Skills, assets, wallet, mail, contracts — ESI synced.",
    },
    {
        "category": "Fitting",
        "sources": ["Pyfa", "EVEShip.fit", "Theorycrafter"],
        "window_id": "ip-planner",
        "label": "Fittings & Builds",
        "description": "Doctrine fittings and build cost from live assets.",
    },
    {
        "category": "PI",
        "sources": ["Adam4EVE PI", "EVE-PI"],
        "window_id": "pi-overview",
        "label": "Planetary Interaction",
        "description": "Colony overview from ESI PI scopes.",
    },
    {
        "category": "SRP",
        "sources": ["EVE-SRP", "EVE SRP mail"],
        "window_id": "srp-program",
        "label": "SRP Program",
        "description": "Ship replacement claims and payouts.",
    },
    {
        "category": "Corp / Alliance",
        "sources": ["SeAT", "Seatplus", "EveWho", "Eve-HR"],
        "window_id": "suite-corpwho",
        "label": "Corp Who",
        "description": "Live corp roster via ESI + auth linkage flags.",
    },
    {
        "category": "Skills",
        "sources": ["SkillQ", "EVE-Skillplan.net"],
        "window_id": "suite-skills",
        "label": "Skill Queues",
        "description": "Roster skill levels from audit DB.",
    },
    {
        "category": "Reference",
        "sources": ["EVE Ref", "Fuzzworks", "Hoboleaks"],
        "window_id": "sde-browser",
        "label": "Knowledge & SDE",
        "description": "Item database and wiki-linked reference.",
    },
    {
        "category": "Route Intel",
        "sources": ["Eve Gate Camp Check", "Eden Navigator", "Dotlan"],
        "window_id": "suite-gatecamp",
        "label": "Gate Camp Route",
        "description": "Plan a route and flag systems with recent zKill activity.",
    },
    {
        "category": "Hauling",
        "sources": ["EVE Trade", "Adam4EVE", "Venal"],
        "window_id": "suite-haul",
        "label": "Haul Finder",
        "description": "Cross-hub buy-low / sell-high opportunities from live prices.",
    },
    {
        "category": "Structures",
        "sources": ["Upwell.gg", "SeAT structures", "AVRSE"],
        "window_id": "suite-structures",
        "label": "Structure Board",
        "description": "Authed structures with market / reprocessing from ESI sync.",
    },
    {
        "category": "Fitting",
        "sources": ["Pyfa", "Theorycrafter", "EVEShip.fit"],
        "window_id": "suite-ships",
        "label": "Ship Compare",
        "description": "Side-by-side hull stats from ESI dogma attributes.",
    },
    {
        "category": "Market",
        "sources": ["Eve Insurance Fraud", "Adam4EVE"],
        "window_id": "suite-insurance",
        "label": "Insurance Check",
        "description": "Hull sell price vs platinum insurance payout.",
    },
]


def catalog() -> dict[str, Any]:
    return {
        "source": "https://github.com/devfleet/awesome-eve",
        "note": "Features combined and expanded inside EMUMS using ESI, zKill, Janice, and audit DB — no static demo rows.",
        "tools": AWESOME_CATALOG,
    }


def _parse_paste_lines(text: str) -> list[str]:
    names: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # D-scan: "Name\tType\tDistance" or "Name\tDistance"
        if "\t" in line:
            line = line.split("\t", 1)[0].strip()
        # Local often has just names
        line = re.sub(r"\s+\d+(\.\d+)?\s*(km|m|AU)\s*$", "", line, flags=re.I).strip()
        if line and line not in names:
            names.append(line)
        if len(names) >= 80:
            break
    return names


async def _esi_post(path: str, body: Any) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{_ESI}{path}",
            json=body,
            headers={"User-Agent": _UA, "Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def _esi_get(path: str) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{_ESI}{path}",
            headers={"User-Agent": _UA, "Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def resolve_names(names: list[str]) -> list[dict[str, Any]]:
    """POST /universe/ids/ then affiliations for characters."""
    if not names:
        return []
    payload = await _esi_post("/universe/ids/", names[:80])
    if not isinstance(payload, dict):
        return [{"name": n, "category": "unknown"} for n in names]

    chars = payload.get("characters") or []
    corps = payload.get("corporations") or []
    alliances = payload.get("alliances") or []
    systems = payload.get("systems") or []
    inventory = payload.get("inventory_types") or []

    by_name: dict[str, dict[str, Any]] = {}
    for row in chars:
        by_name[str(row.get("name") or "")] = {
            "name": row.get("name"),
            "category": "character",
            "id": int(row.get("id") or 0),
        }
    for row in corps:
        by_name[str(row.get("name") or "")] = {
            "name": row.get("name"),
            "category": "corporation",
            "id": int(row.get("id") or 0),
        }
    for row in alliances:
        by_name[str(row.get("name") or "")] = {
            "name": row.get("name"),
            "category": "alliance",
            "id": int(row.get("id") or 0),
        }
    for row in systems:
        by_name[str(row.get("name") or "")] = {
            "name": row.get("name"),
            "category": "system",
            "id": int(row.get("id") or 0),
        }
    for row in inventory:
        by_name[str(row.get("name") or "")] = {
            "name": row.get("name"),
            "category": "type",
            "id": int(row.get("id") or 0),
        }

    char_ids = [r["id"] for r in by_name.values() if r.get("category") == "character" and r.get("id")]
    aff_map: dict[int, dict[str, Any]] = {}
    if char_ids:
        affs = await _esi_post("/characters/affiliation/", char_ids)
        if isinstance(affs, list):
            for a in affs:
                if isinstance(a, dict) and a.get("character_id"):
                    aff_map[int(a["character_id"])] = a

    # Resolve corp/alliance names for affiliations
    corp_ids = {int(a.get("corporation_id") or 0) for a in aff_map.values() if a.get("corporation_id")}
    alli_ids = {int(a.get("alliance_id") or 0) for a in aff_map.values() if a.get("alliance_id")}
    name_map: dict[int, str] = {}
    id_list = [i for i in (corp_ids | alli_ids) if i > 0]
    for offset in range(0, len(id_list), 1000):
        chunk = id_list[offset : offset + 1000]
        named = await _esi_post("/universe/names/", chunk)
        if isinstance(named, list):
            for row in named:
                if isinstance(row, dict) and row.get("id"):
                    name_map[int(row["id"])] = str(row.get("name") or "")

    out: list[dict[str, Any]] = []
    for n in names:
        hit = by_name.get(n) or {"name": n, "category": "unknown", "id": 0}
        if hit.get("category") == "character" and hit.get("id"):
            aff = aff_map.get(int(hit["id"]), {})
            corp_id = int(aff.get("corporation_id") or 0)
            alli_id = int(aff.get("alliance_id") or 0)
            hit["corporation_id"] = corp_id or None
            hit["corporation_name"] = name_map.get(corp_id, "")
            hit["alliance_id"] = alli_id or None
            hit["alliance_name"] = name_map.get(alli_id, "")
        out.append(hit)
    return out


async def intel_paste(text: str, *, with_zkill: bool = True) -> dict[str, Any]:
    names = _parse_paste_lines(text)
    resolved = await resolve_names(names)
    characters = [r for r in resolved if r.get("category") == "character"]
    types = [r for r in resolved if r.get("category") == "type"]
    systems = [r for r in resolved if r.get("category") == "system"]
    unknown = [r for r in resolved if r.get("category") == "unknown"]

    if with_zkill and characters:
        stats = await asyncio.gather(
            *[fetch_character_stats(int(c["id"])) for c in characters[:40]],
            return_exceptions=True,
        )
        for c, st in zip(characters, stats):
            if isinstance(st, dict) and not st.get("error"):
                c["zkill"] = {
                    "ships_destroyed": st.get("ships_destroyed", 0),
                    "ships_lost": st.get("ships_lost", 0),
                    "isk_destroyed": st.get("isk_destroyed", 0),
                    "isk_lost": st.get("isk_lost", 0),
                    "url": f"https://zkillboard.com/character/{c['id']}/",
                }
            else:
                c["zkill"] = None

    corps = Counter(
        (c.get("corporation_name") or f"corp:{c.get('corporation_id')}")
        for c in characters
        if c.get("corporation_id")
    )
    return {
        "input_lines": len(names),
        "characters": characters,
        "types": types,
        "systems": systems,
        "unknown": unknown,
        "corp_breakdown": [{"name": k, "count": v} for k, v in corps.most_common(20)],
        "summary": {
            "characters": len(characters),
            "types": len(types),
            "systems": len(systems),
            "unknown": len(unknown),
        },
    }


async def trade_margins(
    session: AsyncSession,
    *,
    text: str = "",
    type_ids: list[int] | None = None,
    hub: str = "jita",
    limit: int = 40,
) -> dict[str, Any]:
    ids: set[int] = set(int(t) for t in (type_ids or []) if int(t) > 0)
    if text.strip():
        names = _parse_paste_lines(text)
        resolved = await resolve_names(names)
        for r in resolved:
            if r.get("category") == "type" and r.get("id"):
                ids.add(int(r["id"]))

    if not ids:
        # Sample tradeable types from SDE index (live DB, not static fixtures).
        rows = (
            await session.scalars(
                select(SdeTypeIndex)
                .where(SdeTypeIndex.base_price > 0)
                .order_by(SdeTypeIndex.type_id)
                .limit(limit)
            )
        ).all()
        ids = {int(r.type_id) for r in rows}

    ids = set(list(ids)[:limit])
    prices, source = await hub_prices_for_types(session, ids, hub=hub)
    names_map: dict[int, str] = {}
    if ids:
        for r in (
            await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(ids)))
        ).all():
            names_map[int(r.type_id)] = r.name

    lines: list[dict[str, Any]] = []
    for tid in ids:
        p = prices.get(tid) or {}
        buy = p.get("buy")
        sell = p.get("sell")
        if buy is None and sell is None:
            continue
        buy_f = float(buy or 0)
        sell_f = float(sell or 0)
        spread = sell_f - buy_f if sell_f and buy_f else 0.0
        margin_pct = (spread / buy_f * 100.0) if buy_f > 0 else 0.0
        lines.append(
            {
                "type_id": tid,
                "name": names_map.get(tid, f"Type {tid}"),
                "buy": buy_f,
                "sell": sell_f,
                "spread": spread,
                "margin_pct": round(margin_pct, 2),
            }
        )
    lines.sort(key=lambda r: r["margin_pct"], reverse=True)
    return {"hub": hub, "pricing_source": source, "lines": lines}


async def corp_who(corporation_id: int | None = None, corporation_name: str = "") -> dict[str, Any]:
    corp_id = int(corporation_id or 0)
    if not corp_id and corporation_name.strip():
        resolved = await resolve_names([corporation_name.strip()])
        for r in resolved:
            if r.get("category") == "corporation" and r.get("id"):
                corp_id = int(r["id"])
                break
    if corp_id <= 0:
        return {"error": "corporation_not_found"}

    info = await _esi_get(f"/corporations/{corp_id}/")
    if not isinstance(info, dict):
        return {"error": "esi_corporation_failed", "corporation_id": corp_id}

    # Public member list requires a corp token; use zKill / ESI public corp info only.
    # Member IDs: try ESI corporation members (needs auth) — fall back to empty + info.
    members_raw = await _esi_get(f"/corporations/{corp_id}/members/")
    member_ids: list[int] = []
    if isinstance(members_raw, list):
        member_ids = [int(x) for x in members_raw if int(x) > 0]

    member_names: dict[int, str] = {}
    for offset in range(0, len(member_ids), 1000):
        chunk = member_ids[offset : offset + 1000]
        named = await _esi_post("/universe/names/", chunk)
        if isinstance(named, list):
            for row in named:
                if isinstance(row, dict) and row.get("id"):
                    member_names[int(row["id"])] = str(row.get("name") or "")

    members = [
        {
            "character_id": cid,
            "character_name": member_names.get(cid, f"Character {cid}"),
            "zkill_url": f"https://zkillboard.com/character/{cid}/",
        }
        for cid in sorted(member_ids, key=lambda i: member_names.get(i, "").lower())
    ]

    return {
        "corporation_id": corp_id,
        "corporation_name": info.get("name") or "",
        "ticker": info.get("ticker") or "",
        "member_count": info.get("member_count") or len(members),
        "alliance_id": info.get("alliance_id"),
        "ceo_id": info.get("ceo_id"),
        "members": members,
        "members_public": bool(members),
        "note": (
            None
            if members
            else "Member list requires a corporation membership ESI token; showing public corp info only."
        ),
    }


async def battle_report(system_id: int, *, limit: int = 50) -> dict[str, Any]:
    """Aggregate recent kills in a system from zKill (brcat-style)."""
    url = f"{_ZKB}/kills/solarSystemID/{int(system_id)}/"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip"})
            rows = resp.json() if resp.status_code == 200 else []
        except Exception:
            logger.exception("battle report zkill failed")
            rows = []

    kills: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            km_id = int(row.get("killmail_id") or 0)
            zkb = row.get("zkb") if isinstance(row.get("zkb"), dict) else {}
            victim = row.get("victim") if isinstance(row.get("victim"), dict) else {}
            kills.append(
                {
                    "killmail_id": km_id,
                    "total_value": float(zkb.get("totalValue") or 0),
                    "victim_character_id": int(victim.get("character_id") or 0) or None,
                    "victim_corporation_id": int(victim.get("corporation_id") or 0) or None,
                    "ship_type_id": int(victim.get("ship_type_id") or 0) or None,
                    "zkill_url": f"https://zkillboard.com/kill/{km_id}/",
                    "killmail_time": row.get("killmail_time"),
                }
            )

    total_isk = sum(k["total_value"] for k in kills)
    corps = Counter(k["victim_corporation_id"] for k in kills if k.get("victim_corporation_id"))
    return {
        "system_id": system_id,
        "kill_count": len(kills),
        "total_isk": total_isk,
        "victim_corps": [{"corporation_id": k, "losses": v} for k, v in corps.most_common(15)],
        "kills": kills,
    }


async def roster_skill_snapshot(
    session: AsyncSession, character_ids: list[int]
) -> dict[str, Any]:
    if not character_ids:
        return {"characters": []}
    rows = (
        await session.scalars(
            select(CharacterSkillLevel).where(
                CharacterSkillLevel.character_id.in_(character_ids)
            )
        )
    ).all()
    by_char: dict[int, list[dict[str, Any]]] = {}
    names: dict[int, str] = {}
    for r in rows:
        names[int(r.character_id)] = r.character_name or ""
        by_char.setdefault(int(r.character_id), []).append(
            {
                "skill_id": int(r.skill_type_id),
                "skill_name": r.skill_name,
                "trained_level": int(r.trained_level or 0),
                "skillpoints": int(r.skillpoints_in_skill or 0),
            }
        )
    characters = []
    for cid in character_ids:
        skills = by_char.get(cid, [])
        characters.append(
            {
                "character_id": cid,
                "character_name": names.get(cid, ""),
                "skill_count": len(skills),
                "total_sp": sum(s["skillpoints"] for s in skills),
                "skills": sorted(skills, key=lambda s: (-s["trained_level"], s["skill_name"]))[:50],
            }
        )
    return {"characters": characters}


# --- Pass expansions ---


async def _zkill_system_kill_count(system_id: int) -> dict[str, Any]:
    url = f"{_ZKB}/stats/solarSystemID/{int(system_id)}/"
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.get(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip"})
            if resp.status_code != 200:
                return {"system_id": system_id, "ships_destroyed": 0, "isk_destroyed": 0}
            data = resp.json()
        except Exception:
            return {"system_id": system_id, "ships_destroyed": 0, "isk_destroyed": 0}
    return {
        "system_id": system_id,
        "ships_destroyed": int(data.get("shipsDestroyed") or 0),
        "isk_destroyed": float(data.get("iskDestroyed") or 0),
    }


async def gate_camp_route(
    session: AsyncSession,
    *,
    origin_system_id: int,
    destination_system_id: int,
    avoid_low_sec: bool = False,
) -> dict[str, Any]:
    """Route plan + per-system zKill heat (Gate Camp Check / Eden Navigator)."""
    from app.services.route_planner import plan_route

    route = await plan_route(
        session,
        origin_system_id=origin_system_id,
        destination_system_id=destination_system_id,
        avoid_low_sec=avoid_low_sec,
    )
    if route.get("error"):
        return route

    systems = route.get("systems") or []
    stats = await asyncio.gather(
        *[_zkill_system_kill_count(int(s["system_id"])) for s in systems],
        return_exceptions=True,
    )
    hot: list[dict[str, Any]] = []
    for sys, st in zip(systems, stats):
        if not isinstance(st, dict):
            st = {"ships_destroyed": 0, "isk_destroyed": 0}
        ships = int(st.get("ships_destroyed") or 0)
        isk = float(st.get("isk_destroyed") or 0)
        heat = "hot" if ships >= 50 or isk >= 5_000_000_000 else ("warm" if ships >= 10 else "cold")
        entry = {
            **sys,
            "ships_destroyed": ships,
            "isk_destroyed": isk,
            "heat": heat,
            "zkill_url": f"https://zkillboard.com/system/{sys['system_id']}/",
        }
        hot.append(entry)

    return {
        "jumps": route.get("jumps", 0),
        "route": route.get("route", []),
        "systems": hot,
        "hot_systems": [s for s in hot if s["heat"] in ("hot", "warm")],
    }


async def haul_finder(
    session: AsyncSession,
    *,
    text: str = "",
    buy_hub: str = "jita",
    sell_hub: str = "amarr",
    limit: int = 30,
    min_margin_pct: float = 5.0,
) -> dict[str, Any]:
    """Cross-hub haul opportunities (EVE Trade / Adam4EVE style)."""
    buy = await trade_margins(session, text=text, hub=buy_hub, limit=limit * 2)
    sell = await trade_margins(session, text=text, hub=sell_hub, limit=limit * 2)
    buy_map = {int(r["type_id"]): r for r in buy.get("lines") or []}
    sell_map = {int(r["type_id"]): r for r in sell.get("lines") or []}

    opportunities: list[dict[str, Any]] = []
    for tid, b in buy_map.items():
        s = sell_map.get(tid)
        if not s:
            continue
        buy_price = float(b.get("sell") or 0)  # pay sell orders in buy hub
        sell_price = float(s.get("buy") or 0)  # sell to buy orders in sell hub
        if buy_price <= 0 or sell_price <= 0:
            continue
        profit = sell_price - buy_price
        margin = profit / buy_price * 100.0
        if margin < min_margin_pct:
            continue
        opportunities.append(
            {
                "type_id": tid,
                "name": b.get("name") or s.get("name"),
                "buy_hub": buy_hub,
                "sell_hub": sell_hub,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "profit_per_unit": profit,
                "margin_pct": round(margin, 2),
            }
        )
    opportunities.sort(key=lambda r: r["margin_pct"], reverse=True)
    return {
        "buy_hub": buy_hub,
        "sell_hub": sell_hub,
        "min_margin_pct": min_margin_pct,
        "opportunities": opportunities[:limit],
    }


async def structure_board(session: AsyncSession) -> dict[str, Any]:
    """Authed structures board (Upwell / SeAT structures style)."""
    from app.models.tools import AuthedStructure

    rows = (
        await session.scalars(select(AuthedStructure).order_by(AuthedStructure.structure_name))
    ).all()
    structures = [
        {
            "structure_id": int(r.structure_id),
            "structure_name": r.structure_name,
            "system_name": r.system_name,
            "solar_system_id": int(r.solar_system_id or 0) or None,
            "has_market": bool(r.has_market),
            "has_reprocessing": bool(r.has_reprocessing),
            "owner_character_id": int(r.owner_character_id or 0) or None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
    return {
        "count": len(structures),
        "with_market": sum(1 for s in structures if s["has_market"]),
        "with_reprocessing": sum(1 for s in structures if s["has_reprocessing"]),
        "structures": structures,
    }


async def ship_compare(session: AsyncSession, type_a: int, type_b: int) -> dict[str, Any]:
    """Side-by-side hull dogma attributes (Pyfa / Theorycrafter lite)."""
    from app.services.sde_type_detail import get_type_detail

    a, b = await asyncio.gather(get_type_detail(session, type_a), get_type_detail(session, type_b))
    if not a or not b:
        return {"error": "type_not_found"}

    def _attr_map(detail: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        for attr in detail.get("attributes") or []:
            if not isinstance(attr, dict):
                continue
            name = str(attr.get("name") or attr.get("display_name") or "").strip()
            if not name:
                continue
            try:
                out[name] = float(attr.get("value") or 0)
            except (TypeError, ValueError):
                continue
        return out

    attrs_a = _attr_map(a)
    attrs_b = _attr_map(b)
    keys = sorted(set(attrs_a) | set(attrs_b))
    # Prefer combat-relevant attributes first
    priority = (
        "shieldCapacity",
        "armorHP",
        "hp",
        "cpuOutput",
        "powerOutput",
        "speed",
        "maxVelocity",
        "signatureRadius",
        "scanResolution",
        "maxTargetRange",
        "droneBandwidth",
        "droneCapacity",
        "capacitorCapacity",
        "rechargeRate",
    )
    ordered = [k for k in priority if k in keys] + [k for k in keys if k not in priority]

    comparisons = []
    for key in ordered[:40]:
        va = attrs_a.get(key)
        vb = attrs_b.get(key)
        comparisons.append({"attribute": key, "a": va, "b": vb})

    return {
        "a": {
            "type_id": a.get("type_id"),
            "name": a.get("name"),
            "group_name": a.get("group_name"),
            "volume_m3": a.get("volume"),
            "mass": a.get("mass"),
        },
        "b": {
            "type_id": b.get("type_id"),
            "name": b.get("name"),
            "group_name": b.get("group_name"),
            "volume_m3": b.get("volume"),
            "mass": b.get("mass"),
        },
        "comparisons": comparisons,
    }


# Platinum insurance payout ≈ 50% of base price (simplified CCP formula proxy).
_INSURANCE_PLATINUM_FRACTION = 0.5


async def insurance_check(
    session: AsyncSession,
    *,
    text: str = "",
    type_ids: list[int] | None = None,
    hub: str = "jita",
) -> dict[str, Any]:
    """Hull market sell vs platinum insurance payout (Eve Insurance Fraud style)."""
    ids: set[int] = set(int(t) for t in (type_ids or []) if int(t) > 0)
    if text.strip():
        resolved = await resolve_names(_parse_paste_lines(text))
        for r in resolved:
            if r.get("category") == "type" and r.get("id"):
                ids.add(int(r["id"]))
    if not ids:
        rows = (
            await session.scalars(
                select(SdeTypeIndex)
                .where(SdeTypeIndex.category_name == "Ship")
                .where(SdeTypeIndex.base_price > 0)
                .order_by(SdeTypeIndex.base_price.desc())
                .limit(30)
            )
        ).all()
        ids = {int(r.type_id) for r in rows}

    prices, source = await hub_prices_for_types(session, ids, hub=hub)
    type_rows = (
        await session.scalars(select(SdeTypeIndex).where(SdeTypeIndex.type_id.in_(ids)))
    ).all()
    meta = {int(r.type_id): r for r in type_rows}

    lines: list[dict[str, Any]] = []
    for tid in ids:
        row = meta.get(tid)
        if not row:
            continue
        base = float(row.base_price or 0)
        payout = base * _INSURANCE_PLATINUM_FRACTION
        sell = float((prices.get(tid) or {}).get("sell") or 0)
        buy = float((prices.get(tid) or {}).get("buy") or 0)
        # Profit if buy hull on market, insure platinum, destroy: payout - buy_price
        fraud_profit = payout - buy if buy > 0 else payout - sell
        lines.append(
            {
                "type_id": tid,
                "name": row.name,
                "group_name": row.group_name,
                "base_price": base,
                "platinum_payout": payout,
                "market_buy": buy,
                "market_sell": sell,
                "fraud_profit": fraud_profit,
                "worth_insuring": fraud_profit > 0,
            }
        )
    lines.sort(key=lambda r: r["fraud_profit"], reverse=True)
    return {"hub": hub, "pricing_source": source, "lines": lines}
