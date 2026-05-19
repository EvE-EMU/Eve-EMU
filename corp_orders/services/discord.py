from __future__ import annotations

import logging
from typing import Any

import requests

from corp_orders.models import FreightOrder, FreightOrdersSettings

logger = logging.getLogger(__name__)

_DISCORD_FIELD_MAX = 1024
_DISCORD_DESC_MAX = 4096


def _post_webhook(url: str, payload: dict[str, Any]) -> bool:
    if not url:
        return False
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("Discord webhook failed for corp_orders")
        return False


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _format_items_required(lines_json: list[dict]) -> str:
    if not lines_json:
        return "—"
    rows = [
        f"• {row.get('name', '?')} ×{row.get('quantity', '?')}"
        for row in lines_json
    ]
    return _truncate("\n".join(rows), _DISCORD_FIELD_MAX)


def _format_contract_required(order: FreightOrder, *, config: FreightOrdersSettings) -> str:
    from corp_orders.services.contracts import contract_creation_instructions

    instructions = contract_creation_instructions(order, config=config)
    hub = config.destination_system
    final = (order.final_destination_system or "").strip()
    dest_line = final or hub
    if final and final.lower() != hub.lower():
        dest_line = f"{final} (freight priced to {hub})"

    lines = [
        "**Item exchange — create in game**",
        f"Type: {instructions['type']}",
        f"Assignee: {instructions['assignee']}",
        f"I will pay: **{order.contract_price_isk:,} ISK**",
        "I will receive: **nothing (0 ISK / no items)**",
        f"Description (copy exactly): `{order.contract_description}`",
        f"Expiration: ~{order.expiration_hours} hours",
        f"Final destination: **{dest_line}**",
        f"Freight route (PushX): {config.origin_system} → {hub}",
        f"Wallet: {order.get_wallet_method_display()}",
    ]
    if order.wallet_notes:
        lines.append(f"Wallet notes: {order.wallet_notes}")
    return _truncate("\n".join(lines), _DISCORD_FIELD_MAX)


def notify_new_order(order: FreightOrder, *, config: FreightOrdersSettings) -> bool:
    url = config.new_contract_webhook_url
    if not url:
        return False

    hub = config.destination_system
    final = (order.final_destination_system or "").strip()
    deliver_value = final if final else hub
    if final and final.lower() != hub.lower():
        deliver_value = f"{final} (stock via {hub})"

    embed = {
        "title": f"New corp stock order {order.code}",
        "color": 0x47D1FF,
        "description": _truncate(
            f"{order.get_speed_display()} — officer **{order.character_name}** must create the contract below.",
            _DISCORD_DESC_MAX,
        ),
        "fields": [
            {
                "name": "Contract (required)",
                "value": _format_contract_required(order, config=config),
                "inline": False,
            },
            {
                "name": "Items to add to contract",
                "value": _format_items_required(order.lines_json or []),
                "inline": False,
            },
            {"name": "Deliver to", "value": deliver_value, "inline": True},
            {
                "name": "Freight quoted",
                "value": f"{config.origin_system} → {hub}",
                "inline": True,
            },
            {"name": "Contract value", "value": f"{order.contract_price_isk:,} ISK", "inline": True},
            {"name": "Timeframe", "value": order.get_speed_display(), "inline": True},
            {"name": "Issuer", "value": order.get_issuer_kind_display(), "inline": True},
            {"name": "Volume", "value": f"{order.total_volume_m3:,.0f} m³", "inline": True},
        ],
    }
    return _post_webhook(url, {"embeds": [embed]})


def notify_payback(order: FreightOrder, *, config: FreightOrdersSettings) -> bool:
    url = config.payback_webhook_url
    if not url:
        return False
    embed = {
        "title": f"Payback due — {order.code}",
        "color": 0xFFB347,
        "description": (
            f"Contract **{order.eve_contract_id or 'n/a'}** completed.\n"
            f"Reimburse **{order.character_name}** for **{order.contract_price_isk:,} ISK** "
            f"via {order.get_wallet_method_display()}."
        ),
        "fields": [
            {"name": "Wallet", "value": order.get_wallet_method_display(), "inline": True},
            {"name": "Notes", "value": order.wallet_notes or "—", "inline": True},
        ],
    }
    return _post_webhook(url, {"embeds": [embed]})
