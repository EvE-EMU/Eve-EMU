"""Progress and ETA reporting for Wiki.js SDE import."""

from __future__ import annotations

import time


def format_duration(seconds: float) -> str:
    """Human-readable duration (e.g. 2h 15m, 45s)."""
    if seconds < 0 or seconds != seconds:  # NaN
        return "?"
    total = int(seconds + 0.5)
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    if minutes:
        return f"{hours}h {minutes}m"
    return f"{hours}h"


class ImportProgress:
    """Tracks overall and per-phase progress with elapsed time and ETA."""

    def __init__(self, stdout, *, interval: int = 25):
        self.stdout = stdout
        self.interval = max(1, interval)
        self.total = 0
        self.done = 0
        self.phase = ""
        self.phase_total = 0
        self.phase_done = 0
        self._started: float | None = None

    def start(self, total: int) -> None:
        self.total = total
        self.done = 0
        self._started = time.monotonic()
        if self.stdout:
            self.stdout.write(f"Pages to process: {total:,}")

    def set_phase(self, name: str, phase_total: int) -> None:
        self.phase = name
        self.phase_total = phase_total
        self.phase_done = 0
        if self.stdout:
            self.stdout.write(f"  → {name} ({phase_total:,} pages)")

    def tick(self) -> None:
        self.done += 1
        self.phase_done += 1
        if not self.stdout or not self._started:
            return
        if self.done != 1 and self.done % self.interval != 0 and self.done != self.total:
            return
        self._emit()

    def finish(self) -> None:
        if not self.stdout or not self._started:
            return
        elapsed = time.monotonic() - self._started
        self.stdout.write(
            f"Finished {self.done:,}/{self.total:,} pages in {format_duration(elapsed)}."
        )

    def _emit(self) -> None:
        elapsed = time.monotonic() - (self._started or time.monotonic())
        rate = self.done / elapsed if elapsed > 0 else 0.0
        remaining = (self.total - self.done) / rate if rate > 0 else 0.0
        overall_pct = (100.0 * self.done / self.total) if self.total else 0.0
        phase_pct = (100.0 * self.phase_done / self.phase_total) if self.phase_total else 0.0
        self.stdout.write(
            f"  {self.phase}: {self.phase_done:,}/{self.phase_total:,} ({phase_pct:.1f}%) | "
            f"overall {self.done:,}/{self.total:,} ({overall_pct:.1f}%) | "
            f"elapsed {format_duration(elapsed)} | remaining {format_duration(remaining)}"
        )
