"""Ore valuation (miningtaxes OrePrices / Janice Jita 4-4 reprocess buy) and moon rarity lookup."""

from __future__ import annotations

from decimal import Decimal

from emu_moons.models import MoonRarity, OrePriceSnapshot

MOON_GROUP_RARITY = {
    1884: MoonRarity.R4,
    1920: MoonRarity.R8,
    1921: MoonRarity.R16,
    1922: MoonRarity.R32,
    1923: MoonRarity.R64,
}


def moon_ore_group_ids() -> tuple[int, ...]:
    """EVE groups for true moon ores (R4–R64), same as miningtaxes / cerlestes moon table."""
    try:
        from miningtaxes.helpers import PriceGroups

        return PriceGroups.moon_ore_groups
    except ImportError:
        return tuple(MOON_GROUP_RARITY.keys())


def is_moon_ore_type_id(type_id: int) -> bool:
    """True only for moon chunk ores (not belt ores like Kylixium, Gneiss, Jaspet)."""
    if not type_id:
        return False
    try:
        from eveuniverse.models import EveType

        group_id = (
            EveType.objects.filter(id=type_id)
            .values_list("eve_group_id", flat=True)
            .first()
        )
        if group_id is not None:
            return int(group_id) in moon_ore_group_ids()
    except Exception:
        pass
    return False


def rarity_for_type_id(type_id: int) -> str:
    try:
        from eveuniverse.models import EveType

        et = EveType.objects.filter(id=type_id).select_related("eve_group").first()
        if et and et.eve_group_id in MOON_GROUP_RARITY:
            return MOON_GROUP_RARITY[et.eve_group_id]
    except Exception:
        pass
    return MoonRarity.UNKNOWN


def rarity_for_type_name(type_name: str) -> str:
    if not type_name:
        return MoonRarity.UNKNOWN
    try:
        from eveuniverse.models import EveType

        et = EveType.objects.filter(name__iexact=type_name.strip()).first()
        if et:
            return rarity_for_type_id(et.id)
    except Exception:
        pass
    return MoonRarity.UNKNOWN


def volume_m3_for_type(type_id: int, quantity: int) -> Decimal:
    try:
        from eveuniverse.models import EveType

        et = EveType.objects.filter(id=type_id).first()
        if et and et.volume:
            return Decimal(str(et.volume)) * quantity
    except Exception:
        pass
    return Decimal(quantity)


def material_unit_isk(op) -> Decimal:
    """
    ISK per unit for taxable material value.

    Matches Janice Jita 4-4 reprocess *buy* where that equals miningtaxes ``buy``
    (e.g. Lavish Sperrylite ~2,928 ISK/unit). Compressed moon ore uses ``buy`` only:
    miningtaxes ``refined_price`` is computed per compressed unit using mineral math
    and overstates stacks (e.g. 10× Compressed Lavish Sperrylite ≈ 26,110 ISK on
    Janice vs ~29,430 at uncompressed refine per unit). Uncompressed ores use
    miningtaxes ``taxed_price`` unless Janice ore buy matches reprocess buy
    (within 2%, e.g. Lavish Sperrylite ~2,928 ISK/unit).
    """
    if not op:
        return Decimal("0")
    try:
        type_name = (op.eve_type.name or "").strip()
    except Exception:
        type_name = ""
    if type_name.startswith("Compressed "):
        for val in (op.buy, op.raw_price):
            if val and float(val) > 0:
                return Decimal(str(val))
        return Decimal(str(op.taxed_price or op.refined_price or 0))
    buy = Decimal(str(op.buy or op.raw_price or 0))
    taxed = Decimal(str(op.taxed_price or op.refined_price or 0))
    if buy > 0 and taxed > 0 and buy >= taxed * Decimal("0.98"):
        return buy
    for val in (op.taxed_price, op.refined_price, op.buy, op.raw_price, op.sell):
        if val and float(val) > 0:
            return Decimal(str(val))
    return Decimal("0")


def isk_value_for_type(type_id: int, quantity: int) -> Decimal:
    """Material value for ``quantity`` units of ``type_id``."""
    if quantity <= 0:
        return Decimal("0")
    try:
        from miningtaxes.models import OrePrices

        op = OrePrices.objects.filter(eve_type_id=type_id).select_related("eve_type").first()
        if op:
            unit = material_unit_isk(op)
            if unit > 0:
                return unit * quantity
    except Exception:
        pass
    snap = (
        OrePriceSnapshot.objects.filter(type_id=type_id)
        .order_by("-snapshot_at")
        .first()
    )
    if snap and snap.refined_isk_per_unit:
        return snap.refined_isk_per_unit * quantity
    return Decimal("0")


def refresh_prices_from_miningtaxes() -> int:
    """Snapshot current miningtaxes ore prices for invoice audit trail."""
    try:
        from miningtaxes.models import OrePrices
    except ImportError:
        return 0
    count = 0
    for op in OrePrices.objects.all().iterator():
        raw = Decimal(str(op.raw_price or op.buy or 0))
        refined = Decimal(str(op.refined_price or op.sell or raw))
        OrePriceSnapshot.objects.create(
            type_id=op.eve_type_id,
            type_name=(op.eve_type_name or "")[:128],
            raw_isk_per_unit=raw,
            refined_isk_per_unit=refined,
            source="miningtaxes",
        )
        count += 1
    return count
