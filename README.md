# Tracker

Ubuntu desktop app that tracks work sessions and takes screenshots every 10 minutes. Screenshots are saved locally. **Share** sends new screenshots via a public Apps Script link — **no Google credentials in the app**.

See [APP.md](APP.md) and [drive_upload/README.md](drive_upload/README.md).

## Setup

```bash
sudo apt install python3-tk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Drive sharing (no app credentials)

1. Follow [drive_upload/README.md](drive_upload/README.md) (one-time Apps Script deploy)
2. In Tracker: **Share** → paste the `/exec` URL → **Start share**
3. Stays on across sessions until you click **Stop share**

## Run

```bash
./tracker
```

Screenshots are saved to `~/Documents/TrackerApp/YYYY-MM-DD/` (one folder per day).
Folders older than **15 days** are deleted automatically when the app starts.
