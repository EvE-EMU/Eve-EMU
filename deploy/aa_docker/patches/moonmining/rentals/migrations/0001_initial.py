# Generated for eve-emu moon rental module

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("moonmining", "0007_add_localization"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RentalPermissions",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "permissions": (
                    (
                        "view_leases",
                        "Can view moon rental leases and available moons",
                    ),
                    ("apply_rent", "Can apply to rent a moon"),
                    (
                        "admin_management",
                        "Can manage moon rental settings and leases",
                    ),
                ),
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="RentalModuleSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("corporation_id", models.BigIntegerField(default=98799892)),
                ("wallet_division", models.PositiveSmallIntegerField(default=1)),
                (
                    "payment_keyword",
                    models.CharField(default="MOON-RENT-REVENUE", max_length=64),
                ),
                ("due_day_of_month", models.PositiveSmallIntegerField(default=1)),
                ("grace_period_days", models.PositiveSmallIntegerField(default=3)),
                (
                    "fuel_alert_threshold_percent",
                    models.PositiveSmallIntegerField(default=20),
                ),
                ("fuel_webhook_url", models.URLField(blank=True, max_length=512)),
                ("payment_webhook_url", models.URLField(blank=True, max_length=512)),
                (
                    "esi_token_id",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "rental module settings",
                "verbose_name_plural": "rental module settings",
            },
        ),
        migrations.CreateModel(
            name="MoonLease",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("grace", "Grace period"),
                            ("evicted", "Evicted"),
                            ("pending", "Pending"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=16,
                    ),
                ),
                ("renter_corporation", models.CharField(max_length=128)),
                ("monthly_rent_isk", models.BigIntegerField(default=0)),
                ("poc_may_view_fuel", models.BooleanField(default=True)),
                ("route_structural_alerts", models.BooleanField(default=True)),
                (
                    "payment_status",
                    models.CharField(
                        choices=[
                            ("paid", "Paid"),
                            ("unpaid", "Unpaid"),
                            ("overdue", "Overdue"),
                        ],
                        db_index=True,
                        default="unpaid",
                        max_length=16,
                    ),
                ),
                (
                    "payment_reference",
                    models.CharField(blank=True, db_index=True, max_length=128),
                ),
                ("fuel_percent", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("last_paid_at", models.DateTimeField(blank=True, null=True)),
                ("billing_period_start", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "main_poc",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="moon_rental_poc_leases",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "moon",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lease",
                        to="moonmining.moon",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="MoonRentalApplication",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("renter_corporation", models.CharField(max_length=128)),
                ("proposed_rent_isk", models.BigIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "applicant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "moon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rental_applications",
                        to="moonmining.moon",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
