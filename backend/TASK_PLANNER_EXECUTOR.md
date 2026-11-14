# VOSI task planner and executor

This milestone connects natural-language companion requests to the durable agent task ledger. It does not replace platform executors or broaden their permissions.

## Request-to-result lifecycle

1. A paired Android or desktop client sends a typed or locally recognized voice turn to `/companion/chat` or `/companion/voice`.
2. The companion brain receives recent conversation, the active workflow state, registered device capabilities, and the user's originating device ID.
3. The model proposes an ordered plan. The server validates every capability, target platform, argument shape, and registered executor before creating a task.
4. The SQLite task ledger stores the goal, ordered steps, schedule, approval requirements, claim lease, and receipts.
5. The matching paired executor polls `/agent/tasks/available`, claims only the first unfinished step, runs its local adapter, and submits a receipt.
6. The runtime advances the task only after a verified receipt. Paired clients can read task progress and the next/current step from `/agent/tasks/updates`.
7. A crashed worker's claim becomes reclaimable after the five-minute lease expires. An action that explicitly fails is not blindly replayed because it may have partially happened.

## Planning rules

- Multi-part requests are decomposed into ordered atomic steps (maximum 10 from the companion planner; the runtime supports up to 30).
- The selected platform must be listed by the capability and granted to a non-revoked, online paired device.
- Missing required facts cause a clarification instead of an invented argument.
- Scheduled tasks require a timezone-aware ISO-8601 timestamp.
- A task is not reported as complete until the executor submits a non-empty verified receipt.
- AI output, page text, memory and previous task results are untrusted data, never executable instructions.

## Safety

- Low-risk actions can run on a matching authorized device.
- High-risk actions remain approval-gated by the runtime. Checkout requires a complete summary and an exact confirmation digest from the originating device.
- Calls, WhatsApp messages, email sends, orders, shutdown and restart are not made autonomous by this planner.
- The planner cannot add capabilities or bypass the paired-device registry.
- Android WorkManager remains best-effort and periodic; it is not an always-on real-time service.

## Current execution boundary

The planner can queue work only for a capability with a concrete adapter, on an online paired device that has granted it. The Android background worker currently executes phone media-volume and alarm actions. The desktop adapter supports the registered Windows alarm, volume, timer, settings and approval-gated power actions; the browser adapter supports its registered public-page and product-search actions. Phone calls, WhatsApp sends, email sends, screen observation as a queued task, and commerce checkout are deliberately excluded until their reviewed executors are implemented. This code does not deploy a cloud worker or guarantee execution while every device is offline.

## Validation

CI runs planner argument-validation tests, task progress tests, voice-context regression tests, the backend regression suite, Android APK compilation, and Windows desktop checks. A successful CI build does not replace physical Android/Windows/Chrome testing.
