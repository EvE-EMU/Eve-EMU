from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase

from marketmanager import tasks


class TestTasks(SimpleTestCase):
    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_markets_region_id_orders")
    @patch("marketmanager.tasks.PublicConfig")
    def test_fetch_public_market_orders_queues_buy_and_sell(
        self, mock_public_config: Mock, mock_fetch_region: Mock, _mock_randint: Mock
    ) -> None:
        region = Mock(id=10000002)
        mock_public_config.get_solo.return_value.fetch_regions.all.return_value = [region]

        tasks.fetch_public_market_orders()

        self.assertEqual(mock_fetch_region.apply_async.call_count, 2)

    @patch("marketmanager.tasks.get_markets_region_id_orders_paged")
    @patch("marketmanager.tasks.Order")
    @patch("marketmanager.tasks.Region")
    def test_fetch_markets_region_id_orders_handles_empty_page(
        self, mock_region: Mock, mock_order: Mock, mock_paged: Mock
    ) -> None:
        order_region = Mock()
        mock_region.objects.get.return_value = order_region
        mock_order.objects.filter.return_value = Mock()

        headers = Mock()
        headers.headers = {"X-Pages": "1"}
        mock_paged.return_value = ([], headers)

        tasks.fetch_markets_region_id_orders.run(10000002, "buy")

        mock_order.objects.bulk_create.assert_called_once_with([], batch_size=500)
        mock_order.objects.bulk_update.assert_called_once_with([], batch_size=500, fields=["price", "volume_remain", "issued"])

    @patch("marketmanager.tasks.get_markets_region_id_orders_by_typeid_paged", side_effect=tasks.HTTPNotModified(304, {}))
    @patch("marketmanager.tasks.Order")
    @patch("marketmanager.tasks.Region")
    def test_fetch_markets_region_id_orders_not_modified_returns(
        self, mock_region: Mock, mock_order: Mock, _mock_paged: Mock
    ) -> None:
        mock_region.objects.get.return_value = Mock()
        mock_order.objects.filter.return_value = Mock()

        result = tasks.fetch_markets_region_id_orders.run(10000002, "buy", type_id=34)

        self.assertIsNone(result)

    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_characters_character_id_orders")
    @patch("marketmanager.tasks.Token")
    def test_fetch_all_character_orders_queues_unique_characters(
        self, mock_token: Mock, mock_fetch_character: Mock, _mock_randint: Mock
    ) -> None:
        mock_token.objects.values_list.return_value.require_scopes.return_value = [
            (90000001,),
            (90000001,),
            (90000002,),
        ]

        tasks.fetch_all_character_orders()

        self.assertEqual(mock_fetch_character.apply_async.call_count, 2)
        self.assertEqual(
            mock_fetch_character.apply_async.call_args_list,
            [
                call(args=[90000001], priority=tasks.MARKETMANAGER_TASK_PRIORITY_ORDERS, countdown=1),
                call(args=[90000002], priority=tasks.MARKETMANAGER_TASK_PRIORITY_ORDERS, countdown=1),
            ],
        )

    @patch("marketmanager.tasks.get_characters_character_id_orders", return_value=[])
    def test_fetch_characters_character_id_orders_empty_ok(self, _mock_get_orders: Mock) -> None:
        result = tasks.fetch_characters_character_id_orders.run(90000001)
        self.assertIsNone(result)

    @patch("marketmanager.tasks.get_corp_token", return_value=False)
    @patch("marketmanager.tasks.logger")
    def test_fetch_corporations_corporation_id_orders_no_token(
        self, mock_logger: Mock, _mock_token: Mock
    ) -> None:
        result = tasks.fetch_corporations_corporation_id_orders.run(99000001)
        self.assertIsNone(result)
        self.assertTrue(mock_logger.error.called)

    @patch("marketmanager.tasks.get_corporations_corporation_id_orders", return_value=[])
    @patch("marketmanager.tasks.get_corp_token")
    @patch("marketmanager.tasks.EveCorporationInfo")
    def test_fetch_corporations_corporation_id_orders_empty(
        self, mock_corp: Mock, mock_get_corp_token: Mock, _mock_get_orders: Mock
    ) -> None:
        mock_get_corp_token.return_value = Mock()
        mock_corp.objects.get.return_value = Mock()

        result = tasks.fetch_corporations_corporation_id_orders.run(99000001)

        self.assertIsNone(result)

    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_corporations_corporation_id_orders")
    @patch("marketmanager.tasks.EveCorporationInfo")
    def test_fetch_all_corporation_orders_queues(
        self, mock_corp: Mock, mock_fetch: Mock, _mock_randint: Mock
    ) -> None:
        mock_corp.objects.filter.return_value = [Mock(corporation_id=99000001)]

        tasks.fetch_all_corporation_orders()

        mock_fetch.apply_async.assert_called_once_with(
            args=[99000001],
            priority=tasks.MARKETMANAGER_TASK_PRIORITY_ORDERS,
            countdown=1,
        )

    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_universe_structures_structure_id")
    @patch("marketmanager.tasks.get_universe_structures", return_value=[1024])
    def test_fetch_public_structures_queues_each(
        self, _mock_get: Mock, mock_fetch: Mock, _mock_randint: Mock
    ) -> None:
        tasks.fetch_public_structures.run()

        mock_fetch.apply_async.assert_called_once_with(
            args=[1024],
            priority=tasks.MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=1,
        )

    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_universe_structures_structure_id")
    @patch("marketmanager.tasks.Structure")
    def test_update_private_structures_queues(
        self, mock_structure: Mock, mock_fetch: Mock, _mock_randint: Mock
    ) -> None:
        mock_structure.objects.all.return_value = [Mock(structure_id=55)]

        tasks.update_private_structures()

        mock_fetch.apply_async.assert_called_once_with(
            args=[55, False],
            priority=tasks.MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=1,
        )

    @patch("marketmanager.tasks.get_random_market_token", return_value=False)
    @patch("marketmanager.tasks.logger")
    def test_fetch_universe_structures_structure_id_no_token_public(
        self, mock_logger: Mock, _mock_token: Mock
    ) -> None:
        result = tasks.fetch_universe_structures_structure_id.run(55, public=True)

        self.assertIsNone(result)
        self.assertTrue(mock_logger.error.called)

    @patch("marketmanager.tasks.get_matching_privateconfig_token", return_value=False)
    @patch("marketmanager.tasks.logger")
    def test_fetch_universe_structures_structure_id_no_token_private(
        self, mock_logger: Mock, _mock_token: Mock
    ) -> None:
        result = tasks.fetch_universe_structures_structure_id.run(55, public=False)

        self.assertIsNone(result)
        self.assertTrue(mock_logger.error.called)

    @patch("marketmanager.tasks.Structure")
    @patch("marketmanager.tasks.ItemType")
    @patch("marketmanager.tasks.SolarSystem")
    @patch("marketmanager.tasks.get_universe_structures_structure_id")
    @patch("marketmanager.tasks.get_random_market_token")
    def test_fetch_universe_structures_structure_id_updates_model(
        self,
        mock_token: Mock,
        mock_get_structure: Mock,
        mock_solar: Mock,
        mock_item_type: Mock,
        mock_structure_model: Mock,
    ) -> None:
        mock_token.return_value = Mock()
        structure = Mock(name="Citadel", owner_id=10, solar_system_id=30000142, type_id=35832)
        mock_get_structure.return_value = structure
        mock_solar.objects.get.return_value = Mock()
        mock_item_type.objects.get.return_value = Mock()

        tasks.fetch_universe_structures_structure_id.run(55, public=True)

        self.assertTrue(mock_structure_model.objects.update_or_create.called)

    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_markets_structures_structure_id")
    @patch("marketmanager.tasks.Structure")
    def test_fetch_all_structure_orders_queues(
        self, mock_structure: Mock, mock_fetch: Mock, _mock_randint: Mock
    ) -> None:
        mock_structure.objects.all.return_value = [Mock(structure_id=1)]

        tasks.fetch_all_structure_orders()

        mock_fetch.apply_async.assert_called_once_with(
            args=[1],
            priority=tasks.MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=1,
        )

    @patch("marketmanager.tasks.get_matching_privateconfig_token", return_value=False)
    @patch("marketmanager.tasks.logger")
    def test_fetch_markets_structures_structure_id_no_token(
        self, mock_logger: Mock, _mock_token: Mock
    ) -> None:
        result = tasks.fetch_markets_structures_structure_id.run(123)

        self.assertIsNone(result)
        self.assertTrue(mock_logger.error.called)

    @patch("marketmanager.tasks.get_markets_structures_structure_id", return_value=[])
    @patch("marketmanager.tasks.Structure")
    @patch("marketmanager.tasks.get_matching_privateconfig_token")
    def test_fetch_markets_structures_structure_id_empty(
        self, mock_get_token: Mock, mock_structure: Mock, _mock_get_orders: Mock
    ) -> None:
        mock_get_token.return_value = Mock()
        region = Mock()
        solar_system = Mock(eve_constellation=Mock(region=region))
        mock_structure_obj = Mock(solar_system=solar_system)
        mock_structure.objects.get.return_value = mock_structure_obj

        result = tasks.fetch_markets_structures_structure_id.run(123)

        self.assertIsNone(result)

    @patch("marketmanager.tasks.randint", return_value=1)
    @patch("marketmanager.tasks.fetch_corporations_corporation_id_structures")
    @patch("marketmanager.tasks.EveCorporationInfo")
    def test_fetch_all_corporations_structures_queues(
        self, mock_corp: Mock, mock_fetch: Mock, _mock_randint: Mock
    ) -> None:
        mock_corp.objects.all.return_value = [Mock(corporation_id=99000001)]

        tasks.fetch_all_corporations_structures()

        mock_fetch.apply_async.assert_called_once_with(
            args=[99000001],
            priority=tasks.MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=1,
        )

    @patch("marketmanager.tasks.logger")
    def test_fetch_corporations_corporation_id_structures_skips_npc(self, mock_logger: Mock) -> None:
        result = tasks.fetch_corporations_corporation_id_structures.run(1999999)

        self.assertIsNone(result)
        self.assertTrue(mock_logger.error.called)

    @patch("marketmanager.tasks.get_corp_token", return_value=False)
    @patch("marketmanager.tasks.logger")
    def test_fetch_corporations_corporation_id_structures_no_token(
        self, mock_logger: Mock, _mock_token: Mock
    ) -> None:
        result = tasks.fetch_corporations_corporation_id_structures.run(99000001)

        self.assertIsNone(result)
        self.assertTrue(mock_logger.error.called)

    @patch("marketmanager.tasks.Structure")
    @patch("marketmanager.tasks.ItemType")
    @patch("marketmanager.tasks.SolarSystem")
    @patch("marketmanager.tasks.get_corporations_corporation_id_structures")
    @patch("marketmanager.tasks.get_corp_token")
    def test_fetch_corporations_corporation_id_structures_updates_market_services(
        self,
        mock_get_token: Mock,
        mock_get_structures: Mock,
        mock_solar: Mock,
        mock_item_type: Mock,
        mock_structure_model: Mock,
    ) -> None:
        mock_get_token.return_value = Mock()
        service_market = Mock()
        service_market.name = "market"
        structure = Mock(
            services=[service_market],
            structure_id=77,
            name="Market Hub",
            corporation_id=99000001,
            system_id=30000142,
            type_id=35832,
        )
        mock_get_structures.return_value = [structure]
        mock_solar.objects.get.return_value = Mock()
        mock_item_type.objects.get.return_value = Mock()

        tasks.fetch_corporations_corporation_id_structures.run(99000001)

        self.assertTrue(mock_structure_model.objects.update_or_create.called)

    @patch("marketmanager.tasks.run_margin_config")
    @patch("marketmanager.tasks.run_price_config")
    @patch("marketmanager.tasks.run_supply_config")
    @patch("marketmanager.tasks.MarginConfig")
    @patch("marketmanager.tasks.PriceConfig")
    @patch("marketmanager.tasks.SupplyConfig")
    def test_run_all_watch_configs_queues_all(
        self,
        mock_supply_config: Mock,
        mock_price_config: Mock,
        mock_margin_config: Mock,
        mock_run_supply: Mock,
        mock_run_price: Mock,
        mock_run_margin: Mock,
    ) -> None:
        mock_supply_config.objects.all.return_value = [Mock(pk=1)]
        mock_price_config.objects.all.return_value = [Mock(pk=2)]
        mock_margin_config.objects.all.return_value = [Mock(pk=3)]

        tasks.run_all_watch_configs()

        mock_run_supply.apply_async.assert_called_once()
        mock_run_price.apply_async.assert_called_once()
        mock_run_margin.apply_async.assert_called_once()

    @patch("marketmanager.tasks.Order")
    def test_garbage_collection_deletes_expected_sets(self, mock_order: Mock) -> None:
        filters = [Mock(), Mock(), Mock()]
        mock_order.objects.filter.side_effect = filters

        tasks.garbage_collection()

        for filtered in filters:
            filtered.delete.assert_called_once()

    @patch("marketmanager.tasks.TypeStatistics")
    @patch("marketmanager.tasks.calculate_type_statistics")
    @patch("marketmanager.tasks.Order")
    @patch("marketmanager.tasks.ItemType")
    def test_update_all_type_statistics_mixed_paths(
        self,
        mock_item_type: Mock,
        mock_order: Mock,
        mock_calculate_type_statistics: Mock,
        mock_type_statistics: Mock,
    ) -> None:
        item_type_a = Mock(id=34)
        item_type_b = Mock(id=35)
        mock_item_type.objects.filter.return_value = [item_type_a, item_type_b]

        enough_orders = Mock()
        enough_orders.count.return_value = tasks.MARKETMANAGER_TYPESTATISTICS_MINIMUM_ORDER_COUNT
        low_orders = Mock()
        low_orders.count.return_value = 0
        mock_order.objects.filter.side_effect = [enough_orders, low_orders]

        tasks.update_all_type_statistics()

        mock_calculate_type_statistics.apply_async.assert_called_once_with(
            args=[34], priority=tasks.MARKETMANAGER_TASK_PRIORITY_BACKGROUND
        )
        mock_type_statistics.objects.filter.assert_called_with(item_type=item_type_b)
        mock_type_statistics.objects.filter.return_value.delete.assert_called_once()

    @patch("marketmanager.tasks.median", return_value=3.0)
    @patch("marketmanager.tasks.weighted_average", return_value=2.0)
    @patch("marketmanager.tasks.fifth_percentile", return_value=1.0)
    @patch("marketmanager.tasks.Order")
    @patch("marketmanager.tasks.StatisticsConfig")
    @patch("marketmanager.tasks.TypeStatistics")
    @patch("marketmanager.tasks.ItemType")
    def test_calculate_type_statistics_updates_and_deletes(
        self,
        mock_item_type: Mock,
        mock_type_statistics: Mock,
        mock_statistics_config: Mock,
        mock_order: Mock,
        _mock_fifth: Mock,
        _mock_weighted: Mock,
        _mock_median: Mock,
    ) -> None:
        item_type = Mock(name="Tritanium")
        mock_item_type.objects.get.return_value = item_type

        region_a = Mock(name="A")
        region_b = Mock(name="B")
        mock_statistics_config.get_solo.return_value.calculate_regions.all.return_value = [region_a, region_b]

        exists_true = Mock()
        exists_true.exists.return_value = True
        exists_false = Mock()
        exists_false.exists.return_value = False
        mock_order.objects.filter.side_effect = [exists_true, exists_false]

        existing_stat = Mock()
        mock_type_statistics.objects.get.return_value = existing_stat

        tasks.calculate_type_statistics(34)

        self.assertGreaterEqual(mock_type_statistics.objects.update_or_create.call_count, 2)
        mock_type_statistics.objects.get.assert_called_once_with(item_type=item_type, region=region_b)
        existing_stat.delete.assert_called_once()

    @patch("marketmanager.tasks.create_embed_price")
    @patch("marketmanager.tasks.filter_orders_by_location")
    @patch("marketmanager.tasks.Order")
    @patch("marketmanager.tasks.PriceConfig")
    def test_run_price_config_no_matching_orders(
        self,
        mock_price_config: Mock,
        mock_order: Mock,
        mock_filter_orders: Mock,
        mock_create_embed_price: Mock,
    ) -> None:
        config = Mock(
            buy_order=False,
            minimum=0,
            scalp=False,
            jita_compare_percent=100,
        )
        config.item_type.all.return_value = []
        config.item_group.all.return_value = []
        config.item_market_group.all.return_value = []
        config.webhooks.all.return_value = []
        config.channels.all.return_value = []
        mock_price_config.objects.get.return_value = config

        orders = Mock()
        mock_order.objects.filter.return_value = orders
        orders_location = Mock()
        mock_filter_orders.return_value = orders_location
        orders_location_type = Mock()
        orders_location.filter.return_value = orders_location_type
        orders_location_type.order_by.return_value = []

        tasks.run_price_config(1)

        mock_create_embed_price.assert_called_once()
        config.save.assert_called_once()

    @patch("marketmanager.tasks.create_embed_margin")
    @patch("marketmanager.tasks.ItemType")
    @patch("marketmanager.tasks.MarginConfig")
    def test_run_margin_config_empty_item_types(
        self,
        mock_margin_config: Mock,
        mock_item_type: Mock,
        mock_create_embed_margin: Mock,
    ) -> None:
        config = Mock(margin_percent=5, freight_cost=1)
        config.item_type.all.return_value = set()
        mock_item_type.objects.filter.return_value = set()

        for attr in [
            "source_structure",
            "source_solar_system",
            "source_region",
            "source_station",
            "destination_structure",
            "destination_solar_system",
            "destination_region",
            "destination_station",
        ]:
            getattr(config, attr).count.return_value = 0
            getattr(config, attr).all.return_value = []

        config.source_buy = True
        config.destination_buy = True
        config.webhooks.all.return_value = []
        config.channels.all.return_value = []
        mock_margin_config.objects.get.return_value = config

        tasks.run_margin_config(1)

        mock_create_embed_margin.assert_called_once()
        config.save.assert_called_once()

    @patch("marketmanager.tasks.update_managed_supply_config_fittings_fit", create=True)
    @patch("marketmanager.tasks.fittings_active", return_value=True)
    @patch("marketmanager.tasks.ManagedSupplyConfig")
    def test_update_managed_supply_configs_runs_fittings_handler(
        self,
        mock_managed_supply_config: Mock,
        _mock_fittings_active: Mock,
        mock_update_fittings: Mock,
    ) -> None:
        managed_config = Mock(managed_app="fittings", managed_app_reason="unit-test")
        mock_managed_supply_config.objects.all.return_value = [managed_config]

        tasks.update_managed_supply_configs()

        mock_update_fittings.assert_called_once_with(managed_config)
