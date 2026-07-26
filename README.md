# Screen Tracker

Ubuntu desktop app that tracks work sessions and takes screenshots every 10 minutes. Screenshots are saved locally; Google Drive upload is optional.

See [APP.md](APP.md) for a product summary and feature list.

## Requirements

- Ubuntu (X11; Wayland may need a fallback screenshot tool)
- Python 3.10+
- `python3-tk` system package
- (Optional) Google Cloud OAuth Desktop client with Drive API enabled

## Setup

```bash
sudo apt install python3-tk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You can run with **local saves only** — no Google credentials required.

### Optional: Google Drive (OAuth sign-in)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project.
2. Enable the **Google Drive API**.
3. Configure the **OAuth consent screen** (add your account as a test user while in Testing).
4. Create credentials → **OAuth client ID** → **Desktop app**.
5. Download the JSON as `credentials/client_secret.json`.
6. Create/open a Drive folder and copy the folder ID from the URL.

### Environment

```bash
cp .env.example .env
```

```
GOOGLE_OAUTH_CLIENT_FILE=credentials/client_secret.json
GOOGLE_TOKEN_FILE=credentials/token.json
GOOGLE_DRIVE_FOLDER_ID=your_folder_id_here
SCREENSHOT_INTERVAL_SECONDS=600
```

`GOOGLE_DRIVE_FOLDER_ID` is only needed if you use Drive.

## Run

```bash
source .venv/bin/activate
python main.py
```

For the dock/app menu icon, launch **Screen Tracker** from the app menu (desktop entry is installed). Running from the terminal may still show a generic Python icon in some desktop environments.

- **Start** works immediately and saves screenshots to `captures/`.
- Click **Connect** anytime to sign in; pending local screenshots sync to Drive.

## Notes

- Screenshots: `captures/`
- Upload log: `data/uploaded.json`
- Daily time totals: `data/time_log.json`
- Keep `credentials/` and `.env` out of version control.
