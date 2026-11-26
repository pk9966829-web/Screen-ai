# VOSI single-node production deployment

This is the first production deployment profile for a **single API instance**. It uses persistent SQLite databases and a persistent account-upload volume. It is not a horizontally scalable PostgreSQL deployment.

## What the stack provides

- Python 3.12 API container running as a non-root user
- Persistent volume for agent tasks, account identity, companion memory, screen history and account screenshots
- Caddy reverse proxy with automatic HTTPS certificates for the configured domain
- Liveness and readiness probes
- Explicit CORS allow-list
- Strict multi-tenant mode, which requires account sessions on legacy screen/history/task APIs and disables shared local-only Gmail, browser-bridge, WhatsApp and letter-file integrations
- Restart policy and Docker health checks

## Deploy

1. Provision a Linux VM with Docker Engine and the Docker Compose plugin.
2. Point the DNS A/AAAA record for `VOSI_DOMAIN` to the VM. Allow inbound TCP ports 80 and 443 (and UDP 443 for HTTP/3).
3. Copy `.env.production.example` to `.env` in this directory and replace every placeholder. Use a long random `VOSI_AGENT_TOKEN`, a separate random `VOSI_IDENTITY_CHALLENGE_SECRET` of at least 32 characters, a real AI provider key, and a supported transactional email provider (SMTP is recommended for hosted production).
4. Set `VOSI_DOMAIN` and `VOSI_CORS_ORIGINS` to your real API domain and exact frontend origins. Never use `*` in production.
5. Ensure the desktop and mobile clients send `X-VOSI-Account-Token` when calling legacy `/ask`, `/screen`, `/history`, `/workflow`, `/state`, `/task`, `/awareness`, and companion-memory routes. Do not launch hosted multi-user traffic until this client integration has been tested.
6. Start the stack:

   ```bash
   docker compose up -d --build
   ```
7. Check status and readiness:

   ```bash
   docker compose ps
   docker compose logs -f api
   curl https://$VOSI_DOMAIN/health/ready
   ```

## Persistence and backups

All application SQLite databases and account screenshots are stored in the `vosi_data` named volume mounted at `/data`. Back up this volume regularly, encrypt backups, and test restores before upgrades. Stop the API or use SQLite's online backup mechanism for consistent snapshots; do not copy a live SQLite database file with an ordinary file copy.

Keep one API replica. SQLite is the supported store in this deployment profile; multiple API replicas or multiple cloud workers sharing this volume are not supported. Do not put the SQLite volume on an unreliable network filesystem.

## Security operations

- Terminate public TLS at Caddy; do not publish port 8001 directly.
- Keep `.env` outside source control and restrict VM access.
- Rotate account, agent and provider credentials if exposed.
- Configure firewall access to only ports 80/443 and administrative SSH.
- Monitor `/health/live`, `/health/ready`, container restarts, disk usage and database backup success.
- The cloud-worker lease API accepts an authenticated `X-VOSI-Account-Token` in multi-tenant mode and scopes claims, heartbeats, results and expired-claim recovery to that account. The external worker must keep its account session and worker token in a secret store; do not share one worker session between accounts.
- Gmail, WhatsApp, the legacy browser bridge and shared letter-file routes remain disabled in multi-tenant mode until account-specific connector authorization is implemented.

## Current production limits

- SQLite single-instance only; PostgreSQL migration and multi-instance coordination are not included.
- Screen frame buffers and live context are per-process memory and reset on restart. Durable screen metadata and task events survive in the volume.
- Android WorkManager remains best-effort and does not guarantee real-time background execution after force-stop or aggressive battery restrictions.
- Physical Android, Windows, Chrome and production-domain tests are still required.
- This configuration does not deploy itself to a cloud provider; a VM, DNS name, secrets and SMTP account must be supplied by the operator.
- A cloud worker adapter is a separately deployed process and is not included in this Compose stack. It must use a real browser automation adapter, validate receipts and store its account session securely. The API lease endpoint alone does not perform web actions.

## Local Gmail OAuth for transactional email

For local development, the backend can send account-verification and QR device-approval emails through Gmail API without a Gmail App Password.

