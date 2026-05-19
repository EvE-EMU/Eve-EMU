"""Compute monthly KPI aggregates per character."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from standing_fleet_tracker.models import (
    CharacterMonthlyKPI,
    FleetLocationSample,
    FleetSessionShipLog,
    MiningLedgerEntry,
    ShipFitSnapshot,
    WalletJournalEntry,
)
from standing_fleet_tracker.services.universe import region_name_for_system, ship_group_name


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = timezone.make_aware(datetime(year, month, 1))
    if month == 12:
        end = timezone.make_aware(datetime(year + 1, 1, 1))
    else:
        end = timezone.make_aware(datetime(year, month + 1, 1))
    return start, end


def compute_character_monthly_kpi(character, year: int, month: int) -> CharacterMonthlyKPI:
    start, end = _month_bounds(year, month)

    locs = FleetLocationSample.objects.filter(
        character=character,
        recorded_at__gte=start,
        recorded_at__lt=end,
    )
    total_samples = locs.count()
    standing_samples = locs.filter(in_standing_fleet=True).count()
    pct_standing = Decimal("0")
    if total_samples:
        pct_standing = (Decimal(standing_samples) / Decimal(total_samples) * Decimal("100")).quantize(
            Decimal("0.01")
        )

    ship_groups: Counter[str] = Counter()
    for snap in ShipFitSnapshot.objects.filter(
        character=character, recorded_at__gte=start, recorded_at__lt=end
    ):
        ship_groups[ship_group_name(snap.ship_type_id)] += 1
    for log in FleetSessionShipLog.objects.filter(
        session__character=character,
        recorded_at__gte=start,
        recorded_at__lt=end,
    ).select_related("session"):
        ship_groups[ship_group_name(log.ship_type_id)] += 1
    avg_ship_group = ship_groups.most_common(1)[0][0] if ship_groups else ""

    regions: Counter[str] = Counter()
    for loc in locs.only("solar_system_id"):
        rname = region_name_for_system(loc.solar_system_id)
        if rname:
            regions[rname] += 1
    avg_region = regions.most_common(1)[0][0] if regions else ""

    ratting_in = (
        WalletJournalEntry.objects.filter(
            character=character,
            recorded_at__gte=start,
            recorded_at__lt=end,
            in_fleet=True,
            amount__gt=0,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    ratting_out = (
        WalletJournalEntry.objects.filter(
            character=character,
            recorded_at__gte=start,
            recorded_at__lt=end,
            in_fleet=False,
            amount__gt=0,
        ).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    ratting_in = Decimal(ratting_in)
    ratting_out = Decimal(ratting_out)
    pct_diff = Decimal("0")
    if ratting_out > 0:
        pct_diff = ((ratting_in - ratting_out) / ratting_out * Decimal("100")).quantize(Decimal("0.01"))
    elif ratting_in > 0:
        pct_diff = Decimal("100")

    mining_standing = (
        MiningLedgerEntry.objects.filter(
            character=character,
            ledger_date__gte=start.date(),
            ledger_date__lt=end.date(),
            in_standing_fleet=True,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    mining_out = (
        MiningLedgerEntry.objects.filter(
            character=character,
            ledger_date__gte=start.date(),
            ledger_date__lt=end.date(),
            in_standing_fleet=False,
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    kpi, _ = CharacterMonthlyKPI.objects.update_or_create(
        character=character,
        year=year,
        month=month,
        defaults={
            "avg_ship_group_name": avg_ship_group,
            "avg_region_name": avg_region,
            "pct_standing_fleet": pct_standing,
            "isk_ratting_in_fleet": ratting_in,
            "isk_ratting_out_fleet": ratting_out,
            "ratting_isk_pct_diff": pct_diff,
            "mining_m3_standing_fleet": Decimal(mining_standing),
            "mining_m3_outside_fleet": Decimal(mining_out),
        },
    )
    return kpi


def compute_all_characters_for_month(year: int, month: int) -> int:
    from allianceauth.eveonline.models import EveCharacter
    from standing_fleet_tracker.services.polling import iter_tracked_characters

    count = 0
    seen = set()
    for character, _token in iter_tracked_characters():
        if character.pk in seen:
            continue
        seen.add(character.pk)
        compute_character_monthly_kpi(character, year, month)
        count += 1
    for character in EveCharacter.objects.filter(standing_fleet_fit_snapshots__isnull=False).distinct():
        if character.pk in seen:
            continue
        compute_character_monthly_kpi(character, year, month)
        count += 1
    return count
