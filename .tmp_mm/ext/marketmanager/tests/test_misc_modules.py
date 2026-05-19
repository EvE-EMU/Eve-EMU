import datetime
import importlib
import sys
import types
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from marketmanager import (
    admin_helpers, app_settings, auth_hooks, models, providers,
)


class TestAdminHelpers(SimpleTestCase):
    def test_returns_none_for_empty_list(self) -> None:
        result = admin_helpers.list_2_html_w_tooltips([], max_items=3)
        self.assertIsNone(result)

    def test_returns_plain_string_when_not_truncated(self) -> None:
        result = admin_helpers.list_2_html_w_tooltips(["a", "b"], max_items=3)
        self.assertEqual(result, "a, b")

    def test_returns_tooltip_html_when_truncated(self) -> None:
        result = admin_helpers.list_2_html_w_tooltips(["a", "b", "c"], max_items=2)
        self.assertIn('data-tooltip="a, b, c"', result)
        self.assertIn("a, b, (...)", result)


class TestAppSettings(SimpleTestCase):
    @override_settings(ESI_SSO_CALLBACK_URL="https://auth.example.com/sso/callback")
    def test_get_site_url(self) -> None:
        self.assertEqual(app_settings.get_site_url(), "https://auth.example.com")

    @patch("marketmanager.app_settings.apps.is_installed", return_value=True)
    def test_discord_bot_active(self, mock_is_installed: Mock) -> None:
        self.assertTrue(app_settings.discord_bot_active())
        mock_is_installed.assert_called_once_with("aadiscordbot")

    @patch("marketmanager.app_settings.apps.is_installed", return_value=True)
    def test_fittings_active(self, mock_is_installed: Mock) -> None:
        self.assertTrue(app_settings.fittings_active())
        mock_is_installed.assert_called_once_with("fittings")


class TestAuthHooks(SimpleTestCase):
    @patch("marketmanager.auth_hooks.MenuItemHook.render", return_value="rendered")
    def test_market_menu_item_renders_when_user_has_perm(self, mock_render: Mock) -> None:
        request = Mock()
        request.user.has_perm.return_value = True

        item = auth_hooks.MarketManagerMarketBrowserMenuItem()
        result = item.render(request)

        self.assertEqual(result, "rendered")
        request.user.has_perm.assert_called_once_with("marketmanager.basic_market_browser")
        mock_render.assert_called_once_with(item, request)

    def test_market_menu_item_returns_empty_when_no_perm(self) -> None:
        request = Mock()
        request.user.has_perm.return_value = False

        item = auth_hooks.MarketManagerMarketBrowserMenuItem()
        result = item.render(request)

        self.assertEqual(result, "")

    def test_register_menu_returns_item(self) -> None:
        self.assertIsInstance(
            auth_hooks.register_menu(),
            auth_hooks.MarketManagerMarketBrowserMenuItem,
        )

    def test_register_urls_returns_url_hook(self) -> None:
        url_hook = auth_hooks.register_urls()
        self.assertIsInstance(url_hook, auth_hooks.UrlHook)

    def test_register_cogs(self) -> None:
        self.assertEqual(auth_hooks.register_cogs(), ["marketmanager.cogs.marketmanager"])


