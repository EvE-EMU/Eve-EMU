"""EMU Moons view access (roles beyond static Django permissions)."""

from __future__ import annotations

import os
from datetime import date

from django.contrib.auth import get_user_model

User = get_user_model()

REXAN_CHARACTER_NAMES = frozenset(
    n.strip().lower()
    for n in os.environ.get("AA_EMU_MOONS_REXAN_CHARACTERS", "Rexan Darkstar").split(",")
    if n.strip()
)
ALLIANCE_USERNAMES = frozenset(
    n.strip().lower()
    for n in os.environ.get("AA_EMU_MOONS_ALLIANCE_USERS", "sevey").split(",")
    if n.strip()
)
DIRECTOR_ROLE_NAMES = frozenset(
    n.strip()
    for n in os.environ.get(
        "AA_EMU_MOONS_DIRECTOR_ROLES",
        "Director,Config_Starbase_Equipment",
    ).split(",")
    if n.strip()
)


def tax_effective_date() -> date:
    from emu_moons.models import EmuMoonsSettings

    return EmuMoonsSettings.load().tax_effective_date


def invoice_in_tax_period(inv) -> bool:
    """True when invoice counts for tax / naughty / statements."""
    cutoff = tax_effective_date()
    issued = inv.issued_at.date() if inv.issued_at else inv.due_at
    return issued >= cutoff and inv.due_at >= cutoff


def user_corp_id(user) -> int | None:
    try:
        main = user.profile.main_character
        if main:
            return int(main.corporation_id)
    except Exception:
        pass
    return None


def user_is_sevey(user) -> bool:
    return bool(user and user.username.lower() in ALLIANCE_USERNAMES)


def user_is_rexan(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    try:
        from allianceauth.eveonline.models import EveCharacter

        for ec in EveCharacter.objects.filter(character_ownership__user=user):
            if ec.character_name.lower() in REXAN_CHARACTER_NAMES:
                return True
    except Exception:
        pass
    return False


def user_has_director_role(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.has_perm("emu_moons.emu_moons_admin"):
        return True
    try:
        from allianceauth.eveonline.models import EveCharacter
        from buybackprogram.providers import esi
        from buybackprogram_esi_compat import esi_row_to_dict
        from esi.models import Token
    except ImportError:
        return False

    scope = "esi-characters.read_corporation_roles.v1"
    for ec in EveCharacter.objects.filter(character_ownership__user=user).distinct():
        token = (
            Token.objects.filter(character_id=ec.character_id)
            .require_scopes(scope)
            .order_by("-created")
            .first()
        )
        if not token:
            continue
        try:
            raw = esi.client.Character.GetCharactersCharacterIdRoles(
                character_id=ec.character_id,
                token=token,
            ).result(use_etag=False)
            payload = esi_row_to_dict(raw) if not isinstance(raw, dict) else raw
            roles = payload.get("roles") or []
            for role in roles:
                if role in DIRECTOR_ROLE_NAMES:
                    return True
        except Exception:
            continue
    return False


def can_view_naughty_list(_request) -> bool:
    return True


def can_view_own_statement(user) -> bool:
    return bool(user and user.is_authenticated)


def can_view_corp_dashboard(user) -> bool:
    return bool(user and user.is_authenticated and user_corp_id(user))


def can_view_alliance_dashboard(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return (
        user_is_sevey(user)
        or user_is_rexan(user)
        or user_has_director_role(user)
        or user.has_perm("emu_moons.emu_moons_view_alliance")
    )


def can_view_all_accounts(user) -> bool:
    return can_view_alliance_dashboard(user)


def can_view_user_statement(viewer, target_user) -> bool:
    if not viewer or not viewer.is_authenticated:
        return False
    if target_user.pk == viewer.pk:
        return True
    if can_view_alliance_dashboard(viewer):
        return True
    if can_view_corp_dashboard(viewer):
        corp = user_corp_id(viewer)
        if corp:
            from emu_moons.models import EmuInvoice

            return EmuInvoice.objects.filter(
                user=target_user, corporation_id=corp
            ).exists()
    return viewer.has_perm("emu_moons.emu_moons_view_corp") or viewer.has_perm(
        "emu_moons.emu_moons_view_alliance"
    )


def can_view_invoice(viewer, inv) -> bool:
    if not invoice_in_tax_period(inv):
        return viewer.is_superuser if viewer else False
    if inv.on_naughty_list:
        return True
    if not viewer or not viewer.is_authenticated:
        return inv.on_naughty_list
    if can_view_alliance_dashboard(viewer):
        return True
    if can_view_corp_dashboard(viewer) and inv.corporation_id == user_corp_id(viewer):
        return True
    if inv.user_id == viewer.pk:
        return True
    return False


def nav_context(request) -> dict:
    user = getattr(request, "user", None)
    authed = bool(user and user.is_authenticated)
    return {
        "emu_moons_can_naughty": can_view_naughty_list(request),
        "emu_moons_can_statement": can_view_own_statement(user) if authed else False,
        "emu_moons_can_all_accounts": can_view_all_accounts(user) if authed else False,
        "emu_moons_can_alliance": can_view_alliance_dashboard(user) if authed else False,
        "emu_moons_can_corp": can_view_corp_dashboard(user) if authed else False,
        "emu_moons_tax_effective": tax_effective_date(),
    }
