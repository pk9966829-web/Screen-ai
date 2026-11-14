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
3. Copy `.env.production.example` to `.env` in this directory and replace every placeholder. Use a long random `VOSI_AGENT_TOKEN`, a separate random `VOSI_IDENTITY_CHALLENGE_SECRET` of at least 32 characters, a real AI provider key, and SMTP credentials.
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
- The shared cloud worker is intentionally disabled in multi-tenant mode until its leases and execution receipts are account-scoped.
- Gmail, WhatsApp, the legacy browser bridge and shared letter-file routes remain disabled in multi-tenant mode until account-specific connector authorization is implemented.

## Current production limits

- SQLite single-instance only; PostgreSQL migration and multi-instance coordination are not included.
- Screen frame buffers and live context are per-process memory and reset on restart. Durable screen metadata and task events survive in the volume.
- Android WorkManager remains best-effort and does not guarantee real-time background execution after force-stop or aggressive battery restrictions.
- Physical Android, Windows, Chrome and production-domain tests are still required.
- This configuration does not deploy itself to a cloud provider; a VM, DNS name, secrets and SMTP account must be supplied by the operator.
