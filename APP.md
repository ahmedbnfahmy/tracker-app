# Tracker

## Summary
Tracker tracks work time and captures your screen every 10 minutes (saved locally). Optional **Share session** can upload screenshots to Google Drive via an Apps Script web-app link — the desktop app does not store Google credentials.

## Features

### Start / Stop tracking
Timer + screenshots only while a session is active.

### Pause / Resume
Freeze the session timer without ending the session. Screenshots pause too; Resume continues from the same elapsed time.

### Lap (named task segments)
While tracking, Lap saves the current segment with a name, lists it under **Today's laps**, and resets the session timer for the next task. Each lap row has a delete control (✕).

### Todo list
Add tasks, check them off, and delete them. Todos persist locally and sit above today's laps so you can plan work, then track time with Start / Lap.

### Session timer / Time today
Live session clock and persisted daily total.

### Share session
Paste an Apps Script `/exec` upload URL. While sharing is on, screenshots upload to your Drive folder (script runs as you; access set to Anyone). No OAuth/service-account files in Tracker. (UI may be hidden; code remains for later.)

### Last screenshot preview
Shows the newest capture at the bottom of the window.
