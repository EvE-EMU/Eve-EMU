import logging

from esi.exceptions import HTTPClientError
from esi.openapi_clients import ESIClientProvider

from allianceauth import (
    __esi_compatibility_date__, __title_useragent__, __url__, __version__,
)

# for the love of Bob please add operations you use here. I'm tired of breaking undocumented things.
# Open API
OPEN_API_OPERATIONS = [
    "GetAlliancesAllianceId",
    "GetAlliancesAllianceIdCorporations",
    "GetCorporationsCorporationId",
    "PostCharactersAffiliation",
    "PostUniverseNames",
    "GetUniverseFactions",
    "GetUniverseTypesTypeId"
]

logger = logging.getLogger(__name__)


class ObjectNotFound(Exception):
    def __init__(self, obj_id, type_name):
        self.id = obj_id
        self.type = type_name

    def __str__(self) -> str:
        return f'{self.type} with ID {self.id} not found.'


class Entity:
    def __init__(self, id=None, name=None, **kwargs):
        super().__init__(**kwargs)
        self.id = id
        self.name = name

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ({self.id}): {self.name}>"

    def __bool__(self) -> bool:
        return bool(self.id)

    def __eq__(self, other):
        return self.id == other.id


class AllianceMixin:
    def __init__(self, alliance_id=None, **kwargs):
        super().__init__(**kwargs)
        self.alliance_id = alliance_id
        self._alliance = None

    @property
    def alliance(self):
        if self.alliance_id:
            if not self._alliance:
                self._alliance = open_api_provider.get_alliance(self.alliance_id, use_etag=False)  # ETAG False, We need response data to create the alliance object.
            return self._alliance
        return Entity(None, None)


class FactionMixin:
    def __init__(self, faction_id=None, **kwargs):
        super().__init__(**kwargs)
        self.faction_id = faction_id
        self._faction = None

    @property
    def faction(self):
        if self.faction_id:
            if not self._faction:
                self._faction = open_api_provider.get_faction(self.faction_id)
            return self._faction
        return Entity(None, None)


class Corporation(Entity, AllianceMixin, FactionMixin):
    def __init__(self, ticker=None, ceo_id=None, members=None, **kwargs):
        super().__init__(**kwargs)
        self.ticker = ticker
        self.ceo_id = ceo_id
        self.members = members
        self._ceo = None

    @property
    def ceo(self):
        if not self._ceo:
            self._ceo = open_api_provider.get_character(self.ceo_id)
        return self._ceo


class Alliance(Entity, FactionMixin):
    def __init__(self, ticker=None, corp_ids=None, executor_corp_id=None, **kwargs):
        super().__init__(**kwargs)
        self.ticker = ticker
        self.corp_ids = corp_ids
        self.executor_corp_id = executor_corp_id
        self._corps = {}

    def corp(self, id):
        assert id in self.corp_ids
        if id not in self._corps:
            self._corps[id] = open_api_provider.get_corp(id, use_etag=False)  # ETAG False, We need response data to create the corp object.
            self._corps[id]._alliance = self
        return self._corps[id]

    @property
    def corps(self):
        return sorted((self.corp(c_id) for c_id in self.corp_ids), key=lambda x: x.name)

    @property
    def executor_corp(self):
        if self.executor_corp_id:
            return self.corp(self.executor_corp_id)
        return Entity(None, None)


class Character(Entity, AllianceMixin, FactionMixin):
    def __init__(self, corp_id=None, **kwargs):
        super().__init__(**kwargs)
        self.corp_id = corp_id
        self._corp = None

    @property
    def corp(self) -> Corporation:
        if not self._corp:
            self._corp = open_api_provider.get_corp(self.corp_id, use_etag=False)  # ETAG False, We need response data to create the corp object.
        return self._corp


