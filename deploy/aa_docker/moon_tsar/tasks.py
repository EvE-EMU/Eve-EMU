"""Celery tasks for Moon Tsar."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="moon_tsar.tasks.discover_extractions")
def discover_extractions() -> int:
    from moon_tsar.services.extraction import discover_extractions_from_moonmining

    return discover_extractions_from_moonmining()


@shared_task(name="moon_tsar.tasks.sync_extraction_ledgers")
def sync_extraction_ledgers() -> int:
    from moon_tsar.services.extraction import sync_all_active_extractions

    return sync_all_active_extractions()


@shared_task(name="moon_tsar.tasks.generate_pending_bills")
def generate_pending_bills() -> int:
    from moon_tsar.services.billing import generate_all_pending_bills

    return generate_all_pending_bills()


@shared_task(name="moon_tsar.tasks.poll_tax_payments")
def poll_tax_payments() -> int:
    from moon_tsar.services.payments import poll_wallet_tax_payments

    return poll_wallet_tax_payments()


@shared_task(name="moon_tsar.tasks.send_bill_reminders")
def send_bill_reminders() -> int:
    from moon_tsar.services.discord_bills import send_due_reminders

    return send_due_reminders()


@shared_task(name="moon_tsar.tasks.refresh_heatmap")
def refresh_heatmap() -> int:
    from django.utils import timezone

    from moon_tsar.services.heatmap import refresh_heatmap_for_period

    end = timezone.localdate()
    start = end.replace(day=1)
    return refresh_heatmap_for_period(start, end)


@shared_task(name="moon_tsar.tasks.refresh_profitability_snapshots")
def refresh_profitability_snapshots() -> int:
    from django.utils import timezone

    from moon_tsar.models import MoonExtractionEvent, MoonProfitabilitySnapshot

    today = timezone.localdate()
    agg = MoonExtractionEvent.objects.filter(popped_at__date=today)
    mined = sum(e.total_ore_isk for e in agg)
    tax = sum(e.total_tax_isk for e in agg)
    MoonProfitabilitySnapshot.objects.update_or_create(
        snapshot_date=today,
        defaults={
            "total_mined_isk": mined,
            "total_tax_isk": tax,
            "total_fuel_isk": 0,
            "net_isk": mined - tax,
            "extraction_count": agg.count(),
        },
    )
    return 1
