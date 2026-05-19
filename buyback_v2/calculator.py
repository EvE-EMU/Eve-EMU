"""Shared buyback calculator (inventory paste → line prices)."""

from __future__ import annotations

from buybackprogram.app_settings import BUYBACKPROGRAM_PRICE_SOURCE_NAME
from buybackprogram.helpers import (
    get_item_buy_value,
    get_item_prices,
    get_item_values,
    item_missing,
)
from eveuniverse.models import EveType


def parse_inventory_lines(
    *,
    program,
    items_text: str,
) -> tuple[list[dict], list[dict]]:
    """
    Parse in-game inventory paste into buyback_data rows.
    Returns (buyback_data, row_notes).
    """
    buyback_data: list[dict] = []
    global_notes: list[dict] = []

    if "\t" not in items_text:
        return buyback_data, global_notes

    for line in items_text.split("\n"):
        if not line.strip():
            continue

        item_accepted = True
        notes: list[dict] = []
        parts = line.split("\t")
        name = parts[0].replace("*", "")
        item_type = EveType.objects.filter(name=name).first()

        if item_type:
            if item_type.eve_group.eve_category.name == "Blueprint":
                item_accepted = False
                notes.append(
                    {
                        "icon": "fa-print",
                        "color": "orange",
                        "message": f"{name} is a blueprint and is not accepted.",
                    }
                )
        else:
            item_accepted = False
            notes.append(
                {
                    "icon": "fa-skull-crossbones",
                    "color": "red",
                    "message": f"{name} was not found in the SDE.",
                }
            )

        quantity = 1
        if len(parts) == 1:
            if not program.allow_unpacked_items:
                item_accepted = False
                notes.append(
                    {
                        "icon": "fa-box-open",
                        "color": "red",
                        "message": f"Repack {name} to get a price.",
                    }
                )
        elif len(parts) == 2:
            if parts[1] != "\r":
                quantity = int("".join(filter(str.isdigit, parts[1])))
            elif not program.allow_unpacked_items:
                item_accepted = False
        else:
            if parts[1]:
                quantity = int("".join(filter(str.isdigit, parts[1])))
            elif not program.allow_unpacked_items:
                item_accepted = False

        if item_accepted and item_type:
            item_prices = get_item_prices(item_type, name, quantity, program)
            item_values = get_item_values(item_type, item_prices, program)
            buyback_data.append(
                {
                    "type_data": item_type,
                    "item_prices": item_prices,
                    "item_values": item_values,
                }
            )
        else:
            buyback_data.append(
                {
                    "type_data": item_type,
                    "item_prices": {
                        "notes": notes,
                        "raw_prices": False,
                        "material_prices": False,
                        "compression_prices": False,
                        "npc_prices": False,
                    },
                    "item_values": item_missing(name, quantity),
                }
            )

    return buyback_data, global_notes


def run_calculator(
    *,
    program,
    items_text: str,
    donation: int = 0,
) -> dict:
    buyback_data, _notes = parse_inventory_lines(program=program, items_text=items_text)
    contract_price_data = get_item_buy_value(buyback_data, program, donation)
    return {
        "program": program,
        "buyback_data": buyback_data,
        "contract_price_data": contract_price_data,
        "donation": donation,
        "price_source": BUYBACKPROGRAM_PRICE_SOURCE_NAME,
    }
