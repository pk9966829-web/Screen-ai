# VOSI Autonomous Cross-Device Companion

## Product direction

VOSI is one persistent AI companion available on Android, desktop, and supported browsers. The Android application is a capability bridge and companion surface, not a second disconnected product. The desktop application and browser bridge are peers of the same VOSI identity and task system.

The selected operating mode is **autonomous**, with **phone + computer presence**. Autonomy means VOSI may plan and perform permitted, low-risk work without asking at every step; it does not mean bypassing operating-system permissions, silently accessing private data, or performing high-impact actions without confirmation.

## Current repository baseline

The strongest integration base is feature/whatsapp-personal-android, which is 10 commits ahead of feature/gmail-connectors and includes the latter branch's Gmail, Windows command, and Chrome bridge work plus the Android WhatsApp companion and tests.

Existing foundations:
- FastAPI backend with /ask, /screen, /state, /workflow, /task, Gmail routes, and a Flipkart Chrome extension bridge.
- SQLite persistence for screen metadata, interactions, and task progress.
- Tauri desktop app with screen capture and a floating companion.
- Android companion with contact lookup, user-confirmed calling, WhatsApp notification previews, and notification quick replies.
- Bearer-token protection for the WhatsApp sync endpoints.

Important gaps identified during review:
- The Chrome bridge's /browser/command, /browser/ack, and /browser/results endpoints have no authentication, use process-local dictionaries, and accept results without proving which extension instance sent them.
- The FastAPI app currently enables wildcard CORS. This should be narrowed to the actual desktop origins and paired extension origin strategy; CORS is not authentication.
- Browser extension polling and product extraction are Flipkart-specific and do not yet form a general browser capability interface.
- Android exposes a small number of direct functions; there is no versioned, typed capability protocol for phone actions, capability discovery, or execution receipts.
- TaskEngine persists progress but does not own a permission-aware plan, execution lease, approval state, or cross-device action receipt.
- The current screen memory is primarily recent session context and interaction history, not a user-controlled, cross-device long-term memory service.
- A successful HTTP response or queued command must never be presented as proof that a device action happened.

## Target architecture

### 1. VOSI Core (backend)

Owns the user-facing identity, conversation orchestration, task planner, memory policy, capability registry, approval policy, and event history. It must remain provider-agnostic: AI providers propose plans, while deterministic policy and capability adapters decide what can actually execute.

### 2. Device bridges

- **Android bridge:** versioned HTTPS/loopback-compatible protocol for capability discovery, permission status, action requests, and signed/paired execution receipts. Android permissions remain controlled by Android settings and explicit runtime prompts.
- **Desktop bridge:** Tauri commands for supported Windows/macOS/Linux actions, with a typed allow-list and OS-level permission checks.
- **Browser bridge:** Chrome Manifest V3 extension for tab/page context and narrowly scoped browser actions. It should request only the host permissions needed for a user-enabled site or task.

Each bridge registers a device ID, platform, protocol version, supported capabilities, and last-seen time. Device identity is paired; device tokens are revocable and scoped.

### 3. Capability model

Capabilities use stable names such as:
- screen.observe
- browser.read_visible_page
- browser.search_products
- browser.open_tab
- phone.contacts.read
- phone.call
- phone.notification_previews.read
- phone.whatsapp.quick_reply
- device.alarm.create
- device.volume.set

Each capability declares its data scope, platform, risk tier, permission requirement, and whether the action is reversible. An adapter must validate inputs and return a structured receipt. No arbitrary shell, JavaScript, ADB, or OS command string is accepted from the model.

### 4. Autonomy and approval policy

- **Low risk, reversible, pre-authorized:** may run autonomously (for example, search a public product listing or open a tab).
- **Private-data access:** requires the corresponding connector/device permission and a clear user request; minimize returned data.
- **External communication or financial/legal consequences:** require a user-visible review/confirmation immediately before execution (for example, send email, send WhatsApp reply, purchase, post, book).
- **Destructive or security-sensitive actions:** require explicit confirmation, and some actions may remain unsupported (for example, shutdown, delete data, change account/security settings).
- **Unknown capability, expired pairing, or missing permission:** do not attempt execution. Explain what permission or bridge is missing.

A plan is not an execution. A queued request is not an execution. A bridge acknowledgement is not proof of the device-side effect. Mark a step complete only after an adapter returns a verified receipt or the user confirms the result.

### 5. Task lifecycle

draft -> planned -> awaiting_approval -> ready -> running -> completed

Alternative terminal states: failed, cancelled, expired.

A task stores:
- stable task and user IDs;
- originating device and target device;
- user goal and structured steps;
- required capabilities and approval decisions;
- execution lease / idempotency key;
- per-step status, timestamps, and evidence receipt;
- cancellation and expiry information.

Tasks survive backend restarts and can be resumed on another paired device. The first implementation should add the task contract and persistence before connecting more device actions.

### 6. Memory and privacy

Separate short-term screen context, conversation history, user-approved long-term memories, and connector data. Keep connector payloads scoped and time-limited. Give the user controls to inspect, clear, and revoke data sources. Treat screen text, browser content, email, notifications, and documents as untrusted input; never follow instructions embedded in them as agent policy.

## Device pairing protocol (implemented foundation)

The first device-registry slice is implemented in `backend/device_registry.py` and exposed through `backend/agent_api.py`.

