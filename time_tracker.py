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
    def is_running(self) -> bool:
        return self._session_start is not None

    def start(self) -> None:
        if self._session_start is not None:
            return
        self._session_start = datetime.now()

    def session_elapsed_seconds(self) -> int:
        if self._session_start is None:
            return 0
        return max(0, int((datetime.now() - self._session_start).total_seconds()))

    def today_total_seconds(self) -> int:
        return self.stored_seconds_for(date.today()) + self.session_elapsed_seconds()

    def stop(self) -> int:
        """Stop session, persist seconds (split across midnight if needed). Return session seconds."""
        if self._session_start is None:
            return 0

        start = self._session_start
        end = datetime.now()
        self._session_start = None

        current = start
        while current.date() < end.date():
            next_midnight = datetime.combine(current.date() + timedelta(days=1), datetime.min.time())
            chunk = int((next_midnight - current).total_seconds())
            self._add_seconds(current.date(), chunk)
            current = next_midnight

        remaining = int((end - current).total_seconds())
        self._add_seconds(end.date(), remaining)
        return max(0, int((end - start).total_seconds()))
