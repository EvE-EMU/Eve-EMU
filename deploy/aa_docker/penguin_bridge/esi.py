"""Thin ESI proxy: take a django-esi Token, forward a request to ESI as that
character/corp, hand the response straight back.

Generic on purpose — the desktop client can hit any ESI route its token's
scopes allow. Scope enforcement is ESI's job; a 403 from ESI is forwarded as-is
so the client can prompt a re-auth.
"""

from __future__ import annotations

import logging
import os

import requests
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

ESI_BASE = os.environ.get("ESI_URL", "https://esi.evetech.net/latest").rstrip("/")
_COMPAT_DATE = os.environ.get("AA_ESI_COMPATIBILITY_DATE", "2025-12-16").strip()
_UA = "eve-penguin-proxy/1.0 (+https://eve-emu.com; alliance client)"
_PASS_THROUGH_HEADERS = ("ETag", "Expires", "Last-Modified", "X-Pages", "Warning")
_TIMEOUT = 45
_MAX_PAGES = 20  # cap merged pagination (assets can be huge)

# Any of these present on a token ⇒ treat it as a good candidate for corp routes.
CORP_SCOPE_HINTS = (
    "esi-wallet.read_corporation_wallets.v1",
    "esi-corporations.read_divisions.v1",
    "esi-corporations.read_structures.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-contracts.read_corporation_contracts.v1",
)


def token_scope_names(token) -> set[str]:
    try:
        return {s.name for s in token.scopes.all()}
    except Exception:
        return set()


def pick_widest_token(tokens: list, *, prefer_scopes: tuple[str, ...] = ()) -> object | None:
    """Of several tokens for one character, the one most likely to satisfy the
    call: most matches against `prefer_scopes` first, then most scopes overall."""
    if not tokens:
        return None
    prefer = set(prefer_scopes)

    def rank(tok):
        names = token_scope_names(tok)
        return (len(names & prefer), len(names))

    return max(tokens, key=rank)


def _normalise_path(esi_path: str) -> str:
    p = esi_path.strip().lstrip("/")
    # ESI latest routes are trailing-slash; add one unless the last segment
    # looks like a file/extension or a query was already glued on.
    if "?" not in p and "." not in p.rsplit("/", 1)[-1] and not p.endswith("/"):
        p += "/"
    return p


def proxy(request, token, esi_path: str) -> HttpResponse:
    try:
        access_token = token.valid_access_token()
    except Exception as exc:  # refresh failed / token revoked upstream
        logger.warning("penguin esi: token refresh failed: %s", exc)
        return JsonResponse(
            {"error": "token_refresh_failed", "detail": str(exc)}, status=502
        )

    url = f"{ESI_BASE}/{_normalise_path(esi_path)}"
    params = request.GET.copy()
    params.pop("token", None)
    params.setdefault("datasource", "tranquility")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": _UA,
        "X-Compatibility-Date": _COMPAT_DATE,
    }
    data = None
    if request.method == "POST":
        data = request.body or b""
        headers["Content-Type"] = request.headers.get("Content-Type", "application/json")

    try:
        r = requests.request(
            request.method,
            url,
            params=params,
            headers=headers,
            data=data,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("penguin esi: upstream error for %s: %s", url, exc)
        return JsonResponse({"error": "esi_unreachable", "detail": str(exc)}, status=502)

    # Auto-follow pagination for GET routes that return a JSON array: assets,
    # journals, contracts, orders, etc. The client gets one merged array.
    try:
        total_pages = int(r.headers.get("X-Pages", "1") or "1")
    except ValueError:
        total_pages = 1
    if (
        request.method == "GET"
        and r.ok
        and total_pages > 1
        and "page" not in params
        and r.headers.get("Content-Type", "").startswith("application/json")
    ):
        try:
            merged = r.json()
            if isinstance(merged, list):
                for page in range(2, min(total_pages, _MAX_PAGES) + 1):
                    pr = requests.get(
                        url,
                        params={**params, "page": page},
                        headers=headers,
                        timeout=_TIMEOUT,
                    )
                    if not pr.ok:
                        break
                    chunk = pr.json()
                    if not isinstance(chunk, list):
                        break
                    merged.extend(chunk)
                resp = JsonResponse(merged, safe=False, status=200)
                resp["X-Penguin-Pages-Merged"] = str(min(total_pages, _MAX_PAGES))
                resp["X-Penguin-Esi-Url"] = url
                return resp
        except ValueError:
            pass  # not JSON after all; fall through to raw passthrough

    content_type = r.headers.get("Content-Type", "application/json")
    resp = HttpResponse(r.content, status=r.status_code, content_type=content_type)
    for h in _PASS_THROUGH_HEADERS:
        if h in r.headers:
            resp[h] = r.headers[h]
    resp["X-Penguin-Esi-Url"] = url
    return resp
