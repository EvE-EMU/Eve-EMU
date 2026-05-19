"""
Tests for marketmanager.views
"""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from allianceauth.tests.auth_utils import AuthUtils
from allianceauth.utils.testing import NoSocketsTestCase

from marketmanager.views import (
    add_char, add_corp, bulk_location_resolver, location_resolver,
    type_statistics,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_user_with_perm(self, *perm_codenames):
    """Create an AA member user and add requested marketmanager permissions."""
    user = AuthUtils.create_member("testuser")
    AuthUtils.add_main_character_2(
        user=user,
        name="testuser",
        character_id=123456,
        disconnect_signals=True,
    )

    if perm_codenames:
        perm_names = [f"marketmanager.{codename}" for codename in perm_codenames]
        user = AuthUtils.add_permissions_to_user_by_name(perm_names, user)

    return user


# ---------------------------------------------------------------------------
# location_resolver
# ---------------------------------------------------------------------------


class TestLocationResolver(NoSocketsTestCase):
    """Tests for the location_resolver helper."""

    @patch("marketmanager.views.NPCStation")
    def test_station_range_returns_name(self, mock_npc: Mock) -> None:
        station = Mock()
        station.name = "Jita IV - Moon 4 - Caldari Navy Assembly Plant"
        mock_npc.objects.get.return_value = station

        result = location_resolver(60003760)

        mock_npc.objects.get.assert_called_once_with(id=60003760)
        self.assertEqual(result, "Jita IV - Moon 4 - Caldari Navy Assembly Plant")

    @patch("marketmanager.views.NPCStation")
    def test_station_range_lower_boundary(self, mock_npc: Mock) -> None:
        mock_npc.objects.get.return_value.name = "Low Boundary"
        location_resolver(60000000)
        mock_npc.objects.get.assert_called_once_with(id=60000000)

    @patch("marketmanager.views.NPCStation")
    def test_station_range_upper_boundary(self, mock_npc: Mock) -> None:
        mock_npc.objects.get.return_value.name = "High Boundary"
        location_resolver(64000000)
        mock_npc.objects.get.assert_called_once_with(id=64000000)

    @patch("marketmanager.views.Structure")
    def test_structure_returns_name(self, mock_structure: Mock) -> None:
        mock_structure.objects.get.return_value.name = "My Keepstar"

        result = location_resolver(1000000000001)

        mock_structure.objects.get.assert_called_once_with(structure_id=1000000000001)
        self.assertEqual(result, "My Keepstar")

    @patch("marketmanager.views.Structure")
    def test_structure_above_station_range(self, mock_structure: Mock) -> None:
        mock_structure.objects.get.return_value.name = "Fort"
        location_resolver(64000001)
        mock_structure.objects.get.assert_called_once_with(structure_id=64000001)

    @patch("marketmanager.views.Structure")
    def test_structure_below_station_range(self, mock_structure: Mock) -> None:
        mock_structure.objects.get.return_value.name = "Fort"
        location_resolver(59999999)
        mock_structure.objects.get.assert_called_once_with(structure_id=59999999)

    @patch("marketmanager.views.Structure")
    def test_structure_exception_returns_str_id(self, mock_structure: Mock) -> None:
        mock_structure.objects.get.side_effect = Exception("DoesNotExist")

        result = location_resolver(1000000000999)

        self.assertEqual(result, "1000000000999")


# ---------------------------------------------------------------------------
# bulk_location_resolver
# ---------------------------------------------------------------------------


class TestBulkLocationResolver(NoSocketsTestCase):
    """Tests for the bulk_location_resolver helper."""

    @patch("marketmanager.views.Structure")
    @patch("marketmanager.views.NPCStation")
    def test_splits_station_and_structure_ids(
        self, mock_npc: Mock, mock_structure: Mock
    ) -> None:
        station_mock = Mock()
        structure_mock = Mock()
        mock_npc.objects.in_bulk.return_value = {60003760: station_mock}
        mock_structure.objects.in_bulk.return_value = {1000000000001: structure_mock}

        stations, structures = bulk_location_resolver([60003760, 1000000000001])

        mock_npc.objects.in_bulk.assert_called_once_with([60003760])
        mock_structure.objects.in_bulk.assert_called_once_with([1000000000001])
        self.assertEqual(stations[60003760], station_mock)
        self.assertEqual(structures[1000000000001], structure_mock)

    @patch("marketmanager.views.Structure")
    @patch("marketmanager.views.NPCStation")
    def test_empty_returns_empty_dicts(
        self, mock_npc: Mock, mock_structure: Mock
    ) -> None:
        mock_npc.objects.in_bulk.return_value = {}
        mock_structure.objects.in_bulk.return_value = {}

        stations, structures = bulk_location_resolver([])

        mock_npc.objects.in_bulk.assert_called_once_with([])
        mock_structure.objects.in_bulk.assert_called_once_with([])
        self.assertEqual(stations, {})
        self.assertEqual(structures, {})

    @patch("marketmanager.views.Structure")
    @patch("marketmanager.views.NPCStation")
    def test_only_station_ids(
        self, mock_npc: Mock, mock_structure: Mock
    ) -> None:
        mock_npc.objects.in_bulk.return_value = {60003760: Mock(), 60000001: Mock()}
        mock_structure.objects.in_bulk.return_value = {}

        stations, structures = bulk_location_resolver([60003760, 60000001])

        mock_structure.objects.in_bulk.assert_called_once_with([])
        self.assertEqual(len(stations), 2)
        self.assertEqual(structures, {})

    @patch("marketmanager.views.Structure")
    @patch("marketmanager.views.NPCStation")
    def test_only_structure_ids(
        self, mock_npc: Mock, mock_structure: Mock
    ) -> None:
        mock_npc.objects.in_bulk.return_value = {}
        mock_structure.objects.in_bulk.return_value = {
            1000000000001: Mock(),
        }

        stations, structures = bulk_location_resolver([1000000000001])

        mock_npc.objects.in_bulk.assert_called_once_with([])
        self.assertEqual(stations, {})
        self.assertEqual(len(structures), 1)


class TestTypeStatistics(NoSocketsTestCase):
    """Tests for the type_statistics helper."""

    def _make_orders_mock(self, buy_volume=100, sell_volume=200):
        """Return a mock Order queryset with predictable aggregate results."""
        orders_qs = MagicMock()
        buy_qs = MagicMock()
        sell_qs = MagicMock()
        buy_qs.aggregate.return_value = {"volume": buy_volume}
        sell_qs.aggregate.return_value = {"volume": sell_volume}
        orders_qs.filter.side_effect = lambda **kwargs: (
            buy_qs if kwargs.get("is_buy_order") is True else sell_qs
        )
        return orders_qs

    @patch("marketmanager.views.TypeStatistics")
    @patch("marketmanager.views.Order")
    def test_returns_zeros_when_no_statistics_exist(
        self, mock_order: Mock, mock_type_stats: Mock
    ) -> None:
        from django.core.exceptions import ObjectDoesNotExist

        mock_order.objects.filter.return_value = self._make_orders_mock()
        mock_type_stats.objects.get.side_effect = ObjectDoesNotExist

        item_type = Mock(id=34)
        region = None

        result = type_statistics(item_type=item_type, region=region)

        self.assertEqual(result["buy_fifth_percentile"], 0)
        self.assertEqual(result["sell_fifth_percentile"], 0)
        self.assertEqual(result["buy_weighted_average"], 0)
        self.assertEqual(result["sell_weighted_average"], 0)
        self.assertEqual(result["buy_median"], 0)
        self.assertEqual(result["sell_median"], 0)
        self.assertIsNotNone(result["explain"])

    @patch("marketmanager.views.TypeStatistics")
    @patch("marketmanager.views.Order")
    def test_returns_stats_when_statistics_exist(
        self, mock_order: Mock, mock_type_stats: Mock
    ) -> None:
        orders_qs = self._make_orders_mock(buy_volume=50, sell_volume=80)
        mock_order.objects.filter.return_value = orders_qs

        stats = Mock()
        stats.buy_fifth_percentile = Decimal("100.00")
        stats.sell_fifth_percentile = Decimal("110.00")
        stats.buy_weighted_average = Decimal("105.00")
        stats.sell_weighted_average = Decimal("108.00")
        stats.buy_median = Decimal("103.00")
        stats.sell_median = Decimal("107.00")
        mock_type_stats.objects.get.return_value = stats

        item_type = Mock(id=34)
        region = Mock(id=10000002)

        result = type_statistics(item_type=item_type, region=region)

        self.assertEqual(result["buy_fifth_percentile"], Decimal("100.00"))
        self.assertEqual(result["sell_fifth_percentile"], Decimal("110.00"))
        self.assertEqual(result["buy_weighted_average"], Decimal("105.00"))
        self.assertEqual(result["sell_weighted_average"], Decimal("108.00"))
        self.assertEqual(result["buy_median"], Decimal("103.00"))
        self.assertEqual(result["sell_median"], Decimal("107.00"))
        self.assertIsNone(result["explain"])

    @patch("marketmanager.views.TypeStatistics")
    @patch("marketmanager.views.Order")
    def test_filters_by_region_when_provided(
        self, mock_order: Mock, mock_type_stats: Mock
    ) -> None:
        from django.core.exceptions import ObjectDoesNotExist

        inner_qs = self._make_orders_mock()
        outer_qs = MagicMock()
        outer_qs.filter.return_value = inner_qs
        mock_order.objects.filter.return_value = outer_qs
        mock_type_stats.objects.get.side_effect = ObjectDoesNotExist

        item_type = Mock(id=34)
        region = Mock(id=10000002)

        type_statistics(item_type=item_type, region=region)

        # Should filter by region on the outer queryset
        outer_qs.filter.assert_called_once_with(region=region)

    @patch("marketmanager.views.TypeStatistics")
    @patch("marketmanager.views.Order")
    def test_no_region_filter_when_region_is_none(
        self, mock_order: Mock, mock_type_stats: Mock
    ) -> None:
        from django.core.exceptions import ObjectDoesNotExist

        qs = MagicMock()
        buy_qs, sell_qs = MagicMock(), MagicMock()
        buy_qs.aggregate.return_value = {"volume": 0}
        sell_qs.aggregate.return_value = {"volume": 0}

        region_filter_called = False

        def _filter(**kwargs):
            nonlocal region_filter_called
            if "region" in kwargs:
                region_filter_called = True
            return buy_qs if kwargs.get("is_buy_order") is True else sell_qs

        qs.filter.side_effect = _filter
        mock_order.objects.filter.return_value = qs
        mock_type_stats.objects.get.side_effect = ObjectDoesNotExist

        type_statistics(item_type=Mock(id=34), region=None)

        self.assertFalse(
            region_filter_called,
            "region filter should not be applied when region=None",
        )


# ---------------------------------------------------------------------------
# Views — authentication / permission redirects
# ---------------------------------------------------------------------------


class TestViewAuthRedirects(TestCase):
    """Verify that unauthenticated requests are redirected to login."""

    def _assert_login_redirect(self, url_name: str) -> None:
        url = reverse(url_name)
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 301])
        # AA uses /account/login/ (no trailing 's')
        self.assertIn("login", response["Location"])

    def test_marketbrowser_requires_login(self) -> None:
        self._assert_login_redirect("marketmanager:marketbrowser")

    def test_marketwatches_requires_login(self) -> None:
        self._assert_login_redirect("marketmanager:marketwatches")

    def test_autocomplete_requires_login(self) -> None:
        self._assert_login_redirect("marketmanager:marketbrowser_autocomplete")

    def test_buy_orders_requires_login(self) -> None:
        self._assert_login_redirect("marketmanager:marketbrowser_buy_orders")

    def test_sell_orders_requires_login(self) -> None:
        self._assert_login_redirect("marketmanager:marketbrowser_sell_orders")


