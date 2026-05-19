from __future__ import annotations

from corp_orders.models import FreightOrder

TERMINAL_STATUSES = frozenset(
    {
        FreightOrder.Status.COMPLETED,
        FreightOrder.Status.PAYBACK_SENT,
        FreightOrder.Status.CANCELLED,
    }
)

CANCELLABLE_STATUSES = frozenset(
    {
        FreightOrder.Status.DRAFT,
        FreightOrder.Status.QUOTED,
        FreightOrder.Status.PENDING_CONTRACT,
        FreightOrder.Status.CONTRACT_LINKED,
        FreightOrder.Status.IN_PROGRESS,
    }
)


def can_cancel_order(order: FreightOrder) -> bool:
    return order.status in CANCELLABLE_STATUSES


def cancel_order(order: FreightOrder) -> bool:
    """Mark order cancelled. Returns False if already terminal."""
    if not can_cancel_order(order):
        return False
    order.status = FreightOrder.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    return True
