from types import SimpleNamespace
from typing import Any, NoReturn, Optional, cast

from esi.exceptions import HTTPClientError


class OpenAPIOperationStub:
    """Stub to simulate aiopenapi3 EsiOperation behavior used in tests."""

    class ResponseStub:
        def __init__(self, headers: dict, status_code: int = 200) -> None:
            self.headers = headers
            self.status_code = status_code

    def __init__(
        self,
        data,
        headers: dict | None = None,
    ):
        self._data = data
        self._headers = headers if headers else {"x-pages": 1}
        self._args = []
        self._kwargs = {}

    @classmethod
    def _to_namespace(cls, value):
        if isinstance(value, dict):
            return SimpleNamespace(**{k: cls._to_namespace(v) for k, v in value.items()})
        if isinstance(value, list):
            return [cls._to_namespace(v) for v in value]
        return value

    def __call__(self, *args, **kwargs) -> "OpenAPIOperationStub":
        self._args = args
        self._kwargs = kwargs
        return self

    def _resolve_data(self):
        data = self._data(*self._args, **self._kwargs) if callable(self._data) else self._data
        return self._to_namespace(data)

    def result(self, **kwargs):
        return_response = kwargs.pop("return_response", False)
        _ = kwargs.pop("use_etag", None)
        _ = kwargs.pop("force_refresh", None)
        _ = kwargs.pop("use_cache", None)
        _ = kwargs.pop("store_cache", None)
        data = self._resolve_data()
        response = self.ResponseStub(self._headers)
        if return_response:
            return data, response
        return data

    def results(self, **kwargs):
        return_response = kwargs.pop("return_response", False)
        data = self.result(**kwargs)
        if return_response:
            results, response = data
            if not isinstance(results, list):
                results = [results]
            return results, response
        if not isinstance(data, list):
            return [data]
        return data


class EsiClientStub:
    """Stub for an ESI client."""

    @staticmethod
    def _operation(data, headers: dict | None = None) -> OpenAPIOperationStub:
        return OpenAPIOperationStub(data, headers=headers)

    @staticmethod
    def _raise_not_found(resource: str, resource_id: int) -> NoReturn:
        raise HTTPClientError(
            status_code=404,
            headers={},
            data=cast(
                Any,
                {"detail": f"{resource.title()} with ID {resource_id} not found"},
            ),
        )

    class Alliance:
        @staticmethod
        def GetAlliancesAllianceId(alliance_id) -> OpenAPIOperationStub:
            data = {
                3001: {
                    "name": "Wayne Enterprises",
                    "ticker": "WYE",
                    "executor_corporation_id": 2001
                }
            }
            try:
                return EsiClientStub._operation(data[int(alliance_id)])
            except KeyError:
                EsiClientStub._raise_not_found("alliances", int(alliance_id))

        @staticmethod
        def GetAlliancesAllianceIdCorporations(alliance_id) -> OpenAPIOperationStub:
            data = [2001, 2002, 2003]
            return EsiClientStub._operation(data)

        get_alliances_alliance_id = GetAlliancesAllianceId
        get_alliances_alliance_id_corporations = GetAlliancesAllianceIdCorporations

    class Character:
        @staticmethod
        def GetCharactersCharacterId(character_id) -> OpenAPIOperationStub:
            data = {
                1001: {
                    "corporation_id": 2001,
                    "name": "Bruce Wayne",
                },
                1002: {
                    "corporation_id": 2001,
                    "name": "Peter Parker",
                },
                1011: {
                    "corporation_id": 2011,
                    "name": "Lex Luthor",
                }
            }
            try:
                return EsiClientStub._operation(data[int(character_id)])
            except KeyError:
                EsiClientStub._raise_not_found("characters", int(character_id))

        @staticmethod
        def PostCharactersAffiliation(body: list) -> OpenAPIOperationStub:
            data = [
                {'character_id': 1001, 'corporation_id': 2001, 'alliance_id': 3001},
                {'character_id': 1002, 'corporation_id': 2001, 'alliance_id': 3001},
                {'character_id': 1011, 'corporation_id': 2011},
                {'character_id': 1666, 'corporation_id': 1000001},
            ]
            return EsiClientStub._operation(
                [x for x in data if x['character_id'] in body]
            )

        @staticmethod
        def post_characters_affiliation(characters: list) -> OpenAPIOperationStub:
            return EsiClientStub.Character.PostCharactersAffiliation(body=characters)

        get_characters_character_id = GetCharactersCharacterId

    class Corporation:
        @staticmethod
        def GetCorporationsCorporationId(corporation_id) -> OpenAPIOperationStub:
            data = {
                2001: {
                    "ceo_id": 1091,
                    "member_count": 10,
                    "name": "Wayne Technologies",
                    "ticker": "WTE",
                    "alliance_id": 3001
                },
                2002: {
                    "ceo_id": 1092,
                    "member_count": 10,
                    "name": "Wayne Food",
                    "ticker": "WFO",
                    "alliance_id": 3001
                },
                2003: {
                    "ceo_id": 1093,
                    "member_count": 10,
                    "name": "Wayne Energy",
                    "ticker": "WEG",
                    "alliance_id": 3001
                },
                2011: {
                    "ceo_id": 1,
                    "member_count": 3,
                    "name": "LexCorp",
                    "ticker": "LC",
                },
                1000001: {
                    "ceo_id": 3000001,
                    "creator_id": 1,
                    "description": "The internal corporation used for characters in graveyard.",
                    "member_count": 6329026,
                    "name": "Doomheim",
                    "ticker": "666",
                }
            }
            try:
                return EsiClientStub._operation(data[int(corporation_id)])
            except KeyError:
                EsiClientStub._raise_not_found("corporations", int(corporation_id))

        get_corporations_corporation_id = GetCorporationsCorporationId

    class Universe:
        @staticmethod
        def PostUniverseNames(body: list) -> OpenAPIOperationStub:
            data = [
                {"category": "character", "id": 1001, "name": "Bruce Wayne"},
                {"category": "character", "id": 1002, "name": "Peter Parker"},
                {"category": "character", "id": 1011, "name": "Lex Luthor"},
                {"category": "character", "id": 1666, "name": "Hal Jordan"},
                {"category": "corporation", "id": 2001, "name": "Wayne Technologies"},
                {"category": "corporation", "id": 2002, "name": "Wayne Food"},
                {"category": "corporation", "id": 1000001, "name": "Doomheim"},
            ]
            return EsiClientStub._operation([x for x in data if x['id'] in body])

        post_universe_names = PostUniverseNames
