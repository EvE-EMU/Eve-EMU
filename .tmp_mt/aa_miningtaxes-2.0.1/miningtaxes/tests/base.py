import datetime as dt

from dateutil.relativedelta import relativedelta

from django.utils.timezone import now

from allianceauth.tests.auth_utils import AuthUtils
from app_utils.testing import NoSocketsTestCase, add_new_token

from ..models import (
    AdminCharacter,
    AdminMiningCorpLedgerEntry,
    Character,
    OrePrices,
    Settings,
    Stats,
)
from .testdata.load_entities import load_entities
from .testdata.load_eve_sde import load_eve_sde
from .utils import (
    add_auth_character_to_user,
    add_miningtaxes_character_to_user,
    create_user_from_evecharacter_with_access,
)


class MiningTaxesBaseTestCase(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eve_sde()
        load_entities()

    def setUp(self):
        super().setUp()
        self._reset_singletons()
        self.user, self.ownership = create_user_from_evecharacter_with_access(1001)
        self.user = AuthUtils.add_permission_to_user_by_name(
            "miningtaxes.admin_access", self.user
        )
        self.user = AuthUtils.add_permission_to_user_by_name(
            "miningtaxes.auditor_access", self.user
        )
        self.main_character = Character.objects.update_or_create(
            eve_character=self.ownership.character
        )[0]
        self.alt_character = add_miningtaxes_character_to_user(self.user, 1002)
        self.admin_character = AdminCharacter.objects.update_or_create(
            eve_character=self.ownership.character
        )[0]
        self.other_user, self.other_ownership = (
            create_user_from_evecharacter_with_access(1101)
        )
        self.other_character = Character.objects.update_or_create(
            eve_character=self.other_ownership.character
        )[0]
        self.unregistered_ownership = add_auth_character_to_user(self.user, 1102)
        self.prev_month = (now().date() + relativedelta(months=-1)).replace(day=15)
        self.current_month = now().date().replace(day=min(10, now().date().day))
        self.seed_prices()
        self.seed_ledgers_and_admin_data()
        add_new_token(self.user, self.ownership.character, Character.get_esi_scopes())
        add_new_token(
            self.user, self.ownership.character, AdminCharacter.get_esi_scopes()
        )

    def _reset_singletons(self):
        settings = Settings.load()
        settings.phrase = ""
        settings.interest_rate = 5.0
        settings.save()
        stats = Stats.load()
        for field in [
            "admin_char_json",
            "admin_main_json",
            "ore_prices_json",
            "admin_mining_by_sys_json",
            "admin_tax_revenue_json",
            "admin_month_json",
            "admin_corp_ledger",
            "admin_corp_mining_history",
            "leaderboards",
            "admin_get_all_activity_json",
            "curmonth_leadergraph",
            "user_mining_ledger_90day",
        ]:
            setattr(stats, field, None)
        stats.save()

    def seed_prices(self):
        for type_id, buy, sell in [
            (45511, 10, 100),
            (62586, 5, 50),
            (1230, 2, 20),
            (16635, 20, 200),
        ]:
            ore, _ = OrePrices.objects.update_or_create(
                eve_type_id=type_id,
                defaults={"buy": buy, "sell": sell, "updated": now()},
            )
            ore.calc_prices()

    def add_ledger_entry(
        self, character, date, quantity, eve_type_id=45511, system_id=30002537
    ):
        entry = character.mining_ledger.create(
            date=date,
            quantity=quantity,
            eve_type_id=eve_type_id,
            eve_solar_system_id=system_id,
        )
        entry.calc_prices()
        return entry

    def seed_ledgers_and_admin_data(self):
        self.add_ledger_entry(self.main_character, self.prev_month, 10, 45511, 30002537)
        self.add_ledger_entry(
            self.main_character, self.current_month, 5, 1230, 30000142
        )
        self.add_ledger_entry(self.alt_character, self.prev_month, 7, 45511, 30000142)
        self.add_ledger_entry(
            self.other_character, self.prev_month, 11, 45511, 31000005
        )
        self.main_character.give_credit(25, "paid")
        self.alt_character.give_credit(5, "credit")

        AdminMiningCorpLedgerEntry.objects.create(
            character=self.admin_character,
            date=now() - dt.timedelta(days=20),
            taxed_id=self.main_character.eve_character.character_id,
            amount=150.0,
            reason="moon tax",
        )
        AdminMiningCorpLedgerEntry.objects.create(
            character=self.admin_character,
            date=now() - dt.timedelta(days=10),
            taxed_id=1102,
            amount=75.0,
            reason="moon tax",
        )
        AdminMiningCorpLedgerEntry.objects.create(
            character=self.admin_character,
            date=now() - dt.timedelta(days=5),
            taxed_id=9999,
            amount=20.0,
            reason="other",
        )

        observer = self.admin_character.mining_obs.create(
            obs_id=123456789,
            obs_type="structure",
            name="Amamake Test",
            sys_name="Amamake",
        )
        observer.mining_log.create(
            date=self.current_month,
            miner_id=self.main_character.eve_character.character_id,
            eve_type_id=45511,
            quantity=100,
            observer_type="structure",
            eve_solar_system_id=30002537,
        )
        observer.mining_log.create(
            date=self.current_month,
            miner_id=1102,
            eve_type_id=45511,
            quantity=50,
            observer_type="structure",
            eve_solar_system_id=30002537,
        )
        observer.mining_log.create(
            date=self.current_month,
            miner_id=9999,
            eve_type_id=45511,
            quantity=20,
            observer_type="structure",
            eve_solar_system_id=30002537,
        )
