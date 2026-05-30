"""Discovery and ledger sync for post-pop windows."""

from __future__ import annotations

import logging
import os
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from moon_tsar.models import MoonExtractionEvent, MoonExtractionLedgerLine, MoonTsarSettings
from moon_tsar.services.pricing import isk_value_for_type, tax_rate_for_type, volume_m3_for_type

logger = logging.getLogger(__name__)
User = get_user_model()


def _tracking_hours() -> int:
    raw = os.environ.get("AA_MOON_TSAR_TRACKING_HOURS", "").strip()
    if raw.isdigit():
        return int(raw)
    return MoonTsarSettings.load().tracking_hours_after_pop


def _parse_moon_from_label(label: str) -> tuple[str, int | None]:
    m = re.search(r"^(.+?)\s*[-–]\s*Moon\s*(\d+)\s*$", label, re.I)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return label.strip(), None


def discover_extractions_from_moonmining() -> int:
    """Create MoonExtractionEvent rows from aa-moonmining extractions."""
    try:
        from moonmining.models import Extraction
    except ImportError:
        return 0

    hours = _tracking_hours()
    created = 0
    for ext in Extraction.objects.filter(extraction_end_time__isnull=False).order_by("-extraction_end_time")[:200]:
        if MoonExtractionEvent.objects.filter(moonmining_extraction_id=ext.pk).exists():
            continue
        pop = ext.extraction_end_time or ext.extraction_start_time
        if not pop:
            continue
        moon = getattr(ext, "moon", None)
        label = str(moon) if moon else getattr(ext, "structure_name", "") or f"Extraction {ext.pk}"
        system, moon_num = _parse_moon_from_label(label)
        MoonExtractionEvent.objects.create(
            moonmining_extraction_id=ext.pk,
            moon_label=label[:255],
            system_name=system[:128],
            moon_number=moon_num,
            structure_name=(getattr(ext, "structure_name", None) or "")[:255],
            popped_at=pop,
            tracking_ends_at=pop + timedelta(hours=hours),
        )
        created += 1
    return created


def _resolve_user_for_character(character_id: int):
    try:
        from allianceauth.eveonline.models import EveCharacter

        ec = EveCharacter.objects.filter(character_id=character_id).select_related(
            "character_ownership__user"
        ).first()
        if ec and hasattr(ec, "character_ownership"):
            return ec.character_ownership.user
    except Exception:
        pass
    return None


@transaction.atomic
def sync_ledger_for_extraction(event: MoonExtractionEvent) -> int:
    """Import AdminMiningObsLog lines into extraction ledger."""
    try:
        from miningtaxes.models import AdminMiningObsLog
    except ImportError:
        return 0

    start = event.popped_at.date()
    end = event.tracking_ends_at.date()
    qs = AdminMiningObsLog.objects.filter(
        date__gte=start,
        date__lte=end,
    )
    if event.system_name:
        qs = qs.filter(eve_solar_system__name__iexact=event.system_name)
    if event.moon_number:
        qs = qs.filter(observer__icontains=f"moon {event.moon_number}")

    lines = 0
    total_m3 = 0
    total_ore = 0
    total_tax = 0
    for row in qs.iterator():
        if MoonExtractionLedgerLine.objects.filter(observer_log_id=row.pk).exists():
            continue
        type_id = row.eve_type.type_id if row.eve_type_id else 0
        type_name = row.eve_type.type_name if row.eve_type_id else ""
        qty = int(row.quantity or 0)
        rate_pct, use_adj = tax_rate_for_type(type_id, type_name)
        gross = isk_value_for_type(type_id, qty, use_adjusted=use_adj)
        tax = (gross * rate_pct / Decimal("100")).quantize(Decimal("0.01"))
        vol = volume_m3_for_type(type_id, qty)
        user = _resolve_user_for_character(row.miner_id)
        MoonExtractionLedgerLine.objects.create(
            extraction=event,
            miner_character_id=row.miner_id,
            miner_character_name="",
            user=user,
            type_id=type_id,
            type_name=type_name,
            quantity=qty,
            volume_m3=vol,
            gross_isk=gross,
            tax_isk=tax,
            observer_log_id=row.pk,
            mined_at=row.date,
        )
        lines += 1
        total_m3 += int(vol)
        total_ore += gross
        total_tax += tax

    event.ledger_synced_at = timezone.now()
    event.total_mined_m3 = total_m3
    event.total_ore_isk = total_ore
    event.total_tax_isk = total_tax
    event.save(
        update_fields=[
            "ledger_synced_at",
            "total_mined_m3",
            "total_ore_isk",
            "total_tax_isk",
        ]
    )
    return lines


def sync_all_active_extractions() -> int:
    now = timezone.now()
    total = 0
    for event in MoonExtractionEvent.objects.filter(tracking_ends_at__gte=now):
        total += sync_ledger_for_extraction(event)
    return total