class TestProviders(SimpleTestCase):
    @patch("marketmanager.providers.esi")
    def test_get_universe_structures(self, mock_esi: Mock) -> None:
        mock_esi.client.Universe.GetUniverseStructures.return_value.results.return_value = [1, 2]

        result = providers.get_universe_structures("market")

        self.assertEqual(result, [1, 2])

    @patch("marketmanager.providers.esi")
    def test_get_universe_structures_structure_id(self, mock_esi: Mock) -> None:
        token = Mock()
        expected = Mock()
        mock_esi.client.Universe.GetUniverseStructuresStructureId.return_value.result.return_value = expected

        result = providers.get_universe_structures_structure_id(123, token)

        self.assertEqual(result, expected)

    @patch("marketmanager.providers.esi")
    def test_get_markets_region_id_orders(self, mock_esi: Mock) -> None:
        mock_esi.client.Market.GetMarketsRegionIdOrders.return_value.results.return_value = [Mock()]

        result = providers.get_markets_region_id_orders(10000002)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.esi")
    def test_get_markets_region_id_orders_paged(self, mock_esi: Mock) -> None:
        response = Mock()
        mock_esi.client.Market.GetMarketsRegionIdOrders.return_value.result.return_value = ([Mock()], response)

        result, resp = providers.get_markets_region_id_orders_paged(10000002, 2)

        self.assertEqual(len(result), 1)
        self.assertEqual(resp, response)

    @patch("marketmanager.providers.esi")
    def test_get_markets_region_id_orders_by_typeid(self, mock_esi: Mock) -> None:
        mock_esi.client.Market.GetMarketsRegionIdOrders.return_value.results.return_value = [Mock()]

        result = providers.get_markets_region_id_orders_by_typeid(10000002, type_id=34)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.esi")
    def test_get_markets_region_id_orders_by_typeid_paged(self, mock_esi: Mock) -> None:
        response = Mock()
        mock_esi.client.Market.GetMarketsRegionIdOrders.return_value.result.return_value = ([Mock()], response)

        result, resp = providers.get_markets_region_id_orders_by_typeid_paged(10000002, 1, type_id=34)

        self.assertEqual(len(result), 1)
        self.assertEqual(resp, response)

    @patch("marketmanager.providers.esi")
    def test_get_markets_region_id_history(self, mock_esi: Mock) -> None:
        mock_esi.client.Market.GetMarketsRegionIdHistory.return_value.results.return_value = [Mock()]

        result = providers.get_markets_region_id_history(10000002, 34)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.esi")
    def test_get_markets_structures_structure_id(self, mock_esi: Mock) -> None:
        token = Mock()
        mock_esi.client.Market.GetMarketsStructuresStructureId.return_value.results.return_value = [Mock()]

        result = providers.get_markets_structures_structure_id(123, token)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.Token")
    @patch("marketmanager.providers.esi")
    def test_get_characters_character_id_orders(self, mock_esi: Mock, mock_token: Mock) -> None:
        mock_token.get_token.return_value = Mock()
        mock_esi.client.Market.GetCharactersCharacterIdOrders.return_value.results.return_value = [Mock()]

        result = providers.get_characters_character_id_orders(90000001)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.Token")
    @patch("marketmanager.providers.esi")
    def test_get_characters_character_id_orders_history(self, mock_esi: Mock, mock_token: Mock) -> None:
        mock_token.get_token.return_value = Mock()
        mock_esi.client.Market.GetCharactersCharacterIdOrdersHistory.return_value.results.return_value = [Mock()]

        result = providers.get_characters_character_id_orders_history(90000001)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.esi")
    def test_get_characters_character_id_roles_from_token(self, mock_esi: Mock) -> None:
        token = Mock(character_id=90000001)
        expected = Mock()
        mock_esi.client.Character.GetCharactersCharacterIdRoles.return_value.result.return_value = expected

        result = providers.get_characters_character_id_roles_from_token(token)

        self.assertEqual(result, expected)

    @patch("marketmanager.providers.esi")
    def test_get_corporations_corporation_id_orders(self, mock_esi: Mock) -> None:
        token = Mock()
        mock_esi.client.Market.GetCorporationsCorporationIdOrders.return_value.results.return_value = [Mock()]

        result = providers.get_corporations_corporation_id_orders(99000001, token)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.esi")
    def test_get_corporations_corporation_id_orders_history(self, mock_esi: Mock) -> None:
        token = Mock()
        mock_esi.client.Market.GetCorporationsCorporationIdOrdersHistory.return_value.results.return_value = [Mock()]

        result = providers.get_corporations_corporation_id_orders_history(99000001, token)

        self.assertEqual(len(result), 1)

    @patch("marketmanager.providers.esi")
    def test_get_corporations_corporation_id_structures(self, mock_esi: Mock) -> None:
        token = Mock()
        mock_esi.client.Corporation.GetCorporationsCorporationIdStructures.return_value.results.return_value = [Mock()]

        result = providers.get_corporations_corporation_id_structures(99000001, token)

        self.assertEqual(len(result), 1)


