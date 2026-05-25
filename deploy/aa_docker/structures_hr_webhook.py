"""Route aa-structures HR / membership notifications to a dedicated Discord webhook.

Join messages like ``Eveeno joins False Gods`` are ``CharAppAcceptMsg`` embeds from
``structures.core.notification_embeds.corporate_embeds.NotificationCharAppAcceptMsg``.
They are sent to every active Owner webhook whose ``notification_types`` includes
that type — typically a catch-all webhook posting to a general channel.

Set ``AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL`` to a webhook for your HR channel; on boot
(or via ``manage.py structures_hr_webhook_sync``) this module creates/updates an HR-only
webhook and removes those types from named catch-all webhooks.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

from corptools_corp_token import FALSE_GODS_CORP_ID

logger = logging.getLogger(__name__)

DEFAULT_HR_NOTIFICATION_TYPES: tuple[str, ...] = (
    "CharAppAcceptMsg",
    "CharLeftCorpMsg",
    "CorpAppNewMsg",
    "CorpAppInvitedMsg",
    "CharAppRejectMsg",
    "CorpAppRejectCustomMsg",
    "CharAppWithdrawMsg",
)

DEFAULT_HR_WEBHOOK_NAME = "False Gods HR"
DEFAULT_STRIP_HR_FROM_WEBHOOK_NAMES = ("ALL WEBHOOKS TESTING",)


def _truthy(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def structures_hr_webhook_enabled() -> bool:
    return bool(os.environ.get("AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL", "").strip())


def _hr_webhook_url() -> str | None:
    raw = os.environ.get("AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL", "").strip()
    if not raw:
        return None
    if not raw.startswith("https://discord.com/api/webhooks/"):
        logger.warning(
            "structures_hr_webhook: AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL is not a "
            "Discord webhook URL (ignored)"
        )
        return None
    return raw


def _parse_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _parse_hr_notification_types() -> list[str]:
    try:
        from structures.models.notifications import NotificationType
    except ImportError:
        return list(DEFAULT_HR_NOTIFICATION_TYPES)

    allowed = {choice[0] for choice in NotificationType.choices}
    requested = _parse_csv_env(
        "AA_STRUCTURES_HR_NOTIFICATION_TYPES",
        DEFAULT_HR_NOTIFICATION_TYPES,
    )
    valid = [t for t in requested if t in allowed]
    skipped = [t for t in requested if t not in allowed]
    if skipped:
        logger.warning(
            "structures_hr_webhook: unknown notification types ignored: %s",
            ", ".join(skipped),
        )
    return valid or list(DEFAULT_HR_NOTIFICATION_TYPES)


def _corp_id() -> int:
    raw = os.environ.get("AA_STRUCTURES_HR_CORP_ID", str(FALSE_GODS_CORP_ID)).strip()
    try:
        return int(raw)
    except ValueError:
        return FALSE_GODS_CORP_ID


def _strip_hr_from_types(
    notification_types: Iterable[str], hr_types: set[str]
) -> list[str]:
    return [t for t in notification_types if t not in hr_types]


def sync_structures_hr_webhook(*, dry_run: bool = False) -> dict[str, object]:
    """Create/update HR webhook and remove HR types from catch-all webhooks."""
    url = _hr_webhook_url()
    if not url:
        return {"skipped": True, "reason": "no AA_STRUCTURES_HR_DISCORD_WEBHOOK_URL"}

    try:
        from django.db import transaction

        from structures.models import Owner, Webhook
    except ImportError:
        logger.warning("structures_hr_webhook: structures app not installed")
        return {"skipped": True, "reason": "structures not installed"}

    corp_id = _corp_id()
    owner = (
        Owner.objects.filter(corporation__corporation_id=corp_id, is_active=True)
        .first()
    )
    if owner is None:
        logger.warning(
            "structures_hr_webhook: no active Owner for corporation %s", corp_id
        )
        return {"skipped": True, "reason": f"no owner for corp {corp_id}"}

    hr_types = set(_parse_hr_notification_types())
    hr_name = os.environ.get(
        "AA_STRUCTURES_HR_WEBHOOK_NAME", DEFAULT_HR_WEBHOOK_NAME
    ).strip() or DEFAULT_HR_WEBHOOK_NAME
    strip_names = set(
        _parse_csv_env(
            "AA_STRUCTURES_STRIP_HR_FROM_WEBHOOK_NAMES",
            DEFAULT_STRIP_HR_FROM_WEBHOOK_NAMES,
        )
    )

    result: dict[str, object] = {
        "corp_id": corp_id,
        "hr_webhook_name": hr_name,
        "hr_types": sorted(hr_types),
        "stripped_from": [],
        "dry_run": dry_run,
    }

    if dry_run:
        result["would_set_hr_webhook_url"] = url[:48] + "…"
        result["would_strip_from"] = sorted(strip_names)
        return result

    with transaction.atomic():
        hr_webhook, created = Webhook.objects.get_or_create(
            name=hr_name,
            defaults={
                "url": url,
                "is_active": True,
                "webhook_type": 1,
                "notification_types": sorted(hr_types),
            },
        )
        updated_fields: list[str] = []
        if hr_webhook.url != url:
            hr_webhook.url = url
            updated_fields.append("url")
        if not hr_webhook.is_active:
            hr_webhook.is_active = True
            updated_fields.append("is_active")
        current_hr = set(hr_webhook.notification_types or [])
        if current_hr != hr_types:
            hr_webhook.notification_types = sorted(hr_types)
            updated_fields.append("notification_types")
        if updated_fields:
            hr_webhook.save(update_fields=updated_fields)

        if not hr_webhook.owners.filter(pk=owner.pk).exists():
            hr_webhook.owners.add(owner)

        result["hr_webhook_id"] = hr_webhook.pk
        result["hr_webhook_created"] = created
        result["hr_webhook_updated_fields"] = updated_fields

        for webhook in owner.webhooks.filter(name__in=strip_names).exclude(pk=hr_webhook.pk):
            before = list(webhook.notification_types or [])
            after = _strip_hr_from_types(before, hr_types)
            if before == after:
                continue
            webhook.notification_types = after
            webhook.save(update_fields=["notification_types"])
            result["stripped_from"].append(
                {"name": webhook.name, "removed": sorted(hr_types & set(before))}
            )

    logger.info("structures_hr_webhook: sync complete %s", result)
    return result


def maybe_sync_structures_hr_webhook() -> None:
    if not _truthy("AA_STRUCTURES_HR_WEBHOOK_SYNC_ON_BOOT", "1"):
        return
    if not structures_hr_webhook_enabled():
        return
    try:
        sync_structures_hr_webhook()
    except Exception:
        logger.exception("structures_hr_webhook: sync failed")