1. In Google Cloud, enable the Gmail API and create an OAuth client with type **Desktop app**. Add your Google account as a test user if the OAuth app is in Testing mode.
2. Put the downloaded client JSON in `backend/gmail_oauth_credentials.json`, or set `VOSI_GMAIL_OAUTH_CLIENT_FILE` to its local path. Never commit this file.
3. In `backend/.env`, set `VOSI_EMAIL_PROVIDER=gmail_oauth`, `VOSI_GMAIL_FROM` to the authorized Gmail sender address, and optionally set the client/token file paths.
4. From the backend directory, run `python authorize_gmail_email.py`. A browser opens for Google consent. The backend saves a send-only refresh token to `gmail_oauth_token.json`; keep it private and never commit it.
5. Restart the backend and check `GET /health/ready`. Both account verification and QR approval now use the same configured provider.

The transactional mailer requests only `https://www.googleapis.com/auth/gmail.send`. The existing interactive Gmail connector remains separate and keeps its own permissions and token. Google OAuth apps left in External/Testing mode can have refresh tokens expire after seven days; reauthorize when required or complete Google's production publishing/verification requirements before relying on this for long-running service. For hosted production, prefer a dedicated SMTP or transactional-email provider unless the Gmail OAuth client and refresh token are provisioned and managed securely on the server.

## Secure QR account pairing

The web-to-Android QR flow is registered at `/identity/pairing` and requires an already verified CHERRY AI account on the web side.

- Set `VOSI_PUBLIC_API_URL` to the public API origin (for example, `https://api.example.com`). It must be reachable from the Android phone and from the browser used to open the approval email.
- Configure the selected transactional email provider. The same provider sends account-verification and device-approval emails. SMTP remains supported; local Gmail OAuth uses the send-only Gmail scope.
- The frontend must be served from an origin listed in `VOSI_CORS_ORIGINS`. Configure its API URL in the web pairing panel; production deployments must use HTTPS.
- The QR credential expires after 2 minutes and can be scanned once. The email approval expires after 5 minutes. Opening the approval page is read-only; the owner must press **Approve device** or **Deny**.
- The Android app stores the returned device credential encrypted with Android Keystore. Device bearer tokens, QR tokens, email approval tokens and polling tokens are not stored in plaintext by the API.

For local LAN testing, start the backend with `--host 0.0.0.0`, use the computer's LAN address (not `127.0.0.1`) as the web API URL so the Android phone can reach the backend, and allow the backend port through the firewall only on the trusted network. If `VOSI_PUBLIC_API_URL` is unset, the approval link uses the API origin from the QR request. If you set it, use that same LAN origin. Do not use plain HTTP on public networks.

The end-to-end test must use a real verified account, reachable SMTP inbox, a browser session signed into that account, and a physical Android device with camera permission. Verify both approval and denial paths, QR expiry, duplicate scans, and that the device appears under `GET /identity/devices` only after approval.


## Google sign-in for CHERRY AI web accounts

The web mobile-pairing panel supports both email/password accounts and Google sign-in. Google sign-in uses Google's verified ID token and does not require a Google client secret in the web app.

1. In Google Cloud Console, create an OAuth client with type **Web application** (separate from the Gmail send-only Desktop OAuth client).
2. Add authorized JavaScript origins for the exact frontend origins used during testing, such as `http://localhost:5173`, `http://localhost:1420`, and your deployed frontend origin. Add the exact LAN origin if signing in from a LAN-hosted browser; Google does not accept wildcard origins.
3. Copy the Web client ID (not the client secret) to `VOSI_GOOGLE_CLIENT_ID` in `backend/.env`.
4. Restart the backend. The web UI fetches the public client ID from `GET /identity/config` and renders Google's sign-in button when configured.
5. Google sign-in verifies the ID token's signature, audience, issuer, and verified-email claim server-side. It creates or securely links a verified account, then issues the same CHERRY AI account session used by email/password login.

Do not put a Google client secret in frontend code or Git. The Gmail send-only OAuth client remains separate and is only for transactional email delivery.
