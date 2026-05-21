from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("corp_orders", "0003_freightorder_final_destination"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="freightorder",
            name="claimed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="claimed_freight_orders",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="freightorder",
            name="claimed_character_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="freightorder",
            name="claimed_character_name",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="freightorder",
            name="claimed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="freightorder",
            name="discord_message_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Discord message ID for the new-order webhook (used to edit after claim).",
                max_length=32,
            ),
        ),
        migrations.AlterModelOptions(
            name="freightorder",
            options={
                "ordering": ["-created_at"],
                "permissions": [
                    ("create_order", "Create corp stock orders"),
                    ("create_corp_contract", "Create corp stock orders (corporation wallet)"),
                    ("manage_orders", "Manage all corp stock orders"),
                    ("claim_fulfillment", "Claim corp stock order filling from Discord / AA"),
                ],
                "verbose_name": "Corp stock order",
                "verbose_name_plural": "Corp stock orders",
            },
        ),
    ]
