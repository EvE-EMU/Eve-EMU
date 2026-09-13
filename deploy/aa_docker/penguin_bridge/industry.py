"""Read-only bridge into the alliance's real industry infrastructure, for the
desktop client's Industry Calculator:

- GET  /penguin/structures            Auth Indy Hub's registered structures
                                       (taxes, rigs, resolved ME/TE/job-cost
                                       bonuses, system cost indexes)
- GET  /penguin/freight/systems       valid SLYCE freight-mesh system names
- POST /penguin/freight/quote         a freight price estimate

Both wrap **already-correct, already-live** server-side logic
(`mfg_projects.services.craft.structures.list_auth_structures` and
`freight_bridge.services.pricing.calculate_quote`) rather than
reimplementing structure-bonus or freight-rate math a second time closer to
the client — those numbers come from a real Indy Hub structure registry and
the alliance's actual freight service, not a guess. Restricted to False
Gods members (or superusers) since this is that alliance's own industry
infrastructure, not something to expose to every eve-emu.com account.
"""

from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")


def _require_false_gods(request):
    """`(user, None)` on success, `(None, error_response)` on failure —
    same shape `_session_user` itself returns, so callers can `return err`
    directly."""
    user, _ = _session_user(request)
    if user is None:
        return None, JsonResponse({"error": "invalid_session"}, status=401)
    try:
        from mfg_projects.services.workbench import user_in_false_gods
    except Exception:
        logger.warning("penguin industry: mfg_projects.workbench unavailable", exc_info=True)
        return None, JsonResponse({"error": "industry_unavailable"}, status=502)
    if not (user_in_false_gods(user) or getattr(user, "is_superuser", False)):
        return None, JsonResponse({"error": "false_gods_required"}, status=403)
    return user, None


@require_GET
def structures(request):
    _user, err = _require_false_gods(request)
    if err:
        return err
    try:
        from mfg_projects.services.craft.structures import list_auth_structures
    except Exception:
        logger.exception("penguin industry: structures lookup failed")
        return JsonResponse({"error": "structures_unavailable"}, status=502)
    return JsonResponse(list_auth_structures(manufacturing_only=True))


@require_GET
def freight_systems(request):
    _user, err = _require_false_gods(request)
    if err:
        return err
    try:
        from freight_bridge.services.pricing import slyce_system_names
    except Exception:
        logger.exception("penguin industry: freight system list failed")
        return JsonResponse({"error": "freight_unavailable"}, status=502)
    names = sorted(slyce_system_names())
    return JsonResponse({"systems": names, "count": len(names)})


@csrf_exempt
@require_http_methods(["POST"])
def freight_quote(request):
    user, err = _require_false_gods(request)
    if err:
        return err
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "bad_json"}, status=400)

    start_system = str(body.get("start_system") or "").strip()
    end_system = str(body.get("end_system") or "").strip()
    try:
        volume = float(body.get("volume") or 0)
        collateral = float(body.get("collateral") or 0)
    except (TypeError, ValueError):
        return JsonResponse({"error": "bad_volume_or_collateral"}, status=400)
    if not start_system or not end_system:
        return JsonResponse({"error": "missing_systems"}, status=400)
    if volume <= 0:
        return JsonResponse({"error": "volume_must_be_positive"}, status=400)

    try:
        from freight_bridge.services.pricing import calculate_quote
    except Exception:
        logger.exception("penguin industry: freight quote failed")
        return JsonResponse({"error": "freight_unavailable"}, status=502)

    # audit=False, mint_token=False: this is a price *estimate* for the
    # calculator, not an actual contract booking — it shouldn't leave an
    # audit-log row or mint a real single-use discount code every time
    # someone tweaks a number in the Industry Calculator.
    try:
        quote = calculate_quote(
            start_system=start_system,
            end_system=end_system,
            volume=volume,
            collateral=collateral,
            auth_user_id=int(user.pk),
            has_sso=True,
            audit=False,
            mint_token=False,
        )
    except Exception:
        logger.exception("penguin industry: calculate_quote raised")
        return JsonResponse({"error": "freight_quote_failed"}, status=502)
    return JsonResponse(quote)
