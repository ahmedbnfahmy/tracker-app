# Tracker

## Summary
Tracker tracks work time and, by default, captures your screen every 10 minutes (saved locally). Screenshots are optional and can be turned off anytime. Optional **Share session** can upload screenshots to Google Drive via an Apps Script web-app link — the desktop app does not store Google credentials.

## Features

### Start / Pause / Resume / Stop
**Start** begins the timer (and screenshots if enabled). While running the same button becomes **Pause**, then **Resume**. **Stop** asks for a task name, saves that segment under today's laps, and ends the session. Screenshots pause with the timer.

### Screenshots on / off
Enabled by default (**Shots on**). Click the button to turn captures off without stopping the timer; click again to turn them back on.

### Todo list / Today's laps
Open with **Show lists** (right sidebar). Add tasks, check them off, delete them; stopped sessions appear under today's laps (each with delete ✕). Close with **Hide lists** or ✕.

### Session timer / Time today
Live session clock and persisted daily total.

### Share
**Share off / Share on** toggles uploading to your Drive link. First time on, paste the Apps Script `/exec` URL; after that the toggle just enables/disables upload (persists across restarts). **↗** opens the public Drive folder. See `drive_upload/README.md` for one-time setup.

### Last screenshot preview
Shows the newest capture at the bottom of the window.
