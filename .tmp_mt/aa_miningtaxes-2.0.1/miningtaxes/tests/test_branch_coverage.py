import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.http.response import Http404
from django.test import RequestFactory
from django.utils.timezone import now
from esi.errors import TokenError

from allianceauth.eveonline.models import EveCharacter

from .. import tasks, views
from ..models import AdminCharacter, Character, CharacterUpdateStatus, Settings, Stats
from ..models.admin import AdminMiningObservers
from ..models.admin import _esi_value as admin_esi_value
from ..models.character import _esi_value as char_esi_value
from ..models.character import (
    _is_high_sec,
    _is_low_sec,
    _is_null_sec,
    _is_trig_space,
    _is_w_space,
    _rounded_security_status,
)
from .base import MiningTaxesBaseTestCase
from .utils import create_character_update_status


class TestBranchCoverage(MiningTaxesBaseTestCase):
    def test_character_helper_functions(self):
        trig = SimpleNamespace(
            name="Pochven", security_status=-0.2, visual_effect="TRIGLAVIAN_HOME"
        )
        wormhole = SimpleNamespace(
            name="J123456", security_status=-0.9, visual_effect=""
        )
        hisec = SimpleNamespace(name="Amarr", security_status=0.51, visual_effect="")
        lowsec = SimpleNamespace(name="Auner", security_status=0.35, visual_effect="")
        nullsec = SimpleNamespace(name="Null", security_status=-0.1, visual_effect="")
        unknown = SimpleNamespace(
            name="Unknown", security_status=None, visual_effect=""
        )

        self.assertEqual(admin_esi_value({"x": 1}, "x"), 1)
        self.assertEqual(char_esi_value(SimpleNamespace(x=2), "x"), 2)
        self.assertIsNone(_rounded_security_status(unknown))
        self.assertTrue(_is_trig_space(trig))
        self.assertTrue(_is_w_space(wormhole))
        self.assertFalse(_is_w_space(trig))
        self.assertTrue(_is_high_sec(hisec))
        self.assertTrue(_is_low_sec(lowsec))
        self.assertTrue(_is_null_sec(nullsec))
        self.assertFalse(_is_null_sec(wormhole))

    def test_orphan_character_properties_and_fetch_token(self):
        eve = EveCharacter.objects.create(
            character_id=1300,
            character_name="Orphan Annie",
            corporation_id=2999,
            corporation_name="No Corp",
            corporation_ticker="NC",
            alliance_id=None,
            alliance_name="",
            alliance_ticker="",
        )
        orphan = Character.objects.create(eve_character=eve)

        self.assertTrue(orphan.is_orphan)
        self.assertIsNone(orphan.user)
        self.assertIsNone(orphan.main_character)
        self.assertFalse(orphan.is_main)
        self.assertFalse(orphan.user_is_owner(self.user))
        with self.assertRaises(TokenError):
            orphan.fetch_token()

    @patch("miningtaxes.models.character.notify_throttled")
    def test_fetch_token_missing_notifies(self, mock_notify):
        with self.assertRaises(TokenError):
            self.main_character.fetch_token(scopes=["missing.scope"])
        mock_notify.assert_called_once()

    def test_queryset_access_helpers(self):
        self.assertIn(
            self.main_character.eve_character.character_id,
            Character.objects.eve_character_ids(),
        )
        self.assertTrue(
            Character.objects.owned_by_user(self.user)
            .filter(pk=self.main_character.pk)
            .exists()
        )
        self.assertTrue(
            Character.objects.user_has_access(self.user)
            .filter(pk=self.other_character.pk)
            .exists()
        )
        self.assertFalse(
            Character.objects.user_has_access(self.other_user)
            .filter(pk=self.main_character.pk)
            .exists()
        )
        self.assertTrue(self.main_character.user_has_access(self.user))
        self.assertFalse(self.main_character.user_has_access(self.other_user))

    def test_update_status_helpers(self):
        old_update_section = getattr(Character, "UpdateSection", None)
        Character.UpdateSection = SimpleNamespace(choices=[("ledger", "Ledger")])
        self.assertIsNone(self.main_character.is_update_status_ok())
        status = CharacterUpdateStatus.objects.create(
            character=self.main_character,
            is_success=True,
            started_at=now() - dt.timedelta(minutes=10),
            finished_at=now(),
            last_error_message="",
        )
        self.assertTrue(self.main_character.is_update_status_ok())
        self.assertFalse(status.is_updating)
        status.finished_at = None
        status.save()
        self.assertTrue(status.is_updating)
        self.assertTrue(status.has_changed({"a": 1}))
        status.update_content_hash({"a": 1})
        self.assertFalse(status.has_changed({"a": 1}))
        status.update_content_hash({"b": 2}, hash_num=2)
        status.update_content_hash({"c": 3}, hash_num=3)
        status.reset(root_task_id="root", parent_task_id="parent")
        self.assertEqual(status.root_task_id, "root")
        self.assertEqual(status.parent_task_id, "parent")
        if old_update_section is None:
            delattr(Character, "UpdateSection")
        else:
            Character.UpdateSection = old_update_section

    def test_is_update_status_error_and_ledger_stale(self):
        CharacterUpdateStatus.objects.create(
            character=self.main_character,
            is_success=False,
            started_at=now() - dt.timedelta(minutes=10),
            finished_at=now() - dt.timedelta(minutes=5),
            last_error_message="boom",
        )
        self.assertFalse(self.main_character.is_update_status_ok())
        self.assertTrue(self.main_character.is_ledger_stale())

        self.main_character.update_status_set.all().delete()
        create_character_update_status(
            self.main_character,
            started_at=now()
            - Character.update_time_until_stale()
            - dt.timedelta(minutes=1),
            finished_at=now(),
        )
        self.assertTrue(self.main_character.is_ledger_stale())

    def test_character_aggregate_helpers(self):
        self.assertTrue(self.main_character.get_curmonth_daily_mining().exists())
        self.assertGreaterEqual(self.main_character.get_lifetime_taxes(), 0)
        self.assertGreaterEqual(self.main_character.get_lifetime_credits(), 0)
        self.assertTrue(self.main_character.get_monthly_taxes())
        self.assertTrue(self.main_character.get_monthly_credits())
        self.assertTrue(self.main_character.get_monthly_mining())
        self.assertTrue(self.main_character.get_90d_mining().exists())
        self.assertIsNotNone(self.main_character.last_paid())
        with self.assertRaises(Exception):
            self.main_character.give_credit(1, "bad")
        self.main_character.precalc_all()

    def test_character_json_standardize(self):
        months = [
            {"month": dt.datetime(2024, 1, 1), "total": 1},
            {"month": dt.date(2024, 2, 1), "total": 2},
        ]
        standardized = self.main_character.json_standardize(months)
        self.assertEqual(standardized["2024-01-01"], 1)
        self.assertEqual(
            self.main_character.standardize(standardized)[dt.date(2024, 2, 1)], 2
        )

    @patch("miningtaxes.models.character.get_tax", return_value=0.1)
    @patch(
        "miningtaxes.models.character.ore_calc_prices", return_value=(10.0, 8.0, 6.0)
    )
    def test_calc_prices_tax_filters(self, mock_prices, mock_tax):
        ledger = self.main_character.mining_ledger.create(
            date=now().date(),
            quantity=1,
            eve_type_id=45511,
            eve_solar_system_id=30002537,
        )

        with patch(
            "miningtaxes.models.character.MININGTAXES_WHITELIST", ["Somewhere Else"]
        ):
            ledger.calc_prices()
            self.assertEqual(ledger.taxes_owed, 0.0)

        with patch("miningtaxes.models.character.MININGTAXES_WHITELIST", []), patch(
            "miningtaxes.models.character.MININGTAXES_BLACKLIST",
            [ledger.eve_solar_system.name],
        ):
            ledger.calc_prices()
            self.assertEqual(ledger.taxes_owed, 0.0)

        with patch("miningtaxes.models.character.MININGTAXES_BLACKLIST", []):
            ledger.calc_prices(corpmoon=True)
            self.assertEqual(ledger.taxes_owed, 0.6)

    @patch.object(AdminCharacter, "update_corp_ledger")
    @patch.object(AdminCharacter, "update_mining_observers")
    def test_admin_update_all_and_scopes(self, mock_obs, mock_ledger):
        self.assertIn(
            "esi-wallet.read_corporation_wallets.v1", AdminCharacter.get_esi_scopes()
        )
        with patch("miningtaxes.models.admin.MININGTAXES_TAX_ONLY_CORP_MOONS", True):
            self.admin_character.update_all()
            mock_obs.assert_called_once()
        with patch("miningtaxes.models.admin.MININGTAXES_TAX_ONLY_CORP_MOONS", False):
            self.admin_character.update_all()
        self.assertEqual(mock_ledger.call_count, 2)

    @patch.object(
        AdminCharacter,
        "fetch_token",
        return_value=SimpleNamespace(character_name="Admin", pk=1),
    )
    def test_admin_update_mining_observers_and_ledger(self, mock_fetch_token):
        industry = MagicMock()
        universe = MagicMock()
        wallet = MagicMock()
        mock_client = SimpleNamespace(
            Industry=industry, Universe=universe, Wallet=wallet
        )
        with patch(
            "miningtaxes.models.admin.esi", new=SimpleNamespace(client=mock_client)
        ):

            industry.GetCorporationCorporationIdMiningObservers.return_value.results.return_value = [
                {"observer_id": 777, "observer_type": "structure"},
                {"observer_id": 778, "observer_type": "structure"},
            ]
            universe.GetUniverseStructuresStructureId.side_effect = [
                SimpleNamespace(
                    result=lambda use_etag=False: {
                        "name": "A Very Long Structure Name That Gets Trimmed",
                        "solar_system_id": 30002537,
                    }
                ),
                Exception("gone"),
            ]
            industry.GetCorporationCorporationIdMiningObserversObserverId.return_value.results.return_value = [
                {
                    "character_id": 1001,
                    "last_updated": now().date(),
                    "type_id": 45511,
                    "quantity": 3,
                }
            ]
            wallet.GetCorporationsCorporationIdWalletsDivisionJournal.return_value.results.return_value = [
                {
                    "ref_type": "other",
                    "first_party_id": 1,
                    "date": now(),
                    "amount": 1,
                    "reason": "skip",
                },
                {
                    "ref_type": "player_donation",
                    "first_party_id": 1001,
                    "date": now(),
                    "amount": 5,
                    "reason": "abcdefghijklmnopqrstuvwxyz123456789",
                },
            ]

            self.admin_character.update_mining_observers()
            self.admin_character.update_corp_ledger()

        self.assertTrue(AdminMiningObservers.objects.filter(obs_id=777).exists())
        self.assertTrue(self.admin_character.corp_ledger.filter(taxed_id=1001).exists())
        self.assertTrue(
            self.admin_character.corp_ledger.filter(
                taxed_id=1001, amount=5, reason="abcdefghijklmnopqrstuvwxyz123456"
            ).exists()
        )

    @patch.object(
        AdminCharacter,
        "fetch_token",
        return_value=SimpleNamespace(character_name="Admin", pk=1),
    )
    def test_admin_update_mining_observers_integrity_and_bad_system(
        self, mock_fetch_token
    ):
        existing = self.admin_character.mining_obs.create(
            obs_id=900, obs_type="structure", name="Existing", sys_name="A"
        )
        mock_client = SimpleNamespace(Industry=MagicMock(), Universe=MagicMock())
        with patch(
            "miningtaxes.models.admin.esi", new=SimpleNamespace(client=mock_client)
        ), patch(
            "miningtaxes.models.admin.AdminMiningObservers.objects.update_or_create",
            side_effect=[IntegrityError()],
        ):
            mock_client.Industry.GetCorporationCorporationIdMiningObservers.return_value.results.return_value = [
                {"observer_id": 900, "observer_type": "structure"},
                {"observer_id": 901, "observer_type": "structure"},
            ]
            mock_client.Universe.GetUniverseStructuresStructureId.side_effect = [
                SimpleNamespace(
                    result=lambda use_etag=False: {
                        "name": "Existing Structure",
                        "solar_system_id": 30002537,
                    }
                ),
                SimpleNamespace(
                    result=lambda use_etag=False: {
                        "name": "Bad System",
                        "solar_system_id": 99999999,
                    }
                ),
            ]
            mock_client.Industry.GetCorporationCorporationIdMiningObserversObserverId.return_value.results.return_value = (
                []
            )
            self.admin_character.update_mining_observers()
        self.assertTrue(AdminMiningObservers.objects.filter(pk=existing.pk).exists())

    def test_task_helper_branches(self):
        eve = EveCharacter.objects.create(
            character_id=1301,
            character_name="No Profile",
            corporation_id=2001,
            corporation_name="Wayne Technologies",
            corporation_ticker="WYT",
            alliance_id=3001,
            alliance_name="Wayne Enterprises",
            alliance_ticker="WYN",
        )
        self.assertIsNone(tasks.get_user(eve.character_id))
        with patch("miningtaxes.tasks.MININGTAXES_PRICE_METHOD", "Bad"):
            with self.assertRaises(TypeError):
                tasks.get_bulk_prices([1])

    def test_add_tax_credit_branches(self):
        settings = Settings.load()
        settings.phrase = "moon"
        settings.save()

        fallback_char = self.main_character
        fallback_char.tax_credits.all().delete()
        self.admin_character.corp_ledger.create(
            date=now(), taxed_id=1400, amount=10, reason="moon taxes"
        )

        with patch(
            "miningtaxes.tasks.EveCharacter.objects.get",
            return_value=SimpleNamespace(pk=999),
        ), patch(
            "miningtaxes.tasks.get_object_or_404", side_effect=Character.DoesNotExist()
        ), patch(
            "miningtaxes.tasks.get_user", return_value=fallback_char
        ):
            tasks.add_tax_credits()

        self.assertTrue(fallback_char.tax_credits.filter(credit=10).exists())

        with patch(
            "miningtaxes.tasks.EveCharacter.objects.get",
            side_effect=EveCharacter.DoesNotExist(),
        ):
            tasks.add_tax_credits()

        with patch(
            "miningtaxes.tasks.EveCharacter.objects.get",
            return_value=SimpleNamespace(pk=999),
        ), patch("miningtaxes.tasks.get_object_or_404", side_effect=Http404()):
            tasks.add_tax_credits()

    @patch(
        "miningtaxes.tasks.OrePrices.objects.bulk_create", side_effect=tasks.Error("db")
    )
    @patch(
        "miningtaxes.tasks.get_bulk_prices",
        return_value={"45511": {"buy": {"max": "1"}, "sell": {"min": "2"}}},
    )
    def test_update_all_prices_error_branch(self, mock_bulk_prices, mock_bulk_create):
        from ..models import OrePrices

        OrePrices.objects.filter(eve_type_id=45511).delete()
        tasks.update_all_prices.run(force=[45511])
        self.assertTrue(mock_bulk_create.called)

    def test_stats_remaining_paths(self):
        stats = Stats.load()
        orphan_eve = EveCharacter.objects.create(
            character_id=1500,
            character_name="No Main",
            corporation_id=2001,
            corporation_name="Wayne Technologies",
            corporation_ticker="WYT",
            alliance_id=3001,
            alliance_name="Wayne Enterprises",
            alliance_ticker="WYN",
        )
        orphan = Character.objects.create(eve_character=orphan_eve)
        orphan.mining_ledger.create(
            date=now().date(),
            quantity=1,
            eve_type_id=45511,
            eve_solar_system_id=30002537,
            taxed_value=10,
            taxes_owed=1,
        )

        with patch(
            "miningtaxes.models.stats.bootstrap_icon_plus_name_html",
            side_effect=lambda **kwargs: kwargs["name"],
        ), patch(
            "miningtaxes.models.stats.EveCharacter.objects.get",
            side_effect=Exception("boom"),
        ):
            stats.calc_admin_corp_ledger()
            self.assertIn("data", stats.get_admin_corp_ledger())

        with patch(
            "miningtaxes.models.stats.bootstrap_icon_plus_name_html",
            side_effect=lambda **kwargs: kwargs["name"],
        ):
            stats.calc_admin_month_json()
            stats.calc_leaderboards()
            stats.calc_curmonth_leadergraph()
            stats.calc_user_mining_ledger_90day()
            self.assertIn("data", stats.get_curmonth_leadergraph())
            self.assertIn(self.user.pk, stats.get_user_mining_ledger_90day())

    @patch("miningtaxes.views.render", return_value=SimpleNamespace(status_code=200))
    def test_view_branches(self, mock_render):
        factory = RequestFactory()
        request = factory.get("/")
        request.user = AnonymousUser()
        self.assertEqual(
            views.remove_character(request, 9999).status_code,
            (
                302
                if hasattr(views.remove_character(request, 9999), "status_code")
                else 302
            ),
        )


