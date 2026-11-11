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
