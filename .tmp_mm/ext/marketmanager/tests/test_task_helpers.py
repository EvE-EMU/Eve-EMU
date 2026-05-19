from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.exceptions import ObjectDoesNotExist
from django.test import SimpleTestCase

from marketmanager import task_helpers


def _rel(items) -> Mock:
    rel = Mock()
    rel.count.return_value = len(items)
    rel.all.return_value = items
    return rel


class TestTaskHelpers(SimpleTestCase):
    @patch("marketmanager.task_helpers.get_characters_character_id_roles_from_token")
    @patch("marketmanager.task_helpers.Token")
    @patch("marketmanager.task_helpers.EveCharacter")
    def test_get_corp_token_returns_matching_role_token(
        self, mock_character: Mock, mock_token_model: Mock, mock_roles_fn: Mock
    ) -> None:
        token = Mock()
        mock_character.objects.filter.return_value.values.return_value = [{"character_id": 1}]
        mock_token_model.objects.filter.return_value.require_scopes.return_value = [token]
        roles = Mock()
        roles.roles = ["Station_Manager"]
        mock_roles_fn.return_value = roles

        scopes = ["esi-markets.structure_markets.v1"]
        result = task_helpers.get_corp_token(123, scopes, ["Station_Manager"])

        self.assertEqual(result, token)
        self.assertIn("esi-characters.read_corporation_roles.v1", scopes)

    @patch("marketmanager.task_helpers.get_characters_character_id_roles_from_token")
    @patch("marketmanager.task_helpers.Token")
    @patch("marketmanager.task_helpers.EveCharacter")
    def test_get_corp_token_returns_false_when_no_matching_roles(
        self, mock_character: Mock, mock_token_model: Mock, mock_roles_fn: Mock
    ) -> None:
        token = Mock()
        mock_character.objects.filter.return_value.values.return_value = [{"character_id": 1}]
        mock_token_model.objects.filter.return_value.require_scopes.return_value = [token]
        roles = Mock()
        roles.roles = ["Other_Role"]
        mock_roles_fn.return_value = roles

        result = task_helpers.get_corp_token(123, [], ["Station_Manager"])

        self.assertFalse(result)

    @patch("marketmanager.task_helpers.random.choice")
    @patch("marketmanager.task_helpers.Token")
    def test_get_random_market_token_success(self, mock_token_model: Mock, mock_choice: Mock) -> None:
        token = Mock()
        mock_token_model.objects.all.return_value.require_scopes.return_value = [token]
        mock_choice.return_value = token

        result = task_helpers.get_random_market_token()

        self.assertEqual(result, token)

    @patch("marketmanager.task_helpers.logger")
    @patch("marketmanager.task_helpers.random.choice", side_effect=Exception("x"))
    @patch("marketmanager.task_helpers.Token")
    def test_get_random_market_token_exception(
        self, mock_token_model: Mock, _mock_choice: Mock, mock_logger: Mock
    ) -> None:
        mock_token_model.objects.all.return_value.require_scopes.return_value = []

        result = task_helpers.get_random_market_token()

        self.assertFalse(result)
        self.assertTrue(mock_logger.exception.called)

    def test_is_existing_order_found(self) -> None:
        order = Mock(order_id=10)
        current_orders = Mock()
        current_orders.get.return_value = "existing"

        result = task_helpers.is_existing_order(order, current_orders)

        self.assertEqual(result, "existing")

    def test_is_existing_order_not_found(self) -> None:
        order = Mock(order_id=10)
        current_orders = Mock()
        current_orders.get.side_effect = ObjectDoesNotExist

        result = task_helpers.is_existing_order(order, current_orders)

        self.assertFalse(result)

    @patch("marketmanager.task_helpers.random.choice")
    @patch("marketmanager.task_helpers.PrivateConfig")
    @patch("marketmanager.task_helpers.Structure")
    def test_get_matching_privateconfig_token_direct(
        self, mock_structure: Mock, mock_private_config: Mock, mock_choice: Mock
    ) -> None:
        structure = Mock(owner_id=555)
        token_holder = Mock(token="token")
        configured = Mock()
        configured.count.return_value = 1
        mock_structure.objects.get.return_value = structure
        mock_private_config.objects.filter.return_value = configured
        mock_choice.return_value = token_holder

        result = task_helpers.get_matching_privateconfig_token(12345)

        self.assertEqual(result, "token")

    @patch("marketmanager.task_helpers.random.choice")
    @patch("marketmanager.task_helpers.PrivateConfig")
    @patch("marketmanager.task_helpers.EveCorporationInfo")
    @patch("marketmanager.task_helpers.Structure")
    def test_get_matching_privateconfig_token_fallback_corp(
        self,
        mock_structure: Mock,
        mock_corp: Mock,
        mock_private_config: Mock,
        mock_choice: Mock,
    ) -> None:
        structure = Mock(owner_id=555)
        corporation = Mock()
        configured_first = Mock()
        configured_first.count.return_value = 0
        configured_second = Mock()
        configured_second.count.return_value = 1
        token_holder = Mock(token="corp-token")

        mock_structure.objects.get.return_value = structure
        mock_corp.objects.get.return_value = corporation
        mock_private_config.objects.filter.side_effect = [configured_first, configured_second]
        mock_choice.return_value = token_holder

        result = task_helpers.get_matching_privateconfig_token(12345)

        self.assertEqual(result, "corp-token")

    @patch("marketmanager.task_helpers.PrivateConfig")
    @patch("marketmanager.task_helpers.Structure")
    def test_get_matching_privateconfig_token_object_not_found(
        self, mock_structure: Mock, mock_private_config: Mock
    ) -> None:
        configured_first = Mock()
        configured_first.count.return_value = 0
        mock_private_config.objects.filter.return_value = configured_first
        mock_structure.objects.get.side_effect = [Mock(owner_id=1), ObjectDoesNotExist]

        result = task_helpers.get_matching_privateconfig_token(1)

        self.assertFalse(result)

    @patch("marketmanager.task_helpers.random.choice", side_effect=IndexError)
    @patch("marketmanager.task_helpers.PrivateConfig")
    @patch("marketmanager.task_helpers.Structure")
    def test_get_matching_privateconfig_token_no_choice(
        self, mock_structure: Mock, mock_private_config: Mock, _mock_choice: Mock
    ) -> None:
        configured = Mock()
        configured.count.return_value = 1
        mock_private_config.objects.filter.return_value = configured
        mock_structure.objects.get.return_value = Mock(owner_id=1)

        result = task_helpers.get_matching_privateconfig_token(1)

        self.assertFalse(result)

    @patch("marketmanager.task_helpers.get_site_url", return_value="https://auth.local")
    def test_create_embed_base_buy_with_locations_and_structure_types(self, _mock_site: Mock) -> None:
        config = Mock()
        config.buy_order = True
        config.structure = _rel([Mock(name="s1")])
        config.solar_system = _rel([Mock(name="sys1")])
        config.region = _rel([Mock(name="reg1")])
        config.structure_type = _rel([Mock(name="type1")])
        config.structure.all.return_value = [Mock(name="Fortizar")]
        config.solar_system.all.return_value = [Mock(name="Jita")]
        config.region.all.return_value = [Mock(name="The Forge")]
        config.structure_type.all.return_value = [Mock(name="Keepstar")]

        embed = task_helpers.create_embed_base(config)

        self.assertEqual(embed.fields[0].value, "BUY")
        self.assertEqual(embed.url, "https://auth.local/marketmanager/marketbrowser")
        self.assertEqual(len(embed.fields), 3)

    @patch("marketmanager.task_helpers.get_site_url", return_value="https://auth.local")
    def test_create_embed_base_sell_minimal(self, _mock_site: Mock) -> None:
        config = Mock()
        config.buy_order = False
        config.structure = _rel([])
        config.solar_system = _rel([])
        config.region = _rel([])
        config.structure_type = _rel([])

        embed = task_helpers.create_embed_base(config)

        self.assertEqual(embed.fields[0].value, "SELL")
        self.assertEqual(len(embed.fields), 1)

    @patch("marketmanager.task_helpers.get_site_url", return_value="https://auth.local")
    @patch("marketmanager.task_helpers.create_embed_base")
    def test_create_embed_supply_jita_and_managed_fittings(
        self, mock_base: Mock, _mock_site: Mock
    ) -> None:
        embed = Mock()
        mock_base.return_value = embed
        item_type = Mock(name="Tritanium", id=34)

        managed = Mock(managed_app="fittings", managed_app_reason="Fit A", managed_quantity=2)
        config = Mock(
            item_type=item_type,
            volume=500,
            jita_compare_percent=110,
            price=0,
            managed_supply_config=managed,
        )

        task_helpers.create_embed_supply(config, 250, "desc", calculated_price=1234)

        embed.set_thumbnail.assert_called_once_with(url="https://images.evetech.net/types/34/icon")
        self.assertTrue(embed.insert_field_at.called)
        embed.add_field.assert_called_once()

    @patch("marketmanager.task_helpers.get_site_url", return_value="https://auth.local")
    @patch("marketmanager.task_helpers.create_embed_base")
    def test_create_embed_supply_price_branch_no_managed(
        self, mock_base: Mock, _mock_site: Mock
    ) -> None:
        embed = Mock()
        mock_base.return_value = embed
        item_type = Mock(name="Tritanium", id=34)
        item_type.icon_url.return_value = "icon-url"

        config = Mock(
            item_type=item_type,
            volume=10,
            jita_compare_percent=0,
            price=Decimal("100.00"),
            managed_supply_config=None,
        )

        task_helpers.create_embed_supply(config, 2, "desc")

        self.assertTrue(embed.insert_field_at.called)
        embed.add_field.assert_not_called()

    @patch("marketmanager.task_helpers.create_embed_base")
    def test_create_embed_price_scalp_jita(self, mock_base: Mock) -> None:
        embed = Mock()
        mock_base.return_value = embed
        config = Mock(scalp=True, jita_compare_percent=105, price=0)

        task_helpers.create_embed_price(config, "desc")

        self.assertEqual(embed.title, "Price Check: Scalping")
        self.assertTrue(embed.insert_field_at.called)

    @patch("marketmanager.task_helpers.create_embed_base")
    def test_create_embed_price_bargain_price(self, mock_base: Mock) -> None:
        embed = Mock()
        mock_base.return_value = embed
        config = Mock(scalp=False, jita_compare_percent=0, price=Decimal("55.00"))

        task_helpers.create_embed_price(config, "desc")

        self.assertEqual(embed.title, "Price Check: Bargains")
        self.assertTrue(embed.insert_field_at.called)

    @patch("marketmanager.task_helpers.get_site_url", return_value="https://auth.local")
    def test_create_embed_margin_source_and_destination(self, _mock_site: Mock) -> None:
        config = Mock()
        config.importing = True
        config.margin_percent = 5
        config.source_buy = True
        config.destination_buy = False
        config.freight_cost = 700

        config.source_structure = _rel([Mock(name="Fort")])
        config.source_solar_system = _rel([])
        config.source_region = _rel([])
        config.source_station = _rel([Mock(name="Jita 4-4")])
        config.source_structure.all.return_value = [Mock(name="Fort")]
        config.source_solar_system.all.return_value = []
        config.source_region.all.return_value = []
        config.source_station.all.return_value = [Mock(name="Jita 4-4")]

        config.destination_structure = _rel([Mock(name="Keep")])
        config.destination_solar_system = _rel([])
        config.destination_region = _rel([])
        config.destination_station = _rel([Mock(name="Amarr 8")])
        config.destination_structure.all.return_value = [Mock(name="Keep")]
        config.destination_solar_system.all.return_value = []
        config.destination_region.all.return_value = []
        config.destination_station.all.return_value = [Mock(name="Amarr 8")]

        embed = task_helpers.create_embed_margin(config, "margin desc")

        self.assertIn("Importing", embed.title)
        self.assertGreaterEqual(len(embed.fields), 3)

    @patch("marketmanager.task_helpers.Order")
    def test_percentile_region_none_returns_price(self, mock_order: Mock) -> None:
        order1 = Mock(volume_remain=10, price=Decimal("1.00"))
        order2 = Mock(volume_remain=20, price=Decimal("2.00"))
        qs = Mock()
        qs.aggregate.return_value = {"volume": 30}
        qs.__iter__ = Mock(return_value=iter([order1, order2]))
        mock_order.objects.filter.return_value.order_by.return_value = qs

        region = Mock(id=None)
        result = task_helpers.percentile(Mock(), 0.05, region=region, buy_order=False)

        self.assertEqual(result, Decimal("1.00"))

    @patch("marketmanager.task_helpers.Order")
    def test_percentile_total_volume_none_returns_zero(self, mock_order: Mock) -> None:
        qs = Mock()
        qs.aggregate.return_value = {"volume": None}
        qs.__iter__ = Mock(return_value=iter([]))
        mock_order.objects.filter.return_value.order_by.return_value = qs

        result = task_helpers.percentile(Mock(), 0.5, region=Mock(id=10000002), buy_order=False)

        self.assertEqual(result, 0)

    @patch("marketmanager.task_helpers.Order")
    def test_weighted_average_success(self, mock_order: Mock) -> None:
        qs = Mock()
        qs.aggregate.side_effect = [
            {"aggregate_volume": Decimal("10")},
            {"aggregate_price": Decimal("100")},
        ]
        mock_order.objects.filter.return_value = qs

        result = task_helpers.weighted_average(Mock(), region=Mock(id=None), buy_order=False)

        self.assertEqual(result, Decimal("10"))

    @patch("marketmanager.task_helpers.Order")
    def test_weighted_average_zero_division_returns_zero(self, mock_order: Mock) -> None:
        qs = Mock()
        qs.aggregate.side_effect = [
            {"aggregate_volume": Decimal("0")},
            {"aggregate_price": Decimal("100")},
        ]
        mock_order.objects.filter.return_value = qs

        result = task_helpers.weighted_average(Mock(), region=Mock(id=None), buy_order=False)

        self.assertEqual(result, 0)

    @patch("marketmanager.task_helpers.Structure")
    def test_filter_orders_by_location_with_structure_type(self, mock_structure: Mock) -> None:
        orders = Mock()
        loc_qs = Mock()
        typed_qs = Mock()
        orders.filter.return_value = loc_qs
        loc_qs.filter.return_value = typed_qs

        valid_structures = Mock()
        valid_structures.all.return_value = [1, 2]
        mock_structure.objects.filter.return_value = valid_structures

        config = Mock()
        config.structure = _rel([Mock()])
        config.solar_system = _rel([])
        config.region = _rel([])
        config.structure_type = _rel([Mock()])

        result = task_helpers.filter_orders_by_location(orders, config)

        self.assertEqual(result, typed_qs)

    def test_filter_orders_by_location_no_filters(self) -> None:
        orders = Mock()
        config = Mock()
        config.structure = _rel([])
        config.solar_system = _rel([])
        config.region = _rel([])
        config.structure_type = _rel([])

        result = task_helpers.filter_orders_by_location(orders, config)

        self.assertEqual(result, orders)

    @patch("marketmanager.task_helpers.Region")
    @patch("marketmanager.task_helpers.TypeStatistics")
    def test_calculate_comparator_price_buy_jita(self, mock_type_stats: Mock, mock_region: Mock) -> None:
        stats = Mock(buy_weighted_average=100, sell_weighted_average=120)
        mock_type_stats.objects.get.return_value = stats

        config = Mock(price=0, jita_compare_percent=110, item_type=Mock(), buy_order=True)
        result = task_helpers.calculate_comparator_price(config)

        self.assertAlmostEqual(result, 110)
        mock_region.objects.get.assert_called_once_with(id=10000002)

    @patch("marketmanager.task_helpers.Region")
    @patch("marketmanager.task_helpers.TypeStatistics")
    def test_calculate_comparator_price_fallback_zero(self, mock_type_stats: Mock, mock_region: Mock) -> None:
        mock_region.objects.get.return_value = Mock()
        mock_type_stats.objects.get.side_effect = ObjectDoesNotExist
        config = Mock(price=0, jita_compare_percent=101, item_type=Mock(), buy_order=False)

        result = task_helpers.calculate_comparator_price(config)

        self.assertEqual(result, 0)

    def test_calculate_comparator_price_direct_price(self) -> None:
        config = Mock(price=Decimal("55.00"), jita_compare_percent=0)

        result = task_helpers.calculate_comparator_price(config)

        self.assertEqual(result, Decimal("55.00"))

    @patch("marketmanager.task_helpers.NPCStation")
    def test_location_resolver_to_solar_system_station_success(self, mock_station: Mock) -> None:
        solar_system = Mock()
        mock_station.objects.get.return_value.solar_system = solar_system

        result = task_helpers.location_resolver_to_solar_system(60003760)

        self.assertEqual(result, solar_system)

    @patch("marketmanager.task_helpers.logger")
    @patch("marketmanager.task_helpers.NPCStation")
    def test_location_resolver_to_solar_system_station_failure(self, mock_station: Mock, mock_logger: Mock) -> None:
        mock_station.objects.get.side_effect = Exception("x")

        result = task_helpers.location_resolver_to_solar_system(60003760)

        self.assertIsNone(result.id)
        self.assertTrue(mock_logger.debug.called)

    @patch("marketmanager.task_helpers.Structure")
    def test_location_resolver_to_solar_system_structure_success(self, mock_structure: Mock) -> None:
        solar_system = Mock()
        mock_structure.objects.get.return_value.solar_system = solar_system

        result = task_helpers.location_resolver_to_solar_system(70000000)

        self.assertEqual(result, solar_system)

    @patch("marketmanager.task_helpers.logger")
    @patch("marketmanager.task_helpers.Structure")
    def test_location_resolver_to_solar_system_structure_failure(self, mock_structure: Mock, mock_logger: Mock) -> None:
        mock_structure.objects.get.side_effect = Exception("x")

        result = task_helpers.location_resolver_to_solar_system(70000000)

        self.assertIsNone(result.id)
        self.assertTrue(mock_logger.debug.called)
