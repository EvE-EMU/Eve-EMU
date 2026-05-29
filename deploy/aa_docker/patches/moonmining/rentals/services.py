"""Query helpers and serializers for rental UI/API."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Q, QuerySet

from moonmining.app_settings import MOONMINING_VOLUME_PER_MONTH
from moonmining.models import Moon

from .models import MoonLease, MoonRentalApplication, RentalModuleSettings


def active_lease_queryset(*, for_user: User | None = None) -> QuerySet[MoonLease]:
    qs = (
        MoonLease.objects.filter(
            status__in=(MoonLease.STATUS_ACTIVE, MoonLease.STATUS_GRACE)
        )
        .select_related(
            "moon",
            "moon__eve_moon",
            "moon__eve_moon__eve_planet__eve_solar_system",
            "main_poc",
            "main_poc__profile",
        )
        .order_by("moon__eve_moon__eve_planet__eve_solar_system__name")
    )
    if for_user and not for_user.has_perm("moonrentals.admin_management"):
        qs = qs.filter(
            Q(main_poc=for_user)
            | Q(main_poc__isnull=True, renter_corporation__iexact="")
        )
    return qs


def available_moon_queryset() -> QuerySet[Moon]:
    """Surveyed moons with no anchored refinery and no active lease."""
    leased = MoonLease.objects.filter(
        moon_id=OuterRef("pk"),
        status__in=(MoonLease.STATUS_ACTIVE, MoonLease.STATUS_GRACE, MoonLease.STATUS_PENDING),
    )
    return (
        Moon.objects.filter(products_updated_at__isnull=False)
        .annotate(has_lease=Exists(leased))
        .filter(has_lease=False)
        .exclude(refinery__isnull=False)
        .select_related(
            "eve_moon",
            "eve_moon__eve_planet__eve_solar_system",
        )
        .order_by("-value", "eve_moon__eve_planet__eve_solar_system__name")
    )


def moon_volume_m3(moon: Moon) -> int:
    try:
        total = sum(p.amount for p in moon.products.all())
        return int(total * float(MOONMINING_VOLUME_PER_MONTH))
    except Exception:
        return 0


def suggested_rent_isk(moon: Moon) -> int:
    if moon.value:
        return int(moon.value)
    return 0


def lease_to_dict(lease: MoonLease, *, include_admin: bool = False) -> dict[str, Any]:
    settings = RentalModuleSettings.load()
    lease.refresh_payment_calendar()
    due = settings.due_date_for_period(
        lease.billing_period_start or settings.current_billing_period_start()
    )
    row = {
        "id": lease.pk,
        "moon_id": lease.moon_id,
        "moon": lease.location_label,
        "status": lease.status,
        "renter_corporation": lease.renter_corporation,
        "main_poc": lease.main_poc.username if lease.main_poc else "",
        "main_poc_id": lease.main_poc_id,
        "monthly_rent_isk": lease.monthly_rent_isk,
        "payment_status": lease.payment_status,
        "payment_due": due.isoformat(),
        "fuel_percent": lease.fuel_percent,
        "poc_may_view_fuel": lease.poc_may_view_fuel,
        "route_structural_alerts": lease.route_structural_alerts,
    }
    if include_admin:
        row["payment_reference"] = lease.ensure_payment_reference()
        row["notes"] = lease.notes
    elif lease.poc_may_view_fuel and lease.main_poc_id:
        pass
    elif not include_admin:
        row.pop("fuel_percent", None)
    return row


def available_moon_to_dict(moon: Moon) -> dict[str, Any]:
    return {
        "moon_id": moon.pk,
        "moon": f"{moon.solar_system().name} - {moon.eve_moon.name}",
        "volume_m3": moon_volume_m3(moon),
        "estimated_value_isk": int(moon.value or 0),
        "suggested_rent_isk": suggested_rent_isk(moon),
        "rarity": moon.rarity_class,
    }


def user_search_results(query: str, limit: int = 20) -> list[dict[str, Any]]:
    if not query or len(query.strip()) < 2:
        return []
    qs = (
        User.objects.filter(is_active=True)
        .filter(
            Q(username__icontains=query)
            | Q(profile__main_character__character_name__icontains=query)
        )
        .select_related("profile__main_character")[:limit]
    )
    out = []
    for user in qs:
        char = ""
        if hasattr(user, "profile") and user.profile.main_character:
            char = user.profile.main_character.character_name
        out.append(
            {
                "id": user.pk,
                "username": user.username,
                "character_name": char,
                "label": char or user.username,
            }
        )
    return out
