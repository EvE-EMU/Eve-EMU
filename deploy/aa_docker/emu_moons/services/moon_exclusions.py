"""Moons / structures excluded from EMU Moons tax and member-mining import."""

from __future__ import annotations

import os
import re

# Corp moons that must not be taxed or synced into moonmining reports.
_DEFAULT_EXCLUDED_MOON_LABELS = (
    "RF-CN3 V - Moon 6",
    "RF-CN3 V - Moon 8",
    "9-HMO4 IV - Moon 6",
)

# Match "DS-…" structures whose name includes P7M5 (e.g. DS-LO3 … P7M5), not YW-SYT P7M5.
_STRUCTURE_EXCLUSION_RULES: tuple[tuple[str, ...], ...] = (
    ("DS-", "P7M5"),
)

_MOON_LABEL_RE = re.compile(
    r"^(.+?)\s*[-–]\s*(?:Moon\s*)?(\d+)\s*$",
    re.IGNORECASE,
)


def _normalize_label(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text.strip().upper())
    t = re.sub(r"\s*[-–]\s*", " - ", t)
    t = re.sub(r"\bMOON\s+(\d+)\b", r"\1", t)
    return t


def _canonical_moon_key(text: str) -> str:
    """Normalize to ``SYSTEM BODY - N`` when parseable."""
    norm = _normalize_label(text)
    m = _MOON_LABEL_RE.match(norm)
    if m:
        return f"{m.group(1).strip()} - {m.group(2)}"
    return norm


def _excluded_moon_keys() -> frozenset[str]:
    raw = os.environ.get("AA_EMU_MOONS_EXCLUDED_MOONS", "").strip()
    labels = list(_DEFAULT_EXCLUDED_MOON_LABELS)
    if raw:
        labels.extend(part.strip() for part in raw.split(";") if part.strip())
    return frozenset(_canonical_moon_key(lbl) for lbl in labels)


def structure_name_is_excluded(structure_name: str, system_name: str = "") -> bool:
    upper = (structure_name or "").upper()
    sys_upper = (system_name or "").upper()
    if not upper and not sys_upper:
        return False
    for parts in _STRUCTURE_EXCLUSION_RULES:
        if all(p.upper() in upper or p.upper() in sys_upper for p in parts):
            if parts[0].upper() == "DS-" and sys_upper.startswith("YW-"):
                continue
            if parts[0].upper() == "DS-" and upper.startswith("YW-"):
                continue
            return True
    return False


def moon_label_is_excluded(
    moon_label: str,
    *,
    structure_name: str = "",
    system_name: str = "",
    moon_number: int | None = None,
) -> bool:
    if structure_name_is_excluded(structure_name, system_name):
        return True
    key = _canonical_moon_key(moon_label)
    if key in _excluded_moon_keys():
        return True
    if moon_number is not None and system_name:
        alt = _canonical_moon_key(f"{system_name} - {moon_number}")
        if alt in _excluded_moon_keys():
            return True
    return False


def refinery_is_taxable(
    refinery_id: int,
    refinery_name: str = "",
    moon_label: str = "",
) -> bool:
    """False for private structures or explicitly excluded corp moons."""
    from emu_moons.models import StructureClass
    from emu_moons.services.scheduling import _structure_class

    if _structure_class(refinery_id, refinery_name or "") == StructureClass.PRIVATE:
        return False
    if structure_name_is_excluded(refinery_name or ""):
        return False
    if moon_label and moon_label_is_excluded(
        moon_label, structure_name=refinery_name or ""
    ):
        return False
    try:
        from emu_moons.models import StructureTaxProfile

        prof = StructureTaxProfile.objects.filter(
            moonmining_refinery_id=refinery_id
        ).only("notes").first()
        if prof and prof.notes and "tax_exempt" in prof.notes.lower():
            return False
    except Exception:
        pass
    return True


def extraction_is_taxable(extraction) -> bool:
    return not moon_label_is_excluded(
        extraction.moon_label or "",
        structure_name=extraction.structure_name or "",
        system_name=extraction.system_name or "",
        moon_number=extraction.moon_number,
    )
