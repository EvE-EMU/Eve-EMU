"""Server-rendered renter management UI."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from moonmining.models import Moon

from .applications import approve_application, maybe_auto_approve_application, reject_application
from .forms import LeaseForm, RentalApplicationForm, RentalSettingsForm
from .models import MoonLease, MoonRentalApplication, RentalModuleSettings
from .services import (
    active_lease_queryset,
    available_moon_queryset,
    available_moon_to_dict,
    lease_to_dict,
)
from .structures_fuel import fuel_percent_for_moon, sync_lease_fuel_from_structures


@login_required
@permission_required("moonrentals.view_leases", raise_exception=True)
def renter_management(request):
    tab = request.GET.get("tab", "leases")
    admin = request.user.has_perm("moonrentals.admin_management")
    can_apply = request.user.has_perm("moonrentals.apply_rent")

    active = [
        lease_to_dict(row, include_admin=admin)
        for row in active_lease_queryset(for_user=None if admin else request.user)
    ]
    available = [available_moon_to_dict(m) for m in available_moon_queryset()[:200]]

    pending_applications = []
    if admin:
        pending_applications = list(
            MoonRentalApplication.objects.filter(
                status=MoonRentalApplication.STATUS_PENDING
            )
            .select_related(
                "moon",
                "moon__eve_moon",
                "moon__eve_moon__eve_planet__eve_solar_system",
                "applicant",
            )
            .order_by("-created_at")[:50]
        )

    return render(
        request,
        "moonrentals/renter_management.html",
        {
            "page_title": _("Renter Management"),
            "tab": tab,
            "active_leases": active,
            "available_moons": available,
            "pending_applications": pending_applications,
            "is_admin": admin,
            "can_apply": can_apply,
            "settings_form": RentalSettingsForm(instance=RentalModuleSettings.load())
            if admin
            else None,
        },
    )


@login_required
@require_http_methods(["POST"])
def save_settings(request):
    if not request.user.has_perm("moonrentals.admin_management"):
        messages.error(request, _("Admin permission required."))
        return redirect("moonmining:renter_management")

    settings = RentalModuleSettings.load()
    form = RentalSettingsForm(request.POST, instance=settings)
    if form.is_valid():
        form.save()
        messages.success(request, _("Rental module settings saved."))
    else:
        messages.error(request, _("Could not save settings."))
    return redirect("moonmining:renter_management")


@login_required
@require_http_methods(["GET", "POST"])
def configure_lease(request, moon_id: int):
    moon = get_object_or_404(Moon, pk=moon_id)
    admin = request.user.has_perm("moonrentals.admin_management")
    can_apply = request.user.has_perm("moonrentals.apply_rent")

    if not admin and not can_apply:
        messages.error(request, _("Permission denied."))
        return redirect("moonmining:renter_management")

    lease = MoonLease.objects.filter(moon=moon).first()
    settings = RentalModuleSettings.load()
    structure_fuel_percent = fuel_percent_for_moon(
        moon,
        reference_hours=float(settings.fuel_reference_hours),
    )

    if request.method == "POST":
        if admin:
            lease, _ = MoonLease.objects.get_or_create(
                moon=moon,
                defaults={"status": MoonLease.STATUS_ACTIVE},
            )
            form = LeaseForm(request.POST, instance=lease)
            if form.is_valid():
                lease = form.save()
                lease.ensure_payment_reference()
                sync_lease_fuel_from_structures(lease)
                messages.success(request, _("Lease saved."))
                return redirect("moonmining:renter_management")
        else:
            app_form = RentalApplicationForm(request.POST)
            if app_form.is_valid():
                application = MoonRentalApplication.objects.create(
                    moon=moon,
                    applicant=request.user,
                    **app_form.cleaned_data,
                )
                lease = maybe_auto_approve_application(application)
                if lease:
                    messages.success(
                        request,
                        _("Application approved — lease is now active."),
                    )
                else:
                    messages.success(
                        request,
                        _("Rental application submitted for review."),
                    )
                return redirect(reverse("moonmining:renter_management") + "?tab=available")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = LeaseForm(instance=lease) if admin else RentalApplicationForm()

    location = f"{moon.solar_system().name} - {moon.eve_moon.name}"
    return render(
        request,
        "moonrentals/configure_lease.html",
        {
            "page_title": _("Configure Moon Rental"),
            "moon": moon,
            "location": location,
            "form": form,
            "is_admin": admin,
            "estimated_value": int(moon.value or 0),
            "structure_fuel_percent": structure_fuel_percent,
        },
    )


@login_required
@require_http_methods(["POST"])
def evict_lease(request, lease_id: int):
    if not request.user.has_perm("moonrentals.admin_management"):
        messages.error(request, _("Admin permission required."))
        return redirect("moonmining:renter_management")
    lease = get_object_or_404(MoonLease, pk=lease_id)
    lease.status = MoonLease.STATUS_EVICTED
    lease.save(update_fields=["status", "updated_at"])
    messages.success(request, _("Lease evicted."))
    return redirect("moonmining:renter_management")


@login_required
@require_http_methods(["POST"])
def approve_application_view(request, application_id: int):
    if not request.user.has_perm("moonrentals.admin_management"):
        messages.error(request, _("Admin permission required."))
        return redirect("moonmining:renter_management")
    application = get_object_or_404(
        MoonRentalApplication,
        pk=application_id,
        status=MoonRentalApplication.STATUS_PENDING,
    )
    approve_application(application)
    messages.success(request, _("Application approved and lease created."))
    return redirect("moonmining:renter_management")


@login_required
@require_http_methods(["POST"])
def reject_application_view(request, application_id: int):
    if not request.user.has_perm("moonrentals.admin_management"):
        messages.error(request, _("Admin permission required."))
        return redirect("moonmining:renter_management")
    application = get_object_or_404(
        MoonRentalApplication,
        pk=application_id,
        status=MoonRentalApplication.STATUS_PENDING,
    )
    reject_application(application)
    messages.info(request, _("Application rejected."))
    return redirect("moonmining:renter_management")
