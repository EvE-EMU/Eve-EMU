"""Tax bill generation."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from moon_tsar.models import MoonExtractionEvent, MoonTaxBill, MoonTsarSettings


@transaction.atomic
def generate_bills_for_extraction(event: MoonExtractionEvent) -> int:
    if event.bills_generated_at:
        return 0
    settings = MoonTsarSettings.load()
    due = (event.popped_at + timedelta(days=settings.bill_due_days_after_pop)).date()
    by_user: dict[int, dict] = defaultdict(
        lambda: {
            "character_id": 0,
            "character_name": "",
            "m3": Decimal("0"),
            "gross": Decimal("0"),
            "tax": Decimal("0"),
            "lines": [],
        }
    )
    for line in event.ledger_lines.select_related("user").iterator():
        if not line.user_id:
            continue
        bucket = by_user[line.user_id]
        bucket["character_id"] = line.miner_character_id
        bucket["character_name"] = line.miner_character_name or line.type_name
        bucket["m3"] += line.volume_m3
        bucket["gross"] += line.gross_isk
        bucket["tax"] += line.tax_isk
        bucket["lines"].append(
            {
                "type": line.type_name,
                "qty": line.quantity,
                "tax_isk": str(line.tax_isk),
            }
        )

    created = 0
    for user_id, data in by_user.items():
        if data["tax"] <= 0:
            continue
        _, was_created = MoonTaxBill.objects.get_or_create(
            extraction=event,
            user_id=user_id,
            defaults={
                "character_id": data["character_id"],
                "character_name": data["character_name"],
                "due_date": due,
                "total_m3": data["m3"],
                "total_gross_isk": data["gross"],
                "total_tax_isk": data["tax"],
                "line_summary_json": data["lines"],
            },
        )
        if was_created:
            created += 1

    event.bills_generated_at = timezone.now()
    event.save(update_fields=["bills_generated_at"])
    return created


def generate_all_pending_bills() -> int:
    total = 0
    for event in MoonExtractionEvent.objects.filter(bills_generated_at__isnull=True):
        if event.ledger_lines.exists():
            total += generate_bills_for_extraction(event)
    return total
