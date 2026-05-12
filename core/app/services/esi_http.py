"""Public and authed ESI JSON helpers (Tranquility ``esi.evetech.net``)."""

from __future__ import annotations

from typing import Any

import httpx

_ESI_BASE = "https://esi.evetech.net/latest"
_USER_AGENT = "EVE-EMU-Core/1.0 (+discord-plugin; https://github.com/eve-emu)"


async def esi_get_json(path: str, *, bearer: str | None = None) -> dict[str, Any] | None:
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    url = path if path.startswith("http") else f"{_ESI_BASE}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) else None


async def character_corporation_id(character_id: int) -> int | None:
    data = await esi_get_json(f"/characters/{character_id}/")
    if not data:
        return None
    cid = data.get("corporation_id")
    if cid is None:
        return None
    try:
        return int(cid)
    except (TypeError, ValueError):
        return None


async def corporation_ceo_id(corporation_id: int) -> int | None:
    data = await esi_get_json(f"/corporations/{corporation_id}/")
    if not data:
        return None
    ceo = data.get("ceo_id")
    if ceo is None:
        return None
    try:
        return int(ceo)
    except (TypeError, ValueError):
        return None


def _role_id_sets(roles_body: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for key in ("roles", "roles_at_hq", "roles_at_base", "roles_at_other"):
        block = roles_body.get(key)
        if isinstance(block, list):
            for x in block:
                try:
                    out.add(int(x))
                except (TypeError, ValueError):
                    continue
    return out


async def character_role_ids(*, character_id: int, bearer: str) -> set[int]:
    data = await esi_get_json(f"/characters/{character_id}/roles/", bearer=bearer)
    if not data:
        return set()
    return _role_id_sets(data)
