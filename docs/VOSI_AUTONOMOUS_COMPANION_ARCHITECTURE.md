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
