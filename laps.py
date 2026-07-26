from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR


class LapStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DATA_DIR / "laps.json")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_lap(self, name: str, seconds: int, day: Optional[date] = None) -> dict[str, Any]:
        day = day or date.today()
        entry = {
            "name": name.strip() or "Untitled",
            "seconds": max(0, int(seconds)),
            "ended_at": datetime.now().isoformat(timespec="seconds"),
        }
        data = self._read()
        key = day.isoformat()
        laps = data.get(key) or []
        if not isinstance(laps, list):
            laps = []
        laps.append(entry)
        data[key] = laps
        self._write(data)
        return entry

    def laps_for(self, day: Optional[date] = None) -> list[dict[str, Any]]:
        day = day or date.today()
        data = self._read()
        laps = data.get(day.isoformat()) or []
        return laps if isinstance(laps, list) else []

    def delete_lap(self, index: int, day: Optional[date] = None) -> Optional[dict[str, Any]]:
        day = day or date.today()
        data = self._read()
        key = day.isoformat()
        laps = data.get(key) or []
        if not isinstance(laps, list) or index < 0 or index >= len(laps):
            return None
        removed = laps.pop(index)
        if laps:
            data[key] = laps
        else:
            data.pop(key, None)
        self._write(data)
        return removed if isinstance(removed, dict) else None
