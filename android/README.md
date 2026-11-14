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
- While VOSI Companion is open, it checks the paired-device heartbeat and task queue every 20 seconds. Android background/force-stopped execution is not guaranteed.
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
- Phone-originated task requests are authenticated and restricted to explicitly supported low-risk capabilities, plus Windows shutdown/restart requests that require confirmation on the paired PC. WhatsApp message sends and phone calls are not silently dispatched by the task queue.
- The listener does not use Accessibility Service and does not request payment, PIN, password, or OTP access.

## Phone task execution and completion alerts

After pairing, the Companion can execute these phone-local tasks while the app is open:

- Set media volume to a percentage, e.g. `set phone volume to 70%`.
- Schedule an alarm, e.g. `set an alarm for 6:30 AM on my phone`.

The Android alarm uses AlarmManager's inexact idle-compatible scheduling. Android may delay it under power-saving conditions. The alarm receiver posts an alarm notification; enable VOSI notifications in Android settings for the visible alert and sound.

The phone can also send commands to paired devices:
- `set an alarm for 5 PM on my PC`
- `mute PC`, `volume up`, `volume down`, `unmute PC`
- `start a timer for 20 minutes on my PC`
- `search body spray under 1000 on Flipkart`

Task completion updates are fetched from the backend using the phone's own device credential. Completed/failed tasks create Android notifications when notification permission is granted. The task update endpoint returns only tasks originally requested by that paired phone.

When a Flipkart search completes, the Companion can optionally speak a short top-three product summary. Enable **Speak browser recommendations** in the Companion screen. Speech is off by default and runs only while the Companion is open; it uses Android's built-in text-to-speech engine. Ranking is a transparent heuristic based on visible ratings, review counts, and then price—not an AI quality guarantee. The completion notification remains available even when speech is disabled.

If the Windows PC was paired before these desktop capabilities were added, disconnect and pair the PC again. The Android phone can keep its existing pairing because its task-request capability is unchanged. Keep the Companion open to execute and receive updates; persistent background operation is not yet implemented.


## Windows settings and power requests from the phone

The phone can request `open Bluetooth settings on PC` or `open Wi-Fi settings on PC`. VOSI opens the matching Windows Settings page; the user operates the switch there. VOSI does not silently toggle radios. Commands `shut down my PC` and `restart my PC` create approval-gated tasks. The paired Windows app shows a confirmation dialog; only accepting on the PC releases the action, while declining cancels it. The phone cannot approve its own power request. Keep the Windows VOSI app open. Re-pair the Windows PC if it was paired before these capabilities were added; the phone does not need to be re-paired.


## Chrome browser commands from the phone

The paired phone can now send these browser tasks to Chrome:
- `open https://google.com in Chrome` — opens a new HTTPS tab.
- `read this page` — reads rendered text from the active Chrome tab and returns a completion notification with the page title.

For page reading on a website other than the built-in Flipkart integration, open that website in Chrome, click the VOSI Browser Companion icon, and choose **Enable current website**. Chrome asks permission for that one HTTPS origin. The extension does not request blanket website access at install time. If Chrome was paired before this feature was added, disconnect and pair Chrome again to register `browser.read_visible_page`. Page content is treated as untrusted text; VOSI does not follow instructions embedded in web pages. This milestone does not click arbitrary controls, sign in, submit forms, or purchase items.


## VOSI native mobile app (0.2.0)

The launcher now opens a native Jetpack Compose experience with five destinations:
- **Home** — VOSI companion welcome, voice entry point, and shortcuts.
- **Chat** — entry into the existing voice/companion workspace.
- **Tasks** — activity and approval overview, with live task timeline integration planned next.
- **Devices** — phone, Windows and browser connection overview plus a shortcut to existing pairing controls.
- **Profile** — VOSI identity registration, six-digit email verification, sign-in and sign-out against the shared `/identity` API.

The account session token is encrypted with an AES-GCM key held by Android Keystore. The account API uses the backend URL configured under Profile > Advanced server settings. For a phone connected to a development PC over USB, run `adb reverse tcp:8001 tcp:8001` and keep the development URL as `http://127.0.0.1:8001`. For normal use, configure the deployed HTTPS API URL. Registration remains unavailable until the backend identity challenge secret and SMTP settings are configured.

The older native companion activity remains in the app and is opened from the new Chat and Devices destinations. Existing device pairing, voice, task polling, phone tools and WhatsApp notification features are retained; the Compose screens are the new app shell, not a replacement for those capabilities.

### Current scope and limitations
- The Tasks screen is currently an app overview; live task history and approvals still need their dedicated API/UI integration.
- Chat currently opens the existing voice companion workspace; a fully native chat transcript/composer is a follow-up.
- The Devices screen opens the existing pairing controls; richer device inventory and account linking UI is a follow-up.
- The backend profile endpoint accepts only encrypted profile envelopes. The existing local profile key is device-local, so profile sync is intentionally not enabled until cross-device key recovery is designed.
- This branch has not been tested on a physical Android phone. CI APK build status should be checked on the pull request.