class TestCoveragePush(MiningTaxesBaseTestCase):
    def test_auth_hook_hidden_and_fetch_user_forbidden(self):

        from allianceauth.tests.auth_utils import AuthUtils

        from .. import auth_hooks
        from ..decorators import fetch_user_if_allowed

        menu = auth_hooks.register_menu()
        factory = RequestFactory()
        plain_user = AuthUtils.create_user("plain-user")

        request = factory.get("/")
        request.user = plain_user
        self.assertEqual(menu.render(request), "")
        self.assertTrue(auth_hooks.register_urls())

        @fetch_user_if_allowed()
        def view(request, user_pk, user):
            return SimpleNamespace(status_code=200)

        request.user = self.user
        self.assertEqual(view(request, plain_user.pk).status_code, 403)

    def test_oreprices_fallback_paths(self):
        from django.core.exceptions import ObjectDoesNotExist

        from ..models import OrePrices
        from ..models.orePrices import get_price, get_tax, ore_calc_prices

        eve_type = SimpleNamespace(id=999, base_price=None, portion_size=100)
        with patch(
            "miningtaxes.models.orePrices.OrePrices.objects.get",
            side_effect=OrePrices.DoesNotExist(),
        ):
            self.assertEqual(get_tax(eve_type), 0.10)

        with patch(
            "miningtaxes.models.orePrices.OrePrices.objects.get",
            side_effect=ObjectDoesNotExist(),
        ):
            self.assertEqual(get_price(eve_type), 0.0)
            eve_type.base_price = 7
            self.assertEqual(get_price(eve_type), 7)

        materials = [
            SimpleNamespace(quantity=None, material_item_type=SimpleNamespace()),
            SimpleNamespace(quantity=10, material_item_type=SimpleNamespace()),
        ]
        with patch(
            "miningtaxes.models.orePrices.OrePrices.objects.get",
            side_effect=OrePrices.DoesNotExist(),
        ), patch(
            "miningtaxes.models.orePrices.ItemTypeMaterials.objects.filter",
            return_value=materials,
        ), patch(
            "miningtaxes.models.orePrices.get_price", side_effect=[10, 1]
        ), patch(
            "miningtaxes.models.orePrices.MININGTAXES_ALWAYS_TAX_REFINED", False
        ):
            raw, refined, taxed = ore_calc_prices(
                SimpleNamespace(id=1, base_price=10, portion_size=100), 2
            )
            self.assertGreater(raw, refined)
            self.assertEqual(taxed, raw)

        ore = OrePrices.objects.get(eve_type_id=45511)
        with patch(
            "miningtaxes.models.orePrices.ItemTypeMaterials.objects.filter",
            return_value=materials,
        ), patch("miningtaxes.models.orePrices.get_price", return_value=1):
            ore.calc_prices()
            self.assertGreaterEqual(ore.taxed_price, ore.refined_price)

    @patch("miningtaxes.tasks.print")
    @patch("miningtaxes.tasks.notify")
    @patch("miningtaxes.tasks.Stats.load")
    def test_task_notification_skip_branches(self, mock_load, mock_notify, mock_print):
        mock_load.return_value.get_admin_main_json.return_value = [
            {"balance": 2000000000, "user": 999999}
        ]
        tasks.notify_current_taxes_threshold.run()
        mock_notify.assert_not_called()
        mock_print.assert_called_once()

        with patch(
            "miningtaxes.tasks.calctaxes",
            return_value={self.user: [0.0, 0.0, self.main_character]},
        ):
            tasks.notify_taxes_due.run()
            tasks.notify_second_taxes_due.run()
            tasks.apply_interest.run()
        mock_notify.assert_not_called()

        settings = Settings.load()
        settings.interest_rate = 10
        settings.save()
        with patch(
            "miningtaxes.tasks.calctaxes",
            return_value={self.user: [0.1, 0.0, self.main_character]},
        ):
            tasks.apply_interest.run()
        mock_notify.assert_not_called()

    def test_add_corp_moon_taxes_updates_existing_row(self):
        row = self.main_character.mining_ledger.create(
            date=self.current_month,
            quantity=1,
            eve_type_id=45511,
            eve_solar_system_id=30002537,
        )
        from ..models import CharacterMiningLedgerEntry

        with patch.object(CharacterMiningLedgerEntry, "calc_prices") as mock_calc:
            tasks.add_corp_moon_taxes_by_char(self.main_character)
        row.refresh_from_db()
        self.assertEqual(row.quantity, 100)
        mock_calc.assert_called_once()

    @patch("miningtaxes.tasks.add_corp_moon_taxes")
    def test_update_admin_character_skip_and_corpmoon(self, mock_add_corp):
        eve = EveCharacter.objects.create(
            character_id=1600,
            character_name="Orphan Admin",
            corporation_id=2001,
            corporation_name="Wayne Technologies",
            corporation_ticker="WYT",
            alliance_id=3001,
            alliance_name="Wayne Enterprises",
            alliance_ticker="WYN",
        )
        orphan_admin = AdminCharacter.objects.create(eve_character=eve)
        self.assertFalse(
            tasks.update_admin_character.run(
                character_pk=orphan_admin.pk, force_update=True
            )
        )

        with patch.object(AdminCharacter, "is_ledger_stale", return_value=False):
            self.assertFalse(
                tasks.update_admin_character.run(
                    character_pk=self.admin_character.pk, force_update=False
                )
            )

        with patch.object(AdminCharacter, "update_all") as mock_update, patch(
            "miningtaxes.tasks.MININGTAXES_TAX_ONLY_CORP_MOONS", True
        ):
            tasks.update_admin_character.run(
                character_pk=self.admin_character.pk, force_update=True, celery=False
            )
        mock_update.assert_called_once()
        mock_add_corp.assert_called_once()

    @patch("miningtaxes.tasks.add_corp_moon_taxes_by_char")
    def test_update_character_skip_and_corpmoon(self, mock_add_corp):
        eve = EveCharacter.objects.create(
            character_id=1601,
            character_name="Orphan Char",
            corporation_id=2001,
            corporation_name="Wayne Technologies",
            corporation_ticker="WYT",
            alliance_id=3001,
            alliance_name="Wayne Enterprises",
            alliance_ticker="WYN",
        )
        orphan_char = Character.objects.create(eve_character=eve)
        self.assertFalse(
            tasks.update_character.run(character_pk=orphan_char.pk, force_update=True)
        )

        with patch.object(Character, "is_ledger_stale", return_value=False):
            self.assertFalse(
                tasks.update_character.run(
                    character_pk=self.main_character.pk, force_update=False
                )
            )

        with patch.object(Character, "update_mining_ledger") as mock_update, patch(
            "miningtaxes.tasks.add_tax_credits_by_char"
        ) as mock_credit, patch(
            "miningtaxes.tasks.MININGTAXES_TAX_ONLY_CORP_MOONS", True
        ):
            tasks.update_character.run(
                character_pk=self.main_character.pk, force_update=True, celery=False
            )
        mock_update.assert_called_once()
        mock_credit.assert_called_once()
        mock_add_corp.assert_called_once()

    def test_update_all_prices_material_update_branch(self):
        from ..models import OrePrices
        from ..tests.testdata.load_eve_sde import add_material

        add_material(45511, 16635, 3)
        OrePrices.objects.all().delete()
        OrePrices.objects.create(eve_type_id=16635, buy=1, sell=1, updated=now())

        with patch(
            "miningtaxes.tasks.PriceGroups", return_value=SimpleNamespace(groups=[])
        ), patch(
            "miningtaxes.tasks.get_bulk_prices",
            side_effect=[
                {"45511": {"buy": {"max": "11"}, "sell": {"min": "22"}}},
                {"16635": {"buy": {"max": "5"}, "sell": {"min": "6"}}},
            ],
        ):
            tasks.update_all_prices.run(force=[45511])

        self.assertEqual(OrePrices.objects.get(eve_type_id=16635).buy, 5)


