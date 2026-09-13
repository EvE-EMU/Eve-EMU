"""Classify EVE Online entity IDs for interaction audit."""

from __future__ import annotations


def classify_entity_id(entity_id: int) -> str:
    """Best-effort entity kind without an extra ESI round-trip."""
    eid = int(entity_id)
    if eid <= 0:
        return "unknown"
    if eid >= 1_000_000_000_000:
        return "structure"
    if eid >= 900_000_000:
        return "character"
    if 30_000_000 <= eid <= 50_000_000:
        return "character"
    if 98_000_000 <= eid <= 99_999_999:
        return "corporation"
    if 99_000_000 <= eid <= 99_999_999:
        return "alliance"
    if 1 <= eid < 10_000_000:
        return "npc"
    return "entity"
