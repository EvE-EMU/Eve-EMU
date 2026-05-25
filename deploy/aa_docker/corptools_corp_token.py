"""Pin CorpTools / Market Manager corp ESI tasks to specific django-esi token IDs.

On the private EVE server, corporation role names from ESI often do not include
``Director`` even for characters that can call corp structure endpoints. Set
``AA_FALSE_GODS_CORP_TOKEN_ID=58`` (Lamaashtu) or ``AA_CORP_TOKEN_OVERRIDES``
to bypass role checks and use the designated token when scopes match.
"""

from __future__ import annotations

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)

FALSE_GODS_CORP_ID = 98799892


def _parse_corp_token_overrides() -> dict[int, int]:
    raw = os.environ.get("AA_CORP_TOKEN_OVERRIDES", "").strip()
    if not raw:
        fg_token = os.environ.get("AA_FALSE_GODS_CORP_TOKEN_ID", "").strip()
        if fg_token.isdigit():
            raw = f"{FALSE_GODS_CORP_ID}:{fg_token}"

    overrides: dict[int, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        corp_s, tok_s = part.split(":", 1)
        if corp_s.isdigit() and tok_s.isdigit():
            overrides[int(corp_s)] = int(tok_s)
    return overrides


def _resolve_override_token(corp_id: int, scopes: list, overrides: dict[int, int]):
    from esi.models import Token

    token_pk = overrides.get(int(corp_id))
    if token_pk is None:
        return None

    req_scopes = list(scopes)
    if "esi-characters.read_corporation_roles.v1" not in req_scopes:
        req_scopes.append("esi-characters.read_corporation_roles.v1")

    token = Token.objects.filter(pk=token_pk).require_scopes(req_scopes).first()
    if token:
        logger.debug(
            "corp token override corp=%s token_pk=%s char=%s",
            corp_id,
            token_pk,
            token.character_name,
        )
        return token

    logger.warning(
        "corp token override missing scopes corp=%s token_pk=%s scopes=%s",
        corp_id,
        token_pk,
        req_scopes,
    )
    return None


def _wrap_get_corp_token(orig: Callable, overrides: dict[int, int]):
    def get_corp_token(corp_id: int, scopes: list, req_roles):
        token = _resolve_override_token(corp_id, scopes, overrides)
        if token is not None:
            return token
        return orig(corp_id, scopes, req_roles)

    return get_corp_token


def _rebind_corp_token_imports(get_corp_token) -> None:
    """Task modules bind get_corp_token at import time; refresh those references."""
    modules = (
        "corptools.tasks.corporation.structures",
        "corptools.tasks.corporation.assets",
        "corptools.tasks.corporation.wallet",
        "corptools.tasks.corporation.contracts",
        "corptools.tasks.corporation.indy",
        "corptools.tasks.corporation.characters",
        "corptools.task_helpers.corp_helpers",
    )
    import sys

    for name in modules:
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "get_corp_token"):
            mod.get_corp_token = get_corp_token


def patch_corp_token_overrides() -> None:
    try:
        from django.apps import apps

        if not apps.ready:
            return
    except Exception:
        return

    overrides = _parse_corp_token_overrides()
    if not overrides:
        return

    try:
        from corptools.tasks.corporation import utils as corp_utils

        corp_utils.get_corp_token = _wrap_get_corp_token(corp_utils.get_corp_token, overrides)
        _rebind_corp_token_imports(corp_utils.get_corp_token)
    except Exception:
        logger.exception("corptools_corp_token: failed to patch corptools")

    try:
        import marketmanager.task_helpers as mm_helpers

        mm_helpers.get_corp_token = _wrap_get_corp_token(mm_helpers.get_corp_token, overrides)
    except Exception:
        logger.exception("corptools_corp_token: failed to patch marketmanager")

    logger.info("corptools_corp_token: overrides active %s", overrides)
