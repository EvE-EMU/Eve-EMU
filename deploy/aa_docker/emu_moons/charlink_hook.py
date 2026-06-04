"""Charlink: request corp mining observer ESI scopes for EMU Moons (Guns-R-Us / Rexan)."""

from __future__ import annotations

from charlink.app_imports.utils import AppImport, LoginImport
from django.contrib.auth.models import Permission, User
from django.db.models import Exists, OuterRef, Q
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter
from esi.models import Token

from emu_moons.access import user_is_rexan
from emu_moons.observer_scopes import required_observer_scopes


def _token_has_observer_scopes(token: Token | None) -> bool:
    if token is None:
        return False
    names = set(token.scopes.values_list("name", flat=True))
    return all(s in names for s in required_observer_scopes())


def _add_character_emu_moons_observer(request, token) -> None:
    """Register character in miningtaxes; queue observer sync (must not run in HTTP)."""
    from miningtaxes.models import AdminCharacter

    eve_char = EveCharacter.objects.get_character_by_id(token.character_id)
    admin, _ = AdminCharacter.objects.update_or_create(eve_character=eve_char)
    if not _token_has_observer_scopes(token):
        return
    try:
        from miningtaxes import tasks as mt_tasks

        mt_tasks.update_admin_character.delay(character_pk=admin.pk, force_update=True)
    except Exception:
        try:
            from emu_moons.tasks import sync_observer_admin

            sync_observer_admin.delay(token.character_id)
        except Exception:
            pass


def _is_character_added_emu_moons_observer(character: EveCharacter) -> bool:
    token = Token.objects.filter(character_id=character.character_id).order_by("-created").first()
    return _token_has_observer_scopes(token)


def _can_use_observer_charlink(user: User) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.has_perm("emu_moons.emu_moons_admin"):
        return True
    return user_is_rexan(user)


def _users_with_perms_emu_moons_observer():
    try:
        permission = Permission.objects.get(
            content_type__app_label="emu_moons",
            codename="emu_moons_admin",
        )
    except Permission.DoesNotExist:
        return User.objects.filter(is_superuser=True)

    users_qs = (
        permission.user_set.all()
        | User.objects.filter(
            groups__in=list(permission.group_set.values_list("pk", flat=True))
        )
        | User.objects.select_related("profile").filter(
            profile__state__in=list(permission.state_set.values_list("pk", flat=True))
        )
        | User.objects.filter(is_superuser=True)
    )
    return users_qs.distinct()


def _observer_scope_filter_q():
    q = Q()
    for scope in required_observer_scopes():
        q &= Q(scopes__name=scope)
    return q


app_import = AppImport(
    "emu_moons",
    [
        LoginImport(
            app_label="emu_moons",
            unique_id="corpminingobserver",
            field_label=_("EMU Moons — Guns corp mining observer"),
            add_character=_add_character_emu_moons_observer,
            scopes=required_observer_scopes(),
            check_permissions=_can_use_observer_charlink,
            is_character_added=_is_character_added_emu_moons_observer,
            is_character_added_annotation=Exists(
                Token.objects.filter(
                    character_id=OuterRef("character_id"),
                ).filter(_observer_scope_filter_q())
            ),
            get_users_with_perms=_users_with_perms_emu_moons_observer,
            default_initial_selection=True,
        ),
    ],
)