- `POST /agent/devices/pairing` — requires the VOSI admin bearer token; creates a single-use pairing code for `android`, `desktop`, or `browser`. Codes expire after five minutes.
- `POST /agent/devices/pair` — exchanges the pairing code for a device ID and device bearer token. The token is returned once; only its SHA-256 hash is stored.
- `GET /agent/devices` — admin-only device inventory. It never returns device tokens.
- `DELETE /agent/devices/{device_id}` — admin-only revocation.
- `POST /agent/devices/{device_id}/heartbeat` — device-token authenticated heartbeat. A token cannot heartbeat a different device ID.
- `POST /agent/tasks/{task_id}/claim` — a paired device can claim only a pending task step for its registered platform and advertised capability.
- `POST /agent/tasks/{task_id}/steps/{step_id}/result` — the device holding the claim submits a structured receipt. A task step is completed only when success, verified, and a non-empty receipt are all supplied.

Configure `VOSI_AGENT_TOKEN` in the backend environment before using admin endpoints. The example value in `backend/.env.example` is a placeholder and must be replaced with a long random secret. `VOSI_AGENT_DB_PATH` can optionally select a dedicated SQLite file; otherwise the registry shares the agent runtime database.

Pairing-code exchange is intentionally a bootstrap endpoint and does not use the admin token; possession of the high-entropy, five-minute, single-use code is required. Device credentials are per-device and revocable. Pairing does not grant Android permissions or install desktop/browser adapters: it only registers the capabilities the bridge reports. Actual clients must protect their device token using platform secure storage and send it only over a trusted local connection or HTTPS. Do not expose this API directly to the public internet without TLS, rate limiting, and a stronger user/account authentication layer.

## Chrome browser bridge pairing (implemented first client)

The Chrome Manifest V3 extension in `screen ai/chrome-extension` now includes a pairing popup. An administrator creates a browser pairing code through the authenticated `POST /agent/devices/pairing` endpoint; the extension exchanges that five-minute, single-use code through `POST /agent/devices/pair`.

The per-device credential is stored in `chrome.storage.local` (not Chrome Sync), used by the extension service worker for minute heartbeats, and revoked through `DELETE /agent/devices/me` when the user disconnects. The browser command, acknowledgement, and product-result endpoints now require a valid credential for a device registered as platform `browser`. Content scripts forward extracted results to the service worker; the credential is not exposed to Flipkart page scripts.

The extension currently supports the existing read-only Flipkart search workflow. It does not yet poll the VOSI agent task queue or execute arbitrary browser actions. That is a separate adapter milestone; the pairing protocol and browser bridge authentication are in place first.

## Implementation sequence

### Phase 0 — foundation and safety
1. Preserve the WhatsApp branch as the integration base; do not merge directly into main.
2. Add a versioned agent/task contract, explicit capability metadata, durable task state, and tests.
3. Authenticate the browser extension bridge with a separate, revocable pairing credential; persist pending requests and results; add expiry, request ownership, and idempotency.
4. Replace wildcard CORS with an explicit origin policy and document local-only deployment assumptions.
5. Add a unified action receipt format and never report success from queueing alone.

### Phase 1 — unified device protocol
1. Pair Android, desktop, and Chrome as separate devices under one VOSI account/profile.
2. Add heartbeat, capability discovery, permission status, revocation, and reconnect handling.
3. Route requests to the correct device and return structured receipts.
4. Add device-offline and permission-denied recovery paths.

### Phase 2 — real autonomous workflows
1. Implement browser adapters (read current page, search supported sites, compare products, open tab).
2. Implement Android adapters (contacts, calls, notification previews, supported quick replies, alarms and settings where Android allows).
3. Implement desktop adapters (screen context, app launch, volume, alarms, and supported OS actions).
4. Add multi-step planning, resumable execution, bounded retries, and user-visible confirmation gates.

### Phase 3 — companion experience
1. One friendly VOSI presence and voice interface across phone and computer.
2. Shared conversation continuity and user-controlled memory.
3. Proactive suggestions only when enabled, with quiet hours and clear controls.
4. Transparent activity history showing what VOSI observed, planned, requested, executed, and verified.

## Acceptance criteria

- A provider outage does not prevent deterministic local commands or device bridge status from working.
- A device can only execute capabilities it advertises and the user has granted.
- Every external side effect has an idempotency key and an execution receipt.
- Sensitive actions cannot execute from model output alone.
- Browser content, notifications, and screen text cannot grant permissions or override policy.
- The same task can be inspected from phone and desktop, with truthful step status.
- Pairing credentials are revocable, stored securely, never logged, and scoped per device.
- Tests cover unauthenticated requests, expired pairing, replay, duplicate delivery, permission denial, cancellation, and backend restart recovery.

## First implementation slice

This branch introduces the architecture contract and a small backend task/capability foundation. It intentionally does not claim that phone-wide control or general autonomous execution is already available. Device adapters are added only after the protocol, approval policy, and receipts are tested.


## Windows radio settings and power approvals

Android may request Windows shutdown or restart, but these steps remain in `awaiting_approval` until a paired desktop shows and accepts a confirmation. Only a desktop credential with the matching capability can approve or reject; rejection cancels the task. Other high-risk capabilities remain blocked from phone task requests.

Bluetooth and Wi-Fi commands currently open their Windows Settings pages only. VOSI does not automatically flip the radios: that could require elevation, and disabling Wi-Fi could sever the backend route before a receipt is delivered.
