# VOSI Shared User Identity Backend

## What this milestone adds

- Email/password account registration with a six-digit email verification code.
- Passwords are stored as salted scrypt hashes; raw passwords are never persisted.
- Verification codes expire after 10 minutes and are limited to five attempts.
- Opaque bearer sessions are random, stored only as SHA-256 hashes, expire after 30 days, and can be revoked by logout.
- A paired Android, desktop, or browser device can be explicitly linked to one account using both the account session and its existing device credential.
- Account owners can list and unlink their own devices. Unlinking removes the account association; device credential revocation remains a separate device-management operation.
- The profile sync endpoint accepts only a versioned AES-256-GCM envelope and stores it without decrypting it. Writes use optimistic revisions to prevent silent cross-device overwrites.

## Required backend environment

Configure these secrets on the API service before enabling account registration:

- `VOSI_IDENTITY_CHALLENGE_SECRET`: random secret of at least 32 characters.
- `VOSI_SMTP_HOST`, `VOSI_SMTP_PORT` (normally 587), `VOSI_SMTP_USERNAME`, `VOSI_SMTP_PASSWORD`, `VOSI_SMTP_FROM`: SMTP delivery credentials.

Without these settings, registration is disabled rather than silently creating unverified accounts. Use a dedicated SMTP credential and secret manager; never commit secrets.

## API outline

- `POST /identity/register` — create account and send verification email.
- `POST /identity/verify-email` — verify the six-digit code.
- `POST /identity/login` — return a bearer session after verification.
- `GET /identity/me` and `POST /identity/logout`.
- `POST /identity/devices/link?device_id=...` — account bearer plus `X-VOSI-Device-Token`.
- `GET /identity/devices`, `DELETE /identity/devices/{device_id}`.
- `GET /identity/profile`, `PUT /identity/profile`.

## Encryption boundary and important next step

The server never receives profile plaintext or a profile decryption key. Each client must encrypt profile data before upload and decrypt only after download. The current Android profile uses a device-local Android Keystore key, so it cannot yet be uploaded as-is and decrypted on another device. Cross-device key provisioning/recovery (for example, user-mediated QR transfer or a recovery key) must be implemented and reviewed before turning on Android profile sync. Do not upload the existing local profile in plaintext.

## Not included

- No merchant credentials, cookies, payment data, OTPs, UPI PINs or CVVs.
- No merchant OAuth connections or checkout execution.
- No production email provider credentials or deployment.
- No desktop frontend changes and no claim of physical-device testing.

The backend still uses the existing SQLite single-instance deployment model. Configure persistent storage and a single API instance until the planned PostgreSQL migration.
