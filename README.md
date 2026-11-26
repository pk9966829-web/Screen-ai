<div align="center">

<img src="screen%20ai/src/assets/logo.png" alt="CHERRY AI logo" width="160" />

# CHERRY AI — Screen Intelligence & Companion

Your screen-aware AI companion for web, Windows, and Android.

</div>

CHERRY AI helps users understand their screens, get guided through workflows, search and research the web, and continue a shared companion conversation across paired devices.

## Core features

- **Screen understanding:** observe a user-shared screen, explain what is visible, summarize, and guide the next step.
- **Permissioned Chrome companion:** open browser tabs, search supported public listings (including Flipkart), and read visible page text only after the user grants the current origin permission. It does not bypass sign-in, CAPTCHA, checkout, or payment flows.
- **Shared AI companion:** account-scoped chat, task planning, task history, and companion memory across paired devices.
- **Offline knowledge:** web and Android bundle 491 fact entries and 17 greeting groups; supported local questions can be answered without backend/API access.
- **Windows local commands:** open supported apps/sites, web searches, calculations, local time, screenshots, PC lock, volume controls, and scheduled timers/alarms.
- **Android companion:** native chat, profile, linked-device controls, tasks, phone alarm/volume tools, notifications, call history, and secure device credentials.
- **Secure account/device linking:** email/password or Google account sign-in, verified email, short-lived QR, email approval, Android QR scan, and encrypted device credential storage.
- **Call receptionist:** opt-in Exotel/GPT-Live bridge with caller consent, text summaries and structured callback information; optional Fish Audio TTS with emotion cues. Call audio recording is not enabled.
- **Gmail:** a separate local interactive Gmail connector and send-only Gmail OAuth for transactional verification/device-approval emails.

## Platform boundaries

- Windows-only local commands run only through the local backend/desktop integration.
- Wi-Fi/Bluetooth commands open Windows Settings rather than directly changing radio state.
- Shutdown/restart are confirmation-only; they are not executed by the local command router.
- Android WorkManager is best-effort and not an always-on service; OEM battery controls may delay tasks.
- Browser interaction is bounded by extension permissions and registered capabilities.
- Hosted multi-user mode requires account-scoped configuration, persistent storage, HTTPS, and the deployment checklist.

## Development docs

- [Single-node backend deployment](backend/DEPLOYMENT.md)
- [Account isolation and rollout](backend/ACCOUNT_ISOLATION.md)
- [Chrome extension setup](screen%20ai/chrome-extension/README.md)
- [Windows local commands and limitations](docs/CHERRY_AI_LOCAL_COMMANDS.md)
- [Call receptionist setup](docs/cherry-ai-call-receptionist.md)
- [Android background execution](android/BACKGROUND_EXECUTION.md)
- [Android roadmap](docs/VOSI_ANDROID_APP_ROADMAP.md)

## Local development

Run the backend from `backend` after configuring its private `.env`:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Run the web app from `screen ai`:

```powershell
npm.cmd ci
npm.cmd run dev -- --host 0.0.0.0
```

For phone testing on the same Wi-Fi, configure the web pairing panel with the computer's LAN IP (not `127.0.0.1`), keep the backend reachable, and follow the email-approved QR flow. Gmail sending and Google sign-in require separate OAuth configuration; do not commit credentials or tokens.
