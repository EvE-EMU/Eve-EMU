"""Celery tasks for wallet compliance and fuel alerts."""

from celery import shared_task

from allianceauth.services.hooks import get_extension_logger

logger = get_extension_logger(__name__)


@shared_task(name="moonmining.rentals.tasks.poll_rental_wallet_payments")
def poll_rental_wallet_payments() -> dict:
    from .wallet import poll_wallet_payments

    result = poll_wallet_payments()
    logger.info("moonrentals wallet poll: %s", result)
    return result


@shared_task(name="moonmining.rentals.tasks.sync_rental_fuel_from_structures")
def sync_rental_fuel_from_structures() -> dict:
    from .structures_fuel import sync_all_lease_fuel_from_structures

    result = sync_all_lease_fuel_from_structures()
    logger.info("moonrentals fuel sync: %s", result)
    return result


@shared_task(name="moonmining.rentals.tasks.check_rental_fuel_alerts")
def check_rental_fuel_alerts() -> dict:
    from django.core.cache import cache

    from .discord_notify import send_fuel_webhook
    from .models import MoonLease, RentalModuleSettings
    from .structures_fuel import sync_all_lease_fuel_from_structures

    sync_all_lease_fuel_from_structures()

    settings = RentalModuleSettings.load()
    threshold = settings.fuel_alert_threshold_percent
    sent = 0
    checked = 0
    for lease in MoonLease.objects.filter(
        status__in=(MoonLease.STATUS_ACTIVE, MoonLease.STATUS_GRACE),
        fuel_percent__isnull=False,
    ):
        checked += 1
        if lease.fuel_percent is None or lease.fuel_percent >= threshold:
            continue
        key = f"moonrentals:fuel_alert:{lease.pk}"
        if cache.get(key):
            continue
        if send_fuel_webhook(lease):
            cache.set(key, "1", timeout=60 * 60 * 12)
            sent += 1
    return {"sent": sent, "checked": checked}
