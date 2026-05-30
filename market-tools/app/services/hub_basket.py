"""Compare buy cost for item quantities across main trade hubs (ESI sell order book)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from app.esi.client import esi_get
from app.esi.rate_limit import acquire_slot
from app.services.appraisal import parse_appraisal_text
from app.services.janice import JANICE_MARKETS

logger = logging.getLogger(__name__)

_ESI = "https://esi.evetech.net/latest"
_UA = "EVE-EMU-Market/1.0 (+https://eve-emu.com; hub-basket)"

# Region IDs for primary trade hubs (public market orders).
TRADE_HUB_REGIONS: dict[str, tuple[int, str]] = {
    "jita": (10000002, "Jita (The Forge)"),
    "amarr": (10000043, "Amarr (Domain)"),
    "dodixie": (10000032, "Dodixie (Sinq Laison)"),
    "rens": (10000030, "Rens (Heimatar)"),
    "hek": (10000042, "Hek (Metropolis)"),
}


@dataclass(frozen=True)
class FillResult:
    fillable: bool
    quantity: int
    filled: int
    total_cost: float | None
    unit_avg: float | None
    best_sell: float | None


def fill_cost_from_sell_orders(orders: list[dict[str, Any]], quantity: int) -> FillResult:
    """Walk sell orders (lowest price first) until ``quantity`` units are filled."""
    sells = [o for o in orders if isinstance(o, dict) and not o.get("is_buy_order")]
    sells.sort(key=lambda o: float(o.get("price") or 0))
    remain = quantity
    cost = 0.0
    filled = 0
    best_sell: float | None = None
    for o in sells:
        if remain <= 0:
            break
        try:
            vol = int(o.get("volume_remain") or 0)
            price = float(o["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if vol <= 0:
            continue
        take = min(remain, vol)
        cost += take * price
        filled += take
        remain -= take
        best_sell = price
    if filled < quantity:
        return FillResult(
            fillable=False,
            quantity=quantity,
            filled=filled,
            total_cost=None,
            unit_avg=None,
            best_sell=best_sell,
        )
    return FillResult(
        fillable=True,
        quantity=quantity,
        filled=filled,
        total_cost=cost,
        unit_avg=cost / quantity,
        best_sell=best_sell,
    )


async def resolve_type_ids(names: list[str]) -> dict[str, int]:
    """Map inventory type names to type IDs via public ESI."""
    unique = [n.strip() for n in names if n and n.strip()]
    if not unique:
        return {}
    await acquire_slot()
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"{_ESI}/universe/ids/",
            content=json.dumps(unique),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": _UA,
            },
        )
    if resp.status_code != 200:
        logger.warning("universe/ids %s: %s", resp.status_code, resp.text[:200])
        return {}
    data = resp.json()
    out: dict[str, int] = {}
    for row in data.get("inventory_types") or []:
        if not isinstance(row, dict):
            continue
        try:
            out[str(row["name"])] = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


async def fetch_sell_orders_for_quantity(
    region_id: int,
    type_id: int,
    quantity: int,
    *,
    max_pages: int = 8,
) -> list[dict[str, Any]]:
    """Fetch sell orders page-by-page until ``quantity`` can be filled or pages exhausted."""
    accumulated: list[dict[str, Any]] = []
    for page in range(1, max(1, max_pages) + 1):
        status, data = await esi_get(
            f"/markets/{region_id}/orders/",
            params={"order_type": "sell", "type_id": type_id, "page": page},
            auth=False,
        )
        if status != 200 or not isinstance(data, list) or not data:
            break
        accumulated.extend(o for o in data if isinstance(o, dict))
        if fill_cost_from_sell_orders(accumulated, quantity).fillable:
            return accumulated
        if len(data) < 1000:
            break
    return accumulated


def _fill_to_dict(fill: FillResult) -> dict[str, Any]:
    return {
        "fillable": fill.fillable,
        "quantity": fill.quantity,
        "filled": fill.filled,
        "total_cost": fill.total_cost,
        "unit_avg": fill.unit_avg,
        "best_sell": fill.best_sell,
    }


async def run_hub_basket_compare(
    text: str,
    *,
    hubs: list[str] | None = None,
    max_pages: int = 8,
    concurrency: int = 6,
    on_progress: Callable[[int, int, str, str], None] | None = None,
) -> dict[str, Any]:
    """
    Parse paste text (same format as appraisal) and compare full-quantity buy cost per hub.

    Uses live regional sell orders from public ESI (no Janice key required).
    """
    entries = parse_appraisal_text(text)
    if not entries:
        return {"error": "no_items", "items": [], "basket": {}, "hubs": []}

    hub_keys = [h.lower() for h in (hubs or list(TRADE_HUB_REGIONS))]
    active_hubs: list[tuple[str, int, str]] = []
    for key in hub_keys:
        if key in TRADE_HUB_REGIONS:
            rid, label = TRADE_HUB_REGIONS[key]
            active_hubs.append((key, rid, label))

    names = [str(e["query"]).strip() for e in entries]
    name_to_id = await resolve_type_ids(names)

    jobs: list[tuple[str, int, int, str, int, str]] = []
    for entry in entries:
        name = str(entry["query"]).strip()
        qty = int(entry["quantity"])
        tid = name_to_id.get(name)
        if not tid:
            continue
        for key, region_id, label in active_hubs:
            jobs.append((name, qty, tid, key, region_id, label))

    fill_by_tid_hub: dict[tuple[int, str], FillResult] = {}
    labels_by_key = {key: label for key, _, label in active_hubs}
    total_jobs = len(jobs)
    sem = asyncio.Semaphore(max(1, concurrency))
    done_count = 0
    done_lock = asyncio.Lock()

    async def _fetch_one(
        name: str, qty: int, tid: int, key: str, region_id: int, _label: str
    ) -> tuple[int, str, FillResult]:
        nonlocal done_count
        async with sem:
            orders = await fetch_sell_orders_for_quantity(
                region_id, tid, qty, max_pages=max_pages
            )
            fill = fill_cost_from_sell_orders(orders, qty)
        async with done_lock:
            done_count += 1
            if on_progress:
                on_progress(done_count, total_jobs, name, key)
        return tid, key, fill

    if jobs:
        results = await asyncio.gather(*[_fetch_one(*job) for job in jobs])
        for tid, key, fill in results:
            fill_by_tid_hub[(tid, key)] = fill

    item_rows: list[dict[str, Any]] = []
    basket_totals: dict[str, float] = {k: 0.0 for k, _, _ in active_hubs}
    basket_fillable: dict[str, bool] = {k: True for k, _, _ in active_hubs}

    for entry in entries:
        name = str(entry["query"]).strip()
        qty = int(entry["quantity"])
        tid = name_to_id.get(name)
        hub_results: dict[str, dict[str, Any]] = {}
        best_hub: str | None = None
        best_total: float | None = None

        if not tid:
            item_rows.append(
                {
                    "name": name,
                    "quantity": qty,
                    "type_id": None,
                    "error": "unknown_type",
                    "hubs": {},
                    "best_hub": None,
                    "best_total": None,
                }
            )
            for key, _, _ in active_hubs:
                basket_fillable[key] = False
            continue

        for key, region_id, label in active_hubs:
            fill = fill_by_tid_hub.get((tid, key))
            if fill is None:
                fill = FillResult(
                    fillable=False,
                    quantity=qty,
                    filled=0,
                    total_cost=None,
                    unit_avg=None,
                    best_sell=None,
                )
            hub_results[key] = {
                **_fill_to_dict(fill),
                "label": labels_by_key.get(key, label),
                "region_id": region_id,
            }

            if fill.fillable and fill.total_cost is not None:
                basket_totals[key] += fill.total_cost
                if best_total is None or fill.total_cost < best_total:
                    best_total = fill.total_cost
                    best_hub = key
            else:
                basket_fillable[key] = False

        item_rows.append(
            {
                "name": name,
                "quantity": qty,
                "type_id": tid,
                "hubs": hub_results,
                "best_hub": best_hub,
                "best_total": best_total,
            }
        )

    basket: dict[str, dict[str, Any]] = {}
    ranked: list[tuple[float, str, float]] = []
    for key, _, label in active_hubs:
        fillable = basket_fillable.get(key, False)
        total = basket_totals.get(key, 0.0) if fillable else None
        basket[key] = {
            "label": label,
            "fillable": fillable,
            "total_cost": total,
        }
        if fillable and total is not None:
            ranked.append((total, key, total))
    ranked.sort()

    mixed_total = 0.0
    mixed_ok = True
    for row in item_rows:
        if row.get("best_total") is None:
            mixed_ok = False
            break
        mixed_total += float(row["best_total"])

    return {
        "items": item_rows,
        "basket": basket,
        "hubs": [
            {"id": k, "label": lbl, "region_id": rid, "janice_station": JANICE_MARKETS.get(k)}
            for k, rid, lbl in active_hubs
        ],
        "best_single_hub": ranked[0][1] if ranked else None,
        "best_single_hub_total": ranked[0][2] if ranked else None,
        "best_mixed_total": mixed_total if mixed_ok else None,
        "method": "esi_sell_order_walk",
        "esi_requests": total_jobs,
    }


def format_hub_basket_report(result: dict[str, Any]) -> str:
    """Human-readable report for CLI output."""
    if result.get("error") == "no_items":
        return "No items parsed. Use lines like: Broadcast Node x900"

    lines: list[str] = []
    lines.append("=== Per item (buy full qty from sell orders) ===")

    for row in result.get("items") or []:
        name = row.get("name", "?")
        qty = row.get("quantity", 0)
        lines.append(f"\n{name} x{qty:,}")
        if row.get("error") == "unknown_type":
            lines.append("  (unknown item name — check spelling)")
            continue
        for hub_key, hub in (row.get("hubs") or {}).items():
            label = hub.get("label") or hub_key
            if hub.get("fillable"):
                lines.append(
                    f"  {label}: {hub['unit_avg']:,.2f} ISK/u avg  "
                    f"(top sell {hub['best_sell']:,.2f}, total {hub['total_cost']:,.0f})"
                )
            else:
                filled = hub.get("filled", 0)
                lines.append(
                    f"  {label}: cannot fill ({filled:,} / {qty:,} on sell orders)"
                )
        best = row.get("best_hub")
        if best:
            lines.append(
                f"  >> Best: {best} ({row['best_total']:,.0f} ISK)"
            )
        else:
            lines.append("  >> No hub can fill")

    lines.append("\n=== Basket total (all items at one hub) ===")
    basket = result.get("basket") or {}
    for hub_key in sorted(basket.keys()):
        b = basket[hub_key]
        label = b.get("label") or hub_key
        if b.get("fillable"):
            lines.append(f"{label}: {b['total_cost']:,.0f} ISK")
        else:
            lines.append(f"{label}: cannot fill entire list")

    best_hub = result.get("best_single_hub")
    if best_hub:
        lines.append(
            f"\n>> Cheapest single hub: {best_hub} "
            f"({result.get('best_single_hub_total'):,.0f} ISK)"
        )
    mixed = result.get("best_mixed_total")
    if mixed is not None and best_hub:
        save = float(result["best_single_hub_total"]) - mixed
        if save > 0:
            lines.append(
                f">> Cheapest per-item mix across hubs: {mixed:,.0f} ISK "
                f"(save {save:,.0f} vs best single hub)"
            )

    return "\n".join(lines)
