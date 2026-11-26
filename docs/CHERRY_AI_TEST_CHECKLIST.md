# CHERRY AI end-to-end test checklist

This checklist separates automated builds/tests from live user-device testing. Do not treat CI compilation as proof that an OAuth flow, QR scan, background task, or call works on a real device.

## 1. Local backend and web
- [ ] Configure backend `.env` with AI provider, identity challenge secret, and agent token.
- [ ] Start backend at port 8001 and confirm `/health/ready` and `/docs`.
- [ ] Install web dependencies and start Vite.
- [ ] Confirm screen observation only starts after the user grants screen capture.

## 2. Google sign-in and email
- [ ] Create a Google OAuth Web client; add exact JavaScript origins for localhost, Tauri dev, LAN test origin, and deployment.
- [ ] Set `VOSI_GOOGLE_CLIENT_ID` in backend `.env`, restart, and confirm web Connect-to-Mobile shows Google sign-in.
- [ ] Register Android OAuth client for `com.vosi.companion` with debug signing SHA-1 (and release SHA-1 before release).
- [ ] Test Google sign-in from web and Android Profile; verify each returns the same CHERRY AI account.
- [ ] Test email/password registration, 6-digit verification, login, logout, and Google linking to an existing verified email.
- [ ] Configure Gmail send-only OAuth separately using the Desktop OAuth client, sender `pk9966829@gmail.com`, and `gmail.send` scope.
- [ ] Run `python authorize_gmail_email.py`; verify local token file remains ignored by Git.
- [ ] Trigger a real verification/QR approval email and confirm it arrives and the approval link is correct.

## 3. Secure mobile pairing
- [ ] On web, sign in and generate a QR.
- [ ] Scan it on Android and confirm the backend origin shown before approving.
- [ ] Approve the email request; confirm Android exchanges the one-time credential.
- [ ] Verify paired-device listing and connection state.
- [ ] Test denial, QR expiry, approval expiry, duplicate scan, revoked device, and network interruption.

## 4. Offline knowledge
- [ ] Ask exact fact questions in web and Android with backend disconnected.
- [ ] Ask a question with common filler words (for example, “what is the capital of India?”).
- [ ] Test greetings and a question not present in the offline facts; confirm unknown questions fall back to online AI when configured.
- [ ] Verify web/mobile offline assets remain identical (CI).

## 5. Windows local commands
- [ ] Open an allow-listed app and website.
- [ ] Run Google/YouTube/Flipkart search.
- [ ] Calculate a simple expression.
- [ ] Set volume to a percentage, mute, unmute, and volume up/down.
- [ ] Lock PC and save screenshot.
- [ ] Set a 20-minute timer and an alarm for a future time; confirm alert while awake and logged in.
- [ ] Confirm Wi-Fi/Bluetooth opens Settings (does not directly toggle).
- [ ] Confirm shutdown/restart are confirmation-only.

## 6. Chrome extension
- [ ] Load unpacked extension from `screen ai/chrome-extension`.
- [ ] Pair browser using a one-time code.
- [ ] Search a supported public Flipkart listing; compare visible product results and verify voice response.
- [ ] Grant a separate origin permission before testing page reading on another site.
- [ ] Disconnect/revoke and verify heartbeat reports revoked/offline.

## 7. Android and background behavior
- [ ] Install the debug APK and test profile, chat, tasks, devices, QR scanner, and call history.
- [ ] Test alarms and volume tasks.
- [ ] Test WorkManager while the app is closed but not force-stopped; verify task receipt and notification.
- [ ] Test under Xiaomi/HyperOS battery/autostart restrictions.
- [ ] Test Android call-screening permission and incoming-call UI.

## 8. Call receptionist
- [ ] Configure Exotel, public WSS, GPT-Live key, owner user ID, and consent prompt.
- [ ] Test caller consent, caller transcript, summary, outcome, callback details, and owner-only history.
- [ ] Confirm audio recording remains disabled.
- [ ] Test Fish Audio TTS with a real API key/voice ID, emotion cues, and GPT-Live fallback.
- [ ] Test real inbound call and conditional forwarding only after the full call path and carrier charges are verified.

## 9. Production and release
- [ ] Deploy HTTPS backend and frontend; configure CORS, public API URL, secrets, backups, and readiness.
- [ ] Test account isolation and device revocation in hosted mode.
- [ ] Reconcile integration branches and merge the approved integration PR into main.
- [ ] Create release-signed Android APK/AAB and verify update/upgrade path.
- [ ] Publish Chrome extension and Android release only after security, privacy, and live-device tests pass.
