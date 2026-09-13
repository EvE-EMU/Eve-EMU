"""Read-only view of the signed-in user's Industrial PI colony snapshots —
the same server-synced data `emu_pi`'s own Celery task
(`emu_pi.sync_all_users`, real AA/django-esi tokens, not a per-desktop-
client ESI call) already keeps in `emu_pi.models.PiPlanetState`.

Read directly via ORM, gated on "does this row belong to the requesting
user" — no separate permission needed, the same way a user can always see
their own wallet — rather than going through `emu_pi.api`'s own
`freight_bridge`-session-gated views (unreachable from `penguin_bridge`'s
own separate session; see `docs/INDUSTRY_COMMAND.md`'s auth-boundary
section, and `penguin_bridge/projects.py` for the same shortcut applied to
Indy Hub).

This exists to fix M10 (EVE-Penguin `OUTSTANDING.md`): `pi_plugin.rs`
polling ESI live, once per open desktop client, was what was actually
driving PI into ESI's rate limit — N clients each polling the same
colonies independently. Reading the already-server-synced snapshot instead
means one shared poll total, on `emu_pi`'s own schedule
(`EMU_PI_SYNC_MINUTES`, set to daily per the user's direction for this
item), regardless of how many desktop clients have the PI screen open.

GET /penguin/pi -> every non-archived `PiPlanetState` row across every
                   character on this account.
"""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")


def _planet_payload(p) -> dict:
    return {
        "character_id": p.character_id,
        "character_name": p.character_name,
        "planet_id": p.planet_id,
        "solar_system_id": p.solar_system_id,
        "system_name": p.system_name,
        "planet_type": p.planet_type,
        "upgrade_level": p.upgrade_level,
        "status": p.status,
        "num_pins": p.num_pins,
        "active_extractors": p.active_extractors,
        "expired_extractors": p.expired_extractors,
        "factories_ok": p.factories_ok,
        "factories_starved": p.factories_starved,
        "storage_used": p.storage_used,
        "storage_capacity": p.storage_capacity,
        "storage_fill_pct": p.storage_fill_pct,
        "next_expiry_at": p.next_expiry_at.isoformat() if p.next_expiry_at else None,
        "hours_to_expiry": p.hours_to_expiry,
        "throughput_units_per_day": p.throughput_units_per_day,
        "attention_reasons": p.attention_reasons or [],
        "pins": p.pins or [],
        "synced_at": p.synced_at.isoformat(),
    }


@require_GET
def pi_colonies(request):
    user, _ = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)
    try:
        from emu_pi.models import PiPlanetState
    except Exception:
        logger.warning("penguin pi: emu_pi app unavailable", exc_info=True)
        return JsonResponse({"error": "pi_unavailable"}, status=502)
    rows = (
        PiPlanetState.objects.filter(user=user, archived=False)
        .order_by("system_name", "planet_type")
    )
    return JsonResponse({"planets": [_planet_payload(p) for p in rows]})
