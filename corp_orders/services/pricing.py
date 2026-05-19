from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from buyback_v2.pricing import fetch_janice_price_row
from buybackprogram.app_settings import (
    BUYBACKPROGRAM_PRICE_JANICE_API_KEY,
    BUYBACKPROGRAM_PRICE_METHOD,
)
from buybackprogram.tasks import valid_janice_api_key
from eveuniverse.models import EveType

_JANICE_OK: bool | None = None
_JANICE_CHECKED_AT: float = 0.0
_JANICE_CHECK_TTL_SEC = 300
_ITEMPRICE_MAX_AGE = timedelta(hours=1)


def _janice_unavailable_reason() -> str:
    method = getattr(settings, "BUYBACKPROGRAM_PRICE_METHOD", None) or BUYBACKPROGRAM_PRICE_METHOD
    key = getattr(settings, "BUYBACKPROGRAM_PRICE_JANICE_API_KEY", None) or BUYBACKPROGRAM_PRICE_JANICE_API_KEY
    if method != "Janice":
        return (
            f"Janice not configured (BUYBACKPROGRAM_PRICE_METHOD={method!r}, expected 'Janice')."
        )
    if not str(key or "").strip():
        return "Janice API key missing (set BUYBACKPROGRAM_PRICE_JANICE_API_KEY in .env)."
    return "Janice API key rejected or Janice API unreachable."


def janice_is_available() -> bool:
    global _JANICE_OK, _JANICE_CHECKED_AT
    now = time.monotonic()
    if _JANICE_OK is not None and (now - _JANICE_CHECKED_AT) < _JANICE_CHECK_TTL_SEC:
        return _JANICE_OK
    _JANICE_OK = valid_janice_api_key()
    _JANICE_CHECKED_AT = now
    return _JANICE_OK


def _sell_from_itemprices(type_ids: list[int]) -> dict[int, Decimal]:
    if not type_ids:
        return {}
    try:
        from buybackprogram.models import ItemPrices
    except Exception:
        return {}

    cutoff = timezone.now() - _ITEMPRICE_MAX_AGE
    rows = ItemPrices.objects.filter(eve_type_id__in=type_ids, updated__gte=cutoff)
    out: dict[int, Decimal] = {}
    for row in rows:
        if row.sell:
            out[row.eve_type_id] = Decimal(str(row.sell))
    return out


def _fetch_one_janice_sell(type_id: int) -> tuple[int, Decimal | None]:
    row = fetch_janice_price_row(type_id)
    if not row:
        return type_id, None
    return type_id, Decimal(str(row["sell"]))


def fetch_janice_sell_prices(type_ids: Iterable[int]) -> dict[int, Decimal]:
    """Batch Janice sell prices (DB cache first, then parallel API for misses)."""
    ids = list(dict.fromkeys(type_ids))
    if not ids:
        return {}

    prices = _sell_from_itemprices(ids)
    missing = [tid for tid in ids if tid not in prices]
    if not missing:
        return prices
    if not janice_is_available():
        return prices

    workers = min(8, len(missing))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_one_janice_sell, tid): tid for tid in missing}
        for future in as_completed(futures):
            type_id, sell = future.result()
            if sell is not None:
                prices[type_id] = sell
    return prices


def janice_sell_price(type_id: int) -> Decimal | None:
    return fetch_janice_sell_prices([type_id]).get(type_id)


def line_unit_price_isk(
    *,
    type_id: int,
    markup_percent: Decimal,
    sell_prices: dict[int, Decimal] | None = None,
) -> tuple[Decimal | None, str]:
    sell = (sell_prices or {}).get(type_id)
    if sell is None:
        sell = janice_sell_price(type_id)
    if sell is None:
        return None, _janice_unavailable_reason()
    unit = (sell * (Decimal("1") + markup_percent / Decimal("100"))).quantize(Decimal("1"))
    return unit, ""


def resolve_types_by_names(names: list[str]) -> dict[str, EveType]:
    clean = [n.strip().replace("*", "") for n in names if n and n.strip()]
    if not clean:
        return {}
    qs = EveType.objects.filter(name__in=clean).select_related("eve_group__eve_category")
    return {t.name: t for t in qs}


def resolve_type_by_name(name: str) -> EveType | None:
    clean = name.strip().replace("*", "")
    if not clean:
        return None
    return resolve_types_by_names([clean]).get(clean)
