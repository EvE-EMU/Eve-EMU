"""Link aa-moonmining extractions to EMU Moons (48h system ledger window)."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from emu_moons.models import EmuExtraction, EmuMoonsSettings, StructureClass, StructureTaxProfile
from emu_moons.services.moon_exclusions import extraction_is_taxable, moon_label_is_excluded
from emu_moons.services.observer_ledger import (
    character_ledger_fallback_enabled,
    extraction_solar_system_key,
    normalize_extraction_system_name,
    sync_observer_ledger,
)
from emu_moons.services.scheduling import _system_name

logger = logging.getLogger(__name__)
User = get_user_model()


def _parse_moon_label(label: str) -> tuple[str, int | None]:
    m = re.search(r"^(.+?)\s*[-–]\s*Moon\s*(\d+)\s*$", label, re.I)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return label.strip(), None


def _structure_class_for_extraction(ext) -> str:
    refinery = getattr(ext, "refinery", None)
    if refinery and refinery.pk:
        prof = StructureTaxProfile.objects.filter(
            moonmining_refinery_id=refinery.pk
        ).first()
        if prof:
            return prof.structure_class
    return StructureClass.PUBLIC


def discover_extractions_from_moonmining(limit: int = 300) -> int:
    try:
        from moonmining.models import Extraction
    except ImportError:
        return 0

    cfg = EmuMoonsSettings.load()
    hours = cfg.ledger_match_hours
    created = 0
    qs = Extraction.objects.filter(chunk_arrival_at__isnull=False).order_by(
        "-chunk_arrival_at"
    )[:limit]
    for ext in qs:
        if EmuExtraction.objects.filter(moonmining_extraction_id=ext.pk).exists():
            continue
        pop = ext.chunk_arrival_at or ext.started_at
        if not pop:
            continue
        moon = getattr(ext, "moon", None)
        refinery = getattr(ext, "refinery", None)
        ref_name = getattr(refinery, "name", "") if refinery else ""
        label = str(moon) if moon else ref_name or f"#{ext.pk}"
        system, moon_num = _parse_moon_label(label)
        if refinery:
            system = _system_name(refinery) or system
        if not system and ref_name:
            m = re.match(r"^([A-Z0-9-]+)\s", ref_name)
            if m:
                system = m.group(1)
        if moon_label_is_excluded(
            label,
            structure_name=ref_name or "",
            system_name=system or "",
            moon_number=moon_num,
        ):
            continue
        sclass = _structure_class_for_extraction(ext)
        EmuExtraction.objects.create(
            moonmining_extraction_id=ext.pk,
            extraction_number=ext.pk,
            moon_label=label[:255],
            system_name=system[:128],
            moon_number=moon_num,
            structure_name=(ref_name or "")[:255],
            structure_class=sclass,
            popped_at=pop,
            ledger_window_end=pop + timedelta(hours=hours),
        )
        created += 1
    return created


@transaction.atomic
def sync_extraction_ledger(extraction: EmuExtraction) -> int:
    """
    Attribute mining from Guns-R-Us corp mining observers (Rexan token).

    Personal character mining ledgers are not used unless
    ``AA_EMU_MOONS_ALLOW_CHARACTER_LEDGER=1``.
    """
    normalize_extraction_system_name(extraction)
    count = sync_observer_ledger(extraction)
    if count > 0:
        return count
    if character_ledger_fallback_enabled():
        from emu_moons.services.character_ledger import sync_character_mining_ledger

        logger.warning(
            "emu_moons: no observer ledger for %s; falling back to character mining ledger",
            extraction.pk,
        )
        return sync_character_mining_ledger(extraction)
    logger.warning(
        "emu_moons: no billable observer ledger for extraction %s (%s); "
        "sync observers or ensure miners are registered on auth.",
        extraction.pk,
        extraction_solar_system_key(extraction) or extraction.moon_label,
    )
    return 0
