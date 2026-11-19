# VOSI Cloud Execution Engine — deployment foundation

## What this milestone adds

- A separately deployable container image for the existing VOSI FastAPI backend.
- An authenticated cloud-worker API at `/cloud-worker`.
- A server-side capability allow-list. Only explicitly configured, low-risk, reversible capabilities can be leased to a cloud worker.
- Task leases with heartbeat renewal and verified execution receipts.
- Expired-lease recovery for low-risk reversible work only.
- Ambiguous or irreversible work is deliberately **not** replayed after a worker disappears. It remains running for manual reconciliation rather than risking a duplicate order or message.
- CI coverage for worker authentication, claim, heartbeat, receipt, and recovery behaviour.

The existing desktop frontend and Android UI are unchanged.

## Configure a single-instance cloud API

Required environment variables:

| Variable | Purpose |
|---|---|
| `VOSI_AGENT_TOKEN` | Existing administrative agent API token |
| `VOSI_CLOUD_WORKER_TOKEN` | Separate secret used only by cloud worker processes |
| `VOSI_CLOUD_WORKER_ID` | Stable worker identity, e.g. `browser-worker-1` |
| `VOSI_CLOUD_WORKER_PLATFORM` | Registered target platform; currently `browser` for the default worker |
| `VOSI_CLOUD_WORKER_CAPABILITIES` | Comma-separated capabilities; default `browser.search_products` |
| `VOSI_CLOUD_WORKER_LEASE_SECONDS` | Lease timeout from 30 to 900 seconds; default 180 |
| `VOSI_AGENT_DB_PATH` | Persistent database file path |

Build from the repository root:

```sh
docker build -f backend/Dockerfile -t vosi-cloud-api ./backend
docker run --rm -p 8001:8001 \
  -e VOSI_AGENT_TOKEN='replace-with-a-long-random-secret' \
  -e VOSI_CLOUD_WORKER_TOKEN='use-a-different-long-random-secret' \
  -e VOSI_AGENT_DB_PATH=/data/vosi_agent.db \
  -v vosi-data:/data \
  vosi-cloud-api
```

Use a platform with an always-on service and a persistent disk mounted at `/data`. Do not scale this SQLite deployment to multiple API replicas or attach multiple writers to a shared SQLite file. The current runtime is single-instance SQLite; production horizontal scaling requires a PostgreSQL-backed runtime and migration, which is not part of this PR.

Keep the administrative token and worker token separate. Store both in the hosting provider's secret manager, use HTTPS, restrict network ingress, and rotate credentials if exposed. Do not commit real secrets.

## Worker protocol

A separately deployed worker authenticates with:

```http
Authorization: Bearer <VOSI_CLOUD_WORKER_TOKEN>
```

1. `GET /cloud-worker/health` returns its server-configured identity and capability allow-list.
2. `POST /cloud-worker/claim` leases one eligible step and returns the task goal, step arguments, and idempotency key. It returns null task/step when no work is ready.
3. While processing, call `POST /cloud-worker/{task_id}/steps/{step_id}/heartbeat` before the lease expires.
4. Submit `POST /cloud-worker/{task_id}/steps/{step_id}/result` with a verified receipt. A task is completed only when the runtime accepts a successful, verified, non-empty receipt.

The worker's platform and capabilities come from server environment variables, not from a task or model response. Approval-gated and irreversible capabilities are filtered out even if accidentally included in the environment list.

## Retry and duplicate-action policy

- An expired claim is requeued only when its capability metadata says low-risk, reversible, and not approval-required.
- An expired irreversible/high-risk claim is left in `running` for manual reconciliation. Never automatically retry an order, payment, email, message, or other external side effect after an uncertain result.
- Executors must use the returned idempotency key where the external service supports it.
- A worker must report a receipt only after independently verifying the external result.
- A heartbeat timeout is not proof that an external action did not happen.

## What is not enabled yet

This PR creates the cloud API and worker lease contract; it does **not** provide a production browser automation adapter. No Zomato/Swiggy checkout, merchant login/session import, cart editing, payment submission, or order placement is enabled. The default capability is public product search only, and a real cloud browser executor still needs to be implemented and tested against a supported site.

The service is not deployed by this repository change. Hosting credentials, a persistent database volume, a separate worker deployment, and a browser runtime are required. A sleeping/off laptop is no longer required once those services are actually deployed and the worker is online.

For a real order, the existing originating-device checkout digest approval remains mandatory. OTP, UPI PIN, CVV, passwords, and payment credentials must be entered directly by the user in the merchant's trusted UI and must never be sent to VOSI or stored in task memory.