class TestFittings(SimpleTestCase):
    def test_inactive_import_path(self) -> None:
        with patch("marketmanager.app_settings.fittings_active", return_value=False):
            import marketmanager.fittings as fittings_module

            fittings_module = importlib.reload(fittings_module)
            self.assertFalse(hasattr(fittings_module, "update_managed_supply_config_fittings_fit"))

    def _load_fittings_module_active(self):
        fake_models = types.ModuleType("fittings.models")
        fake_models.Fitting = Mock()
        fake_models.FittingItem = Mock()

        with (
            patch("marketmanager.app_settings.fittings_active", return_value=True),
            patch.dict(sys.modules, {"fittings.models": fake_models}),
        ):
            import marketmanager.fittings as fittings_module

            return importlib.reload(fittings_module)

    def _managed_supply_config_mock(self) -> Mock:
        managed = Mock()
        managed.managed_app_identifier = "fitting.123"
        managed.managed_quantity = 2
        managed.managed_jita_compare_percent = 25

        for attr in [
            "managed_structure",
            "managed_solar_system",
            "managed_region",
            "managed_structure_type",
            "managed_webhooks",
            "managed_channels",
            "managed_debug_webhooks",
            "managed_debug_channels",
        ]:
            rel = Mock()
            rel.all.return_value = []
            setattr(managed, attr, rel)

        return managed

    def test_update_managed_supply_config_fittings_fit(self) -> None:
        fittings_module = self._load_fittings_module_active()

        managed = self._managed_supply_config_mock()
        fit = Mock(ship_type_type_id=1234)

        with (
            patch.object(fittings_module, "Fitting") as mock_fitting,
            patch.object(fittings_module, "FittingItem") as mock_fitting_item,
            patch.object(fittings_module, "ItemType") as mock_item_type,
            patch.object(fittings_module, "SupplyConfig") as mock_supply_config,
        ):
            existing_configs = Mock()
            mock_supply_config.objects.filter.return_value = existing_configs

            hull_config = Mock()
            fit_item_config = Mock()
            mock_supply_config.side_effect = [hull_config, fit_item_config]

            mock_fitting.objects.get.return_value = fit
            mock_fitting_item.objects.filter.return_value.values.return_value.annotate.return_value = [
                {"type_id": 2222, "quantity": 3}
            ]

            mock_item_type.objects.get_or_create.side_effect = [
                (Mock(id=1234), True),
                (Mock(id=2222), True),
            ]

            fittings_module.update_managed_supply_config_fittings_fit(managed)

            existing_configs.delete.assert_called_once()
            self.assertEqual(mock_supply_config.call_count, 2)
            self.assertTrue(hull_config.save.called)
            self.assertTrue(fit_item_config.save.called)

    def test_update_managed_supply_config_fittings_fit_logs_existing_config_error(self) -> None:
        fittings_module = self._load_fittings_module_active()

        managed = self._managed_supply_config_mock()
        fit = Mock(ship_type_type_id=1234)

        with (
            patch.object(fittings_module, "Fitting") as mock_fitting,
            patch.object(fittings_module, "FittingItem") as mock_fitting_item,
            patch.object(fittings_module, "ItemType") as mock_item_type,
            patch.object(fittings_module, "SupplyConfig") as mock_supply_config,
            patch.object(fittings_module, "logger") as mock_logger,
        ):
            mock_supply_config.objects.filter.side_effect = Exception("filter error")
            mock_supply_config.side_effect = [Mock(), Mock()]

            mock_fitting.objects.get.return_value = fit
            mock_fitting_item.objects.filter.return_value.values.return_value.annotate.return_value = []
            mock_item_type.objects.get_or_create.return_value = (Mock(id=1234), True)

            fittings_module.update_managed_supply_config_fittings_fit(managed)

            self.assertTrue(mock_logger.exception.called)

    def test_update_managed_supply_config_fittings_fit_fit_lookup_error_raises(self) -> None:
        fittings_module = self._load_fittings_module_active()

        managed = self._managed_supply_config_mock()

        with (
            patch.object(fittings_module, "Fitting") as mock_fitting,
            patch.object(fittings_module, "SupplyConfig") as mock_supply_config,
            patch.object(fittings_module, "logger") as mock_logger,
        ):
            mock_supply_config.objects.filter.return_value = Mock(delete=Mock())
            mock_fitting.objects.get.side_effect = Exception("fit lookup error")

            with self.assertRaises(UnboundLocalError):
                fittings_module.update_managed_supply_config_fittings_fit(managed)

            self.assertTrue(mock_logger.exception.called)

    def test_update_managed_supply_config_fittings_doctrine(self) -> None:
        fittings_module = self._load_fittings_module_active()

        self.assertTrue(fittings_module.update_managed_supply_config_fittings_doctrine())


class TestModelsLight(SimpleTestCase):
    def test_order_expiry_property(self) -> None:
        order = models.Order(
            issued=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
            duration=30,
        )

        self.assertEqual(
            order.expiry,
            datetime.datetime(2025, 1, 31, tzinfo=datetime.timezone.utc),
        )

    def test_structure_str(self) -> None:
        structure = models.Structure(name="My Structure")
        self.assertEqual(str(structure), "My Structure")

    def test_webhook_str(self) -> None:
        webhook = models.Webhook(name="Hook")
        self.assertEqual(str(webhook), "Hook")

    @patch("marketmanager.models.SyncWebhook")
    def test_webhook_send_embed(self, mock_sync_webhook: Mock) -> None:
        webhook = models.Webhook(name="Hook", url="https://example.com")
        embed = Mock()

        webhook.send_embed(embed)

        mock_sync_webhook.from_url.assert_called_once_with("https://example.com")
        mock_sync_webhook.from_url.return_value.send.assert_called_once_with(
            embed=embed,
            username="Market Manager",
        )

    def test_channel_str(self) -> None:
        channel = models.Channel(name="Channel Name")
        self.assertEqual(str(channel), "Channel Name")

    def test_managed_supply_config_str(self) -> None:
        config = models.ManagedSupplyConfig(managed_app_reason="Because")
        self.assertEqual(str(config), "Because")

    def test_public_config_str(self) -> None:
        config = models.PublicConfig()
        self.assertEqual(str(config), "Public Market Configuration")

    def test_statistics_config_str(self) -> None:
        config = models.StatisticsConfig()
        self.assertEqual(str(config), "TypeStatistics Calculation Configuration")
        self.assertEqual(str(config), "TypeStatistics Calculation Configuration")
