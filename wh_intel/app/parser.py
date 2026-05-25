"""Parse EVE client chat log lines (showinfo URLs, channel headers)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timezone

SHOWINFO_RE = re.compile(
    r"<url=showinfo:(?P<stype>\d+)//(?P<sid>\d+)>(?P<name>[^<]+)</url>",
    re.IGNORECASE,
)
LINE_RE = re.compile(
    r"^\[(?P<time>\d{2}:\d{2}:\d{2})\]\s*(?P<speaker>[^>]+?)\s*>\s*(?P<body>.+)$"
)
CHANNEL_HEADER_RE = re.compile(
    r"^\s*Channel:\s*(?P<channel>.+?)\s*$",
    re.IGNORECASE,
)
LOCATION_QUERY_RE = re.compile(r"\blocation\s*\?", re.IGNORECASE)

# EVE showinfo type hints (instance id is always after //).
SHOWINFO_CHARACTER_TYPES = frozenset({1, 1375, 1376, 1377, 1380, 1381})
SHOWINFO_SHIP_TYPES = frozenset({626, 1378, 1384, 1385, 1386})
SHOWINFO_SYSTEM_TYPES = frozenset({5, 6})
SHOWINFO_CORP_TYPES = frozenset({2, 16159})
SHOWINFO_ALLIANCE_TYPES = frozenset({3})


@dataclass
class ParsedEntity:
    entity_type: str
    entity_id: int
    name: str
    showinfo_type: int | None = None


@dataclass
class ParsedIntelLine:
    channel: str
    reported_at: datetime
    solar_system_id: int
    solar_system_name: str
    entities: list[ParsedEntity] = field(default_factory=list)
    intel_text: str = ""
    raw_line: str = ""
    # True when system came from a prior ping for the same character (e.g. "DPSDaddy location?").
    inferred_system: bool = False


def classify_showinfo(stype: int) -> str:
    if stype in SHOWINFO_SYSTEM_TYPES:
        return "system"
    if stype in SHOWINFO_CHARACTER_TYPES:
        return "character"
    if stype in SHOWINFO_SHIP_TYPES:
        return "ship"
    if stype in SHOWINFO_CORP_TYPES:
        return "corporation"
    if stype in SHOWINFO_ALLIANCE_TYPES:
        return "alliance"
    return "unknown"


def portrait_url_for(entity_type: str, entity_id: int) -> str | None:
    if entity_type == "character":
        return f"https://images.eveonline.com/characters/{entity_id}/portrait?size=128"
    if entity_type == "corporation":
        return f"https://images.eveonline.com/corporations/{entity_id}/logo?size=128"
    if entity_type == "alliance":
        return f"https://images.eveonline.com/alliances/{entity_id}/logo?size=128"
    return None


def strip_speaker_from_body(body: str) -> tuple[str, list[ParsedEntity]]:
    """Return intel text without showinfo markup + extracted entities."""
    entities: list[ParsedEntity] = []
    for match in SHOWINFO_RE.finditer(body):
        stype = int(match.group("stype"))
        sid = int(match.group("sid"))
        name = match.group("name").strip()
        etype = classify_showinfo(stype)
        entities.append(
            ParsedEntity(
                entity_type=etype,
                entity_id=sid,
                name=name,
                showinfo_type=stype,
            )
        )
    intel_text = SHOWINFO_RE.sub(lambda m: m.group("name").strip(), body)
    intel_text = re.sub(r"\s{2,}", " ", intel_text).strip()
    return intel_text, entities


def parse_chat_line(
    line: str,
    *,
    channel: str,
    log_date: datetime | None = None,
) -> ParsedIntelLine | None:
    line = line.rstrip("\r\n")
    if not line.strip():
        return None

    header = CHANNEL_HEADER_RE.match(line)
    if header:
        return None

    match = LINE_RE.match(line)
    if not match:
        return None

    body = match.group("body")
    intel_text, entities = strip_speaker_from_body(body)

    t = datetime.strptime(match.group("time"), "%H:%M:%S").time()
    base = log_date or datetime.now(timezone.utc)
    reported_at = datetime.combine(base.date(), t, tzinfo=timezone.utc)

    system = next((e for e in entities if e.entity_type == "system"), None)
    if system is not None:
        return ParsedIntelLine(
            channel=channel,
            reported_at=reported_at,
            solar_system_id=system.entity_id,
            solar_system_name=system.name,
            entities=[e for e in entities if e.entity_type != "system"],
            intel_text=intel_text,
            raw_line=line,
        )

    characters = [e for e in entities if e.entity_type == "character"]
    if characters and LOCATION_QUERY_RE.search(intel_text):
        return ParsedIntelLine(
            channel=channel,
            reported_at=reported_at,
            solar_system_id=0,
            solar_system_name="",
            entities=characters,
            intel_text=intel_text,
            raw_line=line,
        )

    return None


def parse_log_chunk(
    text: str,
    *,
    allowed_channels: set[str],
    log_date: datetime | None = None,
) -> list[ParsedIntelLine]:
    """Parse a chunk of chat log text; track ``Channel:`` headers."""
    current_channel = ""
    out: list[ParsedIntelLine] = []
    for raw in text.splitlines():
        header = CHANNEL_HEADER_RE.match(raw)
        if header:
            current_channel = header.group("channel").strip()
            continue
        if current_channel.lower() not in allowed_channels:
            continue
        parsed = parse_chat_line(raw, channel=current_channel, log_date=log_date)
        if parsed:
            out.append(parsed)
    return out
