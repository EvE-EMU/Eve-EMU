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


def proxy_with_fallback(
    request, tokens: list, esi_path: str, *, prefer_scopes: tuple[str, ...] = ()
) -> HttpResponse:
    """Try a character's/corp's tokens widest-scope-match first, falling
    through to the next one on a 403, instead of committing to a single
    "best guess" token and living with whatever it gets back.

    A character can hold more than one django-esi `Token` row: AA's SSO flow
    creates a new row per distinct scope grant rather than merging into an
    existing one, so a character re-authorised after `PENGUIN_SCOPES` grew
    (it has grown more than once) ends up with an old, narrower token *and*
    a new, wider one both on file. Picking "whichever token has the most
    scopes overall" (the old behaviour, still available as
    `pick_widest_token` for the corp-route scope hint) is right in the
    common case but isn't guaranteed to be the one holding the *specific*
    scope this call needs — a user can also uncheck individual boxes at
    ESI's own consent screen on any given re-auth, producing a token that's
    wider in total but narrower for one particular grant. Silently 403ing
    every call for a scope that a *different*, real token on the same
    account actually holds is exactly the bug class this guards against:
    from the desktop client's point of view `missing_scopes` (computed by
    unioning every token's scopes — see `me()`) says the grant is fine, so
    it has no way to explain a 403 it can't distinguish from "genuinely
    missing".
    """
    if not tokens:
        return JsonResponse({"error": "no_token_for_character"}, status=409)
    ordered = sorted(
        tokens,
        key=lambda t: (len(token_scope_names(t) & set(prefer_scopes)), len(token_scope_names(t))),
        reverse=True,
    )
    # 403 = ESI itself rejecting this token's scopes for this route; 401 = a
    # bad/invalid token; 502 here is this proxy's own "token_refresh_failed"
    # (a revoked/expired token) — none of those mean the *route* is wrong,
    # only that *this* token can't serve it, so try the next one. Any other
    # status (a real 2xx, 404, 420 error-limited, ESI 500, …) reflects the
    # request itself and retrying with a different token wouldn't change it.
    retry_statuses = (401, 403, 502)
    last_resp = None
    for token in ordered:
        resp = proxy(request, token, esi_path)
        if resp.status_code not in retry_statuses:
            return resp
        last_resp = resp
    return last_resp
