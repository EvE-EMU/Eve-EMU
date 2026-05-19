from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

from django.test import TestCase

from esi import __url__ as esi_url, __version__ as esi_version
from esi.exceptions import HTTPClientError

from allianceauth import __url__ as aa_url, __version__ as aa_version

from ..providers import (
    Alliance, AllianceMixin, Character, Corporation, Entity,
    EveOpenAPIProvider, FactionMixin, ItemType, ObjectNotFound,
)
from . import set_logger
from .esi_client_stub import EsiClientStub

MODULE_PATH = 'allianceauth.eveonline.providers'

set_logger(MODULE_PATH, __file__)


class TestObjectNotFound(TestCase):

    def test_str(self) -> None:
        x = ObjectNotFound(1001, 'Character')
        self.assertEqual(str(x), 'Character with ID 1001 not found.')


class TestEntity(TestCase):

    def test_str(self) -> None:
        x = Entity(1001, 'Bruce Wayne')
        self.assertEqual(str(x), 'Bruce Wayne')

        # bug - does not return a string
        """
        x = Entity(1001)
        self.assertEqual(str(x), '')

        x = Entity()
        self.assertEqual(str(x), '')
        """

    def test_repr(self) -> None:
        x = Entity(1001, 'Bruce Wayne')
        self.assertEqual(repr(x), '<Entity (1001): Bruce Wayne>')

        x = Entity(1001)
        self.assertEqual(repr(x), '<Entity (1001): None>')

        x = Entity()
        self.assertEqual(repr(x), '<Entity (None): None>')

    def test_bool(self) -> None:
        x = Entity(1001)
        self.assertTrue(bool(x))

        x = Entity()
        self.assertFalse(bool(x))

    def test_eq(self) -> None:
        x1 = Entity(1001)
        x2 = Entity(1001)
        y = Entity(1002)
        z1 = Entity()
        z2 = Entity()

        self.assertEqual(x1, x2)
        self.assertNotEqual(x1, y)
        self.assertNotEqual(x1, z1)
        self.assertEqual(z1, z2)

        # bug: missing _neq_ in Equity to compliment _eq_