# ---------------------------------------------------------------------------
# Views — permission checks (403/redirect for logged-in users without perms)
# ---------------------------------------------------------------------------


class TestViewPermissionChecks(TestCase):
    """Verify that authenticated users without permissions are rejected."""

    def setUp(self) -> None:
        self.user = AuthUtils.create_member("noperms")
        AuthUtils.add_main_character_2(
            user=self.user,
            name="noperms",
            character_id=654321,
            disconnect_signals=True,
        )
        self.client.force_login(self.user)

    def test_marketbrowser_denies_without_perm(self) -> None:
        response = self.client.get(reverse("marketmanager:marketbrowser"))
        self.assertNotEqual(response.status_code, 200)

    def test_marketwatches_denies_without_perm(self) -> None:
        response = self.client.get(reverse("marketmanager:marketwatches"))
        self.assertNotEqual(response.status_code, 200)

    def test_autocomplete_denies_without_perm(self) -> None:
        response = self.client.get(reverse("marketmanager:marketbrowser_autocomplete"))
        self.assertNotEqual(response.status_code, 200)

    def test_buy_orders_denies_without_perm(self) -> None:
        response = self.client.get(reverse("marketmanager:marketbrowser_buy_orders"))
        self.assertNotEqual(response.status_code, 200)

    def test_sell_orders_denies_without_perm(self) -> None:
        response = self.client.get(reverse("marketmanager:marketbrowser_sell_orders"))
        self.assertNotEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# Views — marketbrowser
