from __future__ import annotations

import os
import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone


def _generate_order_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "ORD-" + "".join(secrets.choice(alphabet) for _ in range(8))


class FreightOrdersSettings(models.Model):
    """Singleton-style site configuration (first row wins)."""

    origin_system = models.CharField(max_length=64, default="Jita")
    destination_system = models.CharField(max_length=64, default="Badivefi")
    pushx_api_client = models.CharField(max_length=64, default="eve-emu")
    freight_volume_threshold_m3 = models.PositiveBigIntegerField(default=360_000)
    rhea_nitrogen_isotopes = models.PositiveIntegerField(default=140_000)
    item_markup_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    god_speed_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default=1.25)
    alter_speed_multiplier = models.DecimalField(max_digits=5, decimal_places=3, default=1.15)
    new_contract_webhook_url = models.URLField(blank=True, default="")
    payback_webhook_url = models.URLField(blank=True, default="")
    default_corporation_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="EVE corporation ID for corp-side item exchange contracts.",
    )

    class Meta:
        verbose_name = "Corp stock order configuration"
        verbose_name_plural = "Corp stock order configuration"

    def __str__(self) -> str:
        return f"{self.origin_system} → {self.destination_system}"

    @classmethod
    def load(cls) -> FreightOrdersSettings:
        row = cls.objects.first()
        if not row:
            row = cls.objects.create()
        new_url = os.environ.get("CORP_ORDERS_NEW_CONTRACT_WEBHOOK", "").strip()
        pay_url = os.environ.get("CORP_ORDERS_PAYBACK_WEBHOOK", "").strip()
        pushx = os.environ.get("CORP_ORDERS_PUSHX_CLIENT", "").strip()
        updated_fields: list[str] = []
        if new_url and row.new_contract_webhook_url != new_url:
            row.new_contract_webhook_url = new_url
            updated_fields.append("new_contract_webhook_url")
        if pay_url and row.payback_webhook_url != pay_url:
            row.payback_webhook_url = pay_url
            updated_fields.append("payback_webhook_url")
        if pushx and row.pushx_api_client != pushx:
            row.pushx_api_client = pushx
            updated_fields.append("pushx_api_client")
        if updated_fields:
            row.save(update_fields=updated_fields)
        return row


class FreightOrder(models.Model):
    class Speed(models.TextChoices):
        GOD = "god", "God Speed (6 Hours or Less)"
        ALTER = "alter", "Alter Speed (66 Hours or Less)"
        REGULAR = "regular", "Regular Speed (7 Days)"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUOTED = "quoted", "Quoted"
        PENDING_CONTRACT = "pending_contract", "Awaiting in-game contract"
        CONTRACT_LINKED = "linked", "Contract linked"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        PAYBACK_SENT = "payback_sent", "Payback notified"
        CANCELLED = "cancelled", "Cancelled"

    class IssuerKind(models.TextChoices):
        CHARACTER = "character", "Character contract"
        CORPORATION = "corporation", "Corporation contract"

    class WalletMethod(models.TextChoices):
        CORP_WALLET = "corp_wallet", "Corporation wallet"
        PERSONAL = "personal", "Personal wallet (reimburse on completion)"
        OTHER = "other", "Other (see notes)"

    code = models.CharField(max_length=16, unique=True, default=_generate_order_code, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="freight_orders",
    )
    character_id = models.BigIntegerField()
    character_name = models.CharField(max_length=128)
    corporation_id = models.BigIntegerField(null=True, blank=True)
    corporation_name = models.CharField(max_length=128, blank=True, default="")
    issuer_kind = models.CharField(max_length=16, choices=IssuerKind.choices, default=IssuerKind.CHARACTER)
    speed = models.CharField(max_length=16, choices=Speed.choices, default=Speed.REGULAR)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUOTED)
    wallet_method = models.CharField(
        max_length=16,
        choices=WalletMethod.choices,
        default=WalletMethod.CORP_WALLET,
    )
    wallet_notes = models.CharField(max_length=255, blank=True, default="")
    payback_on_completion = models.BooleanField(
        default=False,
        help_text="Send payback webhook when contract completes (personal wallet).",
    )
    final_destination_system = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Officer-entered final delivery system (freight is quoted to the hub only).",
    )
    items_text = models.TextField(blank=True, default="")
    lines_json = models.JSONField(default=list)
    total_volume_m3 = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    items_subtotal_isk = models.BigIntegerField(default=0)
    freight_isk = models.BigIntegerField(default=0)
    speed_surcharge_isk = models.BigIntegerField(default=0)
    contract_price_isk = models.BigIntegerField(default=0)
    pushx_normal_isk = models.BigIntegerField(null=True, blank=True)
    pushx_rush_isk = models.BigIntegerField(null=True, blank=True)
    freight_detail_json = models.JSONField(default=dict)
    contract_description = models.CharField(max_length=500)
    expiration_hours = models.PositiveIntegerField(default=168)
    eve_contract_id = models.BigIntegerField(null=True, blank=True)
    contract_issuer_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Corp stock order"
        verbose_name_plural = "Corp stock orders"
        permissions = [
            ("create_order", "Create corp stock orders"),
            ("create_corp_contract", "Create corp stock orders (corporation wallet)"),
            ("manage_orders", "Manage all corp stock orders"),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_speed_display()})"
