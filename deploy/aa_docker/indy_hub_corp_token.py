"""Pin Indy Hub corporation ESI sync to django-esi token overrides (e.g. Lamaashtu #58).

Indy Hub normally only uses tokens owned by the logged-in user and requires
``DIRECTOR`` / ``FACTORY_MANAGER`` from ESI roles. On the private server, role
names differ and the corp token may belong to another account — use the same
``AA_FALSE_GODS_CORP_TOKEN_ID`` / ``AA_CORP_TOKEN_OVERRIDES`` env as CorpTools.
"""

from __future__ import annotations

import logging
from typing import Any

from corptools_corp_token import FALSE_GODS_CORP_ID, _parse_corp_token_overrides

logger = logging.getLogger(__name__)

# Private-server role names that should count as corp-industry capable.
_EXTRA_CORP_ROLES = frozenset(
    {
        "DIRECTOR",
        "FACTORY_MANAGER",
        "STATION_MANAGER",
        "CONFIG_STARBASE_EQUIPMENT",
    }
)


def override_character_ids() -> set[int]:
    from esi.models import Token

    ids: set[int] = set()
    for token_pk in _parse_corp_token_overrides().values():
        tid = (
            Token.objects.filter(pk=token_pk)
            .values_list("character_id", flat=True)
            .first()
        )
        if tid:
            ids.add(int(tid))
    return ids


def resolve_override_token(
    corp_id: int,
    scopes: list[str] | None = None,
):
    from esi.models import Token

    token_pk = _parse_corp_token_overrides().get(int(corp_id))
    if token_pk is None:
        return None
    qs = Token.objects.filter(pk=token_pk).require_valid()
    if scopes:
        qs = qs.require_scopes(list(scopes))
    return qs.first()


def _token_has_scopes(token, scopes: list[str]) -> bool:
    if not scopes:
        return True
    from esi.models import Token

    return (
        Token.objects.filter(pk=token.pk)
        .require_scopes(scopes)
        .require_valid()
        .exists()
    )


def _scope_field(token, scope: str, *, roles_scope: str) -> dict[str, Any]:
    from indy_hub.utils.eve import get_character_name

    if not _token_has_scopes(token, [scope, roles_scope]):
        return {
            "has_scope": False,
            "character_id": None,
            "character_name": None,
            "last_updated": None,
        }
    char_id = int(token.character_id)
    return {
        "has_scope": True,
        "character_id": char_id,
        "character_name": get_character_name(char_id) or token.character_name,
        "last_updated": getattr(token, "created", None),
    }


def _authorization_summary(setting) -> dict[str, Any]:
    if not setting:
        return {
            "restricted": False,
            "characters": [],
            "authorized_count": 0,
            "has_authorized": False,
        }
    from indy_hub.utils.eve import get_character_name

    characters = [
        {"id": char_id, "name": get_character_name(char_id)}
        for char_id in setting.authorized_character_ids
    ]
    return {
        "restricted": True,
        "characters": characters,
        "authorized_count": len(characters),
        "has_authorized": bool(characters),
    }


def build_override_corp_status_entry(
    user,
    corp_id: int,
    token,
    *,
    setting,
) -> dict[str, Any]:
    from indy_hub.tasks.industry import (
        CORP_ASSETS_SCOPE,
        CORP_BLUEPRINT_SCOPE,
        CORP_BLUEPRINT_SCOPE_SET,
        CORP_JOBS_SCOPE,
        CORP_JOBS_SCOPE_SET,
        CORP_ROLES_SCOPE,
        MATERIAL_EXCHANGE_SCOPE_SET,
    )
    from indy_hub.utils.eve import get_corporation_name

    corp_name = get_corporation_name(corp_id) or str(corp_id)
    me_ok = _token_has_scopes(token, list(MATERIAL_EXCHANGE_SCOPE_SET))

    entry = {
        "corporation_id": corp_id,
        "corporation_name": corp_name,
        "blueprint": _scope_field(token, CORP_BLUEPRINT_SCOPE, roles_scope=CORP_ROLES_SCOPE),
        "jobs": _scope_field(token, CORP_JOBS_SCOPE, roles_scope=CORP_ROLES_SCOPE),
        "assets": _scope_field(token, CORP_ASSETS_SCOPE, roles_scope=CORP_ROLES_SCOPE),
        "material_exchange": (
            {
                "has_scope": True,
                "character_id": int(token.character_id),
                "character_name": token.character_name,
                "last_updated": getattr(token, "created", None),
            }
            if me_ok
            else {
                "has_scope": False,
                "character_id": None,
                "character_name": None,
                "last_updated": None,
            }
        ),
        "authorization": _authorization_summary(setting),
        "has_director_role": True,
        "roles_unavailable": False,
        "available_scopes": [],
    }

    present: set[str] = set()
    for scope in (
        *CORP_BLUEPRINT_SCOPE_SET,
        *CORP_JOBS_SCOPE_SET,
        *MATERIAL_EXCHANGE_SCOPE_SET,
    ):
        if _token_has_scopes(token, [scope]):
            present.add(scope)
    entry["available_scopes"] = sorted(present)
    return entry


