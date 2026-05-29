"""Parse pasted moon pop lines (tab or multi-space separated)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

from django.contrib.auth.models import User
from django.utils import timezone

from .models import MoonPop

LOCATION_RE = re.compile(
    r"^(?P<system>\S+)\s+(?P<rest>.+?)\s+-\s+Moon\s+(?P<num>\d+)\s*$",
    re.IGNORECASE,
)

DATE_FORMATS = (
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
)


@dataclass
class ParsedMoonPop:
    location_label: str
    system_name: str
    moon_number: int | None
    pop_at: datetime
    rental_kind: str
    private_owner_username: str | None
    line_no: int
    raw_line: str


def _parse_datetime(text: str) -> datetime:
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            if timezone.is_naive(dt):
                return timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date/time: {text!r}")


def _split_line(line: str) -> tuple[str, str, str | None]:
    """Return location, datetime string, optional owner username."""
    line = line.strip()
    if not line or line.startswith("#"):
        raise ValueError("empty or comment")
    owner_hint = None
    if "|" in line:
        line, owner_hint = [p.strip() for p in line.split("|", 1)]
    parts = re.split(r"\t+|\s{2,}", line, maxsplit=1)
    if len(parts) == 1:
        m = re.match(r"^(.+?)\s+(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)\s*$", line)
        if not m:
            raise ValueError("Could not split location and datetime")
        return m.group(1).strip(), m.group(2).strip(), owner_hint
    return parts[0].strip(), parts[1].strip(), owner_hint


def parse_location(location: str) -> tuple[str, int | None]:
    m = LOCATION_RE.match(location.strip())
    if m:
        return m.group("system").upper(), int(m.group("num"))
    system = location.split()[0].upper()
    return system, None


def parse_import_text(
    text: str,
    *,
    default_kind: str = MoonPop.CORP_FALSE_GODS,
    default_owner_username: str | None = None,
) -> Iterator[ParsedMoonPop]:
    for i, raw in enumerate(text.splitlines(), start=1):
        try:
            location, when_str, owner_hint = _split_line(raw)
            pop_at = _parse_datetime(when_str)
            system_name, moon_number = parse_location(location)
            kind = default_kind
            owner_name = owner_hint or default_owner_username
            if owner_name:
                kind = MoonPop.PRIVATE
            elif default_kind == MoonPop.PRIVATE and default_owner_username:
                owner_name = default_owner_username
                kind = MoonPop.PRIVATE
            yield ParsedMoonPop(
                location_label=location,
                system_name=system_name,
                moon_number=moon_number,
                pop_at=pop_at,
                rental_kind=kind,
                private_owner_username=owner_name,
                line_no=i,
                raw_line=raw,
            )
        except ValueError:
            continue


def resolve_owner(username: str | None) -> User | None:
    if not username:
        return None
    username = username.strip()
    if not username:
        return None
    return User.objects.filter(username__iexact=username).first()
