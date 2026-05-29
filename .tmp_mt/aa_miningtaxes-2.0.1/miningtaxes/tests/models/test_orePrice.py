from unittest.mock import patch

from eve_sde.models import ItemType

from django.utils.timezone import now

from app_utils.testing import NoSocketsTestCase

from ...models import OrePrices, get_price, get_tax, ore_calc_prices
from ..testdata.load_eve_sde import add_material, load_eve_sde


class TestOrePrice(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eve_sde()

    def test_calc_prices_without_materials(self):
        ore = OrePrices(eve_type_id=45511, buy=10, sell=100, updated=now())
        ore.calc_prices()

        self.assertEqual(ore.raw_price, 10)
        self.assertEqual(ore.refined_price, 10)
        self.assertEqual(ore.taxed_price, 10)

    def test_calc_prices_uses_refined_value_when_higher(self):
        add_material(45511, 16635, 3)
        OrePrices.objects.create(eve_type_id=16635, buy=2000, sell=200, updated=now())

        ore = OrePrices(eve_type_id=45511, buy=10, sell=100, updated=now())
        ore.calc_prices()

        self.assertEqual(ore.raw_price, 10)
        self.assertEqual(ore.refined_price, 54.378)
        self.assertEqual(ore.taxed_price, 54.378)

    def test_ore_calc_prices_uses_raw_value_when_higher(self):
        add_material(45511, 16635, 3)
        OrePrices.objects.create(eve_type_id=16635, buy=20, sell=200, updated=now())
        ore = OrePrices(eve_type_id=45511, buy=10, sell=100, updated=now())
        ore.calc_prices()

        prices = ore_calc_prices(ItemType.objects.get(id=45511), 20)

        self.assertEqual(prices[0], 200)
        self.assertEqual(prices[1], 10.8756)
        self.assertEqual(prices[2], 200)

    @patch("miningtaxes.models.orePrices.MININGTAXES_ALWAYS_TAX_REFINED", True)
    def test_ore_calc_prices_can_force_refined_tax_value(self):
        add_material(45511, 16635, 3)
        OrePrices.objects.create(eve_type_id=16635, buy=20, sell=200, updated=now())

        prices = ore_calc_prices(ItemType.objects.get(id=45511), 20)

        self.assertEqual(prices[0], 200)
        self.assertEqual(prices[1], 10.8756)
        self.assertEqual(prices[2], 10.8756)

    def test_get_price_falls_back_to_base_price(self):
        self.assertEqual(get_price(ItemType.objects.get(id=1230)), 5)

    def test_get_tax_returns_per_ore_rate(self):
        ore = OrePrices.objects.create(
            eve_type_id=45511, buy=10, sell=100, tax_rate=17.5, updated=now()
        )

        self.assertEqual(get_tax(ore.eve_type), 0.175)

    def test_get_tax_uses_unknown_default_when_missing(self):
        self.assertEqual(get_tax(ItemType.objects.get(id=1230)), 0.10)
