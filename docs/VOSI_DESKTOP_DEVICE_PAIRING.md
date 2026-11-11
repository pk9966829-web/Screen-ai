# VOSI Windows desktop pairing

The Windows Tauri app can now register itself as a paired VOSI desktop device.

## Pair the PC

1. Start the VOSI FastAPI backend with `VOSI_AGENT_TOKEN` configured.
2. Open the backend Swagger page at `http://127.0.0.1:8001/docs`.
3. Authorize with the admin bearer token. Do not put this token in the desktop app, Chrome extension, or phone app.
4. Call `POST /agent/devices/pairing` with:
   ```json
   {"platform":"desktop","label":"VOSI on Windows"}
   ```
5. Copy the one-time code. It expires after five minutes.
6. In VOSI desktop, open Settings > Windows device connection, paste the code, and choose Pair this PC.

The desktop exchanges the one-time code directly with `POST /agent/devices/pair`. The returned device credential is stored through the Windows Credential Manager using the native keyring provider; it is not written to localStorage or a plain-text settings file.

## Current desktop executor

The Windows client sends a heartbeat every minute and polls the paired-device task queue every 15 seconds while VOSI is running. The first supported desktop task is `device.alarm.create`. Its task arguments must include integer `hour` (0–23) and optional integer `minute` (0–59). VOSI schedules the alarm with Windows Task Scheduler and sends an execution receipt to the backend.

This is an initial secure pairing and task-execution slice, not full Windows control. Volume percentage, Bluetooth/Wi-Fi toggles, arbitrary application control, shutdown/restart, and general-purpose desktop automation are not exposed through this task adapter yet. Existing direct VOSI desktop commands are separate from the agent queue.

## Disconnect

Choose **Disconnect this PC** in the same settings panel. VOSI revokes the server-side device credential and removes the local Windows Credential Manager entry.

## Network note

The default backend URL is `http://127.0.0.1:8001`, suitable only when the backend runs on the same Windows machine. For a phone-to-PC setup, both devices must reach the same trusted backend host; do not expose the development backend to the public internet. Use HTTPS, authentication, and network restrictions for remote deployments.

## Send a task from the Android companion

After pairing the Android phone, its Companion screen exposes a small command field. The first supported phone-originated commands are:

- `set an alarm for 5 PM on my PC` — routes a low-risk alarm task to the paired Windows desktop.
- `search body spray under 1000 on Flipkart` — routes a read-only product search to the paired Chrome extension.

The phone submits these through `POST /agent/tasks/request` with its own device credential. The server permits only low-risk, non-approval capabilities and only desktop/browser targets. It does not give the phone the administrator token. High-risk calls, WhatsApp replies, email sends, and arbitrary device commands are rejected by this route.

This is deliberately a first command set. Natural-language task planning, result notifications back to the phone, and broader desktop/Android actions are subsequent work.

## Phone task execution and completion updates

The paired Android Companion now polls its authenticated task queue while the app is open (every 20 seconds). Its first local task adapters are:

- `device.alarm.create`: schedules a phone alarm through Android AlarmManager and posts an alarm notification when it fires
- `device.volume.set`: adjusts Android media volume to a requested percentage and checks the applied stream volume before sending a success receipt

The phone also reads `GET /agent/tasks/updates`. That endpoint returns only tasks created by the authenticated phone's own device ID, with step states and execution receipts. Completed/failed tasks generate an Android notification when notification permission is enabled. This polling is foreground-only; it is not a promise of background or force-stopped delivery.

## Additional Windows task adapters

A paired Windows desktop now supports these low-risk task queue actions:

- `device.alarm.create`: schedule a one-time alarm with Windows Task Scheduler
- `device.volume.action`: volume up, down, mute, and unmute using Windows media keys
- `device.timer.create`: start a one-time timer (up to 24 hours)

Newly paired Windows devices register these capabilities. If a PC was paired before this update, disconnect and pair it again so the server grants the additional capability list.

The Android Companion accepts these initial commands:
- `set an alarm for 5 PM on my PC` or `set an alarm for 5 PM on my phone`
- `set phone volume to 70%`
- `mute PC`, `volume up`, `volume down`, or `unmute PC`
- `start a timer for 20 minutes on my PC`
- `search body spray under 1000 on Flipkart`

The phone-originated task endpoint validates an explicit capability/target allow-list. It rejects unsupported commands rather than creating tasks that no paired executor can perform.
