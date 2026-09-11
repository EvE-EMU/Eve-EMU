"""EVE-Penguin desktop-client endpoints, mounted at /penguin/* on auth.eve-emu.com.

- GET  /penguin/authorize        browser: AA login + ESI consent, redirect back to a
                                 127.0.0.1 loopback URL with a session token
- GET  /penguin/me               session -> account + linked characters + missing scopes
- GET|POST /penguin/esi/<char_id>/<esi_path>       proxy ESI as that character
- GET|POST /penguin/esi/corp/<corp_id>/<esi_path>  proxy ESI as the corp (needs a
                                 linked character with the scope + in-game role)
- POST /penguin/logout           client drops the token; 204
- GET  /penguin/health           liveness

Session is a stateless HMAC token (see session.py). See eve-penguin/docs/AUTH.md.
"""

from __future__ import annotations

import logging
from urllib.parse import quote, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from esi.decorators import token_required

from penguin_bridge import esi as esi_proxy
from penguin_bridge.session import issue, verify

logger = logging.getLogger("penguin_bridge")

# Scopes the desktop client asks AA to hold. Broad, read-oriented, plus the two
# ESI "write" scopes needed for autopilot / open-window. Keep in sync with
# penguin-core::auth::WANTED_SCOPES.
PENGUIN_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-wallet.read_corporation_wallets.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_contacts.v1",
    "esi-corporations.read_contacts.v1",
    "esi-alliances.read_contacts.v1",
    "esi-characters.read_notifications.v1",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-location.read_online.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-assets.read_assets.v1",
    "esi-assets.read_corporation_assets.v1",
    "esi-universe.read_structures.v1",
    "esi-planets.manage_planets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-industry.read_corporation_jobs.v1",
    "esi-corporations.read_divisions.v1",
    "esi-corporations.read_structures.v1",
    "esi-corporations.read_projects.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-contracts.read_corporation_contracts.v1",
    "esi-markets.read_character_orders.v1",
    "esi-markets.read_corporation_orders.v1",
    "esi-mail.read_mail.v1",
    "esi-fittings.read_fittings.v1",
    "esi-fleets.read_fleet.v1",
    "esi-search.search_structures.v1",
    "esi-ui.write_waypoint.v1",
    "esi-ui.open_window.v1",
    "esi-killmails.read_killmails.v1",
]


# --- helpers --------------------------------------------------------------


def _bearer(request) -> str:
    header = request.headers.get("Authorization", "")
    if header[:7].lower() == "bearer ":
        return header[7:].strip()
    return (request.GET.get("token") or request.headers.get("X-Penguin-Session") or "").strip()


def _session_user(request):
    payload = verify(_bearer(request))
    if not payload:
        return None, None
    user = get_user_model().objects.filter(pk=payload.get("uid")).first()
    return user, payload


def _is_loopback(redirect_uri: str) -> bool:
    try:
        host = urlparse(redirect_uri).hostname or ""
    except Exception:
        return False
    return host in ("127.0.0.1", "localhost", "::1")


def _main_character_id(user) -> int:
    try:
        return int(user.profile.main_character.character_id)
    except Exception:
        return 0


# --- endpoints ---------------------------------------------------------


@login_required
@token_required(scopes=PENGUIN_SCOPES)
def authorize(request, token):
    """Browser lands here. `@login_required` puts them through AA login;
    `@token_required` runs EVE SSO / the token picker so a Token covering
    PENGUIN_SCOPES exists for the chosen character. Then bounce back to the
    client's loopback listener with a session token."""
    redirect_uri = request.GET.get("redirect_uri", "")
    state = request.GET.get("state", "")
    if not redirect_uri or not _is_loopback(redirect_uri):
        return HttpResponseBadRequest("redirect_uri must be a 127.0.0.1/localhost URL")

    sess = issue(request.user, main_character_id=_main_character_id(request.user))
    glue = "&" if "?" in redirect_uri else "?"
    logger.info("penguin authorize: issued session for user %s", request.user.pk)
    return redirect(f"{redirect_uri}{glue}token={quote(sess)}&state={quote(state)}")


@require_GET
@csrf_exempt
def me(request):
    user, payload = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)

    from allianceauth.authentication.models import CharacterOwnership
    from esi.models import Token

    scopes_by_char: dict[int, set[str]] = {}
    for tok in Token.objects.filter(user=user).prefetch_related("scopes"):
        scopes_by_char.setdefault(int(tok.character_id), set()).update(
            s.name for s in tok.scopes.all()
        )

    characters = []
    ownerships = (
        CharacterOwnership.objects.filter(user=user)
        .select_related("character")
        .order_by("character__character_name")
    )
    for own in ownerships:
        c = own.character
        have = scopes_by_char.get(int(c.character_id), set())
        characters.append(
            {
                "id": int(c.character_id),
                "name": c.character_name,
                "corporation": c.corporation_name or "",
                "corporation_id": int(c.corporation_id or 0),
                "alliance": c.alliance_name or "",
                "alliance_id": int(c.alliance_id or 0),
                "portrait_url": f"https://images.evetech.net/characters/{c.character_id}/portrait?size=64",
                "missing_scopes": [s for s in PENGUIN_SCOPES if s not in have],
            }
        )

    return JsonResponse(
        {
            "user_id": int(user.pk),
            "user_name": user.username,
            "main_character_id": int(payload.get("main") or _main_character_id(user)),
            "characters": characters,
        }
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def esi_char(request, character_id: int, esi_path: str):
    user, _ = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)

    from allianceauth.authentication.models import CharacterOwnership
    from esi.models import Token

    character_id = int(character_id)
    if not CharacterOwnership.objects.filter(
        user=user, character__character_id=character_id
    ).exists():
        return JsonResponse({"error": "not_your_character"}, status=403)

    tokens = list(
        Token.objects.filter(user=user, character_id=character_id).prefetch_related("scopes")
    )
    token = esi_proxy.pick_widest_token(tokens)
    if token is None:
        return JsonResponse({"error": "no_token_for_character"}, status=409)

    return esi_proxy.proxy(request, token, esi_path)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def esi_corp(request, corporation_id: int, esi_path: str):
    user, _ = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)

    from allianceauth.authentication.models import CharacterOwnership
    from esi.models import Token

    corporation_id = int(corporation_id)
    char_ids = list(
        CharacterOwnership.objects.filter(
            user=user, character__corporation_id=corporation_id
        ).values_list("character__character_id", flat=True)
    )
    if not char_ids:
        return JsonResponse({"error": "no_character_in_corp"}, status=403)

    tokens = list(
        Token.objects.filter(user=user, character_id__in=char_ids).prefetch_related("scopes")
    )
    token = esi_proxy.pick_widest_token(
        tokens, prefer_scopes=esi_proxy.CORP_SCOPE_HINTS
    )
    if token is None:
        return JsonResponse({"error": "no_token_in_corp"}, status=409)

    # ESI enforces the in-game role; a 403 from upstream is forwarded as-is.
    return esi_proxy.proxy(request, token, esi_path)


@csrf_exempt
@require_POST
def logout(request):
    # Stateless sessions — nothing to revoke server-side yet. The client drops
    # the token; a denylist can be added here later without a wire change.
    return JsonResponse({}, status=204)


@require_GET
@csrf_exempt
def health(request):
    return JsonResponse({"ok": True, "scopes": len(PENGUIN_SCOPES)})