class TestAllianceMixin(TestCase):
    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    def test_alliance_defined(self, mock_provider_get_alliance) -> None:
        my_alliance = Alliance(
            id=3001,
            name='Dummy Alliance',
            ticker='Dummy',
            corp_ids=[2001, 2002, 2003],
            executor_corp_id=2001
        )
        mock_provider_get_alliance.return_value = my_alliance

        x = AllianceMixin(alliance_id=3001)
        self.assertEqual(
            x.alliance,
            my_alliance
        )
        self.assertEqual(
            x.alliance,
            my_alliance
        )
        # should fetch alliance once only
        self.assertEqual(mock_provider_get_alliance.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    def test_alliance_not_defined(self, mock_provider_get_alliance) -> None:
        mock_provider_get_alliance.return_value = None

        x = AllianceMixin()
        self.assertEqual(
            x.alliance,
            Entity(None, None)
        )
        self.assertEqual(mock_provider_get_alliance.call_count, 0)


class TestFactionMixin(TestCase):
    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_defined(self, mock_provider_get_faction) -> None:
        my_faction = Entity(id=1337, name='Permabanned')
        mock_provider_get_faction.return_value = my_faction

        x = FactionMixin(faction_id=3001)
        self.assertEqual(
            x.faction,
            my_faction
        )
        self.assertEqual(
            x.faction,
            my_faction
        )
        # should fetch alliance once only
        self.assertEqual(mock_provider_get_faction.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    def test_faction_not_defined(self, mock_provider_get_faction) -> None:
        mock_provider_get_faction.return_value = None

        x = FactionMixin()
        self.assertEqual(
            x.faction,
            Entity(None, None)
        )
        self.assertEqual(mock_provider_get_faction.call_count, 0)


class TestCorporation(TestCase):

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    def test_alliance_defined(self, mock_provider_get_alliance) -> None:
        my_alliance = Alliance(
            id=3001,
            name='Dummy Alliance',
            ticker='Dummy',
            corp_ids=[2001, 2002, 2003],
            executor_corp_id=2001
        )
        mock_provider_get_alliance.return_value = my_alliance

        x = Corporation(alliance_id=3001)
        self.assertEqual(
            x.alliance,
            my_alliance
        )
        self.assertEqual(
            x.alliance,
            my_alliance
        )
        # should fetch alliance once only
        self.assertEqual(mock_provider_get_alliance.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    def test_alliance_not_defined(self, mock_provider_get_alliance) -> None:
        mock_provider_get_alliance.return_value = None

        x = Corporation()
        self.assertEqual(
            x.alliance,
            Entity(None, None)
        )
        self.assertEqual(mock_provider_get_alliance.call_count, 0)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_character')
    def test_ceo(self, mock_provider_get_character) -> None:
        my_ceo = Character(
            id=1001,
            name='Bruce Wayne',
            corp_id=2001,
            alliance_id=3001
        )
        mock_provider_get_character.return_value = my_ceo

        # fetch from provider if not defined
        x = Corporation()
        self.assertEqual(
            x.ceo,
            my_ceo
        )

        # return existing if defined
        mock_provider_get_character.return_value = None
        self.assertEqual(
            x.ceo,
            my_ceo
        )
        self.assertEqual(mock_provider_get_character.call_count, 1)

        # bug in ceo(): will try to fetch character even if ceo_id is None

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_defined(self, mock_provider_get_faction) -> None:
        my_faction = Entity(id=1337, name='Permabanned')
        mock_provider_get_faction.return_value = my_faction

        # fetch from provider if not defined
        x = Corporation(faction_id=1337)
        self.assertEqual(x.faction, my_faction)

        # return existing if defined
        mock_provider_get_faction.return_value = None
        self.assertEqual(x.faction, my_faction)
        self.assertEqual(mock_provider_get_faction.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_undefined(self, mock_provider_get_faction) -> None:
        x = Corporation()
        self.assertEqual(x.faction, Entity())
        self.assertEqual(mock_provider_get_faction.call_count, 0)


class TestAlliance(TestCase):

    def setUp(self):
        self.my_alliance = Alliance(
            id=3001,
            name='Dummy Alliance',
            ticker='Dummy',
            corp_ids=[2001, 2002, 2003],
            executor_corp_id=2001,
            faction_id=1337
        )

    @staticmethod
    def _get_corp(corp_id, *args, **kwargs) -> Corporation | None:
        corps = {
            2001: Corporation(
                id=2001,
                name='Dummy Corp 1',
                alliance_id=3001
            ),
            2002: Corporation(
                id=2002,
                name='Dummy Corp 2',
                alliance_id=3001
            ),
            2003: Corporation(
                id=2003,
                name='Dummy Corp 3',
                alliance_id=3001
            ),
        }

        if corp_id:
            return corps[int(corp_id)]

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_corp')
    def test_corp(self, mock_provider_get_corp) -> None:
        mock_provider_get_corp.side_effect = TestAlliance._get_corp

        # should fetch corp if not in the object
        self.assertEqual(
            self.my_alliance.corp(2001),
            TestAlliance._get_corp(2001)
        )
        # should fetch corp if not in the object
        self.assertEqual(
            self.my_alliance.corp(2002),
            TestAlliance._get_corp(2002)
        )
        # should return from the object if its there
        self.assertEqual(
            self.my_alliance.corp(2001),
            TestAlliance._get_corp(2001)
        )
        # should return from the object if its there
        self.assertEqual(
            self.my_alliance.corp(2002),
            TestAlliance._get_corp(2002)
        )
        # should be called once by used corp only
        self.assertEqual(mock_provider_get_corp.call_count, 2)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_corp')
    def test_corps(self, mock_provider_get_corp) -> None:
        mock_provider_get_corp.side_effect = TestAlliance._get_corp

        self.assertEqual(
            self.my_alliance.corps,
            [
                TestAlliance._get_corp(2001),
                TestAlliance._get_corp(2002),
                TestAlliance._get_corp(2003),
            ]
        )

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_corp')
    def test_executor_corp(self, mock_provider_get_corp) -> None:
        mock_provider_get_corp.side_effect = TestAlliance._get_corp

        self.assertEqual(
            self.my_alliance.executor_corp,
            TestAlliance._get_corp(2001),
        )

        x = Alliance()
        self.assertEqual(
            x.executor_corp,
            Entity(None, None),
        )

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_defined(self, mock_provider_get_faction) -> None:
        my_faction = Entity(id=1337, name='Permabanned')
        mock_provider_get_faction.return_value = my_faction

        # fetch from provider if not defined
        self.assertEqual(self.my_alliance.faction, my_faction)

        # return existing if defined
        mock_provider_get_faction.return_value = None
        self.assertEqual(self.my_alliance.faction, my_faction)
        self.assertEqual(mock_provider_get_faction.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_undefined(self, mock_provider_get_faction) -> None:
        self.my_alliance.faction_id = None
        self.assertEqual(self.my_alliance.faction, Entity())
        self.assertEqual(mock_provider_get_faction.call_count, 0)


class TestCharacter(TestCase):

    def setUp(self) -> None:
        self.my_character = Character(
            id=1001,
            name='Bruce Wayne',
            corp_id=2001,
            alliance_id=3001,
            faction_id=1337,
        )

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_corp')
    def test_corp(self, mock_provider_get_corp) -> None:
        my_corp = Corporation(
            id=2001,
            name='Dummy Corp 1'
        )
        mock_provider_get_corp.return_value = my_corp

        self.assertEqual(self.my_character.corp, my_corp)
        self.assertEqual(self.my_character.corp, my_corp)

        # should call the provider one time only
        self.assertEqual(mock_provider_get_corp.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_corp')
    def test_alliance_has_one(
        self,
        mock_provider_get_corp,
        mock_provider_get_alliance,
    ) -> None:
        my_corp = Corporation(
            id=2001,
            name='Dummy Corp 1',
            alliance_id=3001
        )
        mock_provider_get_corp.return_value = my_corp
        my_alliance = Alliance(
            id=3001,
            name='Dummy Alliance 1',
            executor_corp_id=2001,
            corp_ids=[2001, 2002]
        )
        mock_provider_get_alliance.return_value = my_alliance

        self.assertEqual(self.my_character.alliance, my_alliance)
        self.assertEqual(self.my_character.alliance, my_alliance)

        # should call the provider one time only
        self.assertEqual(mock_provider_get_alliance.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_alliance')
    def test_alliance_has_none(self, mock_provider_get_alliance) -> None:
        self.my_character.alliance_id = None
        self.assertEqual(self.my_character.alliance, Entity(None, None))
        self.assertEqual(mock_provider_get_alliance.call_count, 0)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_defined(self, mock_provider_get_faction) -> None:
        my_faction = Entity(id=1337, name='Permabanned')
        mock_provider_get_faction.return_value = my_faction

        # fetch from provider if not defined
        self.assertEqual(self.my_character.faction, my_faction)

        # return existing if defined
        mock_provider_get_faction.return_value = None
        self.assertEqual(self.my_character.faction, my_faction)
        self.assertEqual(mock_provider_get_faction.call_count, 1)

    @patch(MODULE_PATH + '.EveOpenAPIProvider.get_faction')
    def test_faction_undefined(self, mock_provider_get_faction) -> None:
        self.my_character.faction_id = None
        self.assertEqual(self.my_character.faction, Entity())
        self.assertEqual(mock_provider_get_faction.call_count, 0)


class TestItemType(TestCase):

    def test_init(self) -> None:
        x = ItemType(id=99, name='Dummy Item')
        self.assertIsInstance(x, ItemType)


class TestEveOpenAPIProvider(TestCase):

    @staticmethod
    def esi_get_alliances_alliance_id(alliance_id) -> Mock:
        alliances = {
            3001: {
                'name': 'Dummy Alliance 1',
                'ticker': 'DA1',
                'executor_corporation_id': 2001
            },
            3002: {
                'name': 'Dummy Alliance 2',
                'ticker': 'DA2'
            }
        }
        mock_result = Mock()
        if alliance_id in alliances:
            mock_result.result.return_value = alliances[alliance_id]
            return mock_result
        else:
            raise HTTPClientError(status_code=404, headers={}, data=Mock())

    @staticmethod
    def esi_get_alliances_alliance_id_corporations(alliance_id) -> Mock:
        alliances = {
            3001: [2001, 2002, 2003],
            3002: [2004, 2005]
        }
        mock_result = Mock()
        if alliance_id in alliances:
            mock_result.result.return_value = alliances[alliance_id]
            return mock_result
        else:
            raise HTTPClientError(status_code=404, headers={}, data=Mock())

    @staticmethod
    def esi_get_corporations_corporation_id(corporation_id) -> Mock:
        corporations = {
            2001: {
                'name': 'Dummy Corp 1',
                'ticker': 'DC1',
                'ceo_id': 1001,
                'member_count': 42,
                'alliance_id': 3001
            },
            2002: {
                'name': 'Dummy Corp 2',
                'ticker': 'DC2',
                'ceo_id': 1011,
                'member_count': 5
            }
        }
        mock_result = Mock()
        if corporation_id in corporations:
            mock_result.result.return_value = corporations[corporation_id]
            return mock_result
        else:
            raise HTTPClientError(status_code=404, headers={}, data=Mock())

    @staticmethod
    def esi_get_characters_character_id(character_id) -> Mock:
        characters = {
            1001: {
                'name': 'Bruce Wayne',
                'corporation_id': 2001,
                'alliance_id': 3001
            },
            1002: {
                'name': 'Peter Parker',
                'corporation_id': 2101
            }
        }
        mock_result = Mock()
        if character_id in characters:
            mock_result.result.return_value = characters[character_id]
            return mock_result
        else:
            raise HTTPClientError(status_code=404, headers={}, data=Mock())

    @staticmethod
    def esi_post_characters_affiliation(characters) -> Mock:
        character_data = {
            1001: {
                'corporation_id': 2001,
                'alliance_id': 3001
            },
            1002: {
                'corporation_id': 2101
            }
        }
        mock_result = Mock()
        if isinstance(characters, list):
            characters_result = []
            for character_id in characters:
                if character_id in character_data:
                    characters_result.append(character_data[character_id])
                else:
                    raise HTTPClientError(status_code=404, headers={}, data=Mock())
            mock_result.result.return_value = characters_result
            return mock_result
        else:
            raise TypeError()

    @staticmethod
    def esi_get_universe_types_type_id(type_id) -> Mock:
        types = {
            4001: SimpleNamespace(name='Dummy Type 1'),
            4002: SimpleNamespace(name='Dummy Type 2'),
        }
        mock_result = Mock()
        if type_id in types:
            mock_result.result.return_value = types[type_id]
            return mock_result
        else:
            raise HTTPClientError(status_code=404, headers={}, data=Mock())

    def test_str(self) -> None:
        my_provider = EveOpenAPIProvider()
        self.assertIsInstance(my_provider, EveOpenAPIProvider)

    @patch.object(EveOpenAPIProvider, 'client', new_callable=PropertyMock)
    def test_get_alliance(self, mock_client) -> None:
        mock_client.return_value = EsiClientStub()
        my_provider = EveOpenAPIProvider()

        # fully defined alliance
        my_alliance = my_provider.get_alliance(3001)
        self.assertEqual(my_alliance.id, 3001)
        self.assertEqual(my_alliance.name, 'Wayne Enterprises')
        self.assertEqual(my_alliance.ticker, 'WYE')
        self.assertListEqual(my_alliance.corp_ids, [2001, 2002, 2003])
        self.assertEqual(my_alliance.executor_corp_id, 2001)

        # alliance not found
        with self.assertRaises(ObjectNotFound):
            my_provider.get_alliance(3999)

    @patch.object(EveOpenAPIProvider, 'client', new_callable=PropertyMock)
    def test_get_corp(self, mock_client) -> None:
        mock_client.return_value = EsiClientStub()
        my_provider = EveOpenAPIProvider()

        # corporation with alliance
        my_corp = my_provider.get_corp(2001)
        self.assertEqual(my_corp.id, 2001)
        self.assertEqual(my_corp.name, 'Wayne Technologies')
        self.assertEqual(my_corp.ticker, 'WTE')
        self.assertEqual(my_corp.ceo_id, 1091)
        self.assertEqual(my_corp.members, 10)
        self.assertEqual(my_corp.alliance_id, 3001)

        # another corporation
        my_corp = my_provider.get_corp(2002)
        self.assertEqual(my_corp.id, 2002)
        self.assertEqual(my_corp.alliance_id, 3001)

        # corporation not found
        with self.assertRaises(ObjectNotFound):
            my_provider.get_corp(2999)

    @patch.object(EveOpenAPIProvider, 'client', new_callable=PropertyMock)
    def test_get_character(self, mock_client) -> None:
        mock_client.return_value = EsiClientStub()
        my_provider = EveOpenAPIProvider()

        # character with alliance
        my_character = my_provider.get_character(1001)
        self.assertEqual(my_character.id, 1001)
        self.assertEqual(my_character.name, 'Bruce Wayne')
        self.assertEqual(my_character.corp_id, 2001)
        self.assertEqual(my_character.alliance_id, 3001)

        # character wo/ alliance
        my_character = my_provider.get_character(1011)
        self.assertEqual(my_character.id, 1011)
        self.assertEqual(my_character.alliance_id, None)

        # character not found
        with self.assertRaises(ObjectNotFound):
            my_provider.get_character(1999)

    @patch.object(EveOpenAPIProvider, 'client', new_callable=PropertyMock)
    def test_get_itemtype(self, mock_client) -> None:
        stub = Mock()
        stub.Universe.GetUniverseTypesTypeId.side_effect = (
            lambda type_id: TestEveOpenAPIProvider.esi_get_universe_types_type_id(type_id)
        )
        mock_client.return_value = stub
        my_provider = EveOpenAPIProvider()

        # type exists
        my_type = my_provider.get_itemtype(4001)
        self.assertEqual(my_type.id, 4001)
        self.assertEqual(my_type.name, 'Dummy Type 1')

        # type not found
        with self.assertRaises(ObjectNotFound):
            my_provider.get_itemtype(4999)

    @patch.object(EveOpenAPIProvider, 'client', new_callable=PropertyMock)
    def test_client_can_be_accessed(self, mock_client) -> None:
        stub = EsiClientStub()
        mock_client.return_value = stub
        my_provider = EveOpenAPIProvider()
        self.assertIs(my_provider.client, stub)

    def test_user_agent_header(self):
        my_provider = EveOpenAPIProvider()
        my_client = my_provider.client
        expected_variants = {
            (
                f"AllianceAuth/{aa_version} (dummy@example.net; +{aa_url}) "
                f"DjangoEsi/{esi_version} (+{esi_url})"
            ),  # Django-ESI 8.0.0
        }
        session_factory = getattr(my_client.api, "_session_factory")
        with session_factory() as session:
            self.assertIn(session.headers.get("User-Agent"), expected_variants)
