from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from corp_orders.models import FreightOrder

CLAIMABLE_STATUSES = frozenset(
    {
        FreightOrder.Status.PENDING_CONTRACT,
        FreightOrder.Status.CONTRACT_LINKED,
        FreightOrder.Status.IN_PROGRESS,
    }
)


def can_claim_order(order: FreightOrder) -> bool:
    if order.claimed_by_id:
        return False
    return order.status in CLAIMABLE_STATUSES


def claim_order(
    order: FreightOrder,
    *,
    user: AbstractBaseUser,
    character_id: int,
    character_name: str,
) -> bool:
    if not can_claim_order(order):
        return False
    order.claimed_by = user
    order.claimed_character_id = character_id
    order.claimed_character_name = character_name
    order.claimed_at = timezone.now()
    order.save(
        update_fields=[
            "claimed_by",
            "claimed_character_id",
            "claimed_character_name",
            "claimed_at",
            "updated_at",
        ]
    )
    return True
