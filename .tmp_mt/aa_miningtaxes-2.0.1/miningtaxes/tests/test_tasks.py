from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.utils.timezone import now
from esi.errors import TokenError

from allianceauth.eveonline.models import EveCharacter

from .. import tasks
from ..models import (
    AdminCharacter,
    AdminMiningCorpLedgerEntry,
    Character,
    OrePrices,
    Settings,
    Stats,
)
from .base import MiningTaxesBaseTestCase


class TestTasks(MiningTaxesBaseTestCase):
    def test_calctaxes_and_get_user(self):
        self.assertIn(self.user, tasks.calctaxes())
        self.assertEqual(
            tasks.get_user(self.main_character.eve_character.character_id),
            self.main_character,
        )
        self.assertIsNone(tasks.get_user(9999))

    @patch("miningtaxes.tasks.notify")
    @patch("miningtaxes.tasks.calctaxes")
    def test_notify_tasks(self, mock_calctaxes, mock_notify):
        mock_calctaxes.return_value = {self.user: [100.0, 0.0, self.main_character]}
        tasks.notify_taxes_due.run()
        tasks.notify_second_taxes_due.run()
        self.assertEqual(mock_notify.call_count, 2)

    @patch("miningtaxes.tasks.notify")
    @patch("miningtaxes.tasks.Stats.load")
    def test_notify_current_threshold(self, mock_load, mock_notify):
        mock_load.return_value.get_admin_main_json.return_value = [
            {"balance": 2000000000, "user": self.user.pk},
            {"balance": 1, "user": 9999},
        ]
        tasks.notify_current_taxes_threshold.run()
        mock_notify.assert_called_once()

    @patch("miningtaxes.tasks.notify")
    @patch("miningtaxes.tasks.calctaxes")
    def test_apply_interest(self, mock_calctaxes, mock_notify):
        settings = Settings.load()
        settings.interest_rate = 10
        settings.save()
        mock_calctaxes.return_value = {self.user: [100.0, 0.0, self.main_character]}
        tasks.apply_interest.run()
        self.assertTrue(
            self.main_character.tax_credits.filter(credit_type="interest").exists()
        )
        mock_notify.assert_called_once()

    @patch("miningtaxes.tasks.requests.get")
    def test_valid_janice_api_key(self, mock_get):
        mock_get.return_value.json.return_value = {}
        self.assertTrue(tasks.valid_janice_api_key())
        mock_get.return_value.json.return_value = {"status": "bad"}
        self.assertFalse(tasks.valid_janice_api_key())

    @patch("miningtaxes.tasks.requests.post")
    @patch("miningtaxes.tasks.requests.get")
    def test_get_bulk_prices(self, mock_get, mock_post):
        with patch("miningtaxes.tasks.MININGTAXES_PRICE_METHOD", "Fuzzwork"):
            mock_get.return_value.json.return_value = {
                "45511": {"buy": {"max": "1"}, "sell": {"min": "2"}}
            }
            self.assertIn("45511", tasks.get_bulk_prices([45511]))

        with patch("miningtaxes.tasks.MININGTAXES_PRICE_METHOD", "Janice"):
            mock_post.return_value.json.return_value = [
                {
                    "itemType": {"eid": 45511},
                    tasks.MININGTAXES_PRICE_JANICE_TIMING: {
                        tasks.MININGTAXES_PRICE_JANICE_BUY: 3,
                        tasks.MININGTAXES_PRICE_JANICE_SELL: 4,
                    },
                }
            ]
            self.assertEqual(tasks.get_bulk_prices([45511])["45511"]["buy"]["max"], "3")

    @patch("miningtaxes.tasks.get_bulk_prices")
    def test_update_all_prices(self, mock_bulk):
        def fake_bulk(type_ids):
            return {
                str(tid): {"buy": {"max": "11"}, "sell": {"min": "22"}}
                for tid in type_ids
            }

        mock_bulk.side_effect = fake_bulk
        OrePrices.objects.all().delete()
        tasks.update_all_prices.run(force=[45511])
        self.assertTrue(OrePrices.objects.filter(eve_type_id=45511).exists())

    def test_update_all_prices_non_fuzzwork_branches(self):
        with patch("miningtaxes.tasks.MININGTAXES_PRICE_METHOD", "Invalid"):
            self.assertIsNone(tasks.update_all_prices.run(force=[]))
        with patch("miningtaxes.tasks.MININGTAXES_PRICE_METHOD", "Janice"), patch(
            "miningtaxes.tasks.valid_janice_api_key", return_value=False
        ):
            self.assertIsNone(tasks.update_all_prices.run(force=[]))

    @patch("miningtaxes.tasks.add_corp_moon_taxes")
    @patch("miningtaxes.tasks.Stats.load")
    def test_precalcs(self, mock_stats_load, mock_add_corp):
        stats = Stats.load()
        mock_stats_load.return_value = stats
        with patch.object(stats, "precalc_all") as mock_stats_precalc, patch.object(
            Character, "precalc_all"
        ) as mock_char_precalc:
            tasks.precalcs.run([True, False])
            self.assertTrue(mock_char_precalc.called)
            mock_stats_precalc.assert_called_once()
            mock_add_corp.assert_called_once()

    @patch("miningtaxes.tasks.update_character")
    @patch("esi.models.Token.get_token")
    def test_auto_add_chars(self, mock_get_token, mock_update_character):
        tracked = EveCharacter.objects.create(
            character_id=1200,
            character_name="Tim Drake",
            corporation_id=self.admin_character.eve_character.corporation_id,
            corporation_name=self.admin_character.eve_character.corporation_name,
            corporation_ticker=self.admin_character.eve_character.corporation_ticker,
            alliance_id=self.admin_character.eve_character.alliance_id,
            alliance_name=self.admin_character.eve_character.alliance_name,
            alliance_ticker=self.admin_character.eve_character.alliance_ticker,
        )
        tracked_ownership = self.user.character_ownerships.create(character=tracked)
        self.user.profile.main_character = self.ownership.character
        self.user.profile.save()
        mock_get_token.return_value = object()

        tasks.auto_add_chars.run()

        self.assertTrue(mock_update_character.called)
        self.assertTrue(
            Character.objects.filter(eve_character=tracked_ownership.character).exists()
        )

    @patch("miningtaxes.tasks.chord")
    @patch("miningtaxes.tasks.update_character")
    @patch("miningtaxes.tasks.update_admin_character")
    @patch("miningtaxes.tasks.update_all_prices")
    @patch("miningtaxes.tasks.precalcs")
    def test_update_daily(
        self,
        mock_precalcs,
        mock_prices,
        mock_update_admin,
        mock_update_character,
        mock_chord,
    ):
        mock_update_character.s.side_effect = lambda **kwargs: kwargs
        mock_precalcs.s.return_value = "precalc-sig"
        mock_chord.return_value = lambda sig: None
        tasks.update_daily.run()
        mock_prices.assert_called_once()
        self.assertTrue(mock_update_admin.called)
        mock_chord.assert_called_once()

    def test_add_credit_helpers(self):
        tasks.add_tax_credits()
        self.assertTrue(self.main_character.tax_credits.filter(credit=150.0).exists())

        AdminMiningCorpLedgerEntry.objects.create(
            character=self.admin_character,
            date=now(),
            taxed_id=self.main_character.eve_character.character_id,
            amount=12.0,
            reason="moon",
        )
        settings = Settings.load()
        settings.phrase = "moon"
        settings.save()
        tasks.add_tax_credits_by_char(self.main_character)
        self.assertTrue(self.main_character.tax_credits.filter(credit=12.0).exists())

    def test_add_corp_moon_tax_helpers(self):
        Character.objects.filter(pk=self.main_character.pk).update(life_taxes=0)
        tasks.add_corp_moon_taxes_by_char(self.main_character)
        self.assertTrue(
            self.main_character.mining_ledger.filter(
                eve_type_id=45511, eve_solar_system_id=30002537, quantity=100
            ).exists()
        )
        tasks.add_corp_moon_taxes()

    @patch("miningtaxes.tasks.add_corp_moon_taxes")
    @patch.object(AdminCharacter, "update_all")
    def test_update_admin_character(self, mock_update_all, mock_add_corp):
        self.assertFalse(
            tasks.update_admin_character.run(
                character_pk=self.admin_character.pk, force_update=False
            )
            is True
        )
        tasks.update_admin_character.run(
            character_pk=self.admin_character.pk, force_update=True
        )
        mock_update_all.assert_called()

    @patch("miningtaxes.tasks.users_with_permission")
    @patch("miningtaxes.tasks.notify")
    @patch.object(Character, "update_mining_ledger", side_effect=TokenError())
    def test_update_character_token_error(self, mock_update, mock_notify, mock_users):
        perm = Permission.objects.filter(
            content_type__app_label="miningtaxes", codename="admin_access"
        ).first()
        mock_users.return_value = [self.user]
        self.assertIsNotNone(perm)
        self.assertFalse(
            tasks.update_character.run(
                character_pk=self.main_character.pk, force_update=True
            )
        )
        mock_notify.assert_called_once()

    @patch("miningtaxes.tasks.add_corp_moon_taxes_by_char")
    @patch("miningtaxes.tasks.add_tax_credits_by_char")
    @patch.object(Character, "update_mining_ledger")
    def test_update_character_success(self, mock_update, mock_credits, mock_corp):
        self.assertFalse(
            tasks.update_character.run(
                character_pk=self.main_character.pk, force_update=True
            )
        )
        mock_update.assert_called_once()
        mock_credits.assert_called_once()
