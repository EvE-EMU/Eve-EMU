"""Seed Moon Tsar with demo data for screenshots (idempotent for demo moon)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from moon_tsar.models import (
    MoonExtractionEvent,
    MoonExtractionLedgerLine,
    MoonHeatmapCell,
    MoonOreTaxRate,
    MoonProfitabilitySnapshot,
    MoonRentalProfile,
    MoonTaxBill,
    MoonTaxPayment,
    MoonTsarSettings,
)

User = get_user_model()

DEMO_MOON_LABEL = "9SBB-9 VII - Moon 20"
DEMO_SYSTEM = "9SBB-9 VII"
DEMO_MOON_NUM = 20
DEMO_POPPED = datetime(2026, 5, 28, 19, 0, 0, tzinfo=timezone.utc)

DEMO_ORES = [
    (16634, "Gneiss", Decimal("12.00"), 84200, Decimal("18400000"), Decimal("2208000")),
    (16635, "Gneiss", Decimal("12.00"), 61500, Decimal("13450000"), Decimal("1614000")),
    (16636, "Dark Ochre", Decimal("15.00"), 42100, Decimal("11200000"), Decimal("1680000")),
    (16637, "Spodumain", Decimal("10.00"), 38800, Decimal("9800000"), Decimal("980000")),
    (16638, "Crokite", Decimal("18.00"), 15200, Decimal("7200000"), Decimal("1296000")),
]


class Command(BaseCommand):
    help = "Seed demo Moon Tsar data for 9SBB-9 VII - Moon 20 (screenshots)."

    def handle(self, *args, **options):
        settings = MoonTsarSettings.load()
        settings.tracking_hours_after_pop = 20
        settings.tax_payment_phrase = "MOON-TAX"
        settings.bill_due_days_after_pop = 30
        settings.save()

        for type_id, name, rate, *_ in DEMO_ORES:
            MoonOreTaxRate.objects.update_or_create(
                type_id=type_id,
                defaults={
                    "type_name": name,
                    "tax_rate_percent": rate,
                    "active": True,
                },
            )

        tracking_end = DEMO_POPPED + timedelta(hours=settings.tracking_hours_after_pop)
        event, _ = MoonExtractionEvent.objects.update_or_create(
            moon_label=DEMO_MOON_LABEL,
            popped_at=DEMO_POPPED,
            defaults={
                "moonmining_extraction_id": 902028,
                "system_name": DEMO_SYSTEM,
                "moon_number": DEMO_MOON_NUM,
                "structure_name": "9SBB-9 - W O M P S T A R Athanor",
                "tracking_ends_at": tracking_end,
                "ledger_synced_at": timezone.now(),
                "bills_generated_at": timezone.now(),
                "total_mined_m3": 241800,
                "total_ore_isk": Decimal("59050000"),
                "total_tax_isk": Decimal("7808000"),
            },
        )
        event.ledger_synced_at = timezone.now()
        event.bills_generated_at = timezone.now()
        event.total_mined_m3 = 241800
        event.total_ore_isk = Decimal("59050000")
        event.total_tax_isk = Decimal("7808000")
        event.save()

        MoonExtractionLedgerLine.objects.filter(extraction=event).delete()

        users = list(User.objects.filter(is_active=True).order_by("id")[:5])
        if not users:
            self.stderr.write("No active users — create at least one AA user first.")
            return

        miners = [
            ("Maximus Tittus", 2124049845, 0),
            ("Lamaashtu", 2124394355, 1),
            ("KING_RENEGADE", 2117258419, 2),
            ("Servath Kreoss", 2121651112, 3),
            ("Ata Glance", 2120000001, 4),
        ]
        line_idx = 0
        for type_id, name, rate, qty, gross, tax in DEMO_ORES:
            for mname, mid, uidx in miners[:3]:
                u = users[uidx % len(users)]
                MoonExtractionLedgerLine.objects.create(
                    extraction=event,
                    miner_character_id=mid,
                    miner_character_name=mname,
                    user=u,
                    type_id=type_id + line_idx,
                    type_name=name,
                    quantity=qty // 3,
                    volume_m3=Decimal(qty // 3) * Decimal("0.15"),
                    gross_isk=gross / 3,
                    tax_isk=tax / 3,
                    mined_at=DEMO_POPPED.date(),
                )
                line_idx += 1

        due = (DEMO_POPPED + timedelta(days=30)).date()
        bill_specs = [
            (miners[0][0], miners[0][1], users[0], Decimal("2840000"), "open"),
            (miners[1][0], miners[1][1], users[1 % len(users)], Decimal("1920000"), "partial"),
            (miners[2][0], miners[2][1], users[2 % len(users)], Decimal("1650000"), "paid"),
            (miners[3][0], miners[3][1], users[3 % len(users)], Decimal("980000"), "open"),
        ]
        for cname, cid, user, tax_isk, status in bill_specs:
            bill, _ = MoonTaxBill.objects.update_or_create(
                extraction=event,
                user=user,
                defaults={
                    "character_id": cid,
                    "character_name": cname,
                    "due_date": due,
                    "total_m3": Decimal("42000"),
                    "total_gross_isk": tax_isk * 8,
                    "total_tax_isk": tax_isk,
                    "line_summary_json": [
                        {"type": "Gneiss", "qty": 28000, "tax_isk": str(tax_isk * 6 // 10)},
                        {"type": "Dark Ochre", "qty": 14000, "tax_isk": str(tax_isk * 4 // 10)},
                    ],
                    "status": status,
                    "amount_paid_isk": tax_isk if status == "paid" else (tax_isk // 2 if status == "partial" else 0),
                    "paid_at": timezone.now() if status == "paid" else None,
                },
            )
            if status == "paid" and not bill.payments.exists():
                MoonTaxPayment.objects.create(
                    bill=bill,
                    source=MoonTaxPayment.SOURCE_WALLET,
                    amount_isk=tax_isk,
                    external_id=f"demo-{bill.public_id.hex[:8]}",
                    note=f"MOON-TAX {bill.payment_reference}",
                )

        # Extra extractions for a fuller dashboard
        extras = [
            ("3-FKCZ - W O M P S T A R - Moon 14", "3-FKCZ", 14, datetime(2026, 5, 22, 14, 30, tzinfo=timezone.utc), 198400, 41200000, 5200000),
            ("LQ-OAI - Moon 3", "LQ-OAI", 3, datetime(2026, 5, 15, 9, 15, tzinfo=timezone.utc), 156200, 30100000, 3900000),
            ("M-OSE - Moon 7", "M-OSE", 7, datetime(2026, 5, 8, 22, 0, tzinfo=timezone.utc), 89000, 18500000, 2100000),
        ]
        for label, sys, num, pop, m3, ore, tax in extras:
            MoonExtractionEvent.objects.update_or_create(
                moon_label=label,
                popped_at=pop,
                defaults={
                    "system_name": sys,
                    "moon_number": num,
                    "tracking_ends_at": pop + timedelta(hours=20),
                    "ledger_synced_at": timezone.now(),
                    "bills_generated_at": timezone.now(),
                    "total_mined_m3": m3,
                    "total_ore_isk": Decimal(ore),
                    "total_tax_isk": Decimal(tax),
                },
            )

        start = date(2026, 5, 1)
        end = date(2026, 5, 31)
        for label, m3, score in [
            (DEMO_MOON_LABEL, 241800, 0.94),
            ("3-FKCZ - W O M P S T A R - Moon 14", 198400, 0.88),
            ("LQ-OAI - Moon 3", 156200, 0.72),
            ("M-OSE - Moon 7", 89000, 0.41),
            ("XZ-LY - Moon 11", 0, 0.0),
        ]:
            MoonHeatmapCell.objects.update_or_create(
                period_start=start,
                period_end=end,
                moon_label=label,
                defaults={
                    "system_name": label.split(" - ")[0][:128],
                    "moon_number": DEMO_MOON_NUM if "Moon 20" in label else 14,
                    "mined_m3": m3,
                    "expected_m3": max(m3, 250000),
                    "extraction_count": 1 if m3 else 0,
                    "performance_score": score,
                },
            )

        MoonProfitabilitySnapshot.objects.update_or_create(
            snapshot_date=date(2026, 5, 28),
            defaults={
                "total_mined_isk": Decimal("128350000"),
                "total_tax_isk": Decimal("15008000"),
                "total_fuel_isk": Decimal("4200000"),
                "net_isk": Decimal("109142000"),
                "extraction_count": 4,
                "meta_json": {"demo": True, "highlight_moon": DEMO_MOON_LABEL},
            },
        )

        MoonRentalProfile.objects.update_or_create(
            moon_label=DEMO_MOON_LABEL,
            defaults={
                "renter_user": users[0],
                "renter_corporation_name": "False Gods",
                "monthly_rent_isk": Decimal("500000000"),
                "active": True,
                "notes": "Demo renter profile for screenshots.",
            },
        )

        self.stdout.write(self.style.SUCCESS(f"Demo data ready: {DEMO_MOON_LABEL} @ {DEMO_POPPED}"))
        self.stdout.write(f"  Dashboard: /moon-tsar/?start=2026-05-01&end=2026-05-31")
        self.stdout.write(f"  Bill example: /moon-tsar/bill/{MoonTaxBill.objects.filter(extraction=event).first().public_id}/")