class TestFinalPush(MiningTaxesBaseTestCase):
    @patch.object(
        AdminCharacter,
        "fetch_token",
        return_value=SimpleNamespace(character_name="Admin", pk=1),
    )
    def test_admin_integrity_branch_and_strings(self, mock_fetch_token):
        existing = self.admin_character.mining_obs.create(
            obs_id=9010, obs_type="structure", name="Existing", sys_name="Amamake"
        )
        mock_client = SimpleNamespace(Industry=MagicMock(), Universe=MagicMock())
        mock_client.Industry.GetCorporationCorporationIdMiningObservers.return_value.results.return_value = [
            {"observer_id": 9010, "observer_type": "structure"}
        ]
        mock_client.Universe.GetUniverseStructuresStructureId.return_value = (
            SimpleNamespace(
                result=lambda use_etag=False: {
                    "name": "Existing Structure",
                    "solar_system_id": 30002537,
                }
            )
        )
        mock_client.Industry.GetCorporationCorporationIdMiningObserversObserverId.return_value.results.return_value = [
            {
                "character_id": 1001,
                "last_updated": now().date(),
                "type_id": 45511,
                "quantity": 2,
            }
        ]

        with patch(
            "miningtaxes.models.admin.esi", new=SimpleNamespace(client=mock_client)
        ), patch.object(
            type(self.admin_character.mining_obs),
            "update_or_create",
            side_effect=IntegrityError(),
        ):
            self.admin_character.update_mining_observers()

        log = existing.mining_log.first()
        ledger = self.admin_character.corp_ledger.first()
        self.assertIn("miningObs", str(existing))
        self.assertIn("miningObs", str(log))
        self.assertIn("wallet", str(ledger))

    @patch.object(
        Character,
        "fetch_token",
        return_value=SimpleNamespace(character_name="Char", pk=1),
    )
    def test_character_update_existing_row_and_misc_methods(self, mock_fetch_token):
        row = self.main_character.mining_ledger.create(
            date=self.prev_month,
            quantity=1,
            eve_type_id=1230,
            eve_solar_system_id=30000142,
        )
        from ..models import CharacterMiningLedgerEntry

        mock_client = SimpleNamespace(Industry=MagicMock())
        mock_client.Industry.GetCharactersCharacterIdMining.return_value.results.return_value = [
            {
                "date": self.prev_month,
                "quantity": 5,
                "type_id": 1230,
                "solar_system_id": 30000142,
            }
        ]
        with patch(
            "miningtaxes.models.character.esi", new=SimpleNamespace(client=mock_client)
        ), patch.object(CharacterMiningLedgerEntry, "calc_prices") as mock_calc:
            self.main_character.update_mining_ledger()
        row.refresh_from_db()
        self.assertEqual(row.quantity, 5)
        mock_calc.assert_called_once()
        self.assertEqual(
            Character.get_esi_scopes(), ["esi-industry.read_character_mining.v1"]
        )

        eve = EveCharacter.objects.create(
            character_id=1700,
            character_name="Empty",
            corporation_id=2001,
            corporation_name="Wayne Technologies",
            corporation_ticker="WYT",
            alliance_id=3001,
            alliance_name="Wayne Enterprises",
            alliance_ticker="WYN",
        )
        empty = Character.objects.create(eve_character=eve)
        empty.calc_lifetime_taxes()
        empty.calc_lifetime_credits()
        self.assertEqual(empty.get_monthly_credits(), {})
        self.assertIn("ISK", str(self.main_character.tax_credits.first()))
        self.assertFalse(
            CharacterUpdateStatus(character=self.main_character).is_updating
        )
        self.assertTrue(
            CharacterUpdateStatus(character=self.main_character).has_changed(
                {"a": 1}, hash_num=2
            )
        )
        self.assertTrue(
            CharacterUpdateStatus(character=self.main_character).has_changed(
                {"a": 1}, hash_num=3
            )
        )
        self.assertIsNone(CharacterMiningLedgerEntry.objects.annotate_pricing())
        self.assertIn(str(self.main_character.pk), repr(self.main_character))
        self.assertIn(str(row.id), str(row))

    def test_view_remaining_branches(self):
        from django.http import HttpResponse
        from django.urls import reverse

        from allianceauth.tests.auth_utils import AuthUtils
        from app_utils.testing import add_character_to_user

        with patch("miningtaxes.views.render", return_value=HttpResponse("ok")):
            plain = AuthUtils.create_user("plain-basic")
            plain = AuthUtils.add_permission_to_user_by_name(
                "miningtaxes.basic_access", plain
            )
            self.client.force_login(plain)
            self.assertEqual(
                self.client.get(reverse("miningtaxes:index")).status_code, 302
            )
            request = RequestFactory().get("/")
            request.user = plain
            self.assertEqual(
                __import__("inspect").unwrap(views.launcher)(request).status_code, 200
            )
            summary_request = RequestFactory().get("/")
            summary_request.user = plain
            self.assertEqual(
                __import__("inspect")
                .unwrap(views.summary_month_json)(summary_request, plain.pk)
                .status_code,
                200,
            )

            admin_user = AuthUtils.create_user("admin-alt")
            admin_user = AuthUtils.add_permission_to_user_by_name(
                "miningtaxes.basic_access", admin_user
            )
            admin_user = AuthUtils.add_permission_to_user_by_name(
                "miningtaxes.admin_access", admin_user
            )
            add_character_to_user(
                admin_user,
                EveCharacter.objects.get(character_id=1103),
                is_main=False,
                scopes=Character.get_esi_scopes(),
            )
            Character.objects.create(
                eve_character=EveCharacter.objects.get(character_id=1103)
            )
            self.client.force_login(self.user)
            self.assertEqual(
                self.client.post(
                    reverse("miningtaxes:admin_tables"),
                    {"creditbox": "4", "userid": admin_user.pk},
                ).status_code,
                200,
            )

            self.client.force_login(self.other_user)
            self.assertEqual(
                self.client.get(
                    reverse("miningtaxes:user_mining_ledger_90day", args=[self.user.pk])
                ).status_code,
                403,
            )
