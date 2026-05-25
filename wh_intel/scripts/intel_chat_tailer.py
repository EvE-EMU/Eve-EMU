#!/usr/bin/env python3
"""
Tail EVE chat logs and POST intel lines to the WH intel overlay API.

Default log folder (Windows):
  %USERPROFILE%\\Documents\\EVE\\logs\\Chatlogs

Usage:
  python wh_intel/scripts/intel_chat_tailer.py --api https://wh.eve-emu.com/intel/api/v1/ingest
"""

from __future__ import annotations

import argparse
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

CHANNEL_HEADER_RE = re.compile(
    r"^\s*Channel:\s*(?P<channel>.+?)\s*$",
    re.IGNORECASE,
)


def channel_from_log_path(path: Path) -> str:
    """EVE chat logs: ``intel.womp_20260523_1234567890.txt`` or ``intel.womp.txt``."""
    stem = path.stem
    parts = stem.rsplit("_", 2)
    if len(parts) == 3 and len(parts[1]) == 8 and parts[1].isdigit() and parts[2].isdigit():
        return parts[0]
    if stem and not stem.lower().startswith("chatlog"):
        return stem
    return ""


def seed_channel_from_file_tail(path: Path, *, read_bytes: int = 65536) -> str:
    """Last ``Channel:`` line in the log (EVE only writes it on join / channel switch)."""
    try:
        size = path.stat().st_size
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(max(0, size - read_bytes))
            chunk = fh.read()
    except OSError:
        return ""
    last = ""
    for line in chunk.splitlines():
        m = CHANNEL_HEADER_RE.match(line)
        if m:
            last = m.group("channel").strip()
    return last


def resolve_channel(path: Path, current: str) -> str:
    if current.strip():
        return current.strip()
    return seed_channel_from_file_tail(path) or channel_from_log_path(path)


def flush(api_url: str, lines: list[str], channel: str = "", *, log_path: Path | None = None) -> None:
    if not lines:
        return
    text = "".join(lines)
    if "showinfo:" not in text:
        return
    if not channel.strip() and log_path is not None:
        channel = channel_from_log_path(log_path)
    if not channel.strip():
        print(f"skip: no channel for {len(lines)} line(s) (set Channel: in log or use intel.womp_*.txt filename)")
        return
    # Ingest parser needs a Channel: header; log files only repeat it when the channel changes.
    text = f"Channel: {channel.strip()}\n{text}"
    payload = {
        "text": text,
        "log_date": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(api_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            n = data.get("accepted") or 0
            if n:
                print(f"ingested {n} ping(s)")
            elif data.get("skipped"):
                print(f"skipped {data['skipped']} line(s) (parser)")
            else:
                print(f"no pings accepted: {data}")
    except Exception as exc:
        print(f"ingest failed: {exc}")


def main() -> None:
    p = argparse.ArgumentParser(description="Tail EVE intel chat logs → WH intel API")
    p.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("USERPROFILE", "")) / "Documents" / "EVE" / "logs" / "Chatlogs",
        help="Chatlogs directory",
    )
    p.add_argument(
        "--api",
        default=os.environ.get("WH_INTEL_INGEST_URL", "http://localhost:8020/api/v1/ingest"),
        help="Ingest API URL",
    )
    p.add_argument(
        "--channels",
        default="intel.womp,OnlyQuerious",
        help="Comma-separated channel names",
    )
    args = p.parse_args()
    channels = {c.strip().lower() for c in args.channels.split(",") if c.strip()}
    if not args.dir.is_dir():
        raise SystemExit(f"Chatlogs directory not found: {args.dir}")

    print(f"Tailing {args.dir} → {args.api} channels={channels}")
    offsets: dict[Path, int] = {}
    current_channel: dict[Path, str] = {}
    pending: dict[Path, list[str]] = {}

    while True:
        for path in sorted(args.dir.glob("*.txt")):
            if path not in offsets:
                # Only tail new lines; seed channel from file tail / filename.
                offsets[path] = path.stat().st_size
                seeded = resolve_channel(path, "")
                if seeded:
                    current_channel[path] = seeded
                    print(f"watching {path.name} channel={seeded!r}")
                else:
                    print(f"watching {path.name} (channel unknown until Channel: header)")
                continue

            size = path.stat().st_size
            start = offsets[path]
            if size < start:
                start = 0
            if size == start:
                continue
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(start)
                chunk = fh.read()
                offsets[path] = fh.tell()

            buf = pending.setdefault(path, [])
            for line in chunk.splitlines(keepends=True):
                header = CHANNEL_HEADER_RE.match(line)
                if header:
                    if buf:
                        flush(
                            args.api,
                            buf,
                            current_channel.get(path, ""),
                            log_path=path,
                        )
                        buf.clear()
                    current_channel[path] = header.group("channel").strip()
                    continue
                ch = resolve_channel(path, current_channel.get(path, "")).lower()
                if ch and not current_channel.get(path):
                    current_channel[path] = ch
                if ch in channels:
                    buf.append(line)
                    # Intel reports are sparse — do not wait for 6 lines.
                    if "showinfo:" in line:
                        flush(
                            args.api,
                            buf,
                            current_channel.get(path, ""),
                            log_path=path,
                        )
                        buf.clear()
                    elif len(buf) >= 6:
                        flush(
                            args.api,
                            buf,
                            current_channel.get(path, ""),
                            log_path=path,
                        )
                        buf.clear()
            pending[path] = buf
        time.sleep(0.5)


if __name__ == "__main__":
    main()