def merge_override_corporation_scope_status(
    user,
    corp_status: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure override corps appear on /indy_hub/esi/ using the pinned token."""
    if not user.has_perm("indy_hub.can_manage_corp_bp_requests"):
        return corp_status

    from allianceauth.eveonline.models import EveCorporationInfo
    from indy_hub.models import CorporationSharingSetting, CharacterSettings

    overrides = _parse_corp_token_overrides()
    if not overrides:
        return corp_status

    by_corp = {int(entry["corporation_id"]): entry for entry in corp_status}

    for corp_id, token_pk in overrides.items():
        token = resolve_override_token(corp_id, scopes=None)
        if not token:
            logger.warning(
                "indy_hub override: token %s unavailable for corp %s",
                token_pk,
                corp_id,
            )
            continue

        try:
            corporation = EveCorporationInfo.objects.get(corporation_id=corp_id)
        except EveCorporationInfo.DoesNotExist:
            corporation = EveCorporationInfo.objects.create_corporation(corp_id)

        corp_name = corporation.corporation_name or str(corp_id)
        setting, _ = CorporationSharingSetting.objects.get_or_create(
            user=user,
            corporation_id=corp_id,
            defaults={
                "corporation_name": corp_name,
                "share_scope": CharacterSettings.SCOPE_NONE,
                "allow_copy_requests": False,
            },
        )

        override_entry = build_override_corp_status_entry(
            user, corp_id, token, setting=setting
        )
        existing = by_corp.get(corp_id)
        if existing:
            for key in ("blueprint", "jobs", "assets", "material_exchange"):
                if override_entry[key].get("has_scope"):
                    existing[key] = override_entry[key]
            existing["has_director_role"] = True
            existing["roles_unavailable"] = False
            existing["available_scopes"] = sorted(
                set(existing.get("available_scopes") or [])
                | set(override_entry.get("available_scopes") or [])
            )
        else:
            by_corp[corp_id] = override_entry

    return sorted(by_corp.values(), key=lambda item: (item.get("corporation_name") or ""))


def merge_override_managed_corporation_ids(user, managed_ids: set[int]) -> set[int]:
    """Corp managers can sync/view override corps even without a main on that corp."""
    if not getattr(user, "is_authenticated", False):
        return managed_ids
    if not user.has_perm("indy_hub.can_manage_corp_bp_requests"):
        return managed_ids
    return managed_ids | {int(corp_id) for corp_id in _parse_corp_token_overrides()}


def user_has_required_scopes_via_override(user, scopes: list[str]) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if not user.has_perm("indy_hub.can_manage_corp_bp_requests"):
        return False
    for corp_id in _parse_corp_token_overrides():
        if resolve_override_token(corp_id, scopes=scopes):
            return True
    return False


def user_active_via_corp_override(user) -> bool:
    """Corp managers with a pinned corp token can sync without personal online scope."""
    try:
        from indy_hub.tasks.industry import CORP_BLUEPRINT_SCOPE_SET
    except Exception:
        return False
    return user_has_required_scopes_via_override(user, list(CORP_BLUEPRINT_SCOPE_SET))


def patch_indy_hub_corp_tokens() -> None:
    overrides = _parse_corp_token_overrides()
    if not overrides:
        return

    try:
        import indy_hub.tasks.industry as industry_tasks
        import indy_hub.views.industry as industry_views
        import indy_hub.views.user as user_views
        import indy_hub.services.corporation_blueprint_visibility as corp_visibility
    except Exception:
        logger.exception("indy_hub_corp_token: import failed")
        return

    _orig_scope_status = user_views._collect_corporation_scope_status
    _orig_corp_contexts = industry_tasks._collect_corporation_contexts
    _orig_get_roles = industry_tasks.get_character_corporation_roles
    _orig_required_roles = industry_tasks.REQUIRED_CORPORATION_ROLES
    _orig_has_scopes = industry_views._has_required_scopes
    _orig_managed_corps = corp_visibility.get_managed_corporation_ids
    _orig_is_user_active = industry_tasks._is_user_active
    _orig_request_manual_refresh = industry_tasks.request_manual_refresh

    industry_tasks.REQUIRED_CORPORATION_ROLES = _orig_required_roles | _EXTRA_CORP_ROLES

    def is_user_active(user, *, now=None):
        if _orig_is_user_active(user, now=now):
            return True
        return user_active_via_corp_override(user)

    def request_manual_refresh(
        kind: str,
        user_id: int,
        *,
        priority=None,
        scope: str | None = None,
        check_active: bool = True,
    ):
        normalized_scope = (scope or "").strip().lower()
        from django.contrib.auth.models import User

        if (
            check_active
            and normalized_scope == "corporation"
            and user_active_via_corp_override(
                User.objects.filter(id=user_id).first()
            )
        ):
            check_active = False
        return _orig_request_manual_refresh(
            kind,
            user_id,
            priority=priority,
            scope=scope,
            check_active=check_active,
        )

    def get_managed_corporation_ids(user):
        return merge_override_managed_corporation_ids(
            user, _orig_managed_corps(user)
        )

    def has_required_scopes(user, scopes: list[str]):
        if _orig_has_scopes(user, scopes):
            return True
        return user_has_required_scopes_via_override(user, scopes)

    corp_visibility.get_managed_corporation_ids = get_managed_corporation_ids
    industry_views._has_required_scopes = has_required_scopes
    industry_tasks._is_user_active = is_user_active
    industry_tasks.request_manual_refresh = request_manual_refresh

    def collect_corporation_scope_status(user, *args, **kwargs):
        result = _orig_scope_status(user, *args, **kwargs)
        if isinstance(result, tuple):
            corp_status, warnings = result
            corp_status = merge_override_corporation_scope_status(user, corp_status)
            return corp_status, warnings
        return merge_override_corporation_scope_status(user, result)

    def collect_corporation_contexts(user, required_scopes: list[str]):
        contexts = _orig_corp_contexts(user, required_scopes)
        for corp_id in overrides:
            if corp_id in contexts:
                continue
            token = resolve_override_token(corp_id, scopes=required_scopes or None)
            if not token:
                continue
            from indy_hub.utils.eve import get_character_name, get_corporation_name

            contexts[corp_id] = {
                "character_id": int(token.character_id),
                "character_name": get_character_name(token.character_id)
                or token.character_name,
                "corporation_name": get_corporation_name(corp_id) or str(corp_id),
            }
        return contexts

    def get_character_corporation_roles(character_id: int) -> set[str]:
        if int(character_id) in override_character_ids():
            try:
                roles = _orig_get_roles(character_id)
            except Exception:
                roles = set()
            return set(roles) | set(_EXTRA_CORP_ROLES)
        return _orig_get_roles(character_id)

    user_views._collect_corporation_scope_status = collect_corporation_scope_status
    industry_tasks._collect_corporation_contexts = collect_corporation_contexts
    industry_tasks.get_character_corporation_roles = get_character_corporation_roles

    logger.info(
        "indy_hub_corp_token: overrides active for corps %s "
        "(ESI hub, corporation-bp sync, CorpTools structures use token env)",
        list(overrides.keys()),
    )
