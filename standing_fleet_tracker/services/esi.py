"""ESI HTTP helpers using character tokens from django-esi."""

from __future__ import annotations

import logging
from typing import Any

import requests
from esi.models import Token

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def token_for_character(character_id: int) -> Token | None:
    """Prefer a token that has all standing-fleet scopes (not merely the newest login)."""
    from standing_fleet_tracker.services.scopes import required_scopes

    scopes = required_scopes()
    if scopes:
        try:
            token = Token.get_token(character_id=character_id, scopes=scopes)
            if token:
                return token
        except Token.DoesNotExist:
            pass
    return (
        Token.objects.filter(character_id=character_id)
        .order_by("-created")
        .first()
    )


def esi_get(
    path: str,
    *,
    token: Token | None = None,
    params: dict | None = None,
) -> tuple[int, Any]:
    status, data, _headers = esi_get_response(path, token=token, params=params)
    return status, data


def esi_get_response(
    path: str,
    *,
    token: Token | None = None,
    params: dict | None = None,
) -> tuple[int, Any, requests.structures.CaseInsensitiveDict]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token.valid_access_token()}"
    url = f"{ESI_BASE}{path}"
    try:
        resp = requests.get(url, headers=headers, params=params or {}, timeout=25)
    except requests.RequestException as exc:
        logger.warning("ESI request failed %s: %s", path, exc)
        return 0, None, requests.structures.CaseInsensitiveDict()
    if resp.status_code == 204:
        return resp.status_code, None, resp.headers
    try:
        data = resp.json() if resp.content else None
    except ValueError:
        data = None
    return resp.status_code, data, resp.headers


def get_character_assets(character_id: int, token: Token) -> list[dict] | None:
    """All character assets (paged). Requires esi-assets.read_assets.v1."""
    path = f"/characters/{character_id}/assets/"
    all_rows: list[dict] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        status, data, resp_headers = esi_get_response(path, token=token, params={"page": page})
        if status != 200 or not isinstance(data, list):
            if page == 1:
                return None
            break
        all_rows.extend(data)
        try:
            total_pages = int(resp_headers.get("X-Pages", 1))
        except (TypeError, ValueError):
            total_pages = 1
        page += 1
    return all_rows


def get_character_fleet(character_id: int, token: Token) -> tuple[int, dict | None]:
    return esi_get(f"/characters/{character_id}/fleet/", token=token)


def get_character_location(character_id: int, token: Token) -> tuple[int, dict | None]:
    return esi_get(f"/characters/{character_id}/location/", token=token)


def get_character_ship(character_id: int, token: Token) -> tuple[int, dict | None]:
    return esi_get(f"/characters/{character_id}/ship/", token=token)


def get_character_killmails(character_id: int, token: Token) -> tuple[int, list | None]:
    status, data = esi_get(f"/characters/{character_id}/killmails/recent/", token=token)
    if status != 200 or not isinstance(data, list):
        return status, None
    return status, data


def get_killmail(killmail_id: int, killmail_hash: str, token: Token) -> tuple[int, dict | None]:
    return esi_get(f"/killmails/{killmail_id}/{killmail_hash}/", token=token)


def get_fleet_info(fleet_id: int, token: Token) -> tuple[int, dict | None]:
    return esi_get(f"/fleets/{fleet_id}/", token=token)


def get_fleet_members(
    fleet_id: int,
    token: Token,
    *,
    fleet_boss_id: int | None = None,
) -> list[dict]:
    """Fleet roster; usually requires fleet boss / FC token."""
    tokens_to_try: list[Token] = []
    if fleet_boss_id:
        boss = token_for_character(fleet_boss_id)
        if boss:
            tokens_to_try.append(boss)
    if token not in tokens_to_try:
        tokens_to_try.append(token)

    for read_token in tokens_to_try:
        status, data = esi_get(f"/fleets/{fleet_id}/members/", token=read_token)
        if status == 200 and isinstance(data, list):
            return data
    return []


def get_character_wallet_journal(character_id: int, token: Token) -> list[dict] | None:
    path = f"/characters/{character_id}/wallet/journal/"
    all_rows: list[dict] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        status, data, resp_headers = esi_get_response(path, token=token, params={"page": page})
        if status != 200 or not isinstance(data, list):
            if page == 1:
                return None
            break
        all_rows.extend(data)
        try:
            total_pages = int(resp_headers.get("X-Pages", 1))
        except (TypeError, ValueError):
            total_pages = 1
        page += 1
    return all_rows


def get_character_mining_ledger(character_id: int, token: Token) -> list[dict] | None:
    status, data = esi_get(f"/characters/{character_id}/mining/ledger/", token=token)
    if status != 200 or not isinstance(data, list):
        return None
    return data


def get_sovereignty_map() -> dict[str, int] | None:
    status, data = esi_get("/sovereignty/map/")
    if status != 200 or not isinstance(data, list):
        return None
    return {str(row.get("solar_system_id")): int(row.get("alliance_id", 0)) for row in data}
