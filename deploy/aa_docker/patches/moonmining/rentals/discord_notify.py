"""Discord webhook payloads for fuel and payment events."""

from __future__ import annotations

import logging

import requests

from .models import MoonLease, RentalModuleSettings

logger = logging.getLogger(__name__)


def _post_webhook(url: str, payload: dict) -> bool:
    if not url:
        return False
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code in (200, 204):
            return True
        logger.warning(
            "moonrentals webhook HTTP %s: %s",
            resp.status_code,
            (resp.text or "")[:200],
        )
    except requests.RequestException:
        logger.exception("moonrentals webhook failed")
    return False


def send_fuel_webhook(lease: MoonLease) -> bool:
    settings = RentalModuleSettings.load()
    if not settings.fuel_webhook_url or not lease.route_structural_alerts:
        return False
    fuel = lease.fuel_percent if lease.fuel_percent is not None else 0
    poc_ping = ""
    if lease.main_poc_id:
        try:
            from discord.models import DiscordUser

            du = DiscordUser.objects.filter(user=lease.main_poc).first()
            if du and du.uid:
                poc_ping = f"<@{du.uid}>"
        except Exception:
            pass
    embed = {
        "title": "⚠️ LOW FUEL ALERT: Structure Asset Compromised",
        "color": 15158332,
        "fields": [
            {"name": "Location", "value": lease.location_label, "inline": True},
            {"name": "Assigned Renter", "value": lease.renter_corporation, "inline": True},
            {
                "name": "Current Fuel Status",
                "value": f"**{fuel}% Remaining**",
                "inline": False,
            },
            {"name": "Primary POC Pings", "value": poc_ping or "—", "inline": False},
        ],
    }
    return _post_webhook(settings.fuel_webhook_url, {"embeds": [embed]})


def send_payment_webhook(lease: MoonLease, *, amount_isk: int) -> bool:
    settings = RentalModuleSettings.load()
    if not settings.payment_webhook_url:
        return False
    embed = {
        "title": "💰 RENTAL LEDGER UPDATE: Payment Received",
        "color": 3066993,
        "fields": [
            {"name": "Asset Lease Location", "value": lease.location_label, "inline": True},
            {"name": "Payer Corp", "value": lease.renter_corporation, "inline": True},
            {
                "name": "Transaction Value",
                "value": f"{amount_isk:,} ISK",
                "inline": True,
            },
            {
                "name": "Ledger Standing",
                "value": "Account marked **PAID** for current billing cycle.",
                "inline": False,
            },
        ],
    }
    return _post_webhook(settings.payment_webhook_url, {"embeds": [embed]})
