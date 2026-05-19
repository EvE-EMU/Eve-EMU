# Generated manually for corp_orders

import corp_orders.models
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FreightOrdersSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origin_system", models.CharField(default="Jita", max_length=64)),
                ("destination_system", models.CharField(default="Badivefi", max_length=64)),
                ("pushx_api_client", models.CharField(default="eve-emu", max_length=64)),
                ("freight_volume_threshold_m3", models.PositiveBigIntegerField(default=360000)),
                ("rhea_nitrogen_isotopes", models.PositiveIntegerField(default=140000)),
                ("item_markup_percent", models.DecimalField(decimal_places=2, default=10, max_digits=5)),
                ("god_speed_multiplier", models.DecimalField(decimal_places=3, default=1.25, max_digits=5)),
                ("alter_speed_multiplier", models.DecimalField(decimal_places=3, default=1.15, max_digits=5)),
                ("new_contract_webhook_url", models.URLField(blank=True, default="")),
                ("payback_webhook_url", models.URLField(blank=True, default="")),
                ("default_corporation_id", models.BigIntegerField(blank=True, help_text="EVE corporation ID for corp-side item exchange contracts.", null=True)),
            ],
            options={
                "verbose_name": "Corp orders configuration",
                "verbose_name_plural": "Corp orders configuration",
            },
        ),
        migrations.CreateModel(
            name="FreightOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(default=corp_orders.models._generate_order_code, editable=False, max_length=16, unique=True)),
                ("character_id", models.BigIntegerField()),
                ("character_name", models.CharField(max_length=128)),
                ("corporation_id", models.BigIntegerField(blank=True, null=True)),
                ("corporation_name", models.CharField(blank=True, default="", max_length=128)),
                ("issuer_kind", models.CharField(choices=[("character", "Character contract"), ("corporation", "Corporation contract")], default="character", max_length=16)),
                ("speed", models.CharField(choices=[("god", "God Speed (6 Hours or Less)"), ("alter", "Alter Speed (66 Hours or Less)"), ("regular", "Regular Speed (7 Days)")], default="regular", max_length=16)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("quoted", "Quoted"), ("pending_contract", "Awaiting in-game contract"), ("linked", "Contract linked"), ("in_progress", "In progress"), ("completed", "Completed"), ("payback_sent", "Payback notified"), ("cancelled", "Cancelled")], default="quoted", max_length=24)),
                ("wallet_method", models.CharField(choices=[("corp_wallet", "Corporation wallet"), ("personal", "Personal wallet (reimburse on completion)"), ("other", "Other (see notes)")], default="corp_wallet", max_length=16)),
                ("wallet_notes", models.CharField(blank=True, default="", max_length=255)),
                ("payback_on_completion", models.BooleanField(default=False, help_text="Send payback webhook when contract completes (personal wallet).")),
                ("items_text", models.TextField(blank=True, default="")),
                ("lines_json", models.JSONField(default=list)),
                ("total_volume_m3", models.DecimalField(decimal_places=2, default=0, max_digits=20)),
                ("items_subtotal_isk", models.BigIntegerField(default=0)),
                ("freight_isk", models.BigIntegerField(default=0)),
                ("speed_surcharge_isk", models.BigIntegerField(default=0)),
                ("contract_price_isk", models.BigIntegerField(default=0)),
                ("pushx_normal_isk", models.BigIntegerField(blank=True, null=True)),
                ("pushx_rush_isk", models.BigIntegerField(blank=True, null=True)),
                ("freight_detail_json", models.JSONField(default=dict)),
                ("contract_description", models.CharField(max_length=500)),
                ("expiration_hours", models.PositiveIntegerField(default=168)),
                ("eve_contract_id", models.BigIntegerField(blank=True, null=True)),
                ("contract_issuer_id", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="freight_orders", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "permissions": [("create_order", "Create freight purchase orders"), ("create_corp_contract", "Create orders billed to corporation wallet"), ("manage_orders", "Manage all freight orders")],
            },
        ),
    ]
