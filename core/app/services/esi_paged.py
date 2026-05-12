"""Paginated ESI GET (``X-Pages``) for list endpoints."""

from __future__ import annotations

from typing import Any

import httpx

_ESI_BASE = "https://esi.evetech.net/latest"
_USER_AGENT = "EVE-EMU-Core/1.0 (+moon-taxes; https://github.com/eve-emu)"


async def esi_get_paged_json_list(rel_path: str, *, bearer: str | None = None) -> list[Any]:
    """GET ``/latest/...`` paths that return a JSON array with optional ``page`` query."""
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    sep = "&" if "?" in rel_path else "?"
    out: list[Any] = []
    async with httpx.AsyncClient(timeout=45.0) as client:
        page = 1
        while True:
            url = f"{_ESI_BASE}{rel_path}{sep}page={page}"
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                break
            out.extend(data)
            try:
                total_pages = int(resp.headers.get("X-Pages", "1"))
            except (TypeError, ValueError):
                total_pages = 1
            if page >= total_pages or not data:
                break
            page += 1
    return out
