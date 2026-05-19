from typing import Any, cast
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase, override_settings

from esi.exceptions import HTTPClientError

from ..models import EveAllianceInfo, EveCharacter, EveCorporationInfo
from ..tasks import (
    run_model_update, update_alliance, update_character,
    update_character_chunk, update_corp,
)
from .esi_client_stub import EsiClientStub


class TestUpdateTasks(TestCase):
    def test_should_update_alliance(self) -> None:
        # given
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            my_alliance = EveAllianceInfo.objects.create(
                alliance_id=3001,
                alliance_name="Wayne Enterprises",
                alliance_ticker="WYE",
                executor_corp_id=2003
            )
            # when
            update_alliance(my_alliance.alliance_id)
            # then
            my_alliance.refresh_from_db()
            self.assertEqual(my_alliance.executor_corp_id, 2001)

    def test_should_update_character(self) -> None:
        # given
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            my_character = EveCharacter.objects.create(
                character_id=1001,
                character_name="Bruce Wayne",
                corporation_id=2002,
                corporation_name="Wayne Food",
                corporation_ticker="WYF",
                alliance_id=None
            )
            # when
            update_character(my_character.character_id)
            # then
            my_character.refresh_from_db()
            self.assertEqual(my_character.corporation_id, 2001)

    def test_should_update_corp(self) -> None:
        # given
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            EveAllianceInfo.objects.create(
                alliance_id=3001,
                alliance_name="Wayne Enterprises",
                alliance_ticker="WYE",
                executor_corp_id=2003
            )
            my_corporation = EveCorporationInfo.objects.create(
                corporation_id=2003,
                corporation_name="Wayne Food",
                corporation_ticker="WFO",
                member_count=1,
                alliance=None,
                ceo_id=1999
            )
            # when
            update_corp(my_corporation.corporation_id)
            # then
            my_corporation.refresh_from_db()
            self.assertEqual(my_corporation.alliance.alliance_id, 3001)

    # @patch('allianceauth.eveonline.tasks.EveCharacter')
    # def test_update_character(self, mock_EveCharacter):
    #     update_character(42)
    #     self.assertEqual(
    #         mock_EveCharacter.objects.update_character.call_count, 1
    #     )
    #     self.assertEqual(
    #         mock_EveCharacter.objects.update_character.call_args[0][0], 42
    #     )


@override_settings(CELERY_ALWAYS_EAGER=True)
@patch('allianceauth.eveonline.tasks.providers')
@patch('allianceauth.eveonline.tasks.CHARACTER_AFFILIATION_CHUNK_SIZE', 2)
class TestRunModelUpdate(TransactionTestCase):
    def test_should_run_updates(self, mock_providers) -> None:
        # given
        mock_providers.open_api_provider.client = EsiClientStub()
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            EveCorporationInfo.objects.create(
                corporation_id=2001,
                corporation_name="Wayne Technologies",
                corporation_ticker="WTE",
                member_count=10,
                alliance=None,
            )
            alliance_3001 = EveAllianceInfo.objects.create(
                alliance_id=3001,
                alliance_name="Wayne Enterprises",
                alliance_ticker="WYE",
                executor_corp_id=2003
            )
            corporation_2003 = EveCorporationInfo.objects.create(
                corporation_id=2003,
                corporation_name="Wayne Energy",
                corporation_ticker="WEG",
                member_count=99,
                alliance=None,
            )
            character_1001 = EveCharacter.objects.create(
                character_id=1001,
                character_name="Bruce Wayne",
                corporation_id=2002,
                corporation_name="Wayne Food",
                corporation_ticker="WYF",
                alliance_id=None
            )
            # when
            run_model_update()
            # then
            character_1001.refresh_from_db()
            self.assertEqual(
                character_1001.corporation_id, 2001  # char has new corp
            )
            corporation_2003.refresh_from_db()
            self.assertEqual(
                corporation_2003.alliance.alliance_id, 3001  # corp has new alliance
            )
            alliance_3001.refresh_from_db()
            self.assertEqual(
                alliance_3001.executor_corp_id, 2001  # alliance has been updated
            )


