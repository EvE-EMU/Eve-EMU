"""Discord webhook notifications with retry logging."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests
from django.utils import timezone

from emu_moons.models import DiscordDeliveryLog, DiscordWebhookConfig, EmuExtraction, EmuMoonsSettings

logger = logging.getLogger(__name__)

RETRY_DELAYS_SEC = (60, 300, 1800, 3600)

NOTIF_EXTRACTION_COMPLETE = "extraction_complete"
NOTIF_INVOICE_GENERATED = "invoice_generated"
NOTIF_INVOICE_REMINDER = "invoice_reminder"
NOTIF_INVOICE_OVERDUE = "invoice_overdue"
NOTIF_PAYMENT_RECEIVED = "payment_received"
NOTIF_NAUGHTY_LIST = "naughty_list"
NOTIF_CORP_LIABILITY = "corp_liability"


def _mention_prefix(cfg: DiscordWebhookConfig) -> str:
    parts: list[str] = []
    if cfg.mention_everyone:
        parts.append("@everyone")
    if cfg.mention_here:
        parts.append("@here")
    for rid in cfg.mention_role_ids_json or []:
        parts.append(f"<@&{rid}>")
    return " ".join(parts)


def _post_webhook(cfg: DiscordWebhookConfig, payload: dict, notification_type: str) -> bool:
    content = payload.get("content", "")
    prefix = _mention_prefix(cfg)
    if prefix:
        payload = {**payload, "content": f"{prefix}\n{content}".strip()}

    log = DiscordDeliveryLog.objects.create(
        webhook=cfg,
        notification_type=notification_type,
        payload_json=payload,
    )
    for attempt, delay in enumerate([0, *RETRY_DELAYS_SEC]):
        if delay:
            time.sleep(min(delay, 5))  # cap sleep in worker; full delay via Celery retry task
        try:
            resp = requests.post(
                cfg.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            log.response_code = resp.status_code
            log.response_body = (resp.text or "")[:2000]
            log.retry_count = attempt
            if resp.status_code in (200, 204):
                log.succeeded = True
                log.save()
                return True
        except Exception as exc:
            log.response_body = str(exc)[:2000]
            log.retry_count = attempt
            log.save()
            logger.warning("emu_moons discord webhook failed: %s", exc)

    log.failed_permanently = True
    log.save(update_fields=["failed_permanently"])
    return False


def notify_type(notification_type: str, payload: dict) -> int:
    sent = 0
    for cfg in DiscordWebhookConfig.objects.filter(enabled=True):
        types = cfg.notification_types or []
        if types and notification_type not in types:
            continue
        if _post_webhook(cfg, payload, notification_type):
            sent += 1
    return sent


def extraction_complete_embed(extraction: EmuExtraction) -> dict:
    cfg = EmuMoonsSettings.load()
    ore_lines = extraction.ore_composition_json or []
    ore_field = "\n".join(f"• {line}" for line in ore_lines[:12]) or "(survey pending)"
    tax_lines = []
    try:
        from emu_moons.models import MoonTypeTaxRate, StructureClass

        for row in MoonTypeTaxRate.objects.filter(
            structure_class=extraction.structure_class, active=True
        ).order_by("moon_rarity"):
            tax_lines.append(f"• {row.get_moon_rarity_display()}: {row.tax_rate_percent}%")
    except Exception:
        pass
    tax_field = "\n".join(tax_lines) or "—"
    links = []
    if cfg.tax_portal_url:
        links.append(f"[💰 Tax Portal]({cfg.tax_portal_url})")
    if cfg.how_to_mine_url:
        links.append(f"[⛏️ How To Moon Mine]({cfg.how_to_mine_url})")
    return {
        "content": "",
        "embeds": [
            {
                "title": "🌕 MOON MINING EXTRACTION COMPLETE",
                "description": (
                    f"{extraction.structure_name or extraction.moon_label} has completed "
                    "extraction and is ready to mine."
                ),
                "thumbnail": {"url": cfg.alliance_logo_url} if cfg.alliance_logo_url else {},
                "fields": [
                    {"name": "System", "value": extraction.system_name or "—", "inline": True},
                    {"name": "Region", "value": extraction.region_name or "—", "inline": True},
                    {"name": "Extraction #", "value": str(extraction.extraction_number), "inline": True},
                    {
                        "name": "Structure",
                        "value": extraction.structure_name or "—",
                        "inline": False,
                    },
                    {"name": "Ore Composition", "value": ore_field[:1024], "inline": False},
                    {"name": "Tax Rates", "value": tax_field[:1024], "inline": False},
                    {
                        "name": "Links",
                        "value": "\n".join(links) or "—",
                        "inline": False,
                    },
                ],
                "footer": {"text": "EMU Moons • WOMP Moon Management System"},
            }
        ],
    }


def send_extraction_complete(extraction: EmuExtraction) -> int:
    if extraction.discord_complete_sent:
        return 0
    payload = extraction_complete_embed(extraction)
    count = notify_type(NOTIF_EXTRACTION_COMPLETE, payload)
    extraction.discord_complete_sent = True
    extraction.save(update_fields=["discord_complete_sent"])
    return count
