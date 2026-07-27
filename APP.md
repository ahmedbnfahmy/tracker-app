# Tracker

## Summary
Tracker tracks work time and, by default, captures your screen every 10 minutes (saved locally). Screenshots are optional and can be turned off anytime. Optional **Share session** can upload screenshots to Google Drive via an Apps Script web-app link — the desktop app does not store Google credentials.

## Features

### Start / Stop tracking
**Start** begins the timer (and screenshots if enabled). **Stop** asks for a task name, saves that segment under today's laps, and ends the session.

### Screenshots on / off
Enabled by default (**Shots on**). Click the button to turn captures off without stopping the timer; click again to turn them back on.

### Pause / Resume
Freeze the session timer without ending the session. Screenshots pause too; Resume continues from the same elapsed time.

### Todo list / Today's laps
Open with **Show lists** (right sidebar). Add tasks, check them off, delete them; stopped sessions appear under today's laps (each with delete ✕). Close with **Hide lists** or ✕.

### Session timer / Time today
Live session clock and persisted daily total.

### Share session
Paste an Apps Script `/exec` upload URL. While sharing is on, screenshots upload to your Drive folder (script runs as you; access set to Anyone). No OAuth/service-account files in Tracker. (UI may be hidden; code remains for later.)

### Last screenshot preview
Shows the newest capture at the bottom of the window.
