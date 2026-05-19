"""Resolve fleet MOTD / labels when the member token cannot read fleet details."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.apps import apps
from django.utils import timezone

from standing_fleet_tracker.services import esi as esi_api

logger = logging.getLogger(__name__)


def _labels_from_afat(fleet_id: int) -> list[str]:
    """AFAT fleet name for this ESI fleet ID (any creator — FC identity does not matter)."""
    if not apps.is_installed("afat"):
        return []
    from afat.models import FatLink

    labels: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        text = (label or "").strip()
        if text and text not in seen:
            seen.add(text)
            labels.append(text)

    since = timezone.now() - timedelta(hours=12)
    for row in FatLink.objects.filter(esi_fleet_id=fleet_id, created__gte=since).order_by(
        "-created"
    )[:5]:
        add(row.fleet)

    return labels


def resolve_fleet_metadata(
    fleet_id: int,
    token,
    *,
    fleet_boss_id: int | None = None,
) -> dict:
    """
    Best-effort fleet metadata for standing detection.

    Regular members often receive 404 on GET /fleets/{id}/; we may use the
    current fleet boss token only to read MOTD/members — not for standing classification.
  """
    motd = ""
    commander_id = fleet_boss_id
    is_registered: bool | None = None
    labels: list[str] = []

    def apply_fleet_info(finfo: dict) -> None:
        nonlocal motd, commander_id, is_registered
        motd = str(finfo.get("motd") or "")
        commander_id = finfo.get("fleet_commander_id") or fleet_boss_id
        if "is_registered" in finfo:
            is_registered = bool(finfo.get("is_registered"))

    tokens_to_try = [token]
    if fleet_boss_id:
        boss_token = esi_api.token_for_character(fleet_boss_id)
        if boss_token and getattr(boss_token, "pk", None) != getattr(token, "pk", None):
            tokens_to_try.append(boss_token)

    for read_token in tokens_to_try:
        status, finfo = esi_api.get_fleet_info(fleet_id, read_token)
        if status == 200 and isinstance(finfo, dict):
            apply_fleet_info(finfo)
            if motd.strip():
                break
        elif status not in (404, 0):
            logger.debug(
                "SFT fleet %s token read status %s (char %s)",
                fleet_id,
                status,
                getattr(read_token, "character_id", None),
            )

    labels.extend(_labels_from_afat(fleet_id))
    label_snapshot = labels[0] if labels else ""

    return {
        "motd": motd,
        "fleet_commander_id": commander_id,
        "fleet_boss_id": fleet_boss_id,
        "labels": labels,
        "label_snapshot": label_snapshot,
        "is_registered": is_registered,
    }
