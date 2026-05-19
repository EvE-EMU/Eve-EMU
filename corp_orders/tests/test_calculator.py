from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from corp_orders.models import FreightOrder, FreightOrdersSettings
from corp_orders.services.calculator import build_quote, parse_inventory_lines
from corp_orders.services.freight import calculate_freight_isk


class ParseLinesTests(SimpleTestCase):
    def test_requires_tabs(self):
        lines, errors = parse_inventory_lines("Tritanium 100")
        self.assertEqual(lines, [])
        self.assertTrue(errors)


class FreightLogicTests(SimpleTestCase):
    @patch("corp_orders.services.freight.fetch_pushx_quote")
    @patch("corp_orders.services.freight.janice_sell_price")
    def test_large_volume_caps_at_pushx(self, mock_sell, mock_pushx):
        mock_pushx.return_value = {"PriceNormal": 1_000_000_000, "PriceRush": 2_000_000_000}
        mock_sell.return_value = Decimal("1000")
        config = FreightOrdersSettings(freight_volume_threshold_m3=360_000, rhea_nitrogen_isotopes=140_000)
        freight, detail = calculate_freight_isk(
            config=config,
            volume_m3=Decimal("500000"),
            items_subtotal_isk=50_000_000_000,
        )
        self.assertEqual(detail["method"], "pushx_rhea_split")
        self.assertLessEqual(freight, 1_000_000_000)

    @patch("corp_orders.services.freight.fetch_pushx_quote")
    def test_small_volume_uses_pushx(self, mock_pushx):
        mock_pushx.return_value = {"PriceNormal": 88_500_000, "PriceRush": 138_500_000}
        config = FreightOrdersSettings(freight_volume_threshold_m3=360_000)
        freight, detail = calculate_freight_isk(
            config=config,
            volume_m3=Decimal("1000"),
            items_subtotal_isk=1_000_000,
        )
        self.assertEqual(freight, 88_500_000)
        self.assertEqual(detail["method"], "pushx")


class QuoteSpeedTests(SimpleTestCase):
    @patch("corp_orders.services.calculator.calculate_freight_isk")
    @patch("corp_orders.services.calculator.line_unit_price_isk")
    @patch("corp_orders.services.calculator.resolve_type_by_name")
    def test_god_speed_surcharge(self, mock_resolve, mock_price, mock_freight):
        class _Type:
            id = 34
            name = "Tritanium"
            volume = 0.01

            class eve_group:
                class eve_category:
                    name = "Material"

        mock_resolve.return_value = _Type()
        mock_price.return_value = (Decimal("10"), "")
        mock_freight.return_value = (100, {})
        config = FreightOrdersSettings(
            item_markup_percent=Decimal("10"),
            god_speed_multiplier=Decimal("1.25"),
            alter_speed_multiplier=Decimal("1.15"),
        )
        quote = build_quote(
            config=config,
            items_text="Tritanium\t1000",
            speed=FreightOrder.Speed.GOD,
            issuer_kind=FreightOrder.IssuerKind.CHARACTER,
        )
        self.assertEqual(quote["expiration_hours"], 6)
        self.assertGreater(quote["speed_surcharge_isk"], 0)
