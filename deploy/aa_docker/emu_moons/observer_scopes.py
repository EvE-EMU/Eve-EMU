"""ESI scopes for Guns-R-Us corp mining observers (EMU Moons invoicing)."""

from __future__ import annotations

EMU_MOONS_OBSERVER_SCOPES: tuple[str, ...] = (
    "esi-industry.read_corporation_mining.v1",
    "esi-universe.read_structures.v1",
    "esi-wallet.read_corporation_wallets.v1",
)

_SCOPE_HELP: dict[str, str] = {
    "esi-industry.read_corporation_mining.v1": (
        "Read corporation mining observers and structure mining logs (EMU Moons tax)"
    ),
    "esi-universe.read_structures.v1": (
        "Resolve refinery structure names for mining observers"
    ),
    "esi-wallet.read_corporation_wallets.v1": (
        "Corporation wallet journal for miningtaxes payment matching"
    ),
}


def required_observer_scopes() -> list[str]:
    return list(EMU_MOONS_OBSERVER_SCOPES)


def ensure_emu_moons_observer_scopes_in_db() -> None:
    """Charlink only offers scopes present in django-esi ``Scope`` (sync from CCP list)."""
    try:
        from esi.models import Scope
    except ImportError:
        return
    for name in EMU_MOONS_OBSERVER_SCOPES:
        Scope.objects.get_or_create(
            name=name,
            defaults={"help_text": _SCOPE_HELP.get(name, "EMU Moons corp mining observer")},
        )
