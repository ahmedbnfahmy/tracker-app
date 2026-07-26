from pathlib import Path

from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

SCREENSHOT_INTERVAL_SECONDS = int(os.getenv("SCREENSHOT_INTERVAL_SECONDS", "600"))
SCREENSHOT_RETENTION_DAYS = int(os.getenv("SCREENSHOT_RETENTION_DAYS", "15"))

# Default: ~/Documents/TrackerApp (override with SCREENSHOTS_DIR in .env)
_default_captures = Path.home() / "Documents" / "TrackerApp"
CAPTURES_DIR = Path(os.getenv("SCREENSHOTS_DIR", str(_default_captures))).expanduser()
if not CAPTURES_DIR.is_absolute():
    CAPTURES_DIR = ROOT_DIR / CAPTURES_DIR
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = ROOT_DIR / "data"
TIME_LOG_PATH = DATA_DIR / "time_log.json"
DRIVE_SHARE_PATH = DATA_DIR / "drive_share.json"
ASSETS_DIR = ROOT_DIR / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"
