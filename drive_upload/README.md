# Drive upload + public share link

Google Drive does not allow the desktop app to upload with zero credentials.
This Apps Script is set up **once by the folder owner**. Everyone else only uses Tracker.

## What you get
1. Tracker uploads screenshots through the script (no Google login in the app)
2. The script makes the folder **Anyone with the link can view**
3. Tracker shows that Drive folder link → **Copy link** / **Open link** to share with anyone

## Setup (folder owner, once)

1. Open [script.google.com](https://script.google.com) → **New project**
2. Paste [`Code.gs`](Code.gs)
3. Set `FOLDER_ID` from your folder URL:  
   `https://drive.google.com/drive/folders/FOLDER_ID`
4. **Deploy** → **New deployment** → **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
5. Copy the URL ending in `/exec`
6. **Important:** after editing Code.gs later, deploy a **new version**

## In Tracker (everyone who uploads)
1. **Share session** → paste the `/exec` URL
2. Wait until **Public link** appears
3. Use **Copy link** to share the Drive folder with anyone
4. **Start** tracking — new screenshots appear in that folder
