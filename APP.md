# Screen Tracker

## Summary
Screen Tracker is a simple Ubuntu desktop app that helps you track work time and keep a visual record of your screen. Click Start to begin a session, and the app counts your time and takes a screenshot every 10 minutes. Screenshots are always saved locally. Connecting Google Drive is optional — when connected, local screenshots are uploaded (and any pending local files are synced). Time today is shown on the start page.

## Features

### Start / Stop tracking
One control window with Start and Stop. Tracking (timer + screenshots) runs only while a session is active.

### Session timer
From the moment you click Start, a live timer counts elapsed time in hours (for example `1h 05m 12s`). It stops when you click Stop.

### Time today
The start page shows total time tracked today. It includes finished sessions plus the current live session while tracking is on. Totals are saved locally so they remain after you close the app.

### Automatic screenshots
While tracking, the app captures the current screen once every 10 minutes and saves them under `captures/`.

### Timestamped filenames
Each screenshot is saved with the capture date and time in the filename (for example `2026-07-26_11-45-00.png`). No text is drawn on the image.

### Optional Google Drive
Drive is optional. Use **Connect** when you want cloud backup; the app uploads new captures and syncs any local screenshots not uploaded yet. Password is entered on Google’s secure browser page.

### Status feedback
The UI shows session state and whether the last screenshot was saved locally or uploaded.
