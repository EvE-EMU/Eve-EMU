"""Moon Tsar data model."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MoonTsarPermissions(models.Model):
    """Placeholder model so Django creates custom auth permissions."""

    class Meta:
        managed = True
        default_permissions = ()
        permissions = (
            ("view_dashboard", _("Moon Tsar — view operations dashboard")),
            ("manage_settings", _("Moon Tsar — configure tax rates and module settings")),
            ("view_own_bills", _("Moon Tsar — view own tax bills")),
            ("view_renter_portal", _("Moon Tsar — renter moon portal")),
        )


class MoonTsarSettings(models.Model):
    """Singleton module configuration."""

    corporation_id = models.BigIntegerField(default=98799892)
    wallet_division = models.PositiveSmallIntegerField(default=1)
    tracking_hours_after_pop = models.PositiveSmallIntegerField(
        default=20,
        help_text=_("Hours after extraction pop to attribute observer ledger ore"),
    )
    tax_payment_phrase = models.CharField(
        max_length=32,
        default="MOON-TAX",
        help_text=_("Required in wallet donation reason or contract title"),
    )
    tax_isk_recipient_character_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=_("Optional EVE character ID for ISK donations (else corp wallet)"),
    )
    mineral_contract_corp_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=_("Corp that receives mineral tax contracts"),
    )
    discord_webhook_url = models.URLField(blank=True, max_length=512)
    bill_due_days_after_pop = models.PositiveSmallIntegerField(default=30)
    esi_token_id = models.PositiveIntegerField(null=True, blank=True)
    site_name_override = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Moon Tsar settings")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> MoonTsarSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class MoonOreTaxRate(models.Model):
    """Per-ore tax configuration (admin GUI)."""

    type_id = models.PositiveIntegerField(unique=True)
    type_name = models.CharField(max_length=128)
    tax_rate_percent = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("10.00")
    )
    use_adjusted_price = models.BooleanField(
        default=True,
        help_text=_("Value ore using ESI adjusted price × quantity"),
    )
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["type_name"]
        verbose_name = _("moon ore tax rate")

    def __str__(self) -> str:
        return f"{self.type_name} ({self.tax_rate_percent}%)"


class MoonExtractionEvent(models.Model):
    """Tracks one moon pop and the post-pop observation window."""

    moonmining_extraction_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    moon_label = models.CharField(max_length=255, help_text=_("System — Moon N"))
    system_name = models.CharField(max_length=128, blank=True)
    moon_number = models.PositiveSmallIntegerField(null=True, blank=True)
    structure_name = models.CharField(max_length=255, blank=True)
    popped_at = models.DateTimeField()
    tracking_ends_at = models.DateTimeField()
    ledger_synced_at = models.DateTimeField(null=True, blank=True)
    bills_generated_at = models.DateTimeField(null=True, blank=True)
    total_mined_m3 = models.BigIntegerField(default=0)
    total_ore_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_tax_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-popped_at"]

    def __str__(self) -> str:
        return f"{self.moon_label} @ {self.popped_at:%Y-%m-%d %H:%M}"

    @property
    def tracking_active(self) -> bool:
        return timezone.now() <= self.tracking_ends_at


class MoonExtractionLedgerLine(models.Model):
    extraction = models.ForeignKey(
        MoonExtractionEvent, on_delete=models.CASCADE, related_name="ledger_lines"
    )
    miner_character_id = models.BigIntegerField()
    miner_character_name = models.CharField(max_length=128, blank=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    type_id = models.PositiveIntegerField()
    type_name = models.CharField(max_length=128, blank=True)
    quantity = models.BigIntegerField()
    volume_m3 = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    gross_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    tax_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    observer_log_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    mined_at = models.DateField()

    class Meta:
        ordering = ["-mined_at", "miner_character_name"]


class MoonTaxBill(models.Model):
    """Invoice for one miner for one extraction."""

    STATUS_OPEN = "open"
    STATUS_PARTIAL = "partial"
    STATUS_PAID = "paid"
    STATUS_VOID = "void"
    STATUS_CHOICES = (
        (STATUS_OPEN, _("Open")),
        (STATUS_PARTIAL, _("Partially paid")),
        (STATUS_PAID, _("Paid")),
        (STATUS_VOID, _("Void")),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    extraction = models.ForeignKey(
        MoonExtractionEvent, on_delete=models.CASCADE, related_name="bills"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="moon_tax_bills")
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    due_date = models.DateField()
    total_m3 = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_gross_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_tax_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    amount_paid_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    line_summary_json = models.JSONField(default=list, blank=True)
    reminder_30d_sent = models.DateTimeField(null=True, blank=True)
    reminder_7d_sent = models.DateTimeField(null=True, blank=True)
    reminder_1d_sent = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-due_date", "character_name"]
        unique_together = (("extraction", "user"),)

    def __str__(self) -> str:
        return f"Bill {self.public_id} — {self.character_name}"

    @property
    def balance_isk(self) -> Decimal:
        return max(self.total_tax_isk - self.amount_paid_isk, Decimal("0"))

    @property
    def payment_reference(self) -> str:
        return f"MT-BILL-{self.public_id.hex[:12].upper()}"


class MoonTaxPayment(models.Model):
    SOURCE_WALLET = "wallet"
    SOURCE_CONTRACT = "contract"
    SOURCE_CHOICES = (
        (SOURCE_WALLET, _("Corp wallet donation")),
        (SOURCE_CONTRACT, _("Item exchange contract")),
    )

    bill = models.ForeignKey(MoonTaxBill, on_delete=models.CASCADE, related_name="payments")
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    amount_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    external_id = models.CharField(max_length=64, blank=True)
    note = models.CharField(max_length=512, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]


class MoonRentalProfile(models.Model):
    """Private renter mode for a specific moon (extends lease concept)."""

    moon_label = models.CharField(max_length=255, unique=True)
    moonmining_moon_id = models.PositiveIntegerField(null=True, blank=True)
    renter_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="rented_moons"
    )
    renter_corporation_id = models.BigIntegerField(null=True, blank=True)
    renter_corporation_name = models.CharField(max_length=255, blank=True)
    monthly_rent_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    rent_payment_phrase = models.CharField(max_length=64, default="MOON-RENT-PRIVATE")
    custom_tax_rates_json = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.moon_label


class MoonProfitabilitySnapshot(models.Model):
    """Daily rollup: ore value vs fuel cost for alliance moons."""

    snapshot_date = models.DateField()
    total_mined_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_tax_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_fuel_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    net_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    extraction_count = models.PositiveIntegerField(default=0)
    meta_json = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = (("snapshot_date",),)
        ordering = ["-snapshot_date"]


class MoonHeatmapCell(models.Model):
    """Aggregated mining intensity per moon for heatmap UI."""

    period_start = models.DateField()
    period_end = models.DateField()
    system_name = models.CharField(max_length=128)
    moon_number = models.PositiveSmallIntegerField()
    moon_label = models.CharField(max_length=255)
    mined_m3 = models.BigIntegerField(default=0)
    expected_m3 = models.BigIntegerField(default=0)
    extraction_count = models.PositiveIntegerField(default=0)
    performance_score = models.FloatField(
        default=0.0,
        help_text=_("0–1 ratio mined vs expected"),
    )

    class Meta:
        unique_together = (("period_start", "period_end", "moon_label"),)
        ordering = ["-performance_score"]
