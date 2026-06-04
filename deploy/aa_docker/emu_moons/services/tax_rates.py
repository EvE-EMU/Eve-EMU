"""Default and lookup tax rates by structure class + moon rarity."""

from __future__ import annotations

from decimal import Decimal

from emu_moons.models import MoonRarity, MoonTypeTaxRate, StructureClass

# Spec defaults (public structure)
DEFAULT_PUBLIC_RATES: dict[str, Decimal] = {
    MoonRarity.R4: Decimal("0"),
    MoonRarity.R8: Decimal("0"),
    MoonRarity.R16: Decimal("20"),
    MoonRarity.R32: Decimal("30"),
    MoonRarity.R64: Decimal("40"),
    MoonRarity.UNKNOWN: Decimal("20"),
}


def seed_default_tax_rates() -> int:
    created = 0
    for rarity, pct in DEFAULT_PUBLIC_RATES.items():
        _, was_new = MoonTypeTaxRate.objects.get_or_create(
            structure_class=StructureClass.PUBLIC,
            moon_rarity=rarity,
            defaults={"tax_rate_percent": pct},
        )
        if was_new:
            created += 1
    for rarity in MoonRarity:
        if rarity == MoonRarity.UNKNOWN:
            continue
        _, was_new = MoonTypeTaxRate.objects.get_or_create(
            structure_class=StructureClass.NATIONALIZED,
            moon_rarity=rarity,
            defaults={"tax_rate_percent": Decimal("100")},
        )
        if was_new:
            created += 1
        _, was_new = MoonTypeTaxRate.objects.get_or_create(
            structure_class=StructureClass.PRIVATE,
            moon_rarity=rarity,
            defaults={"tax_rate_percent": Decimal("0")},
        )
        if was_new:
            created += 1
    return created


def tax_rate_percent(structure_class: str, moon_rarity: str) -> Decimal:
    row = MoonTypeTaxRate.objects.filter(
        structure_class=structure_class,
        moon_rarity=moon_rarity,
        active=True,
    ).first()
    if row:
        return row.tax_rate_percent
    if structure_class == StructureClass.NATIONALIZED:
        return Decimal("100")
    if structure_class == StructureClass.PRIVATE:
        return Decimal("0")
    return DEFAULT_PUBLIC_RATES.get(moon_rarity, Decimal("20"))
