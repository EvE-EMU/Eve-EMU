"""Template filters for EMU Moons."""

from __future__ import annotations

from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def isk_amount(value) -> str:
    """Format a number as 1,234,567.89 ISK."""
    if value is None or value == "":
        return "0.00 ISK"
    try:
        amount = Decimal(str(value))
    except Exception:
        return str(value)
    return f"{amount:,.2f} ISK"
