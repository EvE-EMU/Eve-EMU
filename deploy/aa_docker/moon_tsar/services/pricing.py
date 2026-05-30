"""Ore valuation and tax rate lookup."""

from __future__ import annotations

from decimal import Decimal

from moon_tsar.models import MoonOreTaxRate


def tax_rate_for_type(type_id: int, type_name: str = "") -> tuple[Decimal, bool]:
    """Return (tax_rate_percent, use_adjusted_price)."""
    row = MoonOreTaxRate.objects.filter(type_id=type_id, active=True).first()
    if row:
        return row.tax_rate_percent, row.use_adjusted_price
    try:
        from miningtaxes.models import OrePrices

        op = OrePrices.objects.filter(eve_type_id=type_id).first()
        if op and op.tax_rate is not None:
            return Decimal(str(op.tax_rate)), True
    except Exception:
        pass
    return Decimal("10.00"), True


def volume_m3_for_type(type_id: int, quantity: int) -> Decimal:
    try:
        from eveuniverse.models import EveType

        et = EveType.objects.filter(id=type_id).first()
        if et and et.volume:
            return Decimal(str(et.volume)) * quantity
    except Exception:
        pass
    return Decimal(quantity)


def isk_value_for_type(type_id: int, quantity: int, *, use_adjusted: bool) -> Decimal:
    if quantity <= 0:
        return Decimal("0")
    try:
        from miningtaxes.models import OrePrices

        op = OrePrices.objects.filter(eve_type_id=type_id).first()
        if op:
            unit = op.refined_price or op.raw_price or op.sell or op.buy
            if unit:
                return Decimal(str(unit)) * quantity
    except Exception:
        pass
    return Decimal("0")