# ---------------------------------------------------------------------------


class TestMarketBrowserView(TestCase):
    """Tests for the marketbrowser view logic."""

    def setUp(self) -> None:
        self.user = _create_user_with_perm(self, "basic_market_browser")
        self.client.force_login(self.user)

    @patch("marketmanager.views.type_statistics")
    @patch("marketmanager.views.render")
    @patch("marketmanager.views.ItemMarketGroup")
    @patch("marketmanager.views.Region")
    @patch("marketmanager.views.ItemType")
    @patch("marketmanager.views.PublicConfig")
    def test_renders_with_no_params(
        self,
        mock_public_config: Mock,
        mock_item_type: Mock,
        mock_region: Mock,
        mock_img: Mock,
        mock_render: Mock,
        mock_type_stats: Mock,
    ) -> None:
        mock_public_config.get_solo.return_value.fetch_regions.all.return_value = []
        mock_img.objects.filter.return_value = []
        mock_render.return_value = HttpResponse("ok")
        mock_type_stats.return_value = {}

        response = self.client.get(reverse("marketmanager:marketbrowser"))

        self.assertEqual(response.status_code, 200)
        _args, kwargs = mock_render.call_args
        context = _args[2]
        self.assertIsNone(context["item_type"])
        self.assertIsNone(context["region"])
        self.assertIsNone(context["item_type_icon_url"])

    @patch("marketmanager.views.type_statistics")
    @patch("marketmanager.views.render")
    @patch("marketmanager.views.ItemMarketGroup")
    @patch("marketmanager.views.Region")
    @patch("marketmanager.views.ItemType")
    @patch("marketmanager.views.PublicConfig")
    def test_renders_with_valid_type_and_region(
        self,
        mock_public_config: Mock,
        mock_item_type: Mock,
        mock_region: Mock,
        mock_img: Mock,
        mock_render: Mock,
        mock_type_stats: Mock,
    ) -> None:
        mock_public_config.get_solo.return_value.fetch_regions.all.return_value = []
        mock_img.objects.filter.return_value = []

        type_obj = Mock(id=34)
        region_obj = Mock(id=10000002)
        mock_item_type.objects.get.return_value = type_obj
        mock_item_type.DoesNotExist = Exception
        mock_region.objects.get.return_value = region_obj
        mock_region.DoesNotExist = Exception
        mock_render.return_value = HttpResponse("ok")
        mock_type_stats.return_value = {}

        response = self.client.get(
            reverse("marketmanager:marketbrowser"),
            {"type_id": 34, "region_id": 10000002},
        )

        self.assertEqual(response.status_code, 200)
        _args, _ = mock_render.call_args
        context = _args[2]
        self.assertEqual(context["item_type"], type_obj)
        self.assertEqual(context["region"], region_obj)
        self.assertEqual(
            context["item_type_icon_url"],
            "https://images.evetech.net/types/34/icon?size=256",
        )

    @patch("marketmanager.views.type_statistics")
    @patch("marketmanager.views.render")
    @patch("marketmanager.views.ItemMarketGroup")
    @patch("marketmanager.views.Region")
    @patch("marketmanager.views.ItemType")
    @patch("marketmanager.views.PublicConfig")
    def test_handles_invalid_type_id(
        self,
        mock_public_config: Mock,
        mock_item_type: Mock,
        mock_region: Mock,
        mock_img: Mock,
        mock_render: Mock,
        mock_type_stats: Mock,
    ) -> None:
        mock_public_config.get_solo.return_value.fetch_regions.all.return_value = []
        mock_img.objects.filter.return_value = []

        mock_item_type.DoesNotExist = Exception
        mock_item_type.objects.get.side_effect = Exception("DoesNotExist")
        mock_region.DoesNotExist = Exception
        mock_region.objects.get.side_effect = Exception("DoesNotExist")
        mock_render.return_value = HttpResponse("ok")
        mock_type_stats.return_value = {}

        response = self.client.get(
            reverse("marketmanager:marketbrowser"),
            {"type_id": 99999, "region_id": 99999},
        )

        self.assertEqual(response.status_code, 200)
        _args, _ = mock_render.call_args
        context = _args[2]
        self.assertIsNone(context["item_type"])
        self.assertIsNone(context["region"])
        self.assertIsNone(context["item_type_icon_url"])
