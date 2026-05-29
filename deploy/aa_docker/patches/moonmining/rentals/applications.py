"""Approve or reject moon rental applications."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction

from .models import MoonLease, MoonRentalApplication


@transaction.atomic
def approve_application(
    application: MoonRentalApplication,
    *,
    poc: User | None = None,
    monthly_rent_isk: int | None = None,
) -> MoonLease:
    """Create or update a lease from a pending application."""
    if application.status == MoonRentalApplication.STATUS_APPROVED:
        existing = MoonLease.objects.filter(moon=application.moon).first()
        if existing:
            return existing

    rent = (
        monthly_rent_isk
        if monthly_rent_isk is not None
        else application.proposed_rent_isk
    )
    lease, _created = MoonLease.objects.update_or_create(
        moon=application.moon,
        defaults={
            "renter_corporation": application.renter_corporation,
            "monthly_rent_isk": rent,
            "status": MoonLease.STATUS_ACTIVE,
            "main_poc": poc or application.applicant,
            "payment_status": MoonLease.PAYMENT_UNPAID,
        },
    )
    application.status = MoonRentalApplication.STATUS_APPROVED
    application.save(update_fields=["status"])

    lease.ensure_payment_reference()

    from .structures_fuel import sync_lease_fuel_from_structures

    sync_lease_fuel_from_structures(lease)
    return lease


def reject_application(application: MoonRentalApplication) -> None:
    application.status = MoonRentalApplication.STATUS_REJECTED
    application.save(update_fields=["status"])


def maybe_auto_approve_application(application: MoonRentalApplication) -> MoonLease | None:
    """When enabled in settings, immediately promote application to active lease."""
    from .models import RentalModuleSettings

    settings = RentalModuleSettings.load()
    if not settings.auto_approve_applications:
        return None
    return approve_application(application)
