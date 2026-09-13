"""Moon mining timing — activity windows from live mining logs."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MiningLog

# Typical post-pop mining window used for tax attribution (hours).
DEFAULT_WINDOW_HOURS = 48


async def moon_mining_timing(
    session: AsyncSession,
    *,
    days: int = 45,
    idle_days: int = 7,
) -> dict[str, Any]:
    """Aggregate mining logs into per-structure timing board."""
    days = max(7, min(int(days), 180))
    idle_days = max(1, min(int(idle_days), 60))
    today = date.today()
    since = today - timedelta(days=days)

    rows = (
        await session.scalars(
            select(MiningLog)
            .where(MiningLog.mined_date >= since)
            .order_by(MiningLog.mined_date.desc())
        )
    ).all()

    by_structure: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = (row.structure_name or "Unknown").strip() or "Unknown"
        bucket = by_structure.setdefault(
            name,
            {
                "structure_name": name,
                "system_id": int(row.system_id) if row.system_id else None,
                "days": defaultdict(lambda: {"quantity": 0, "isk_value": 0.0, "characters": set()}),
                "rarities": set(),
                "ore_types": set(),
                "miners": set(),
            },
        )
        day = row.mined_date
        day_bucket = bucket["days"][day]
        day_bucket["quantity"] += int(row.quantity or 0)
        day_bucket["isk_value"] += float(row.isk_value or 0)
        day_bucket["characters"].add(row.character_name or str(row.character_id))
        if row.moon_rarity:
            bucket["rarities"].add(row.moon_rarity)
        if row.type_name:
            bucket["ore_types"].add(row.type_name)
        bucket["miners"].add(row.character_name or str(row.character_id))
        if row.system_id and not bucket["system_id"]:
            bucket["system_id"] = int(row.system_id)

    structures: list[dict[str, Any]] = []
    for name, bucket in by_structure.items():
        day_map: dict[date, dict[str, Any]] = bucket["days"]
        if not day_map:
            continue
        active_days = sorted(day_map.keys(), reverse=True)
        last_day = active_days[0]
        days_since = (today - last_day).days

        # Peak day in window = best proxy for last pop / heavy mining day
        peak_day = max(active_days, key=lambda d: day_map[d]["isk_value"])
        peak = day_map[peak_day]

        # Estimate next quiet: if last activity was within window, mining may still be open
        window_end = last_day + timedelta(hours=DEFAULT_WINDOW_HOURS)  # date-level: +2 days
        # Use calendar days: pop day + 2 days of mining
        estimated_window_end = last_day + timedelta(days=2)
        if days_since <= 2:
            phase = "mining_window"
            phase_label = "Active mining window"
        elif days_since <= idle_days:
            phase = "recent"
            phase_label = "Recently mined"
        else:
            phase = "idle"
            phase_label = "Idle — awaiting next pop"

        # Simple cadence: median gap between active days
        gaps: list[int] = []
        ordered = sorted(active_days)
        for i in range(1, len(ordered)):
            gaps.append((ordered[i] - ordered[i - 1]).days)
        median_gap = sorted(gaps)[len(gaps) // 2] if gaps else None
        next_estimate = None
        if median_gap and median_gap >= 3:
            next_estimate = (last_day + timedelta(days=median_gap)).isoformat()

        last_7 = [d for d in active_days if (today - d).days <= 7]
        last_30 = [d for d in active_days if (today - d).days <= 30]

        structures.append(
            {
                "structure_name": name,
                "system_id": bucket["system_id"],
                "last_mined_date": last_day.isoformat(),
                "days_since_last": days_since,
                "phase": phase,
                "phase_label": phase_label,
                "estimated_window_end": estimated_window_end.isoformat(),
                "peak_day": peak_day.isoformat(),
                "peak_isk": peak["isk_value"],
                "peak_quantity": peak["quantity"],
                "peak_miners": len(peak["characters"]),
                "isk_7d": sum(day_map[d]["isk_value"] for d in last_7),
                "isk_30d": sum(day_map[d]["isk_value"] for d in last_30),
                "qty_7d": sum(day_map[d]["quantity"] for d in last_7),
                "qty_30d": sum(day_map[d]["quantity"] for d in last_30),
                "active_days": len(active_days),
                "unique_miners": len(bucket["miners"]),
                "rarities": sorted(bucket["rarities"]),
                "ore_types": sorted(bucket["ore_types"])[:12],
                "median_gap_days": median_gap,
                "next_pop_estimate": next_estimate,
                "recent_days": [
                    {
                        "date": d.isoformat(),
                        "quantity": day_map[d]["quantity"],
                        "isk_value": day_map[d]["isk_value"],
                        "miners": len(day_map[d]["characters"]),
                    }
                    for d in active_days[:14]
                ],
            }
        )

    structures.sort(key=lambda s: (s["days_since_last"], -s["isk_30d"], s["structure_name"].lower()))

    return {
        "as_of": today.isoformat(),
        "lookback_days": days,
        "idle_days_threshold": idle_days,
        "window_hours": DEFAULT_WINDOW_HOURS,
        "summary": {
            "structures": len(structures),
            "mining_window": sum(1 for s in structures if s["phase"] == "mining_window"),
            "recent": sum(1 for s in structures if s["phase"] == "recent"),
            "idle": sum(1 for s in structures if s["phase"] == "idle"),
            "isk_7d": sum(s["isk_7d"] for s in structures),
            "isk_30d": sum(s["isk_30d"] for s in structures),
        },
        "structures": structures,
    }
