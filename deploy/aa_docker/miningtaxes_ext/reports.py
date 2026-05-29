"""Moon ore quantity reports (corp observer logs + optional character ledger)."""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from typing import Any

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils.timezone import now


def _tax_only_corp_moons() -> bool:
    from miningtaxes.app_settings import MININGTAXES_TAX_ONLY_CORP_MOONS

    return bool(MININGTAXES_TAX_ONLY_CORP_MOONS)


def _moon_ore_group_ids() -> tuple[int, ...]:
    from miningtaxes.helpers import PriceGroups

    return PriceGroups.moon_ore_groups


def _miner_ids_for_user(user) -> list[int]:
    from allianceauth.eveonline.models import EveCharacter

    return list(
        EveCharacter.objects.filter(character_ownership__user=user).values_list(
            "character_id", flat=True
        )
    )


def _isk_for_ore_type(eve_type_id: int, quantity: int, type_cache: dict) -> float:
    from miningtaxes.models.orePrices import ore_calc_prices

    if quantity <= 0:
        return 0.0
    eve_type = type_cache.get(eve_type_id)
    if eve_type is None:
        from eve_sde.models import ItemType

        eve_type = ItemType.objects.get(id=eve_type_id)
        type_cache[eve_type_id] = eve_type
    _, _, taxed = ore_calc_prices(eve_type, quantity)
    return float(taxed)


def _merge_ore_buckets(
    merged: dict[str, dict[str, Any]],
    ore_name: str,
    quantity: int,
    value_isk: float,
    *,
    source: str,
) -> None:
    if quantity <= 0:
        return
    row = merged.setdefault(
        ore_name,
        {"ore": ore_name, "quantity": 0, "value_isk": 0.0, "sources": set()},
    )
    row["quantity"] += quantity
    row["value_isk"] += value_isk
    row["sources"].add(source)