class ItemType(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class EveOpenAPIProvider(ESIClientProvider):
    # most operations used here have `use_cache = False` this is cause we don't
    # want to use the space in ram for mostly useless data. We are using etags tho.

    def __init__(self):
        super().__init__(
            __esi_compatibility_date__,
            __title_useragent__,
            __version__,
            __url__,
            operations=OPEN_API_OPERATIONS
        )
        self._faction_list = None

    def get_alliance_corps(self, alliance_id: int, force_refresh=False, use_etag: bool = True) -> list:
        """Fetch alliance from ESI."""
        try:
            corps = self.client.Alliance.GetAlliancesAllianceIdCorporations(
                alliance_id=alliance_id
            ).result(
                force_refresh=force_refresh,
                use_cache=False,
                use_etag=use_etag
            )
            return corps
        except HTTPClientError as e:
            if e.status_code == 404:
                ### check this
                raise ObjectNotFound(alliance_id, 'alliance')
            else:
                raise e

    def get_alliance(self, alliance_id: int, force_refresh=False, use_etag: bool = True) -> Alliance:
        """Fetch alliance from ESI."""
        try:
            data = self.client.Alliance.GetAlliancesAllianceId(
                alliance_id=alliance_id
            ).result(
                force_refresh=force_refresh,
                use_cache=False,
                use_etag=use_etag
            )
            corps = self.get_alliance_corps(alliance_id, force_refresh=force_refresh, use_etag=False)  # ETAG False, We need response data to create the child objects
            model = Alliance(
                id=alliance_id,
                name=data.name,
                ticker=data.ticker,
                corp_ids=corps,
                executor_corp_id=data.executor_corporation_id,
                faction_id=getattr(data, "faction_id", None),
            )
            return model
        except HTTPClientError as e:
            if e.status_code == 404:
                raise ObjectNotFound(alliance_id, 'alliance')
            else:
                raise e

    def get_corp(self, corp_id: int, force_refresh=False, use_etag: bool = True) -> Corporation:
        """Fetch corporation from ESI."""
        try:
            data = self.client.Corporation.GetCorporationsCorporationId(
                corporation_id=corp_id
            ).result(
                force_refresh=force_refresh,
                use_cache=False,
                use_etag=use_etag
            )
            model = Corporation(
                id=corp_id,
                name=data.name,
                ticker=data.ticker,
                ceo_id=data.ceo_id,
                members=data.member_count,
                alliance_id=getattr(data, "alliance_id", None),
                faction_id=getattr(data, "faction_id", None),
            )
            return model
        except HTTPClientError as e:
            logger.error(e)
            if e.status_code == 404:
                raise ObjectNotFound(corp_id, 'corporation')
            else:
                raise e

    def get_character(self, character_id: int, force_refresh=False, use_etag: bool = True) -> Character:
        """Fetch character from ESI."""
        try:
            character_name = self._fetch_character_name(character_id)
            affiliation = self.client.Character.PostCharactersAffiliation(
                body=[character_id]
            ).result(
                force_refresh=force_refresh,
                use_cache=False
            )[0]
            model = Character(
                id=character_id,
                name=character_name,
                corp_id=affiliation.corporation_id,
                alliance_id=getattr(affiliation, "alliance_id", None),
                faction_id=getattr(affiliation, "faction_id", None),
            )
            return model
        except (HTTPClientError, ObjectNotFound) as e:
            logger.error(e)
            raise ObjectNotFound(character_id, 'character')

    def _fetch_character_name(self, character_id: int) -> str:
        """Fetch character name from ESI."""
        data = self.client.Universe.PostUniverseNames(body=[character_id]).result()
        character = data.pop() if data else None
        if (
            not character
            or character.category != "character"
            or character.id != character_id
        ):
            raise ObjectNotFound(character_id, 'character')
        return character.name

    def get_all_factions(self, force_refresh=False, use_cache=True, use_etag=True) -> list:
        """Fetch all factions from ESI."""
        if not self._faction_list:
            self._faction_list = self.client.Universe.GetUniverseFactions(
            ).result(
                force_refresh=force_refresh,
                use_cache=use_cache,
                use_etag=use_etag
            )
        return self._faction_list

    def get_faction(self, faction_id: int, force_refresh=False, use_etag: bool = True):
        """Fetch faction from ESI."""
        faction_id = int(faction_id)
        try:
            if not self._faction_list:
                _ = self.get_all_factions(
                    force_refresh=force_refresh,
                    use_cache=False,
                    use_etag=use_etag,
                )
            for f in self._faction_list:
                if f.faction_id == faction_id:
                    return Entity(id=f.faction_id, name=f.name)
            else:
                raise KeyError()
        except (HTTPClientError, KeyError) as ex:
            if isinstance(ex, HTTPClientError) and ex.status_code not in {404, 422}:
                raise
            raise ObjectNotFound(faction_id, 'faction')

    def get_itemtype(self, type_id: int, force_refresh=False) -> ItemType:
        """Fetch inventory item from ESI."""
        try:
            data = self.client.Universe.GetUniverseTypesTypeId(
                type_id=type_id
            ).result(
                force_refresh=force_refresh,
                use_cache=False
            )
            return ItemType(id=type_id, name=data.name)
        except HTTPClientError as ex:
            if ex.status_code not in {404, 422}:
                raise
            raise ObjectNotFound(type_id, 'type')

open_api_provider = EveOpenAPIProvider()
