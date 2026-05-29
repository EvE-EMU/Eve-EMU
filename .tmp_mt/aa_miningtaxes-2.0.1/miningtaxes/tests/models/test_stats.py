from unittest.mock import patch

from ...models import Settings, Stats
from ..base import MiningTaxesBaseTestCase


class TestStats(MiningTaxesBaseTestCase):
    @patch("miningtaxes.models.stats.bootstrap_icon_plus_name_html")
    def test_stats_full_pipeline(self, mock_icon):
        mock_icon.side_effect = lambda **kwargs: kwargs["name"]
        stats = Stats.load()

        self.assertEqual(stats.characterize(9999)[1], "unknown")
        self.assertEqual(stats.characterize(1102)[1], "unregistered")
        self.assertEqual(stats.characterize(1001)[1], "found")

        taxes = stats.calctaxes()
        self.assertIn(self.user, taxes)
        self.assertIn(self.other_user, taxes)

        stats.precalc_all()

        self.assertTrue(stats.get_admin_char_json())
        self.assertTrue(stats.get_admin_main_json())
        self.assertTrue(stats.get_ore_prices_json())
        self.assertTrue(stats.get_admin_get_all_activity_json())
        self.assertIn("anal", stats.get_admin_mining_by_sys_json())
        self.assertIn("csv", stats.get_admin_tax_revenue_json())
        self.assertIn("xdata", stats.get_admin_month_json())
        self.assertIn("data", stats.get_admin_corp_ledger())
        corp_history = stats.get_admin_corp_mining_history()
        self.assertIn("mining_log", corp_history)
        self.assertIn("unknown_data", corp_history)
        self.assertIn("unregistered_data", corp_history)
        self.assertIn("data", stats.get_leaderboards())
        self.assertIn("data", stats.get_curmonth_leadergraph())
        ledger_90 = stats.get_user_mining_ledger_90day()
        self.assertIn(self.user.pk, ledger_90)

    @patch("miningtaxes.models.stats.bootstrap_icon_plus_name_html")
    def test_stats_singleton_and_phrase_filter(self, mock_icon):
        mock_icon.side_effect = lambda **kwargs: kwargs["name"]
        stats = Stats.load()
        stats.admin_char_json = [{"value": 1}]
        stats.save()
        self.assertEqual(Stats.load().pk, 1)
        self.assertEqual(Stats.load().get_admin_char_json(), [{"value": 1}])

        settings = Settings.load()
        settings.phrase = "moon"
        settings.save()
        stats.calc_admin_tax_revenue_json()
        data = stats.get_admin_tax_revenue_json()
        self.assertEqual(len(data["csv"]), 2)

        stats.delete()
        self.assertTrue(Stats.objects.filter(pk=1).exists())
