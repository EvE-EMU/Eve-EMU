"""Charlink import: request standing-fleet ESI scopes when adding characters."""

from __future__ import annotations

from charlink.app_imports.utils import AppImport, LoginImport
from django.contrib.auth.models import Permission, User
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter

from standing_fleet_tracker.models import CharacterScore
from standing_fleet_tracker.services import esi as esi_api
from standing_fleet_tracker.services.polling import poll_character
from standing_fleet_tracker.services.scopes import missing_scopes_for_token, required_scopes


def _add_character_standing_fleet(request, token) -> None:
    character = EveCharacter.objects.get_character_by_id(token.character_id)
    CharacterScore.objects.get_or_create(character=character)
    poll_character(character, token)


def _is_character_added_standing_fleet(character: EveCharacter) -> bool:
    token = esi_api.token_for_character(character.character_id)
    return not missing_scopes_for_token(token)


def _users_with_perms_standing_fleet():
    permission = Permission.objects.get(
        content_type__app_label="standing_fleet_tracker",
        codename="basic_access",
    )
    return (
        permission.user_set.all()
        | User.objects.filter(
            groups__in=list(permission.group_set.values_list("pk", flat=True))
        )
        | User.objects.select_related("profile").filter(
            profile__state__in=list(permission.state_set.values_list("pk", flat=True))
        )
        | User.objects.filter(is_superuser=True)
    ).distinct()


app_import = AppImport(
    "standing_fleet_tracker",
    [
        LoginImport(
            app_label="standing_fleet_tracker",
            unique_id="fleettrack",
            field_label=_("Standing Fleet Tracker"),
            add_character=_add_character_standing_fleet,
            scopes=required_scopes(),
            check_permissions=lambda user: user.has_perm(
                "standing_fleet_tracker.basic_access"
            ),
            is_character_added=_is_character_added_standing_fleet,
            is_character_added_annotation=Exists(
                CharacterScore.objects.filter(
                    character_id=OuterRef("pk"),
                )
            ),
            get_users_with_perms=_users_with_perms_standing_fleet,
            default_initial_selection=True,
        ),
    ],
)
