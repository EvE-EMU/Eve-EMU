"""CorpTools: enable mail module on workers and tolerate mailing-list sender IDs."""

from __future__ import annotations

import logging
import os
import types

logger = logging.getLogger(__name__)


def _mail_module_enabled() -> bool:
    from django.conf import settings

    if hasattr(settings, "CT_CHAR_MAIL_MODULE"):
        return bool(settings.CT_CHAR_MAIL_MODULE)
    return os.environ.get("AA_CORPTOOLS_MAIL_MODULE", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def apply_corptools_mail_module() -> None:
    """Sync CT_CHAR_MAIL_MODULE into corptools.app_settings (import-time constant)."""
    from django.apps import apps

    if not apps.is_installed("corptools"):
        return

    import corptools.app_settings as cas

    enabled = _mail_module_enabled()
    if cas.CT_CHAR_MAIL_MODULE != enabled:
        cas.CT_CHAR_MAIL_MODULE = enabled
        logger.info(
            "corptools_mail_patch: CT_CHAR_MAIL_MODULE=%s", enabled
        )


def patch_corptools_mail_eve_names() -> None:
    """Skip invalid universe IDs (e.g. mailing lists) during EveName bulk resolve."""
    from django.apps import apps

    if not apps.is_installed("corptools"):
        return

    from corptools.models import EveName
    from esi.exceptions import HTTPClientError

    _orig_bulk = EveName.objects.create_bulk_from_esi

    def create_bulk_from_esi(self, eve_ids):
        filtered = [i for i in eve_ids if i is not None]
        if not filtered:
            return True
        chunk_size = 990
        for i in range(0, len(filtered), chunk_size):
            chunk = filtered[i : i + chunk_size]
            try:
                _orig_bulk(chunk)
            except HTTPClientError:
                for eve_id in chunk:
                    try:
                        EveName.objects.get_or_create_from_esi(eve_id)
                    except HTTPClientError:
                        logger.debug(
                            "corptools_mail_patch: skip unresolved eve_id %s",
                            eve_id,
                        )
                    except Exception:
                        logger.debug(
                            "corptools_mail_patch: skip eve_id %s",
                            eve_id,
                            exc_info=True,
                        )
        return True

    EveName.objects.create_bulk_from_esi = types.MethodType(
        create_bulk_from_esi, EveName.objects
    )
    logger.debug("corptools_mail_patch: patched EveName.create_bulk_from_esi")


def patch_update_character_mail_audit() -> None:
    """Create CharacterAudit when only mail scope is present (partial Charlink)."""
    from django.apps import apps

    if not apps.is_installed("corptools"):
        return

    import corptools.app_settings as cas
    from allianceauth.eveonline.models import EveCharacter
    from corptools.models.audits import CharacterAudit
    from corptools.tasks import character as char_tasks
    from esi.errors import TokenExpiredError
    from esi.models import Token

    task = char_tasks.update_character
    _orig_run = task.run

    def _ensure_audit(char_id):
        if CharacterAudit.objects.filter(character__character_id=char_id).exists():
            return
        token = Token.get_token(char_id, cas.get_character_scopes())
        if token is None and cas.CT_CHAR_MAIL_MODULE:
            token = Token.get_token(char_id, ["esi-mail.read_mail.v1"])
        if token is None:
            token = Token.objects.filter(character_id=char_id).first()
        if not token:
            return
        try:
            if token.valid_access_token():
                CharacterAudit.objects.update_or_create(
                    character=EveCharacter.objects.get_character_by_id(
                        token.character_id
                    )
                )
        except TokenExpiredError:
            return

    def run(self, char_id, force_refresh=False):
        _ensure_audit(char_id)
        return _orig_run(self, char_id, force_refresh=force_refresh)

    task.run = run
    logger.debug("corptools_mail_patch: patched update_character audit bootstrap")


def patch_corptools_mail() -> None:
    apply_corptools_mail_module()
    patch_corptools_mail_eve_names()
    patch_update_character_mail_audit()
