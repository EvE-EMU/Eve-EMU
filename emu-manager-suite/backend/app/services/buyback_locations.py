"""Buyback delivery locations and fee tiers."""

from __future__ import annotations

from app.config import settings

# Fee % applied to Janice basis after line pricing (location + haul distance).
BUYBACK_LOCATIONS: list[dict] = [
    {
        "id": "holy_procurer",
        "label": "3T7-M8 - Citadel of the Holy Procurer (Alpha Republic - Transcenders of Space and Time)",
        "structure_id": settings.wompstar_structure_id,
        "fee_pct": 92.0,
        "market": "jita",
    },
]


def list_buyback_locations() -> list[dict]:
    return [
        {
            "id": loc["id"],
            "label": loc["label"],
            "fee_pct": loc["fee_pct"],
            "market": loc.get("market", "jita"),
        }
        for loc in BUYBACK_LOCATIONS
    ]


def resolve_buyback_location(location_id: str | None) -> dict:
    if not location_id:
        return BUYBACK_LOCATIONS[0]
    key = location_id.strip().lower()
    for loc in BUYBACK_LOCATIONS:
        if loc["id"] == key:
            return loc
    return BUYBACK_LOCATIONS[0]
