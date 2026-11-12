# VOSI Android App — product milestone plan

The Android app is a core VOSI client, not a temporary permission helper. Keep it in the release plan alongside desktop and cloud execution. The existing Android project remains in `android/` with application ID `com.vosi.companion`; its CI APK build must stay enabled.

## Existing native foundation

- Native Android application and secure paired-device credential storage.
- One-time pairing with VOSI and device heartbeat/disconnect.
- Tap-to-talk speech recognition and Android TextToSpeech replies.
- Phone task requests to paired VOSI devices.
- Android alarms and volume controls where supported and permissioned.
- Optional WhatsApp notification-preview access; it does not read WhatsApp's private database.
- Task completion notifications and optional spoken browser recommendations.
- Existing UI is a functional foundation, not the final mobile product experience.

## Product direction

The Android app should become the user's always-available mobile VOSI companion:
- A polished native companion home with a clear connection state, voice conversation, task activity, approvals, and settings.
- Secure account/device identity and pairing with desktop and cloud VOSI.
- Push notifications for task progress, approval requests, failures, and completed work.
- Explicit approval screens showing the exact merchant, items, delivery address, total, and payment method before any order submission.
- User-controlled permissions for microphone, contacts, notifications, screen/accessibility integrations, and background behaviour.
- Reliable background task updates using Android-supported foreground services or push notifications where policy permits; do not promise unrestricted background execution or wake-word listening.
- Optional voice wake experience only after a separate privacy, battery, and Android policy review.
- Cross-device task handoff: phone can ask desktop/browser/cloud VOSI to do work and receive verified completion updates.

## Implementation sequence

1. **Mobile app foundation:** modern native navigation, onboarding, secure sign-in/device pairing, connection diagnostics, and accessible settings.
2. **Companion experience:** conversation history, tap-to-talk, TTS playback controls, and task timeline.
3. **Cloud notifications:** push delivery, deep links into task detail, notification actions, token rotation, and delivery tests.
4. **Approval centre:** immutable checkout summary display, digest binding, approve/reject actions from the originating phone, and audit trail.
5. **Device bridge:** scoped Android capabilities, permission education, foreground-service lifecycle, and honest capability reporting.
6. **Release hardening:** offline states, retry UX, encrypted storage, privacy disclosures, crash reporting controls, accessibility, APK/AAB signing, and physical-device testing.

## Cloud browser milestone relationship

The cloud browser worker can continue safe, public read-only searches while the phone app is closed, once deployed. The Android app is the user's companion and notification/approval surface; it is not required to keep the cloud worker alive. A real order still requires a separate exact-checkout approval from the user, and payment secrets must stay inside the merchant's trusted UI.

## Current boundary

This document records the product direction and staged work. It does not claim the final mobile experience, push service, production cloud deployment, or background execution is already complete. The next dedicated product milestone after this cloud browser executor is the Android companion app experience and push/approval flow.