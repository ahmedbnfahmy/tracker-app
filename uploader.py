from __future__ import annotations

from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import (
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_OAUTH_CLIENT_FILE,
    GOOGLE_TOKEN_FILE,
)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


class DriveUploader:
    def __init__(
        self,
        client_secrets: Path = GOOGLE_OAUTH_CLIENT_FILE,
        token_file: Path = GOOGLE_TOKEN_FILE,
        folder_id: str = GOOGLE_DRIVE_FOLDER_ID,
    ) -> None:
        self.client_secrets = Path(client_secrets)
        self.token_file = Path(token_file)
        self.folder_id = (folder_id or "").strip()
        self._creds: Optional[Credentials] = None
        self._service = None
        self._email: Optional[str] = None

    def is_connected(self) -> bool:
        return self._load_credentials() is not None

    def connected_email(self) -> Optional[str]:
        if not self.is_connected():
            return None
        if self._email:
            return self._email
        try:
            service = build("oauth2", "v2", credentials=self._creds, cache_discovery=False)
            info = service.userinfo().get().execute()
            self._email = info.get("email")
        except Exception:
            self._email = None
        return self._email

    def connect(self) -> str:
        """Run browser OAuth and persist token. Returns connected email."""
        if not self.client_secrets.exists():
            raise FileNotFoundError(
                f"OAuth client file not found: {self.client_secrets}\n"
                "Create an OAuth Desktop client in Google Cloud and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secrets), SCOPES)
        creds = flow.run_local_server(port=0)
        self._save_credentials(creds)
        self._creds = creds
        self._service = None
        self._email = None
        email = self.connected_email() or "connected"
        return email

    def disconnect(self) -> None:
        self._creds = None
        self._service = None
        self._email = None
        if self.token_file.exists():
            self.token_file.unlink()

    def _load_credentials(self) -> Optional[Credentials]:
        if self._creds and self._creds.valid:
            return self._creds

        creds: Optional[Credentials] = None
        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds)
            except Exception:
                creds = None

        if creds and creds.valid:
            self._creds = creds
            return creds

        self._creds = None
        return None

    def _save_credentials(self, creds: Credentials) -> None:
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(creds.to_json(), encoding="utf-8")

    def _get_service(self):
        if self._service is not None:
            return self._service
        creds = self._load_credentials()
        if creds is None:
            raise RuntimeError("Google Drive is not connected. Sign in first.")
        if not self.folder_id or self.folder_id == "your_folder_id_here":
            raise ValueError("GOOGLE_DRIVE_FOLDER_ID is not configured in .env")
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def upload_png(self, file_path: Path) -> str:
        file_path = Path(file_path)
        service = self._get_service()
        metadata = {
            "name": file_path.name,
            "parents": [self.folder_id],
        }
        media = MediaFileUpload(str(file_path), mimetype="image/png", resumable=True)
        created = (
            service.files()
            .create(body=metadata, media_body=media, fields="id", supportsAllDrives=True)
            .execute()
        )
        return created["id"]
