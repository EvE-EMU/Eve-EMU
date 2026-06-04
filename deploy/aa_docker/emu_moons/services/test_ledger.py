"""Test-only extraction ledger from character mining in moon systems.

Production invoicing uses ``AdminMiningObsLog`` (corp observers). This module
attributes *test* moon-ore lines to miners who had volume in the extraction
system during the pop window, using a representative moon ore for the pop rarity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from emu_moons.models import EmuExtraction, MoonRarity
from emu_moons.services.pricing import (
    isk_value_for_type,
    volume_m3_for_type,
)
from emu_moons.services.scheduling import _system_name

User = get_user_model()

_RARITY_TO_GROUP = {
    MoonRarity.R4: 1884,
    MoonRarity.R8: 1920,
    MoonRarity.R16: 1921,
    MoonRarity.R32: 1922,
    MoonRarity.R64: 1923,
}
_SYSTEM_PREFIX = re.compile(r"^([A-Z0-9-]+)")


def _system_prefix(name: str) -> str:
    if not name:
        return ""
    m = _SYSTEM_PREFIX.match(name.strip().upper())
    return m.group(1) if m else name.strip().upper()


def _rarity_for_extraction(extraction: EmuExtraction) -> str:
    comp = extraction.ore_composition_json or []
    if comp and isinstance(comp[0], dict):
        raw = (comp[0].get("rarity") or "").lower()
        if raw in {c.value for c in MoonRarity}:
            return raw
    return MoonRarity.R16


def _sample_moon_ore_type(rarity: str) -> tuple[int, str]:
    """One Eve type id + name for a moon rarity band (for test ledger lines)."""
    group_id = _RARITY_TO_GROUP.get(rarity, _RARITY_TO_GROUP[MoonRarity.R16])
    try:
        from eve_sde.models import ItemType

        it = ItemType.objects.filter(group_id=group_id).order_by("id").first()
        if it:
            return int(it.id), str(it.name)
    except Exception:
        pass
    try:
        from eveuniverse.models import EveType

        et = (
            EveType.objects.filter(eve_group_id=group_id)
            .order_by("id")
            .only("id", "name")
            .first()
        )
        if et:
            return int(et.id), str(et.name)
    except Exception:
        pass
    return 45490, "Test Moon Ore"


def _resolve_user(character_id: int):
    try:
        from allianceauth.eveonline.models import EveCharacter

        ec = (
            EveCharacter.objects.filter(character_id=character_id)
            .select_related("character_ownership__user")
            .first()
        )
        if ec and hasattr(ec, "character_ownership"):
            return ec.character_ownership.user, ec.character_name
    except Exception:
        pass
    return None, ""


@transaction.atomic
def sync_test_extraction_ledger(extraction: EmuExtraction) -> int:
    """Same as production character-mining attribution (per miner, per moon ore)."""
    from emu_moons.services.character_ledger import sync_character_mining_ledger

    return sync_character_mining_ledger(extraction)