# ---------------------------------------------------------------------------
# Views — marketwatches
# ---------------------------------------------------------------------------


class TestMarketWatchesView(TestCase):
    """Tests for the marketwatches view."""

    def setUp(self) -> None:
        self.user = _create_user_with_perm(self, "basic_market_watches")
        self.client.force_login(self.user)

    @patch("marketmanager.views.render")
    @patch("marketmanager.views.SupplyConfig")
    def test_renders_successfully(
        self, mock_supply: Mock, mock_render: Mock
    ) -> None:
        mock_supply.objects.all.return_value.annotate.return_value.filter.return_value = []
        mock_render.return_value = HttpResponse("ok")

        response = self.client.get(reverse("marketmanager:marketwatches"))

        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once()

    @patch("marketmanager.views.render")
    @patch("marketmanager.views.SupplyConfig")
    def test_context_contains_watchconfigs(
        self, mock_supply: Mock, mock_render: Mock
    ) -> None:
        watchconfigs_result = [Mock(), Mock()]
        mock_supply.objects.all.return_value.annotate.return_value.filter.return_value = (
            watchconfigs_result
        )
        mock_render.return_value = HttpResponse("ok")

        self.client.get(reverse("marketmanager:marketwatches"))

        _args, _ = mock_render.call_args
        context = _args[2]
        self.assertEqual(context["watchconfigs"], watchconfigs_result)
