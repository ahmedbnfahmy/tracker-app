from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from config import DATA_DIR, TIME_LOG_PATH


def format_duration(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s"


class TimeTracker:
    def __init__(self, log_path: Path = TIME_LOG_PATH) -> None:
        self.log_path = log_path
        self._session_start: Optional[datetime] = None
        self._accumulated: int = 0
        self._paused: bool = False
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            with self.log_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _write(self, data: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _add_seconds(self, day: date, seconds: int) -> None:
        if seconds <= 0:
            return
        data = self._read()
        key = day.isoformat()
        entry = data.get(key) or {"seconds": 0}
        entry["seconds"] = int(entry.get("seconds", 0)) + seconds
        data[key] = entry
        self._write(data)

    def stored_seconds_for(self, day: Optional[date] = None) -> int:
        day = day or date.today()
        data = self._read()
        entry = data.get(day.isoformat()) or {}
        return int(entry.get("seconds", 0))

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_running(self) -> bool:
        """True while a session is active (running or paused)."""
        return self._session_start is not None or self._paused

    @property
    def is_ticking(self) -> bool:
        """True while the timer is actively counting."""
        return self._session_start is not None and not self._paused

    def start(self) -> None:
        if self.is_running:
            return
        self._accumulated = 0
        self._paused = False
        self._session_start = datetime.now()

    def pause(self) -> None:
        if self._session_start is None or self._paused:
            return
        self._accumulated += max(0, int((datetime.now() - self._session_start).total_seconds()))
        self._session_start = None
        self._paused = True

    def resume(self) -> None:
        if not self._paused:
            return
        self._paused = False
        self._session_start = datetime.now()

    def session_elapsed_seconds(self) -> int:
        elapsed = self._accumulated
        if self._session_start is not None:
            elapsed += max(0, int((datetime.now() - self._session_start).total_seconds()))
        return max(0, elapsed)

    def today_total_seconds(self) -> int:
        return self.stored_seconds_for(date.today()) + self.session_elapsed_seconds()

    def _persist_segment(self, start: datetime, end: datetime) -> int:
        current = start
        while current.date() < end.date():
            next_midnight = datetime.combine(current.date() + timedelta(days=1), datetime.min.time())
            chunk = int((next_midnight - current).total_seconds())
            self._add_seconds(current.date(), chunk)
            current = next_midnight

        remaining = int((end - current).total_seconds())
        self._add_seconds(end.date(), remaining)
        return max(0, int((end - start).total_seconds()))

    def stop(self) -> int:
        """Stop session, persist seconds (split across midnight if needed). Return session seconds."""
        if not self.is_running:
            return 0

        total = 0
        if self._accumulated > 0:
            self._add_seconds(date.today(), self._accumulated)
            total += self._accumulated
            self._accumulated = 0

        if self._session_start is not None:
            start = self._session_start
            end = datetime.now()
            self._session_start = None
            total += self._persist_segment(start, end)

        self._paused = False
        return total

    def lap(self, name: str) -> tuple[int, str]:
        """Save current segment into today's total, reset timer, return (seconds, name)."""
        if not self.is_running:
            return 0, name.strip() or "Untitled"

        seconds = self.stop()
        self.start()
        return seconds, name.strip() or "Untitled"
