from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from config import DRIVE_SHARE_PATH

_DRIVE_FOLDER_RE = re.compile(r"drive\.google\.com/(?:drive/)?(?:.+/)?folders/")


def normalize_upload_url(value: str) -> str:
    """Accept only an Apps Script web-app URL (.../exec)."""
    text = (value or "").strip()
    if not text:
        raise ValueError("Paste your Apps Script web-app link (ends with /exec).")

    if _DRIVE_FOLDER_RE.search(text) or (
        "drive.google.com" in text and "script.google.com" not in text
    ):
        raise ValueError(
            "Paste the Apps Script /exec URL (not the Drive folder link).\n"
            "See drive_upload/README.md — then Tracker will show the public Drive link."
        )

    if "script.google.com/macros/s/" in text and "/exec" in text:
        match = re.search(
            r"(https://script\.google\.com/macros/s/[a-zA-Z0-9_-]+/exec)",
            text,
        )
        if match:
            return match.group(1)

    raise ValueError(
        "Need an Apps Script link like:\n"
        "https://script.google.com/macros/s/.../exec"
    )


class DriveUploader:
    """Upload via Apps Script; receive public anyone-with-link Drive URLs back."""

    def __init__(self, share_path: Path = DRIVE_SHARE_PATH) -> None:
        self.share_path = Path(share_path)
        self._upload_url: str = ""
        self._public_share_link: str = ""
        self._load_share_config()

    def _load_share_config(self) -> None:
        if not self.share_path.exists():
            return
        try:
            data = json.loads(self.share_path.read_text(encoding="utf-8"))
            raw = (data.get("upload_url") or "").strip()
            self._public_share_link = (data.get("public_share_link") or "").strip()
            if raw:
                try:
                    self._upload_url = normalize_upload_url(raw)
                except ValueError:
                    self._upload_url = ""
        except (json.JSONDecodeError, OSError):
            self._upload_url = ""
            self._public_share_link = ""

    def _persist(self) -> None:
        self.share_path.parent.mkdir(parents=True, exist_ok=True)
        self.share_path.write_text(
            json.dumps(
                {
                    "upload_url": self._upload_url,
                    "public_share_link": self._public_share_link,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def save_share_link(self, link: str) -> str:
        self._upload_url = normalize_upload_url(link)
        self._persist()
        return self._upload_url

    def set_public_share_link(self, url: str) -> None:
        self._public_share_link = (url or "").strip()
        self._persist()

    @property
    def folder_link(self) -> str:
        return self._upload_url

    @property
    def upload_url(self) -> str:
        return self._upload_url

    @property
    def public_share_link(self) -> str:
        return self._public_share_link

    def has_folder(self) -> bool:
        return bool(self._upload_url)

    def _request_json(self, method: str, payload: Optional[dict] = None) -> dict[str, Any]:
        if not self._upload_url:
            raise ValueError("No upload endpoint saved.")

        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        request = urllib.request.Request(
            self._upload_url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Request failed ({exc.code}): {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Request failed: {exc.reason}") from exc

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Endpoint did not return JSON. Check the /exec URL.") from exc
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(str(result["error"]))
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected response from upload endpoint.")
        return result

    def fetch_public_share_link(self) -> str:
        """GET the web app — ensures folder is anyone-with-link and returns its URL."""
        result = self._request_json("GET")
        link = (result.get("shareLink") or result.get("folderUrl") or "").strip()
        if not link:
            raise RuntimeError("No share link returned. Redeploy Apps Script with latest Code.gs.")
        self.set_public_share_link(link)
        return link

    def upload_png(self, file_path: Path) -> dict[str, str]:
        file_path = Path(file_path)
        payload = {
            "filename": file_path.name,
            "mimeType": "image/png",
            "content": base64.b64encode(file_path.read_bytes()).decode("ascii"),
        }
        result = self._request_json("POST", payload)
        file_id = str(result.get("id") or "ok")
        share = (result.get("shareLink") or result.get("folderUrl") or "").strip()
        if share:
            self.set_public_share_link(share)
        return {
            "id": file_id,
            "share_link": share or self._public_share_link,
            "file_url": str(result.get("fileUrl") or ""),
        }
