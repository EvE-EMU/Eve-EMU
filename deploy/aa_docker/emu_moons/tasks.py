"""Celery tasks for EMU Moons."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="emu_moons.tasks.sync_observer_admin")
def sync_observer_admin(character_id: int) -> bool:
    """Background corp mining observer sync after Charlink (avoids web worker timeout)."""
    from esi.models import Token
    from miningtaxes.models import AdminCharacter

    from emu_moons.observer_scopes import required_observer_scopes

    scopes = required_observer_scopes()
    if not Token.get_token(character_id, scopes):
        return False
    admin = (
        AdminCharacter.objects.filter(eve_character__character_id=character_id)
        .select_related("eve_character")
        .first()
    )
    if admin is None:
        return False
    try:
        admin.update_mining_observers()
        return True
    except Exception:
        logger.exception("emu_moons: observer sync failed for character_id=%s", character_id)
        return False


@shared_task(name="emu_moons.tasks.discover_extractions")
def discover_extractions() -> int:
    from emu_moons.services.extractions import discover_extractions_from_moonmining

    return discover_extractions_from_moonmining()


@shared_task(name="emu_moons.tasks.process_pending_invoices")
def process_pending_invoices() -> int:
    """Discover extractions, sync ledgers, generate invoices, Discord + mail."""
    from emu_moons.models import EmuExtraction
    from emu_moons.services.discord import send_extraction_complete
    from emu_moons.services.extractions import discover_extractions_from_moonmining, sync_extraction_ledger
    from emu_moons.services.invoices import generate_invoices_for_extraction
    from emu_moons.services.mail import send_invoice_mail

    discover_extractions_from_moonmining()
    from emu_moons.services.moonmining_reports import sync_miningtaxes_observers_sync

    sync_miningtaxes_observers_sync()
    total = 0
    qs = EmuExtraction.objects.filter(invoices_generated=False).order_by("popped_at")[:50]
    for ext in qs:
        sync_extraction_ledger(ext)
        total += generate_invoices_for_extraction(ext)
        if ext.invoices_generated:
            send_extraction_complete(ext)
            for inv in ext.invoices.all():
                send_invoice_mail(inv)
    return total


@shared_task(name="emu_moons.tasks.weekly_invoice_run")
def weekly_invoice_run() -> int:
    return process_pending_invoices()


@shared_task(name="emu_moons.tasks.poll_wallet_payments")
def poll_wallet_payments() -> int:
    from emu_moons.services.payments import poll_wallet_payments as poll

    return poll()


@shared_task(name="emu_moons.tasks.refresh_penalties")
def refresh_penalties() -> int:
    from emu_moons.services.invoices import refresh_penalties as refresh

    return refresh()


@shared_task(name="emu_moons.tasks.refresh_ore_prices")
def refresh_ore_prices() -> int:
    from emu_moons.services.pricing import refresh_prices_from_miningtaxes

    return refresh_prices_from_miningtaxes()


@shared_task(name="emu_moons.tasks.sync_moonmining_reports")
def sync_moonmining_reports() -> dict:
    """Member Mining tab: profiles + non-private refinery ledger import."""
    from emu_moons.services.moonmining_reports import (
        sync_miningtaxes_observers,
        sync_moonmining_member_ledgers,
    )

    sync_miningtaxes_observers()
    return sync_moonmining_member_ledgers()


@shared_task(name="emu_moons.tasks.send_reminders")
def send_reminders() -> int:
    from emu_moons.models import EmuInvoice, EmuMoonsSettings
    from emu_moons.services.mail import send_invoice_mail

    cfg = EmuMoonsSettings.load()
    days = cfg.reminder_days_json or [7, 14, 21, 30]
    sent = 0
    today = timezone.now().date()
    for inv in EmuInvoice.objects.filter(
        status=EmuInvoice.STATUS_OPEN, due_at__gte=cfg.tax_effective_date
    ):
        overdue = (today - inv.due_at).days
        if overdue not in days:
            continue
        key = str(overdue)
        if inv.reminders_sent_json.get(key):
            continue
        if send_invoice_mail(inv):
            inv.reminders_sent_json[key] = timezone.now().isoformat()
            inv.save(update_fields=["reminders_sent_json"])
            sent += 1
    return sent
