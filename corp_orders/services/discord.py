from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings

from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.claim_tokens import make_claim_token

logger = logging.getLogger(__name__)

_DISCORD_FIELD_MAX = 1024
_DISCORD_DESC_MAX = 4096
_WEBHOOK_URL_RE = re.compile(
    r"^https://(?:discord\.com|discordapp\.com)/api/webhooks/(\d+)/([^/?#]+)"
)


def _site_base_url() -> str:
    return str(getattr(settings, "SITE_URL", "") or "").rstrip("/")


def parse_webhook_url(url: str) -> tuple[str, str, str] | None:
    """Return (api_base, webhook_id, token) for Discord webhook message edits."""
    match = _WEBHOOK_URL_RE.match((url or "").strip())
    if not match:
        return None
    webhook_id, token = match.group(1), match.group(2)
    api_base = f"https://discord.com/api/webhooks/{webhook_id}/{token}"
    return api_base, webhook_id, token


def _post_webhook(url: str, payload: dict[str, Any], *, wait: bool = False) -> dict[str, Any] | None:
    if not url:
        return None
    params: dict[str, str] = {}
    if wait:
        params["wait"] = "true"
    if payload.get("components"):
        params["with_components"] = "true"
    try:
        response = requests.post(url, json=payload, params=params or None, timeout=15)
        response.raise_for_status()
        if wait:
            return response.json()
        return {}
    except Exception:
        logger.exception("Discord webhook failed for corp_orders")
        return None


def _patch_webhook_message(api_base: str, message_id: str, payload: dict[str, Any]) -> bool:
    if not api_base or not message_id:
        return False
    try:
        params = {"with_components": "true"} if payload.get("components") else None
        response = requests.patch(
            f"{api_base}/messages/{message_id}",
            json=payload,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("Discord webhook message edit failed for corp_orders")
        return False


def claim_button_url(order: FreightOrder) -> str:
    base = _site_base_url()
    if not base:
        return ""
    token = make_claim_token(order.pk)
    return urljoin(f"{base}/", f"corp-orders/{order.pk}/claim/?t={token}")


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


def _new_order_embed(order: FreightOrder, *, config: FreightOrdersSettings) -> dict[str, Any]:
    hub = config.destination_system
    final = (order.final_destination_system or "").strip()
    deliver_value = final if final else hub
    if final and final.lower() != hub.lower():
        deliver_value = f"{final} (stock via {hub})"

    if order.claimed_by_id:
        claim_line = f"**Claimed by {order.claimed_character_name}** — contract still needs to be created in-game."
        color = 0x57F287
    else:
        claim_line = (
            f"{order.get_speed_display()} — officer **{order.character_name}** must create the contract below.\n"
            "Use **Claim filling** to volunteer (opens Alliance Auth)."
        )
        color = 0x47D1FF

    fields = [
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
    ]
    if order.claimed_by_id:
        fields.insert(
            0,
            {
                "name": "Filling claimed",
                "value": f"**{order.claimed_character_name}**",
                "inline": False,
            },
        )

    return {
        "title": f"New corp stock order {order.code}",
        "color": color,
        "description": _truncate(claim_line, _DISCORD_DESC_MAX),
        "fields": fields,
    }


def _claim_link_components(order: FreightOrder) -> list[dict[str, Any]]:
    if order.claimed_by_id:
        return []
    claim_url = claim_button_url(order)
    if not claim_url.startswith("http"):
        return []
    return [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": "Claim filling",
                    "url": claim_url[:512],
                }
            ],
        }
    ]


def notify_new_order(order: FreightOrder, *, config: FreightOrdersSettings) -> bool:
    url = config.new_contract_webhook_url
    if not url:
        return False

    payload: dict[str, Any] = {"embeds": [_new_order_embed(order, config=config)]}
    components = _claim_link_components(order)
    if components:
        payload["components"] = components

    data = _post_webhook(url, payload, wait=True)
    if data and data.get("id"):
        order.discord_message_id = str(data["id"])
        order.save(update_fields=["discord_message_id", "updated_at"])
        return True
    return data is not None


def refresh_new_order_discord_message(order: FreightOrder, *, config: FreightOrdersSettings) -> bool:
    """Update the original Discord announcement after someone claims filling."""
    url = config.new_contract_webhook_url
    parsed = parse_webhook_url(url)
    if not parsed or not order.discord_message_id:
        return False
    api_base, _, _ = parsed
    payload: dict[str, Any] = {
        "embeds": [_new_order_embed(order, config=config)],
        "components": _claim_link_components(order),
    }
    return _patch_webhook_message(api_base, order.discord_message_id, payload)


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