def _finalize_ore_rows(merged: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ores = sorted(merged.values(), key=lambda x: (-x["quantity"], x["ore"]))
    for row in ores:
        row["value_isk"] = round(row["value_isk"], 2)
        row.pop("sources", None)
    return ores


def _month_bounds(year: int, month: int) -> tuple[dt.date, dt.date]:
    last_day = calendar.monthrange(year, month)[1]
    return dt.date(year, month, 1), dt.date(year, month, last_day)


def moon_ore_report(
    year: int,
    month: int,
    *,
    include_character_ledger: bool = False,
) -> dict[str, Any]:
    """Aggregate corp moon observer logs for a calendar month."""
    from miningtaxes.models import AdminMiningObsLog, CharacterMiningLedgerEntry

    start, end = _month_bounds(year, month)
    month_label = f"{year}-{month:02d}"

    detail_rows: list[dict[str, Any]] = []
    ore_totals: dict[str, int] = defaultdict(int)
    system_totals: dict[str, int] = defaultdict(int)

    obs_qs = (
        AdminMiningObsLog.objects.filter(date__gte=start, date__lte=end)
        .select_related(
            "eve_type",
            "eve_solar_system",
            "observer",
            "observer__character",
        )
        .order_by("date", "eve_solar_system__name", "eve_type__name")
    )

    for row in obs_qs:
        ore_name = row.eve_type.name
        system_name = row.eve_solar_system.name
        qty = int(row.quantity)
        ore_totals[ore_name] += qty
        system_totals[system_name] += qty
        detail_rows.append(
            {
                "date": row.date.isoformat(),
                "system": system_name,
                "ore": ore_name,
                "quantity": qty,
                "observer": row.observer.name if row.observer_id else "",
                "observer_type": row.observer_type or "",
                "source": "corp_moon",
            }
        )

    if include_character_ledger:
        ledger_qs = (
            CharacterMiningLedgerEntry.objects.filter(date__gte=start, date__lte=end)
            .select_related("eve_type", "eve_solar_system", "character__eve_character")
            .order_by("date", "eve_solar_system__name", "eve_type__name")
        )
        for row in ledger_qs:
            ore_name = row.eve_type.name
            system_name = row.eve_solar_system.name
            qty = int(row.quantity)
            ore_totals[ore_name] += qty
            system_totals[system_name] += qty
            detail_rows.append(
                {
                    "date": row.date.isoformat(),
                    "system": system_name,
                    "ore": ore_name,
                    "quantity": qty,
                    "observer": row.character.name,
                    "observer_type": "character_ledger",
                    "source": "ledger",
                }
            )

    ore_summary = [
        {"ore": name, "quantity": qty}
        for name, qty in sorted(ore_totals.items(), key=lambda x: (-x[1], x[0]))
    ]
    system_summary = [
        {"system": name, "quantity": qty}
        for name, qty in sorted(system_totals.items(), key=lambda x: (-x[1], x[0]))
    ]

    return {
        "month": month_label,
        "year": year,
        "month_num": month,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "detail": detail_rows,
        "ore_totals": ore_summary,
        "system_totals": system_summary,
        "detail_count": len(detail_rows),
    }


def user_ore_totals_for_month(user, year: int, month: int) -> dict[str, Any]:
    """Sum mined quantity by ore type for all characters on the account.

    When ``MININGTAXES_TAX_ONLY_CORP_MOONS`` is enabled, true moon ores (R4–R64
    groups) are taken from corp mining observer logs (per-miner attribution), not
    the personal ESI ledger — matching how miningtaxes taxes corp moons.
    """
    from miningtaxes.models import (
        AdminMiningObsLog,
        Character,
        CharacterMiningLedgerEntry,
    )

    start, end = _month_bounds(year, month)
    char_ids = list(
        Character.objects.filter(
            eve_character__character_ownership__user=user
        ).values_list("pk", flat=True)
    )
    miner_ids = _miner_ids_for_user(user)
    empty = {
        "month": f"{year}-{month:02d}",
        "ores": [],
        "total_quantity": 0,
        "total_value_isk": 0.0,
        "corp_moon_mode": _tax_only_corp_moons(),
        "includes_corp_moon_observer": False,
    }
    if not char_ids and not miner_ids:
        return empty

    merged: dict[str, dict[str, Any]] = {}
    moon_groups = _moon_ore_group_ids()
    corp_moon_mode = _tax_only_corp_moons()

    if char_ids:
        ledger_qs = CharacterMiningLedgerEntry.objects.filter(
            character_id__in=char_ids,
            date__gte=start,
            date__lte=end,
        )
        if corp_moon_mode:
            ledger_qs = ledger_qs.exclude(eve_type__group_id__in=moon_groups)

        for row in ledger_qs.values("eve_type__name").annotate(
            quantity=Sum("quantity"),
            value_isk=Sum("taxed_value"),
        ):
            _merge_ore_buckets(
                merged,
                row["eve_type__name"],
                int(row["quantity"] or 0),
                float(row["value_isk"] or 0),
                source="ledger",
            )

    includes_moon_observer = False
    if miner_ids and corp_moon_mode:
        from eve_sde.models import ItemType

        obs_rows = (
            AdminMiningObsLog.objects.filter(
                miner_id__in=miner_ids,
                date__gte=start,
                date__lte=end,
                eve_type__group_id__in=moon_groups,
            )
            .values("eve_type_id", "eve_type__name")
            .annotate(quantity=Sum("quantity"))
        )
        if obs_rows:
            includes_moon_observer = True
            type_ids = [r["eve_type_id"] for r in obs_rows]
            type_cache = {
                t.id: t for t in ItemType.objects.filter(id__in=type_ids)
            }
            for row in obs_rows:
                qty = int(row["quantity"] or 0)
                value_isk = _isk_for_ore_type(row["eve_type_id"], qty, type_cache)
                _merge_ore_buckets(
                    merged,
                    row["eve_type__name"],
                    qty,
                    value_isk,
                    source="corp_moon",
                )

    ores = _finalize_ore_rows(merged)
    return {
        "month": f"{year}-{month:02d}",
        "ores": ores,
        "total_quantity": sum(r["quantity"] for r in ores),
        "total_value_isk": round(sum(r["value_isk"] for r in ores), 2),
        "corp_moon_mode": corp_moon_mode,
        "includes_corp_moon_observer": includes_moon_observer,
    }


def user_ledger_ore_only(user) -> list[dict[str, Any]]:
    """Combined ledger rows (personal ledger + corp moon observer when applicable)."""
    from miningtaxes.models import AdminMiningObsLog, Character

    moon_groups = _moon_ore_group_ids()
    corp_moon_mode = _tax_only_corp_moons()
    combined: dict[str, dict[str, Any]] = {}

    for character in Character.objects.filter(
        eve_character__character_ownership__user=user
    ).select_related("eve_character"):
        qs = character.mining_ledger.select_related("eve_solar_system", "eve_type")
        if corp_moon_mode:
            qs = qs.exclude(eve_type__group_id__in=moon_groups)
        for row in qs:
            key = (
                f"ledger||{row.date.isoformat()}||"
                f"{row.eve_solar_system.name}||{row.eve_type.name}"
            )
            if key not in combined:
                combined[key] = {
                    "date": row.date.isoformat(),
                    "system": row.eve_solar_system.name,
                    "ore": row.eve_type.name,
                    "quantity": 0,
                    "value_isk": 0.0,
                    "source": "ledger",
                }
            combined[key]["quantity"] += int(row.quantity)
            combined[key]["value_isk"] += float(row.taxed_value or 0)

    if corp_moon_mode:
        miner_ids = _miner_ids_for_user(user)
        if miner_ids:
            type_cache: dict = {}
            obs_qs = (
                AdminMiningObsLog.objects.filter(miner_id__in=miner_ids)
                .filter(eve_type__group_id__in=moon_groups)
                .select_related("eve_solar_system", "eve_type", "observer")
            )
            for row in obs_qs:
                qty = int(row.quantity)
                key = (
                    f"moon||{row.date.isoformat()}||"
                    f"{row.eve_solar_system.name}||{row.eve_type_id}"
                )
                if key not in combined:
                    combined[key] = {
                        "date": row.date.isoformat(),
                        "system": row.eve_solar_system.name,
                        "ore": row.eve_type.name,
                        "quantity": 0,
                        "value_isk": 0.0,
                        "source": "corp_moon",
                    }
                combined[key]["quantity"] += qty
                combined[key]["value_isk"] += _isk_for_ore_type(
                    row.eve_type_id, qty, type_cache
                )

    rows = sorted(
        combined.values(), key=lambda r: (r["date"], r["system"], r["ore"]), reverse=True
    )
    for row in rows:
        row["value_isk"] = round(row["value_isk"], 2)
    return rows


def available_report_months(limit: int = 24) -> list[dict[str, int]]:
    """Distinct year/month pairs from corp moon logs (newest first)."""
    from miningtaxes.models import AdminMiningObsLog

    months = (
        AdminMiningObsLog.objects.annotate(m=TruncMonth("date"))
        .values_list("m", flat=True)
        .distinct()
        .order_by("-m")[:limit]
    )
    out = []
    for m in months:
        if m is None:
            continue
        d = m.date() if hasattr(m, "date") else m
        out.append({"year": d.year, "month": d.month})
    if not out:
        today = now().date()
        out.append({"year": today.year, "month": today.month})
    return out
