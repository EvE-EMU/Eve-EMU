"""Read-only view of the SLYCE krab fleet schedule — the same board
`/krab` (core-web) shows, without opening a browser.

This is J4 from EVE-Penguin's `OUTSTANDING.md`: several eve-emu.com web
tools are shared status boards a pilot would want to glance at without
switching windows. The krab schedule is the first one built — its
member-facing view is a plain read-only calendar (signing up for a slot,
approving signups, and Discord/whitelist settings are all separate,
FC/admin-only actions this endpoint does not expose), which needed
nothing more than the same bridge-session -> Django user resolution the
PI and Indy Hub bridges (`pi.py`, `projects.py`) already use.

Reuses `krab_schedule`'s own `can_view()` gate (SLYCE alliance members,
plus any FC/titan whitelist entry or director group, same rule the web
board itself enforces) and its own `_serialize_block()` payload shape
directly, rather than re-deriving "what's visible on a non-admin board"
here — that function already encodes it (approved signups only, no
pending-signup list) and reusing it means the two boards can't drift
apart. Same "reach the app's own helper directly, gate on its own rule"
shortcut as the other single-purpose bridge modules; see
`docs/INDUSTRY_COMMAND.md`'s auth-boundary section for why this can't
just go through `krab_schedule`'s own views (those trust a separate
`X-Freight-Session` header `penguin_bridge` doesn't mint).

GET /penguin/krab -> published, non-cancelled blocks from now through the
                     next 30 days. `can_view: false` (not an error) means
                     the account isn't a SLYCE member / on the FC
                     whitelist — same as the web board redirecting a
                     non-member back to the dashboard.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")

WINDOW_DAYS = 30


@require_GET
def krab_schedule_view(request):
    user, _ = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)
    try:
        from krab_schedule.access import can_view
        from krab_schedule.models import KrabBlock
        from krab_schedule.public_api import _serialize_block
    except Exception:
        logger.warning("penguin krab: krab_schedule app unavailable", exc_info=True)
        return JsonResponse({"error": "krab_unavailable"}, status=502)

    if not can_view(user):
        return JsonResponse({"ok": True, "can_view": False, "blocks": []})

    now = timezone.now()
    end = now + timedelta(days=WINDOW_DAYS)
    blocks = (
        KrabBlock.objects.filter(
            starts_at__lte=end, ends_at__gte=now, cancelled=False, published=True
        )
        .prefetch_related("signups")
        .order_by("starts_at")
    )
    return JsonResponse(
        {
            "ok": True,
            "can_view": True,
            "blocks": [_serialize_block(b, user, admin_board=False) for b in blocks],
        }
    )
