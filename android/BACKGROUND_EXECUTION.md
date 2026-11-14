# VOSI Android background task execution

The Android app registers a persistent WorkManager schedule at application startup.

## What runs in the background

- A one-time worker is queued when the app first initializes, followed by a periodic worker with Android's minimum 15-minute interval.
- Work runs only when Android reports network connectivity.
- The worker uses the existing encrypted Android Keystore device credential and authenticated agent APIs.
- It can execute only the already-registered low-risk Android-local capabilities: device.volume.set and device.alarm.create.
- Each execution is reported to the backend with a verified receipt. Completion/failure updates can be surfaced as Android notifications.
- Backend execution claims expire after five minutes without a receipt, allowing a later worker run to recover work abandoned by a crashed process.
- Existing foreground polling remains available while the Companion activity is open.

## Platform limits

WorkManager is persistent and survives normal process death and device reboot, but it is best-effort: Android controls scheduling, network availability, Doze, battery optimization, and vendor power management. Periodic work is not real-time and has a minimum 15-minute interval. A user force-stopping VOSI can prevent work until the app is opened again. HyperOS may require the user to allow background activity or autostart for more reliable delivery.

This is not an always-on foreground service and does not promise continuous listening or instant task execution. The worker does not perform calls, send WhatsApp messages, submit purchases, access payment credentials, or approve high-risk tasks. Those actions remain outside this background executor and retain explicit confirmation requirements.

## Development test

1. Install and open the updated app at least once.
2. Pair the phone with the backend as usual.
3. Keep the backend reachable over HTTPS or the trusted USB ADB reverse connection.
4. Queue a low-risk phone task such as set phone volume to 40%.
5. Close the VOSI activity without force-stopping the app. WorkManager should process queued work when Android grants a network-constrained execution window.
6. Check the VOSI task receipt/notification and backend GET /agent/tasks/updates.

A physical-device test is still required, especially on Xiaomi HyperOS. The CI APK build validates compilation, not OEM background-delivery behavior.
