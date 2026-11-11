# VOSI Android Companion

Starter native Android project for the VOSI desktop companion.

## Target device
- Redmi A7 Pro
- Xiaomi HyperOS 3.0.2.0.WBVINXM
- Android 16

## Current starter milestone
- Native Kotlin Android app structure.
- Runtime permission request for contacts.
- Local contact lookup by display name.
- Phone call action only after an explicit in-app confirmation.
- No cloud upload of contacts or phone numbers.

## Open and build
1. Install Android Studio.
2. Open the `android` folder in Android Studio.
3. Allow Gradle sync to finish.
4. Connect the Redmi phone with USB debugging enabled, or use Android Studio's wireless debugging.
5. Run the `app` configuration on the phone.

The project uses Android Gradle Plugin 8.9.2, Kotlin 2.1.20, Java 17, compile SDK 36 and minimum SDK 26. Android Studio may ask to install Android SDK Platform 36.

## Pair the phone with VOSI

The app now supports one-time device pairing and stores its device credential encrypted with an AES key held by Android Keystore.

1. Configure `VOSI_AGENT_TOKEN` in the backend environment and start the backend.
2. Open `http://127.0.0.1:8001/docs`, authorize with the VOSI agent token, and call `POST /agent/devices/pairing` using platform `android` and a label such as `My Android phone`.
3. Copy the returned single-use pairing code (expires after five minutes).
4. Connect the phone over USB and forward the backend port from your computer:
   ```powershell
   adb reverse tcp:8001 tcp:8001
   ```
5. Open VOSI Companion, leave the backend URL as `http://127.0.0.1:8001`, paste the code, and tap **Pair this phone with VOSI**.
6. Use **Check VOSI connection** to send an authenticated heartbeat. **Disconnect this phone** revokes the device credential on the backend and clears the encrypted local credential.

For a different trusted network or a remote backend, enter its HTTPS base URL instead. Do not expose the development backend to the public internet.

## HyperOS setup (after installing)
- Allow Contacts and Phone permissions only when prompted.
- The pairing heartbeat runs when the companion is opened or when you tap Check VOSI connection; persistent background execution is a later milestone.
- Do not enable Accessibility until the feature and its exact purpose are presented in the app.
- Keep the phone and desktop on a trusted local network for local development pairing.

## Security boundaries
VOSI Companion must not request or collect banking credentials, payment PINs, lock-screen credentials, passwords or OTPs. It must not attempt to bypass Android or HyperOS security controls. Pairing must use authentication and encrypted transport before remote commands are enabled.


## Personal WhatsApp notification integration (first milestone)

This milestone connects the Android companion to the user's existing WhatsApp installation without the WhatsApp Business API or AI credits.

### What it supports
- Reads notification previews posted by the official WhatsApp Android package (`com.whatsapp`).
- Keeps up to 30 recent previews in private app-local preferences on the phone.
- Shows recent previews in VOSI Companion.
- Offers a reply button when the active WhatsApp notification exposes an Android `RemoteInput` reply action.
- Opens a new WhatsApp chat using a `wa.me` link; the user reviews the recipient and taps Send inside WhatsApp.
- Provides a button to clear locally saved notification previews.

### Enable on the Redmi phone
1. Build and install the updated `android` project.
2. Open VOSI Companion.
3. Tap **Enable WhatsApp notification access**.
4. Android Settings opens. Find **VOSI WhatsApp notification access** / **VOSI Companion** and enable it.
5. Return to VOSI Companion and tap **Refresh recent WhatsApp messages**.
6. Send a test message to the phone from another WhatsApp account. Ensure WhatsApp notification previews are enabled.
7. Tap **Reply** on a message to test notification quick reply, if WhatsApp exposes that action.

HyperOS menu wording can vary. If notification access is not shown, look under Settings > Notifications > Device & app notifications / Notification access.

### Important limitations and privacy
- This is notification access, not full WhatsApp account or chat-database access. Messages hidden by notification privacy settings, muted chats, or notifications that WhatsApp does not post cannot be read this way.
- Quick reply works only while the matching notification is still active and exposes a reply action.
- Starting a new chat opens WhatsApp with a prefilled message; the user must review and tap Send.
- Notification previews are stored locally on the phone (up to 30). Use the in-app clear button to erase them.
- No WhatsApp message content is uploaded to VOSI's backend in this milestone.
- The phone can now register as a VOSI Android device, but the desktop voice assistant does not yet dispatch live agent tasks to the phone. The task-execution adapter is a separate next step; do not expose an unauthenticated network endpoint for message access.
- The listener does not use Accessibility Service and does not request payment, PIN, password, or OTP access.
