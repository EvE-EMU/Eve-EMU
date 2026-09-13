"""Async MediaWiki API client for read-only knowledge lookups."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
_logged_in = False


def _api_url() -> str:
    url = settings.mediawiki_api_url.rstrip("/")
    if not url.endswith("api.php"):
        url = f"{url}/api.php"
    return url


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _client


async def _post(params: dict[str, Any]) -> dict[str, Any]:
    client = await _get_client()
    data = {**params, "format": "json"}
    resp = await client.post(_api_url(), data=data)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise RuntimeError(payload["error"].get("info", str(payload["error"])))
    return payload


async def _ensure_login() -> None:
    """Optional bot login for restricted namespaces."""
    global _logged_in
    if _logged_in or not settings.mediawiki_bot_password:
        return
    try:
        token_resp = await _post({"action": "query", "meta": "tokens", "type": "login"})
        login_token = token_resp["query"]["tokens"]["logintoken"]
        await _post(
            {
                "action": "login",
                "lgname": settings.mediawiki_bot_user or "Admin",
                "lgpassword": settings.mediawiki_bot_password,
                "lgtoken": login_token,
            }
        )
        _logged_in = True
    except Exception as exc:
        logger.warning("MediaWiki bot login skipped: %s", exc)


async def search_pages(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    await _ensure_login()
    payload = await _post(
        {
            "action": "query",
            "list": "search",
            "srsearch": query.strip(),
            "srlimit": max(1, min(limit, 50)),
            "srnamespace": "0",
        }
    )
    return list(payload.get("query", {}).get("search", []))


async def parse_page(title: str) -> dict[str, Any] | None:
    if not title.strip():
        return None
    await _ensure_login()
    try:
        payload = await _post(
            {
                "action": "parse",
                "page": title.strip(),
                "redirects": "1",
                "prop": "text|sections|links|displaytitle",
                "disableeditsection": "1",
            }
        )
    except Exception as exc:
        logger.debug("MediaWiki parse failed for %s: %s", title, exc)
        return None
    parsed = payload.get("parse")
    if not parsed:
        return None
    return {
        "title": str(parsed.get("title") or title),
        "pageid": int(parsed.get("pageid") or 0),
        "displaytitle": str(parsed.get("displaytitle") or parsed.get("title") or title),
        "html": str(parsed.get("text", {}).get("*") or ""),
        "sections": parsed.get("sections") or [],
        "links": parsed.get("links") or [],
    }


def wiki_page_url(title: str) -> str:
    base = settings.mediawiki_public_url.rstrip("/")
    segment = title.replace(" ", "_")
    return f"{base}/index.php/{segment}"
