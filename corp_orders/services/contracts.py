from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.discord import notify_payback

logger = logging.getLogger(__name__)

# ESI contract status: finished
CONTRACT_STATUS_FINISHED = "finished"
CONTRACT_STATUS_IN_PROGRESS = "in_progress"
CONTRACT_STATUS_OUTSTANDING = "outstanding"


def _get_token_for_character(character_id: int):
    from esi.models import Token

    return (
        Token.objects.filter(character_id=character_id)
        .require_valid()
        .require_scopes(["esi-contracts.read_character_contracts.v1"])
        .first()
    )


def poll_order_contract(order: FreightOrder) -> FreightOrder:
    """Match linked EVE contract by ID and advance status / payback."""
    if not order.eve_contract_id:
        return order

    token = _get_token_for_character(order.character_id)
    if not token:
        return order

    try:
        from esi.clients import EsiClientProvider

        client = EsiClientProvider().get_client(token=token)
        detail = client.request(
            "get_characters_character_id_contracts_contract_id",
            character_id=order.character_id,
            contract_id=order.eve_contract_id,
        ).results()
    except Exception:
        logger.exception("ESI contract poll failed for %s", order.code)
        return order

    status = str(detail.get("status") or "")
    if status == CONTRACT_STATUS_FINISHED and order.status != FreightOrder.Status.PAYBACK_SENT:
        order.status = FreightOrder.Status.COMPLETED
        order.completed_at = timezone.now()
        order.save(update_fields=["status", "completed_at", "updated_at"])
        if order.payback_on_completion:
            config = FreightOrdersSettings.load()
            if notify_payback(order, config=config):
                order.status = FreightOrder.Status.PAYBACK_SENT
                order.save(update_fields=["status", "updated_at"])
    elif status in (CONTRACT_STATUS_IN_PROGRESS, CONTRACT_STATUS_OUTSTANDING):
        if order.status == FreightOrder.Status.CONTRACT_LINKED:
            order.status = FreightOrder.Status.IN_PROGRESS
            order.save(update_fields=["status", "updated_at"])

    return order


def contract_creation_instructions(order: FreightOrder, *, config: FreightOrdersSettings) -> dict[str, Any]:
    """In-game steps — ESI does not create item exchange contracts via API."""
    corp_name = order.corporation_name or "your corporation"
    assignee = f"Corporation ({corp_name})" if order.issuer_kind == FreightOrder.IssuerKind.CORPORATION else corp_name
    lines = order.lines_json or []
    item_lines = "\n".join(f"- {row['name']} x{row['quantity']}" for row in lines)
    final = (order.final_destination_system or "").strip()
    hub = config.destination_system
    destination_note = final or hub
    if final and final.lower() != hub.lower():
        destination_note = f"{final} (freight via {hub})"
    return {
        "type": "Item Exchange",
        "assignee": assignee,
        "i_will_pay": order.contract_price_isk,
        "i_will_receive": 0,
        "expiration_hours": order.expiration_hours,
        "description": order.contract_description,
        "items": item_lines,
        "final_destination": destination_note,
        "freight_route": f"{config.origin_system} → {hub}",
        "wallet_method": order.get_wallet_method_display(),
        "steps": [
            "Open Contracts → Create Contract → Item Exchange.",
            f"Final destination: {destination_note}.",
            f"Set assignee to {assignee}.",
            f"I will pay: {order.contract_price_isk:,} ISK. I will receive: nothing (0 ISK / no items).",
            "Add each item and quantity from the list below.",
            f"Description (copy exactly): {order.contract_description}",
            f"Set expiration to approximately {order.expiration_hours} hours from now.",
            "After creating, paste the contract ID on the order page to link tracking.",
        ],
    }
