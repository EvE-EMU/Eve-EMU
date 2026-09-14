"""EVE-Penguin "Send screenshot" feedback intake — a manual, opt-in capture
of exactly one screen, triggered by a button in Settings, never automatic
or background (direct user request, 2026-09-14).

Stored straight in Postgres (`PenguinFeedbackScreenshot`, a plain bytea)
rather than the filesystem: aa-web/aa-worker/aa-beat have no persistent
volume — everything baked in at build time is ephemeral across a redeploy —
and these are small/infrequent enough that the DB is the simplest thing
that's actually durable here.

There is deliberately no read endpoint here — these are pulled directly
from the DB (or exported to files) by whoever's triaging feedback, the same
access model as a crash report; nothing about this is public. Rate-limited
server-side (one per 15s per user, same atomic `cache.add` pattern as the PI
force-sync button) so a client bug can't spam the DB, and a 10MB decoded-
image cap guards against anything absurd landing in a single request.

POST /penguin/feedback/screenshot  {image_b64, note, app_version} -> {"ok": true}
"""

from __future__ import annotations

import base64
import binascii
import json
import logging

from django.core.cache import cache
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from penguin_bridge.views import _session_user

logger = logging.getLogger("penguin_bridge")

MAX_IMAGE_BYTES = 10 * 1024 * 1024
RATE_LIMIT_SECONDS = 15


@csrf_exempt
@require_POST
def feedback_screenshot(request):
    user, _ = _session_user(request)
    if user is None:
        return JsonResponse({"error": "invalid_session"}, status=401)

    key = f"penguin_feedback_screenshot:{user.id}"
    if not cache.add(key, True, timeout=RATE_LIMIT_SECONDS):
        return JsonResponse({"error": "rate_limited"}, status=429)

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("bad json")

    b64 = str(payload.get("image_b64") or "")
    if not b64:
        return JsonResponse({"error": "missing_image"}, status=400)
    # base64 inflates ~4/3 — reject on the encoded length first so an
    # absurd upload never gets fully decoded into memory just to be
    # thrown away.
    if len(b64) > MAX_IMAGE_BYTES * 4 // 3 + 1024:
        return JsonResponse({"error": "image_too_large"}, status=413)
    try:
        image = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        return JsonResponse({"error": "bad_base64"}, status=400)
    if not image or len(image) > MAX_IMAGE_BYTES:
        return JsonResponse({"error": "image_too_large"}, status=413)

    from penguin_bridge.models import PenguinFeedbackScreenshot

    main_name = ""
    try:
        main_name = getattr(user.profile.main_character, "character_name", "") or ""
    except Exception:
        pass

    PenguinFeedbackScreenshot.objects.create(
        user_id=user.id,
        username=user.username,
        main_character_name=main_name,
        app_version=str(payload.get("app_version") or "")[:32],
        note=str(payload.get("note") or "")[:2000],
        image=image,
    )
    logger.info(
        "penguin feedback: screenshot from user %s (%s, %d bytes)",
        user.id,
        main_name or user.username,
        len(image),
    )
    return JsonResponse({"ok": True})
