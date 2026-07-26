from __future__ import annotations

import re
import shutil
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image

from config import CAPTURES_DIR, SCREENSHOT_RETENTION_DAYS

_DAY_FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def day_folder(day: date | None = None, root: Path = CAPTURES_DIR) -> Path:
    """Return ~/Documents/TrackerApp/YYYY-MM-DD and create it if needed."""
    day = day or date.today()
    folder = root / day.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_captures(root: Path = CAPTURES_DIR) -> list[Path]:
    """All screenshots under daily folders (and any loose root files)."""
    root.mkdir(parents=True, exist_ok=True)
    files = list(root.glob("*/*.png")) + list(root.glob("*.png"))
    return sorted(files, key=lambda p: p.stat().st_mtime)


def cleanup_old_day_folders(
    root: Path = CAPTURES_DIR,
    keep_days: int = SCREENSHOT_RETENTION_DAYS,
) -> list[Path]:
    """Delete day folders older than keep_days. Returns removed folder paths."""
    root.mkdir(parents=True, exist_ok=True)
    cutoff = date.today() - timedelta(days=max(0, keep_days))
    removed: list[Path] = []
    for path in root.iterdir():
        if not path.is_dir() or not _DAY_FOLDER_RE.match(path.name):
            continue
        try:
            folder_day = date.fromisoformat(path.name)
        except ValueError:
            continue
        if folder_day < cutoff:
            shutil.rmtree(path, ignore_errors=True)
            removed.append(path)
    return removed


def _timestamp_name() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S.png")


def _capture_with_mss(path: Path) -> None:
    import mss

    with mss.mss() as sct:
        # monitor 0 = virtual desktop spanning all displays
        shot = sct.grab(sct.monitors[0])
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        image.save(path, format="PNG")


def _capture_with_cli(path: Path) -> None:
    if shutil.which("gnome-screenshot"):
        subprocess.run(
            ["gnome-screenshot", "-f", str(path)],
            check=True,
            capture_output=True,
        )
        return
    if shutil.which("import"):
        # ImageMagick: capture root window
        subprocess.run(["import", "-window", "root", str(path)], check=True, capture_output=True)
        return
    raise RuntimeError(
        "No screenshot method available. Install mss dependencies for X11, "
        "or install gnome-screenshot / imagemagick."
    )


def take_screenshot(output_dir: Path | None = None) -> Path:
    folder = day_folder() if output_dir is None else Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _timestamp_name()

    try:
        _capture_with_mss(path)
    except Exception:
        if path.exists():
            path.unlink(missing_ok=True)
        _capture_with_cli(path)

    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Screenshot capture failed: empty or missing file")
    return path
