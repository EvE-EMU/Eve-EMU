"""EMU Moons data model — bolt-on to aa-moonmining + miningtaxes observer logs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class EmuMoonsPermissions(models.Model):
    class Meta:
        managed = True
        default_permissions = ()
        permissions = (
            ("emu_moons_view_self", _("EMU Moons — view own invoices")),
            ("emu_moons_view_corp", _("EMU Moons — view corporation invoices")),
            (
                "emu_moons_view_alliance",
                _("EMU Moons — alliance reporting and naughty list"),
            ),
            ("emu_moons_admin", _("EMU Moons — configure rates, structures, webhooks")),
        )


class StructureClass(models.TextChoices):
    PUBLIC = "public", _("Public")
    NATIONALIZED = "nationalized", _("Nationalized")
    PRIVATE = "private", _("Private")


class MoonRarity(models.TextChoices):
    R4 = "r4", "R4"
    R8 = "r8", "R8"
    R16 = "r16", "R16"
    R32 = "r32", "R32"
    R64 = "r64", "R64"
    UNKNOWN = "unknown", _("Unknown")


class EmuMoonsSettings(models.Model):
    """Singleton alliance configuration."""

    tax_corp_name = models.CharField(
        max_length=128,
        default="Guns-R-Us Toy Company",
        help_text=_("Corporation receiving tax payments"),
    )
    corporation_id = models.BigIntegerField(
        default=98633922,
        help_text=_("EVE corporation ID receiving tax payments (Guns-R-Us Toy Company)"),
    )
    wallet_division = models.PositiveSmallIntegerField(default=1)
    esi_token_id = models.PositiveIntegerField(null=True, blank=True)
    ledger_match_hours = models.PositiveSmallIntegerField(
        default=48,
        help_text=_("Attribute mining in extraction system within this window after pop"),
    )
    invoice_run_weekday = models.PositiveSmallIntegerField(
        default=3,
        help_text=_("0=Monday … 3=Thursday weekly invoice batch"),
    )
    invoice_run_hour_utc = models.PositiveSmallIntegerField(default=12)
    mail_sender_name = models.CharField(max_length=64, default="El Emu Moon Tzar")
    mail_sender_character_id = models.BigIntegerField(null=True, blank=True)
    reprocess_yield = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.8500")
    )
    nationalized_extract_dow = models.PositiveSmallIntegerField(
        default=4,
        help_text=_("0=Monday … 4=Friday for nationalized schedule hint"),
    )
    nationalized_extract_hour = models.PositiveSmallIntegerField(
        default=18, help_text=_("EVE time (UTC) default pop hour for nationalized moons")
    )
    corp_liability_days = models.PositiveSmallIntegerField(default=60)
    penalty_rate_per_week = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal("1.0000"),
        help_text=_("100% = full original balance per overdue week after grace"),
    )
    grace_days_before_penalty = models.PositiveSmallIntegerField(default=30)
    tax_effective_date = models.DateField(
        default=date(2026, 6, 1),
        help_text=_(
            "No tax, penalties, or naughty-list entries before this date (inclusive)."
        ),
    )
    reminder_days_json = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Days after due for reminders, e.g. [7, 14, 21, 30]"),
    )
    alliance_logo_url = models.URLField(blank=True, max_length=512)
    tax_portal_url = models.URLField(blank=True, max_length=512)
    how_to_mine_url = models.URLField(blank=True, max_length=512)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("EMU Moons settings")

    def save(self, *args, **kwargs):
        self.pk = 1
        if not self.reminder_days_json:
            self.reminder_days_json = [7, 14, 21, 30]
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> EmuMoonsSettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class StructureTaxProfile(models.Model):
    """Tax classification for a moonmining refinery / structure."""

    moonmining_refinery_id = models.BigIntegerField(
        unique=True, null=True, blank=True, db_index=True
    )
    structure_name = models.CharField(max_length=255)
    system_name = models.CharField(max_length=128, blank=True)
    structure_class = models.CharField(
        max_length=16,
        choices=StructureClass.choices,
        default=StructureClass.PUBLIC,
    )
    private_owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emu_moons_private_structures",
        help_text=_("Member who can see this private moon on the extraction calendar"),
    )
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["structure_name"]

    def __str__(self) -> str:
        return f"{self.structure_name} ({self.get_structure_class_display()})"


class MoonTypeTaxRate(models.Model):
    """Configurable tax % by structure class and moon rarity band."""

    structure_class = models.CharField(max_length=16, choices=StructureClass.choices)
    moon_rarity = models.CharField(max_length=16, choices=MoonRarity.choices)
    tax_rate_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("structure_class", "moon_rarity"),)
        ordering = ["structure_class", "moon_rarity"]

    def __str__(self) -> str:
        return f"{self.structure_class}/{self.moon_rarity}: {self.tax_rate_percent}%"


class OrePriceSnapshot(models.Model):
    """Cached Janice-style valuation for audit."""

    type_id = models.PositiveIntegerField()
    type_name = models.CharField(max_length=128, blank=True)
    raw_isk_per_unit = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    refined_isk_per_unit = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    jita_buy_json = models.JSONField(default=dict, blank=True)
    snapshot_at = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=32, default="janice")

    class Meta:
        ordering = ["-snapshot_at", "type_name"]
        indexes = [models.Index(fields=["type_id", "-snapshot_at"])]


class EmuExtraction(models.Model):
    """One moonmining extraction tracked for invoicing."""

    moonmining_extraction_id = models.PositiveIntegerField(unique=True)
    extraction_number = models.PositiveIntegerField(db_index=True)
    moon_label = models.CharField(max_length=255)
    system_name = models.CharField(max_length=128, blank=True)
    moon_number = models.PositiveSmallIntegerField(null=True, blank=True)
    region_name = models.CharField(max_length=128, blank=True)
    structure_name = models.CharField(max_length=255, blank=True)
    structure_profile = models.ForeignKey(
        StructureTaxProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="extractions",
    )
    structure_class = models.CharField(
        max_length=16, choices=StructureClass.choices, default=StructureClass.PUBLIC
    )
    popped_at = models.DateTimeField()
    ledger_window_end = models.DateTimeField()
    invoices_generated = models.BooleanField(default=False)
    invoices_generated_at = models.DateTimeField(null=True, blank=True)
    discord_complete_sent = models.BooleanField(default=False)
    estimated_ore_value_isk = models.DecimalField(
        max_digits=20, decimal_places=2, default=0
    )
    estimated_tax_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    ore_composition_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-popped_at"]

    def __str__(self) -> str:
        return f"#{self.extraction_number} {self.moon_label}"


class EmuExtractionLedgerLine(models.Model):
    """Mining attributed to an extraction (48h system window via miningtaxes observer)."""

    extraction = models.ForeignKey(
        EmuExtraction, on_delete=models.CASCADE, related_name="ledger_lines"
    )
    miner_character_id = models.BigIntegerField()
    miner_character_name = models.CharField(max_length=128, blank=True)
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    type_id = models.PositiveIntegerField()
    type_name = models.CharField(max_length=128, blank=True)
    quantity = models.BigIntegerField(default=0)
    volume_m3 = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    gross_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    observer_log_id = models.PositiveIntegerField(null=True, blank=True)
    mined_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["miner_character_name", "type_name"]


class EmuInvoice(models.Model):
    STATUS_OPEN = "open"
    STATUS_PAID = "paid"
    STATUS_PARTIAL = "partial"
    STATUS_CORP_LIABLE = "corp_liable"
    STATUS_VOID = "void"
    STATUS_CHOICES = (
        (STATUS_OPEN, _("Open")),
        (STATUS_PARTIAL, _("Partially paid")),
        (STATUS_PAID, _("Paid")),
        (STATUS_CORP_LIABLE, _("Corporation liable")),
        (STATUS_VOID, _("Void")),
    )

    invoice_number = models.CharField(max_length=16, unique=True, db_index=True)
    extraction = models.ForeignKey(
        EmuExtraction, on_delete=models.CASCADE, related_name="invoices"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="emu_moon_invoices")
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=128, blank=True)
    corporation_id = models.BigIntegerField(null=True, blank=True)
    corporation_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    issued_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateField()
    original_tax_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    penalty_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    amount_paid_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_volume_m3 = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    mail_sent_at = models.DateTimeField(null=True, blank=True)
    mail_error = models.TextField(blank=True)
    corp_liability_at = models.DateTimeField(null=True, blank=True)
    reminders_sent_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    wallet_transaction_id = models.BigIntegerField(null=True, blank=True)
    wallet_division = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        unique_together = (("extraction", "character_id"),)

    def __str__(self) -> str:
        return self.invoice_number

    @property
    def total_due_isk(self) -> Decimal:
        return max(
            self.original_tax_isk + self.penalty_isk - self.amount_paid_isk,
            Decimal("0"),
        )

    @property
    def days_overdue(self) -> int:
        if self.status == self.STATUS_PAID:
            return 0
        return max((timezone.now().date() - self.due_at).days, 0)

    @property
    def on_naughty_list(self) -> bool:
        cfg = EmuMoonsSettings.load()
        if self.due_at < cfg.tax_effective_date:
            return False
        if self.issued_at and self.issued_at.date() < cfg.tax_effective_date:
            return False
        return self.days_overdue > cfg.grace_days_before_penalty and self.status not in (
            self.STATUS_PAID,
            self.STATUS_VOID,
        )


class EmuInvoiceLine(models.Model):
    invoice = models.ForeignKey(
        EmuInvoice, on_delete=models.CASCADE, related_name="lines"
    )
    type_id = models.PositiveIntegerField()
    ore_name = models.CharField(max_length=128)
    moon_rarity = models.CharField(max_length=16, choices=MoonRarity.choices, blank=True)
    goo_type = models.CharField(max_length=64, blank=True)
    tax_rate_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    quantity = models.BigIntegerField()
    volume_m3 = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    material_value_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    tax_due_isk = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    price_snapshot = models.ForeignKey(
        OrePriceSnapshot, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["ore_name"]


class DiscordWebhookConfig(models.Model):
    name = models.CharField(max_length=64)
    webhook_url = models.URLField(max_length=512)
    enabled = models.BooleanField(default=True)
    notification_types = models.JSONField(
        default=list,
        blank=True,
        help_text=_("List of notification type keys"),
    )
    mention_everyone = models.BooleanField(default=False)
    mention_here = models.BooleanField(default=False)
    mention_role_ids_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DiscordDeliveryLog(models.Model):
    webhook = models.ForeignKey(
        DiscordWebhookConfig, on_delete=models.CASCADE, related_name="deliveries"
    )
    notification_type = models.CharField(max_length=64)
    payload_json = models.JSONField(default=dict)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    succeeded = models.BooleanField(default=False)
    failed_permanently = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
