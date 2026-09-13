"""ISK formatting helpers."""

from __future__ import annotations

from decimal import Decimal


def fmt_isk_full(value: Decimal | float | int | str) -> str:
    n = float(value)
    return f"{n:,.2f} ISK"
