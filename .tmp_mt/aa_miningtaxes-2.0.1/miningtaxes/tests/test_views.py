import datetime as dt
import inspect
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now

from .. import views
from ..models import Character, OrePrices, Settings
from .base import MiningTaxesBaseTestCase


class TestViews(MiningTaxesBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.factory = RequestFactory()

    @patch("miningtaxes.views.Stats.load")
    def test_admin_json_views(self, mock_load):
        stats = MagicMock()
        stats.get_admin_char_json.return_value = [{"a": 1}]
        stats.get_admin_main_json.return_value = [{"b": 1}]
        stats.get_admin_get_all_activity_json.return_value = [["h"]]
        stats.get_admin_corp_ledger.return_value = {"data": []}
        stats.get_admin_corp_mining_history.return_value = {"mining_log": []}
        stats.get_admin_mining_by_sys_json.return_value = {"anal": {}}
        stats.get_admin_tax_revenue_json.return_value = {"csv": []}
        stats.get_admin_month_json.return_value = {"csv": []}
        mock_load.return_value = stats

        for name in [
            "admin_char_json",
            "admin_main_json",
            "admin_get_all_activity_json",
            "admin_corp_ledger",
            "admin_corp_mining_history",
            "admin_mining_by_sys_json",
            "admin_tax_revenue_json",
            "admin_month_json",
        ]:
            response = self.client.get(reverse(f"miningtaxes:{name}"))
            self.assertEqual(response.status_code, 200)

    @patch("miningtaxes.views.render", return_value=HttpResponse("ok"))
    def test_admin_launcher_and_tax_table(self, mock_render):
        response = self.client.get(reverse("miningtaxes:admin_launcher"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("miningtaxes:admin_launcher"),
            {"phrase": "abc", "interest_rate": 7},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Settings.load().phrase, "abc")

        response = self.client.get(reverse("miningtaxes:admin_launcher_tax_table"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

        ore = OrePrices.objects.get(eve_type_id=45511)
        response = self.client.post(
            reverse("miningtaxes:admin_launcher_save_rates"),
            {"tax_data": json.dumps([{"tid": ore.id, "tax_rate": 33}])},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        ore.refresh_from_db()
        self.assertEqual(ore.tax_rate, 33)

    @patch("miningtaxes.views.render", return_value=HttpResponse("ok"))
    def test_admin_tables(self, mock_render):
        response = self.client.get(reverse("miningtaxes:admin_tables"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("miningtaxes:admin_tables"),
            {"creditbox": "bad", "userid": self.user.pk},
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("miningtaxes:admin_tables"),
            {"creditbox": "15", "userid": self.user.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.main_character.tax_credits.filter(credit=15).exists())

    @patch("miningtaxes.views.render", return_value=HttpResponse("ok"))
    @patch("miningtaxes.views.Stats.load")
    def test_basic_views_and_json(self, mock_load, mock_render):
        stats = MagicMock()
        stats.get_ore_prices_json.return_value = [{"x": 1}]
        stats.get_leaderboards.return_value = {"data": []}
        stats.get_curmonth_leadergraph.return_value = {"data": {}}
        stats.get_user_mining_ledger_90day.return_value = {
            str(self.user.pk): {"days": []}
        }
        stats.main_data_helper.return_value = (
            {self.ownership.character: {"balance": 1, "last_paid": None}},
            {},
            {self.user: [1]},
        )
        mock_load.return_value = stats

        self.assertEqual(
            self.client.get(reverse("miningtaxes:ore_prices")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("miningtaxes:ore_prices_json")).status_code, 200
        )
        self.assertEqual(self.client.get(reverse("miningtaxes:faq")).status_code, 200)
        self.assertEqual(self.client.get(reverse("miningtaxes:index")).status_code, 302)
        self.assertEqual(
            self.client.get(reverse("miningtaxes:leaderboards")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("miningtaxes:curmonthgraph")).status_code, 200
        )

    @patch("miningtaxes.views.render", return_value=HttpResponse("ok"))
    @patch("miningtaxes.views.humanize_number", side_effect=lambda value: str(value))
    def test_user_views(self, mock_humanize, mock_render):
        response = self.client.get(
            reverse("miningtaxes:user_summary", args=[self.user.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:summary_month_json", args=[self.user.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:all_tax_credits", args=[self.user.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("miningtaxes:launcher")).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:user_ledger", args=[self.user.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:user_ledger_data", args=[self.user.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "miningtaxes:character_mining_ledger_data",
                    args=[self.main_character.pk],
                )
            ).status_code,
            200,
        )

    def test_forbidden_user_views(self):
        self.client.force_login(self.other_user)
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:user_summary", args=[self.user.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:summary_month_json", args=[self.user.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:all_tax_credits", args=[self.user.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:user_ledger", args=[self.user.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:user_ledger_data", args=[self.user.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "miningtaxes:character_mining_ledger_data",
                    args=[self.main_character.pk],
                )
            ).status_code,
            403,
        )

    def test_mutating_views(self):
        observer = self.admin_character.mining_obs.first()
        old_entry = observer.mining_log.create(
            date=(now() - dt.timedelta(days=100)).date(),
            miner_id=1001,
            eve_type_id=45511,
            quantity=1,
            observer_type="structure",
            eve_solar_system_id=30002537,
        )
        response = self.client.get(
            reverse("miningtaxes:purge_old_corphistory"), follow=False
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(type(old_entry).objects.filter(pk=old_entry.pk).exists())

        response = self.client.get(
            reverse(
                "miningtaxes:remove_admin_registered", args=[self.alt_character.pk]
            ),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get(
            reverse(
                "miningtaxes:remove_admin_character", args=[self.admin_character.pk]
            ),
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        removable = Character.objects.create(
            eve_character=self.unregistered_ownership.character
        )
        response = self.client.get(
            reverse("miningtaxes:remove_character", args=[removable.pk]), follow=False
        )
        self.assertEqual(response.status_code, 302)

    def test_remove_character_forbidden_and_notfound(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("miningtaxes:remove_character", args=[self.main_character.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("miningtaxes:remove_admin_registered", args=[9999])
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.get(
            reverse("miningtaxes:remove_admin_character", args=[9999])
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("miningtaxes:remove_character", args=[9999]))
        self.assertEqual(response.status_code, 404)

    @patch("miningtaxes.views.messages.success")
    @patch("miningtaxes.views.tasks.update_admin_character.delay")
    def test_add_admin_character_direct(self, mock_delay, mock_success):
        request = self.factory.get("/")
        request.user = self.user
        response = inspect.unwrap(views.add_admin_character)(
            request, SimpleNamespace(character_id=1001)
        )
        self.assertEqual(response.status_code, 302)
        mock_delay.assert_called_once()

    @patch("miningtaxes.views.messages.success")
    @patch("miningtaxes.views.Stats.load")
    @patch("miningtaxes.views.tasks.update_character.delay")
    def test_add_character_direct(self, mock_delay, mock_load, mock_success):
        request = self.factory.get("/")
        request.user = self.user
        mock_load.return_value = MagicMock()
        response = inspect.unwrap(views.add_character)(
            request, SimpleNamespace(character_id=1102)
        )
        self.assertEqual(response.status_code, 302)
        mock_delay.assert_called_once()

    @patch("miningtaxes.views.render", return_value=HttpResponse("ok"))
    def test_character_viewer_and_user_mining_ledger_90day(self, mock_render):
        self.assertEqual(
            self.client.get(
                reverse("miningtaxes:character_viewer", args=[self.main_character.pk])
            ).status_code,
            200,
        )
        with patch("miningtaxes.views.Stats.load") as mock_load:
            mock_load.return_value.get_user_mining_ledger_90day.return_value = {
                str(self.user.pk): {"days": []}
            }
            self.assertEqual(
                self.client.get(
                    reverse("miningtaxes:user_mining_ledger_90day", args=[self.user.pk])
                ).status_code,
                200,
            )
            mock_load.return_value.get_user_mining_ledger_90day.return_value = {}
            self.assertEqual(
                self.client.get(
                    reverse("miningtaxes:user_mining_ledger_90day", args=[self.user.pk])
                ).status_code,
                403,
            )
