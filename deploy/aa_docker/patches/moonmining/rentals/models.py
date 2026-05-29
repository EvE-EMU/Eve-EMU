"""Lease tracking, module settings, and rental applications."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from moonmining.models import Moon


class RentalPermissions(models.Model):
    """AA group permissions for the renter module (app label ``moonrentals``)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("view_leases", _("Can view moon rental leases and available moons")),
            ("apply_rent", _("Can apply to rent a moon")),
            ("admin_management", _("Can manage moon rental settings and leases")),
        )


class RentalModuleSettings(models.Model):
    """Singleton admin configuration (no .env required)."""

    corporation_id = models.BigIntegerField(
        default=98799892,
        help_text=_("Corporation ID for wallet journal polling"),
    )
    wallet_division = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Corp wallet division (1–7)"),
    )
    payment_keyword = models.CharField(
        max_length=64,
        default="MOON-RENT-REVENUE",
        help_text=_("Substring required in wallet journal description"),
    )
    due_day_of_month = models.PositiveSmallIntegerField(
        default=1,
        validators=[],
        help_text=_("Calendar day rent is due each month (1–28)"),
    )
    grace_period_days = models.PositiveSmallIntegerField(
        default=3,
        help_text=_("Days after due date before marking overdue"),
    )
    fuel_alert_threshold_percent = models.PositiveSmallIntegerField(
        default=20,
        help_text=_("Post fuel webhook when fuel falls below this percent"),
    )
    fuel_webhook_url = models.URLField(blank=True, max_length=512)
    payment_webhook_url = models.URLField(blank=True, max_length=512)
    esi_token_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Optional django-esi Token PK for corp wallet (overrides env)"),
    )
    auto_approve_applications = models.BooleanField(
        default=False,
        help_text=_("Instantly create a lease when a renter submits an application"),
    )
    fuel_reference_hours = models.PositiveIntegerField(
        default=720,
        help_text=_("Hours of fuel treated as 100% when syncing from aa-structures"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("rental module settings")
        verbose_name_plural = _("rental module settings")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> RentalModuleSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def current_billing_period_start(self, *, on: date | None = None) -> date:
        on = on or timezone.localdate()
        day = min(self.due_day_of_month, 28)
        if on.day >= day:
            return date(on.year, on.month, day)
        prev_month = on.month - 1 or 12
        prev_year = on.year if on.month > 1 else on.year - 1
        return date(prev_year, prev_month, day)

    def due_date_for_period(self, period_start: date) -> date:
        return period_start

    def grace_deadline(self, due: date) -> date:
        return due + timedelta(days=self.grace_period_days)


class MoonLease(models.Model):
    """Active or historical rental on a surveyed moon."""

    STATUS_ACTIVE = "active"
    STATUS_GRACE = "grace"
    STATUS_EVICTED = "evicted"
    STATUS_PENDING = "pending"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, _("Active")),
        (STATUS_GRACE, _("Grace period")),
        (STATUS_EVICTED, _("Evicted")),
        (STATUS_PENDING, _("Pending")),
    )

    PAYMENT_PAID = "paid"
    PAYMENT_UNPAID = "unpaid"
    PAYMENT_OVERDUE = "overdue"
    PAYMENT_CHOICES = (
        (PAYMENT_PAID, _("Paid")),
        (PAYMENT_UNPAID, _("Unpaid")),
        (PAYMENT_OVERDUE, _("Overdue")),
    )

    moon = models.OneToOneField(
        Moon,
        on_delete=models.CASCADE,
        related_name="lease",
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    renter_corporation = models.CharField(max_length=128)
    monthly_rent_isk = models.BigIntegerField(default=0)
    main_poc = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moon_rental_poc_leases",
    )
    poc_may_view_fuel = models.BooleanField(
        default=True,
        help_text=_("POC can see fuel level in portal"),
    )
    route_structural_alerts = models.BooleanField(
        default=True,
        help_text=_("Include this lease in structural Discord alerts"),
    )
    payment_status = models.CharField(
        max_length=16,
        choices=PAYMENT_CHOICES,
        default=PAYMENT_UNPAID,
        db_index=True,
    )
    payment_reference = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text=_("Unique wallet description token for this lease"),
    )
    fuel_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=_("Last known fuel percent (manual or synced)"),
    )
    last_paid_at = models.DateTimeField(null=True, blank=True)
    billing_period_start = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.location_label} ({self.renter_corporation})"

    @property
    def location_label(self) -> str:
        moon = self.moon
        return f"{moon.solar_system().name} - {moon.eve_moon.name}"

    def ensure_payment_reference(self) -> str:
        if self.payment_reference:
            return self.payment_reference
        settings = RentalModuleSettings.load()
        ref = f"{settings.payment_keyword} {self.location_label}"
        self.payment_reference = ref[:128]
        self.save(update_fields=["payment_reference", "updated_at"])
        return self.payment_reference

    def refresh_payment_calendar(self) -> None:
        settings = RentalModuleSettings.load()
        period = settings.current_billing_period_start()
        self.billing_period_start = period
        due = settings.due_date_for_period(period)
        today = timezone.localdate()
        grace_end = settings.grace_deadline(due)
        if self.payment_status == self.PAYMENT_PAID:
            if self.last_paid_at and self.last_paid_at.date() >= period:
                return
            if today > grace_end:
                self.payment_status = self.PAYMENT_OVERDUE
                if self.status == self.STATUS_ACTIVE:
                    self.status = self.STATUS_GRACE
        elif today > grace_end:
            self.payment_status = self.PAYMENT_OVERDUE
            if self.status == self.STATUS_ACTIVE:
                self.status = self.STATUS_GRACE
        self.save(
            update_fields=[
                "billing_period_start",
                "payment_status",
                "status",
                "updated_at",
            ]
        )

    def mark_paid(self, *, when=None) -> None:
        self.payment_status = self.PAYMENT_PAID
        self.status = self.STATUS_ACTIVE
        self.last_paid_at = when or timezone.now()
        settings = RentalModuleSettings.load()
        self.billing_period_start = settings.current_billing_period_start()
        self.save(
            update_fields=[
                "payment_status",
                "status",
                "last_paid_at",
                "billing_period_start",
                "updated_at",
            ]
        )


class MoonRentalApplication(models.Model):
    """Renter application when user has apply_rent but not admin."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_APPROVED, _("Approved")),
        (STATUS_REJECTED, _("Rejected")),
    )

    moon = models.ForeignKey(Moon, on_delete=models.CASCADE, related_name="rental_applications")
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    renter_corporation = models.CharField(max_length=128)
    proposed_rent_isk = models.BigIntegerField(default=0)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
