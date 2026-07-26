from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image

from config import CAPTURES_DIR


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


def take_screenshot(output_dir: Path = CAPTURES_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / _timestamp_name()

    try:
        _capture_with_mss(path)
    except Exception:
        if path.exists():
            path.unlink(missing_ok=True)
        _capture_with_cli(path)

    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Screenshot capture failed: empty or missing file")
    return path