@override_settings(CELERY_ALWAYS_EAGER=True)
@patch('allianceauth.eveonline.tasks.update_character', wraps=update_character)
@patch('allianceauth.eveonline.tasks.providers')
@patch('allianceauth.eveonline.tasks.CHARACTER_AFFILIATION_CHUNK_SIZE', 2)
class TestUpdateCharacterChunk(TestCase):
    @staticmethod
    def _updated_character_ids(spy_update_character) -> set:
        """Character IDs passed to update_character task for update."""
        return {
            x[1]["args"][0] for x in spy_update_character.apply_async.call_args_list
        }

    def test_should_update_corp_change(
        self, mock_providers, spy_update_character
    ) -> None:
        # given
        mock_providers.open_api_provider.client = EsiClientStub()
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            character_1001 = EveCharacter.objects.create(
                character_id=1001,
                character_name="Bruce Wayne",
                corporation_id=2003,
                corporation_name="Wayne Energy",
                corporation_ticker="WEG",
                alliance_id=3001,
                alliance_name="Wayne Enterprises",
                alliance_ticker="WYE",
            )
            character_1002 = EveCharacter.objects.create(
                character_id=1002,
                character_name="Peter Parker",
                corporation_id=2001,
                corporation_name="Wayne Technologies",
                corporation_ticker="WTE",
                alliance_id=3001,
                alliance_name="Wayne Enterprises",
                alliance_ticker="WYE",
            )
            # when
            update_character_chunk([
                character_1001.character_id, character_1002.character_id
            ])
            # then
            character_1001.refresh_from_db()
            self.assertEqual(character_1001.corporation_id, 2001)
            self.assertSetEqual(self._updated_character_ids(spy_update_character), {1001})

    def test_should_update_name_change(
        self, mock_providers, spy_update_character
    ) -> None:
        # given
        mock_providers.open_api_provider.client = EsiClientStub()
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            character_1001 = EveCharacter.objects.create(
                character_id=1001,
                character_name="Batman",
                corporation_id=2001,
                corporation_name="Wayne Technologies",
                corporation_ticker="WTE",
                alliance_id=3001,
                alliance_name="Wayne Technologies",
                alliance_ticker="WYT",
            )
            # when
            update_character_chunk([character_1001.character_id])
            # then
            character_1001.refresh_from_db()
            self.assertEqual(character_1001.character_name, "Bruce Wayne")
            self.assertSetEqual(self._updated_character_ids(spy_update_character), {1001})

    def test_should_update_alliance_change(
        self, mock_providers, spy_update_character
    ) -> None:
        # given
        mock_providers.open_api_provider.client = EsiClientStub()
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            character_1001 = EveCharacter.objects.create(
                character_id=1001,
                character_name="Bruce Wayne",
                corporation_id=2001,
                corporation_name="Wayne Technologies",
                corporation_ticker="WTE",
                alliance_id=None,
            )
            # when
            update_character_chunk([character_1001.character_id])
            # then
            character_1001.refresh_from_db()
            self.assertEqual(character_1001.alliance_id, 3001)
            self.assertSetEqual(self._updated_character_ids(spy_update_character), {1001})

    def test_should_not_update_when_not_changed(
        self, mock_providers, spy_update_character
    ) -> None:
        # given
        mock_providers.open_api_provider.client = EsiClientStub()
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            character_1001 = EveCharacter.objects.create(
                character_id=1001,
                character_name="Bruce Wayne",
                corporation_id=2001,
                corporation_name="Wayne Technologies",
                corporation_ticker="WTE",
                alliance_id=3001,
                alliance_name="Wayne Technologies",
                alliance_ticker="WYT",
            )
            # when
            update_character_chunk([character_1001.character_id])
            # then
            self.assertSetEqual(self._updated_character_ids(spy_update_character), set())

    def test_should_fall_back_to_single_updates_when_bulk_update_failed(
        self, mock_providers, spy_update_character
    ) -> None:
        # given
        mock_providers.open_api_provider.client.Character.PostCharactersAffiliation\
            .side_effect = HTTPClientError(
                status_code=403,
                headers={},
                data=cast(Any, {}),
            )
        with patch("allianceauth.eveonline.providers.open_api_provider._client", EsiClientStub()):
            character_1001 = EveCharacter.objects.create(
                character_id=1001,
                character_name="Bruce Wayne",
                corporation_id=2001,
                corporation_name="Wayne Technologies",
                corporation_ticker="WTE",
                alliance_id=3001,
                alliance_name="Wayne Technologies",
                alliance_ticker="WYT",
            )
            # when
            update_character_chunk([character_1001.character_id])
            # then
            self.assertSetEqual(self._updated_character_ids(spy_update_character), {1001})
