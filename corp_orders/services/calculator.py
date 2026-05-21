from __future__ import annotations

from decimal import Decimal

from corp_orders.constants import SPEED_DESCRIPTION_LABEL, SPEED_EXPIRATION_HOURS
from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.freight import calculate_freight_isk
from corp_orders.services.pricing import (
    fetch_janice_sell_prices,
    line_unit_price_isk,
    resolve_types_by_names,
)


def _parse_quantity_cell(value: str) -> int:
    return int("".join(c for c in (value or "") if c.isdigit()) or "0")


def _is_ravworks_header(parts: list[str]) -> bool:
    if len(parts) < 2:
        return False
    col0 = parts[0].strip().lower()
    col1 = parts[1].strip().lower()
    return col0 == "name" and "to buy" in col1


def looks_like_ravworks_paste(items_text: str) -> bool:
    """Ravworks Stocks/Materials table: Name, To Buy, … (tab-separated)."""
    if "\t" not in items_text:
        return False
    for raw in items_text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if _is_ravworks_header(parts):
            return True
        if len(parts) >= 6 and parts[0].strip() and parts[1].strip():
            name = parts[0].strip()
            if name.lower() == "name":
                continue
            qty_cell = parts[1].strip()
            if any(c.isdigit() for c in qty_cell):
                return True
        break
    return False


def parse_ravworks_lines(items_text: str) -> tuple[list[tuple[str, int]], list[str]]:
    """
    Parse Ravworks Stocks/Materials export. Uses the **To Buy** column as quantity;
    rows with To Buy 0 are omitted.
    """
    raw_rows: list[tuple[str, int]] = []
    errors: list[str] = []
    skipped_zero = 0

    if "\t" not in items_text:
        errors.append(
            "Ravworks paste must be tab-separated — copy the Stocks/Materials table from Ravworks."
        )
        return raw_rows, errors

    for raw in items_text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if _is_ravworks_header(parts):
            continue
        if len(parts) < 2:
            continue
        name = parts[0].replace("*", "").strip()
        if not name:
            continue
        to_buy = _parse_quantity_cell(parts[1])
        if to_buy < 1:
            skipped_zero += 1
            continue
        raw_rows.append((name, to_buy))

    if not raw_rows and skipped_zero:
        errors.append(
            "No Ravworks rows with To Buy > 0 — all materials are already covered by stock."
        )
    elif not raw_rows:
        errors.append(
            "No Ravworks material rows found — paste the Stocks/Materials table (with header)."
        )
    return raw_rows, errors


def _lines_from_name_qty_rows(
    raw_rows: list[tuple[str, int]],
) -> tuple[list[dict], list[str]]:
    lines_out: list[dict] = []
    errors: list[str] = []
    names = [name for name, _ in raw_rows]
    types_by_name = resolve_types_by_names(names)
    for name, qty in raw_rows:
        eve_type = types_by_name.get(name)
        if not eve_type:
            errors.append(f"{name} not found in SDE.")
            continue
        if eve_type.eve_group.eve_category.name == "Blueprint":
            errors.append(f"{name} is a blueprint (not accepted).")
            continue
        volume = float(eve_type.volume or 0) * qty
        lines_out.append(
            {
                "type_id": eve_type.id,
                "name": eve_type.name,
                "quantity": qty,
                "volume_m3": volume,
            }
        )
    return lines_out, errors


def parse_inventory_lines(items_text: str) -> tuple[list[dict], list[str]]:
    """Parse in-game inventory or Ravworks Stocks/Materials paste (tab-separated)."""
    if looks_like_ravworks_paste(items_text):
        raw_rows, errors = parse_ravworks_lines(items_text)
        if errors and not raw_rows:
            return [], errors
        lines_out, line_errors = _lines_from_name_qty_rows(raw_rows)
        return lines_out, errors + line_errors

    lines_out: list[dict] = []
    errors: list[str] = []

    if "\t" not in items_text:
        errors.append(
            "Paste must be tab-separated — in-game inventory (Ctrl+C) or Ravworks Stocks/Materials."
        )
        return lines_out, errors

    raw_rows: list[tuple[str, int]] = []
    names: list[str] = []
    for raw in items_text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        name = parts[0].replace("*", "").strip()
        qty = 1
        if len(parts) >= 2 and parts[1].strip():
            qty = _parse_quantity_cell(parts[1])
        if qty < 1:
            errors.append(f"Invalid quantity for {name}.")
            continue
        names.append(name)
        raw_rows.append((name, qty))

    return _lines_from_name_qty_rows(raw_rows)


def build_quote(
    *,
    config: FreightOrdersSettings,
    items_text: str,
    speed: str,
    issuer_kind: str,
    final_destination_system: str = "",
) -> dict:
    lines, errors = parse_inventory_lines(items_text)
    markup = config.item_markup_percent
    priced: list[dict] = []
    subtotal = 0
    total_volume = Decimal("0")

    type_ids = [line["type_id"] for line in lines]
    sell_prices = fetch_janice_sell_prices(type_ids)

    for line in lines:
        unit, err = line_unit_price_isk(
            type_id=line["type_id"],
            markup_percent=markup,
            sell_prices=sell_prices,
        )
        if unit is None:
            errors.append(f"{line['name']}: {err}")
            continue
        line_total = int(unit * line["quantity"])
        subtotal += line_total
        total_volume += Decimal(str(line["volume_m3"]))
        priced.append(
            {
                **line,
                "unit_isk": str(unit),
                "line_total_isk": line_total,
            }
        )

    freight = 0
    freight_detail: dict = {}
    if not errors and priced:
        try:
            freight, freight_detail = calculate_freight_isk(
                config=config,
                volume_m3=total_volume,
                items_subtotal_isk=subtotal,
                sell_prices=sell_prices,
            )
        except Exception as exc:
            errors.append(f"PushX freight quote failed: {exc}")

    multiplier = Decimal("1")
    if speed == FreightOrder.Speed.GOD:
        multiplier = config.god_speed_multiplier
    elif speed == FreightOrder.Speed.ALTER:
        multiplier = config.alter_speed_multiplier

    base = subtotal + freight
    surcharge = int(Decimal(base) * (multiplier - Decimal("1")))
    contract_price = base + surcharge

    hours = SPEED_EXPIRATION_HOURS.get(speed, 168)
    if issuer_kind == FreightOrder.IssuerKind.CORPORATION:
        hours = max(hours, SPEED_EXPIRATION_HOURS["regular"])

    speed_label = SPEED_DESCRIPTION_LABEL.get(speed, speed)
    description = f"{speed_label} | CODE pending"
    dest = (final_destination_system or "").strip()
    freight_hub = config.destination_system

    return {
        "lines": priced,
        "errors": errors,
        "items_subtotal_isk": subtotal,
        "total_volume_m3": str(total_volume),
        "freight_isk": freight,
        "freight_detail": freight_detail,
        "speed_surcharge_isk": surcharge,
        "contract_price_isk": contract_price,
        "expiration_hours": hours,
        "speed_label": speed_label,
        "contract_description_template": description,
        "pushx_normal_isk": freight_detail.get("pushx_normal_isk"),
        "pushx_rush_isk": freight_detail.get("pushx_rush_isk"),
        "final_destination_system": dest,
        "freight_hub_system": freight_hub,
        "freight_route": f"{config.origin_system} → {freight_hub}",
    }
