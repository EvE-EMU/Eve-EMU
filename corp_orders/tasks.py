from celery import shared_task

from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.contracts import poll_order_contract
from corp_orders.services.discord import notify_new_order, refresh_new_order_discord_message


@shared_task
def notify_new_order_task(order_id: int) -> bool:
    order = FreightOrder.objects.filter(pk=order_id).first()
    if not order:
        return False
    config = FreightOrdersSettings.load()
    return notify_new_order(order, config=config)


@shared_task
def refresh_order_discord_task(order_id: int) -> bool:
    order = FreightOrder.objects.filter(pk=order_id).first()
    if not order:
        return False
    config = FreightOrdersSettings.load()
    return refresh_new_order_discord_message(order, config=config)


@shared_task
def poll_active_freight_contracts() -> int:
    """Refresh in-progress orders that have a linked EVE contract ID."""
    count = 0
    for order in FreightOrder.objects.filter(
        eve_contract_id__isnull=False,
        status__in=[
            FreightOrder.Status.CONTRACT_LINKED,
            FreightOrder.Status.IN_PROGRESS,
            FreightOrder.Status.COMPLETED,
        ],
    ):
        poll_order_contract(order)
        count += 1
    return count
