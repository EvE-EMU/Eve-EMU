"""Discord webhook reminders for tax bills."""

from __future__ import annotations

import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from moon_tsar.models import MoonTaxBill, MoonTsarSettings

logger = logging.getLogger(__name__)


def _site_url() -> str:
    return getattr(settings, "SITE_URL", "https://auth.eve-emu.com").rstrip("/")


def bill_url(bill: MoonTaxBill) -> str:
    return f"{_site_url()}/moon-tsar/bill/{bill.public_id}/"


def send_bill_embed(bill: MoonTaxBill, *, days_until_due: int) -> bool:
    cfg = MoonTsarSettings.load()
    webhook = cfg.discord_webhook_url.strip()
    if not webhook:
        return False
    embed = {
        "title": f"Moon tax due in {days_until_due} day(s)",
        "description": (
            f"**{bill.character_name}** — {bill.extraction.moon_label}\n"
            f"Tax owed: **{bill.balance_isk:,.0f} ISK**\n"
            f"Due: **{bill.due_date}**\n"
            f"Reference: `{bill.payment_reference}`\n"
            f"[View bill]({bill_url(bill)})"
        ),
        "color": 0xE67E22 if days_until_due <= 1 else 0xF1C40F,
    }
    try:
        resp = requests.post(webhook, json={"embeds": [embed]}, timeout=15)
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("moon_tsar Discord webhook failed for bill %s", bill.public_id)
        return False


def send_due_reminders() -> int:
    today = timezone.localdate()
    sent = 0
    for days, field in ((30, "reminder_30d_sent"), (7, "reminder_7d_sent"), (1, "reminder_1d_sent")):
        target = today + timedelta(days=days)
        qs = MoonTaxBill.objects.filter(
            due_date=target,
            status__in=(MoonTaxBill.STATUS_OPEN, MoonTaxBill.STATUS_PARTIAL),
            **{f"{field}__isnull": True},
        ).select_related("extraction", "user")
        for bill in qs:
            if send_bill_embed(bill, days_until_due=days):
                setattr(bill, field, timezone.now())
                bill.save(update_fields=[field])
                sent += 1
    return sent
