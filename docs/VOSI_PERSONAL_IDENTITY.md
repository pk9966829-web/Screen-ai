# VOSI Personal Identity & Secure Account Vault

## First implementation slice: Android profile onboarding

This milestone introduces a native Android first-run identity setup without changing the existing desktop frontend or existing companion screen.

### Profile fields

- Display name
- Preferred language
- Country and currency
- Optional preferred brands
- Optional usual shopping budget

Every field except the default locale values is optional. Users can continue without editing an existing profile or delete the saved profile.

### Storage and privacy

- Profile JSON is encrypted with AES-GCM using a key held by Android Keystore.
- Only ciphertext and the GCM IV are written to app-private preferences.
- Android backup is disabled by the existing application manifest.
- Profile values are not sent to the backend in this milestone.
- No merchant password, OTP, UPI PIN, CVV, card number, or payment credential is requested or stored.
- Delivery addresses and payment preferences are deliberately deferred until a reviewed account identity and encrypted sync design exists.

### Cross-device account design (next slice)

The current VOSI pairing model authenticates individual devices; it is not yet a user-account system. Do not treat a device ID as a global user identity. The next backend milestone must introduce:
1. A real user account identifier and verified sign-in/recovery flow.
2. Explicit device linking and revocation under that account.
3. Server-side encryption/key management and per-field access controls for synced profile data.
4. Merchant OAuth connections with least-privilege scopes, token rotation, revocation, and audit logs.
5. Merchant-specific adapters; only supported official authorization flows may connect accounts.
6. Immutable checkout previews and exact-digest approval before order submission.

Do not implement password scraping, browser-cookie extraction, shared raw payment credentials, or silent checkout. Users must enter OTPs and payment authentication directly in the merchant's trusted UI.

### Validation boundary

The GitHub Android APK workflow is the compile check. A physical Android device test is still required for onboarding, encrypted persistence, profile deletion, and the existing companion launch flow.
