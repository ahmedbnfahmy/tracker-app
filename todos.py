from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from config import DATA_DIR


class TodoStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (DATA_DIR / "todos.json")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"items": []})

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                items = data.get("items")
                if not isinstance(items, list):
                    data["items"] = []
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {"items": []}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def all(self) -> list[dict[str, Any]]:
        items = [i for i in self._read().get("items", []) if isinstance(i, dict)]
        open_items = [i for i in items if not i.get("done")]
        done_items = [i for i in items if i.get("done")]
        return open_items + done_items

    def open_count(self) -> int:
        return sum(1 for i in self.all() if not i.get("done"))

    def add(self, text: str) -> dict[str, Any]:
        entry = {
            "id": uuid.uuid4().hex[:12],
            "text": text.strip() or "Untitled",
            "done": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        data = self._read()
        items = data.get("items") or []
        if not isinstance(items, list):
            items = []
        items.append(entry)
        data["items"] = items
        self._write(data)
        return entry

    def toggle(self, todo_id: str) -> Optional[dict[str, Any]]:
        data = self._read()
        items = data.get("items") or []
        if not isinstance(items, list):
            return None
        for item in items:
            if isinstance(item, dict) and item.get("id") == todo_id:
                item["done"] = not bool(item.get("done"))
                self._write(data)
                return item
        return None

    def delete(self, todo_id: str) -> Optional[dict[str, Any]]:
        data = self._read()
        items = data.get("items") or []
        if not isinstance(items, list):
            return None
        for i, item in enumerate(items):
            if isinstance(item, dict) and item.get("id") == todo_id:
                removed = items.pop(i)
                data["items"] = items
                self._write(data)
                return removed
        return None
