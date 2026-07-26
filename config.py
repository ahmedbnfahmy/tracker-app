from pathlib import Path

from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

CREDENTIALS_DIR = ROOT_DIR / "credentials"

GOOGLE_OAUTH_CLIENT_FILE = Path(
    os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "credentials/client_secret.json")
)
if not GOOGLE_OAUTH_CLIENT_FILE.is_absolute():
    GOOGLE_OAUTH_CLIENT_FILE = ROOT_DIR / GOOGLE_OAUTH_CLIENT_FILE

GOOGLE_TOKEN_FILE = Path(os.getenv("GOOGLE_TOKEN_FILE", "credentials/token.json"))
if not GOOGLE_TOKEN_FILE.is_absolute():
    GOOGLE_TOKEN_FILE = ROOT_DIR / GOOGLE_TOKEN_FILE

GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()

SCREENSHOT_INTERVAL_SECONDS = int(os.getenv("SCREENSHOT_INTERVAL_SECONDS", "600"))

CAPTURES_DIR = ROOT_DIR / "captures"
DATA_DIR = ROOT_DIR / "data"
TIME_LOG_PATH = DATA_DIR / "time_log.json"
ASSETS_DIR = ROOT_DIR / "assets"
ICON_PATH = ASSETS_DIR / "icon.png"
