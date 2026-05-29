import datetime
import hashlib
import json
from unittest.mock import patch

from django.utils.timezone import now
from esi.errors import TokenError

from allianceauth.eveonline.models import EveCharacter
from app_utils.testing import NoSocketsTestCase, add_new_token

from ...models import Character, OrePrices
from ..testdata.esi_client_stub import esi_client_stub
from ..testdata.load_entities import load_entities
from ..testdata.load_eve_sde import load_eve_sde
from ..utils import (
    create_character,
    create_character_update_status,
    create_miningtaxes_character,
)

MODELS_PATH = "miningtaxes.models"


class TestCharacter(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eve_sde()
        load_entities()

    def test_user_should_return_user_when_not_orphan(self):
        character = create_miningtaxes_character(1001)
        self.assertEqual(
            character.user, character.eve_character.character_ownership.user
        )

    def test_user_should_be_none_when_orphan(self):
        character = create_character(EveCharacter.objects.get(character_id=1121))
        self.assertIsNone(character.user)
        self.assertTrue(character.is_orphan)

    def test_should_return_main_when_it_exists(self):
        character = create_miningtaxes_character(1001)
        self.assertEqual(
            character.main_character,
            character.eve_character.character_ownership.user.profile.main_character,
        )
        self.assertTrue(character.is_main)

    def test_mining_ledger_aggregation(self):
        date = datetime.date(year=2022, month=1, day=15)
        month_n = datetime.date(year=2022, month=1, day=1)
        character = create_miningtaxes_character(1001)
        OrePrices(eve_type_id=45511, buy=10, sell=100, updated=date).calc_prices()
        entry, _ = character.mining_ledger.update_or_create(
            date=date,
            quantity=10,
            eve_type_id=45511,
            eve_solar_system_id=30000142,
        )
        entry.calc_prices()
        monthly = character.get_monthly_taxes()

        self.assertEqual(entry.raw_price, 100)
        self.assertEqual(entry.refined_price, 100)
        self.assertEqual(entry.taxed_value, 100)
        self.assertEqual(entry.taxes_owed, 10)
        self.assertEqual(character.get_lifetime_taxes(), 10)
        self.assertEqual(monthly[month_n], 10)

    def test_tax_credits(self):
        character = create_miningtaxes_character(1001)
        current = now()
        character.give_credit(1234, "paid")
        monthly = character.get_monthly_credits()
        month_n = datetime.date(year=current.year, month=current.month, day=1)

        self.assertEqual(character.get_lifetime_credits(), 1234)
        self.assertEqual(monthly[month_n], 1234)
        self.assertEqual(character.last_paid().date(), current.date())

    def test_fetch_token_raises_for_orphan(self):
        character = create_character(EveCharacter.objects.get(character_id=1121))
        with self.assertRaises(TokenError):
            character.fetch_token()

    def test_fetch_token_returns_matching_token(self):
        character = create_miningtaxes_character(1001)
        fetched_token = character.fetch_token()

        self.assertEqual(
            fetched_token.character_id, character.eve_character.character_id
        )
        self.assertEqual(fetched_token.user, character.user)

    @patch(MODELS_PATH + ".character.esi")
    def test_get_ledger(self, mock_esi):
        mock_esi.client = esi_client_stub
        character = create_miningtaxes_character(1001)
        add_new_token(
            character.user, character.eve_character, Character.get_esi_scopes()
        )

        character.update_mining_ledger()
        ledger = character.mining_ledger.all()

        self.assertEqual(len(ledger), 1)
        entry = ledger[0]
        self.assertEqual(entry.quantity, 4333)
        self.assertEqual(entry.eve_type_id, 62586)
        self.assertEqual(entry.eve_solar_system_id, 30002537)


class TestCharacterUpdateStatus(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        load_eve_sde()
        load_entities()
        cls.character_1001 = create_miningtaxes_character(1001)
        cls.content = {"alpha": 1, "bravo": 2}

    def test_str(self):
        status = create_character_update_status(character=self.character_1001)
        self.assertEqual(str(status), f"{self.character_1001}")

    def test_reset(self):
        status = create_character_update_status(
            character=self.character_1001,
            is_success=True,
            last_error_message="abc",
            root_task_id="a",
            parent_task_id="b",
        )

        status.reset(root_task_id="1", parent_task_id="2")
        status.refresh_from_db()

        self.assertIsNone(status.is_success)
        self.assertEqual(status.last_error_message, "")
        self.assertEqual(status.root_task_id, "1")
        self.assertEqual(status.parent_task_id, "2")

    def test_has_changed(self):
        status = create_character_update_status(
            character=self.character_1001,
            content_hash_1=hashlib.md5(
                json.dumps(self.content).encode("utf-8")
            ).hexdigest(),
        )

        self.assertFalse(status.has_changed(self.content))
        self.assertTrue(status.has_changed({"changed": True}))

    def test_update_content_hash(self):
        status = create_character_update_status(character=self.character_1001)
        status.update_content_hash(self.content, hash_num=2)
        status.refresh_from_db()

        self.assertEqual(
            status.content_hash_2,
            hashlib.md5(json.dumps(self.content).encode("utf-8")).hexdigest(),
        )

    def test_is_updating(self):
        status = create_character_update_status(
            character=self.character_1001, started_at=now(), finished_at=None
        )
        self.assertTrue(status.is_updating)

        status.finished_at = now()
        status.save()
        self.assertFalse(status.is_updating)