# ---------------------------------------------------------------------------
# Views — marketbrowser_autocomplete
# ---------------------------------------------------------------------------


class TestMarketBrowserAutocomplete(TestCase):
    """Tests for the marketbrowser_autocomplete AJAX view."""

    def setUp(self) -> None:
        self.user = _create_user_with_perm(self, "basic_market_browser")
        self.client.force_login(self.user)

    @patch("marketmanager.views.ItemType")
    def test_returns_json_with_matching_types(self, mock_item_type: Mock) -> None:
        trit = Mock()
        trit.name = "Tritanium"
        trit.id = 34
        mock_item_type.objects.filter.return_value.order_by.return_value = [trit]

        response = self.client.get(
            reverse("marketmanager:marketbrowser_autocomplete"),
            {"term": "Tri"},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        import json
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["label"], "Tritanium")
        self.assertEqual(data[0]["value"], 34)

    @patch("marketmanager.views.ItemType")
    def test_filters_by_market_group_not_null(self, mock_item_type: Mock) -> None:
        mock_item_type.objects.filter.return_value.order_by.return_value = []

        self.client.get(
            reverse("marketmanager:marketbrowser_autocomplete"),
            {"term": "test"},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        mock_item_type.objects.filter.assert_called_once_with(
            name__icontains="test",
            market_group__isnull=False,
            published=1,
        )

    @patch("marketmanager.views.ItemType")
    def test_returns_empty_list_for_no_match(self, mock_item_type: Mock) -> None:
        mock_item_type.objects.filter.return_value.order_by.return_value = []

        response = self.client.get(
            reverse("marketmanager:marketbrowser_autocomplete"),
            {"term": "xyzzy"},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        self.assertEqual(data, [])

    @patch("marketmanager.views.ItemType")
    def test_non_ajax_request_uses_none_search_term(self, mock_item_type: Mock) -> None:
        mock_item_type.objects.filter.return_value.order_by.return_value = []

        response = self.client.get(reverse("marketmanager:marketbrowser_autocomplete"))

        self.assertEqual(response.status_code, 200)
        mock_item_type.objects.filter.assert_called_once_with(
            name__icontains=None,
            market_group__isnull=False,
            published=1,
        )


# ---------------------------------------------------------------------------
# Views — marketbrowser_buy_orders
# ---------------------------------------------------------------------------


def _make_order_dict(**overrides):
    base = {
        "volume_remain": 100,
        "price": Decimal("1000.00"),
        "location_id": 60003760,
        "issued": datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        "duration": 90,
        "region__name": "The Forge",
        "updated_at": datetime.datetime(2025, 1, 2, tzinfo=datetime.timezone.utc),
        "user_is_owner": False,
        "corporation_is_owner": False,
    }
    base.update(overrides)
    return base


class TestMarketBrowserBuyOrders(TestCase):
    """Tests for the marketbrowser_buy_orders AJAX view."""

    def setUp(self) -> None:
        self.user = _create_user_with_perm(self, "basic_market_browser")
        self.client.force_login(self.user)

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_returns_buy_orders_json(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        order = _make_order_dict()
        values_qs = MagicMock()
        values_qs.filter.return_value = [order]
        values_qs.__iter__.return_value = iter([order])
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            values_qs
        )
        station = Mock()
        station.name = "Jita IV"
        mock_resolver.return_value = ({60003760: station}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_buy_orders"),
            {"type_id": 34, "region_id": 10000002},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertIn("buy_orders", data)
        self.assertEqual(data["buy_orders"][0]["location_resolved"], "Jita IV")

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_resolves_structure_location(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        order = _make_order_dict(location_id=1000000000001)
        orders_qs = [order]
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            orders_qs
        )
        structure = Mock()
        structure.name = "My Keepstar"
        mock_resolver.return_value = ({}, {1000000000001: structure})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_buy_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        self.assertEqual(data["buy_orders"][0]["location_resolved"], "My Keepstar")

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_unresolved_location_falls_back_to_id(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        order = _make_order_dict(location_id=9999999999)
        orders_qs = [order]
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            orders_qs
        )
        mock_resolver.return_value = ({}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_buy_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        self.assertEqual(data["buy_orders"][0]["location_resolved"], 9999999999)

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_expiry_is_calculated(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        issued = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        order = _make_order_dict(issued=issued, duration=90)
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            [order]
        )
        station = Mock()
        station.name = "Jita"
        mock_resolver.return_value = ({60003760: station}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_buy_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        expected_expiry = issued + datetime.timedelta(days=90)
        self.assertIn("expiry_calculated", data["buy_orders"][0])
        self.assertEqual(
            data["buy_orders"][0]["expiry_calculated"],
            expected_expiry.isoformat().replace("+00:00", "Z"),
        )

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_no_orders_returns_empty_list(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            []
        )
        mock_resolver.return_value = ({}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_buy_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        self.assertEqual(data["buy_orders"], [])

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_non_ajax_with_highlight_permissions(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        self.user = AuthUtils.add_permissions_to_user_by_name(
            [
                "marketmanager.order_highlight_user",
                "marketmanager.order_highlight_corporation",
            ],
            self.user,
        )
        self.client.force_login(self.user)

        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = []
        mock_resolver.return_value = ({}, {})

        response = self.client.get(reverse("marketmanager:marketbrowser_buy_orders"))

        self.assertEqual(response.status_code, 200)
        mock_order.objects.filter.assert_called_once_with(item_type=None, is_buy_order=True)


# ---------------------------------------------------------------------------
# Views — marketbrowser_sell_orders
# ---------------------------------------------------------------------------


def _make_sell_order_dict(**overrides):
    base = _make_order_dict(**overrides)
    base["order_id"] = overrides.get("order_id", 123456789)
    return base


class TestMarketBrowserSellOrders(TestCase):
    """Tests for the marketbrowser_sell_orders AJAX view."""

    def setUp(self) -> None:
        self.user = _create_user_with_perm(self, "basic_market_browser")
        self.client.force_login(self.user)

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_returns_sell_orders_json(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        order = _make_sell_order_dict()
        values_qs = MagicMock()
        values_qs.filter.return_value = [order]
        values_qs.__iter__.return_value = iter([order])
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            values_qs
        )
        station = Mock()
        station.name = "Jita IV"
        mock_resolver.return_value = ({60003760: station}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_sell_orders"),
            {"type_id": 34, "region_id": 10000002},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertIn("sell_orders", data)
        self.assertEqual(data["sell_orders"][0]["location_resolved"], "Jita IV")

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_resolves_structure_location(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        order = _make_sell_order_dict(location_id=1000000000002)
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            [order]
        )
        structure = Mock()
        structure.name = "Fortizar"
        mock_resolver.return_value = ({}, {1000000000002: structure})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_sell_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        self.assertEqual(data["sell_orders"][0]["location_resolved"], "Fortizar")

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_unresolved_location_falls_back_to_id(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        order = _make_sell_order_dict(location_id=8888888888)
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            [order]
        )
        mock_resolver.return_value = ({}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_sell_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        self.assertEqual(data["sell_orders"][0]["location_resolved"], 8888888888)

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_filters_by_region_when_provided(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        inner_qs = []
        values_qs = MagicMock()
        values_qs.__iter__ = Mock(return_value=iter(inner_qs))
        values_qs.filter.return_value = inner_qs
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            values_qs
        )
        mock_resolver.return_value = ({}, {})

        self.client.get(
            reverse("marketmanager:marketbrowser_sell_orders"),
            {"type_id": 34, "region_id": 10000002},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        values_qs.filter.assert_called_once_with(region="10000002")

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_no_region_filter_without_param(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        values_qs = MagicMock()
        values_qs.__iter__ = Mock(return_value=iter([]))
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            values_qs
        )
        mock_resolver.return_value = ({}, {})

        self.client.get(
            reverse("marketmanager:marketbrowser_sell_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        values_qs.filter.assert_not_called()

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_expiry_is_calculated(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        issued = datetime.datetime(2025, 3, 1, tzinfo=datetime.timezone.utc)
        order = _make_sell_order_dict(issued=issued, duration=30)
        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = (
            [order]
        )
        station = Mock()
        station.name = "Station"
        mock_resolver.return_value = ({60003760: station}, {})

        response = self.client.get(
            reverse("marketmanager:marketbrowser_sell_orders"),
            {"type_id": 34},
            headers={"x-requested-with": "XMLHttpRequest"}
        )

        import json
        data = json.loads(response.content)
        expected_expiry = issued + datetime.timedelta(days=30)
        self.assertEqual(
            data["sell_orders"][0]["expiry_calculated"],
            expected_expiry.isoformat().replace("+00:00", "Z"),
        )

    @patch("marketmanager.views.bulk_location_resolver")
    @patch("marketmanager.views.Order")
    def test_non_ajax_with_highlight_permissions(
        self, mock_order: Mock, mock_resolver: Mock
    ) -> None:
        self.user = AuthUtils.add_permissions_to_user_by_name(
            [
                "marketmanager.order_highlight_user",
                "marketmanager.order_highlight_corporation",
            ],
            self.user,
        )
        self.client.force_login(self.user)

        mock_order.objects.filter.return_value.annotate.return_value.values.return_value = []
        mock_resolver.return_value = ({}, {})

        response = self.client.get(reverse("marketmanager:marketbrowser_sell_orders"))

        self.assertEqual(response.status_code, 200)
        mock_order.objects.filter.assert_called_once_with(item_type=None, is_buy_order=False)


# ---------------------------------------------------------------------------
# Views — item_selector
# ---------------------------------------------------------------------------


class TestItemSelectorView(TestCase):
    """Tests for the item_selector view."""

    def setUp(self) -> None:
        self.user = _create_user_with_perm(self, "basic_market_browser")
        self.client.force_login(self.user)

    @patch("marketmanager.views.render")
    @patch("marketmanager.views.ItemMarketGroup")
    def test_renders_with_market_groups_context(
        self, mock_img: Mock, mock_render: Mock
    ) -> None:
        groups = [Mock(), Mock()]
        mock_img.objects.all.return_value = groups
        mock_render.return_value = HttpResponse("ok")

        # item_selector is not wired to a URL; test via render mock on marketbrowser
        # to confirm item_selector context key — test the function directly instead
        from django.test import RequestFactory

        from marketmanager.views import item_selector

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user
        mock_render.reset_mock()

        item_selector(request)

        _args, _ = mock_render.call_args
        context = _args[2]
        self.assertIn("market_groups", context)
        self.assertEqual(context["market_groups"], groups)

    @patch("marketmanager.views.render")
    @patch("marketmanager.views.ItemMarketGroup")
    def test_uses_item_selector_template(
        self, mock_img: Mock, mock_render: Mock
    ) -> None:
        mock_img.objects.all.return_value = []
        mock_render.return_value = HttpResponse("ok")

        from django.test import RequestFactory

        from marketmanager.views import item_selector

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        item_selector(request)

        _args, _ = mock_render.call_args
        self.assertEqual(_args[1], "marketmanager/item_selector.html")


class TestTokenRedirectViews(SimpleTestCase):
    """Tests for add_char and add_corp redirect endpoints."""

    def test_add_char_returns_marketbrowser_redirect(self) -> None:
        request = RequestFactory().get("/")

        response = add_char.__wrapped__.__wrapped__(request, token=Mock())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("marketmanager:marketbrowser"))

    def test_add_corp_returns_marketbrowser_redirect(self) -> None:
        request = RequestFactory().get("/")

        response = add_corp.__wrapped__.__wrapped__(request, token=Mock())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("marketmanager:marketbrowser"))
        self.assertEqual(response.url, reverse("marketmanager:marketbrowser"))
