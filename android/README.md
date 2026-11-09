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

## HyperOS setup (after installing)
- Allow Contacts and Phone permissions only when prompted.
- If background pairing is added in a later milestone, enable VOSI Companion under Settings > Apps > Permissions > Background autostart (wording may differ by HyperOS release).
- Do not enable Accessibility until the feature and its exact purpose are presented in the app.
- Keep the phone and desktop on a trusted local network for future pairing.

## Planned milestones
1. QR-based authenticated local pairing with VOSI Desktop.
2. Remote contact lookup and call requests, with phone-side confirmation.
3. Additional user-approved Android controls using supported APIs.
4. Optional Accessibility Service for clearly disclosed screen interaction.
5. Call-message speech experiment. Android does not generally allow ordinary apps to inject audio into cellular-call uplink; this must not be represented as guaranteed.

## Security boundaries
VOSI Companion must not request or collect banking credentials, payment PINs, lock-screen credentials, passwords or OTPs. It must not attempt to bypass Android or HyperOS security controls. Pairing must use authentication and encrypted transport before remote commands are enabled.
