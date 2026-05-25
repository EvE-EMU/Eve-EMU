"""Charlink: request ``esi-corporations.read_projects.v1`` for corp project Discord qty/ISK."""

from __future__ import annotations

from charlink.app_imports.utils import AppImport, LoginImport
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter

from corp_project_discord import CORP_PROJECT_DISCORD_SCOPE
from esi.models import Token


def required_corp_project_scopes() -> list[str]:
    return [CORP_PROJECT_DISCORD_SCOPE]


def _token_has_corp_project_scope(token: Token | None) -> bool:
    if token is None:
        return False
    return token.scopes.filter(name=CORP_PROJECT_DISCORD_SCOPE).exists()


def _add_character_corp_projects(request, token) -> None:
    """Scope-only import; corp project Discord reads ESI at notify time."""
    EveCharacter.objects.get_character_by_id(token.character_id)


def _is_character_added_corp_projects(character: EveCharacter) -> bool:
    token = Token.objects.filter(character_id=character.character_id).first()
    return _token_has_corp_project_scope(token)


def _users_with_perms_corp_projects():
    return User.objects.filter(is_active=True)


app_import = AppImport(
    "industry_suite",
    [
        LoginImport(
            app_label="industry_suite",
            unique_id="corp_project_discord",
            field_label=_("Corp project Discord (qty / ISK)"),
            add_character=_add_character_corp_projects,
            scopes=required_corp_project_scopes(),
            check_permissions=lambda user: user.is_authenticated,
            is_character_added=_is_character_added_corp_projects,
            is_character_added_annotation=Exists(
                Token.objects.filter(
                    character_id=OuterRef("character_id"),
                    scopes__name=CORP_PROJECT_DISCORD_SCOPE,
                )
            ),
            get_users_with_perms=_users_with_perms_corp_projects,
            default_initial_selection=True,
        ),
    ],
)
