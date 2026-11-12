# VOSI Autonomous Task Orchestrator

## Purpose

This milestone strengthens the durable task queue so VOSI can accept work from a paired phone or desktop, defer it until a requested time, continue safe preparation steps, and pause at a sensitive action for a precise user approval.

## Durable scheduling

- Tasks accept an optional timezone-aware ISO-8601 `scheduled_at` timestamp.
- The timestamp is stored in the same SQLite task ledger as the plan and receipts.
- A device cannot claim a scheduled task before its scheduled time.
- The task survives a backend process restart because the schedule is persisted.
- When due, it becomes claimable by an online paired executor with the exact registered capability.

## Checkout approval contract

- `commerce.order.place` is classified high-risk, irreversible, and approval-required.
- An order plan must include a complete `checkout_summary`: merchant, items, delivery address, total, currency, and payment method.
- Earlier safe preparation steps can run even while a later checkout step is awaiting approval.
- The originating paired device receives pending approval details through `GET /agent/tasks/pending-approvals`.
- Approval uses a SHA-256 digest of the exact checkout arguments. If any item, address, amount, or payment detail changes, the digest changes and the old approval is rejected.
- Only the device that originated the task can approve or reject an online order. The order step cannot be claimed before approval.
- General permission to perform a task is not payment authorization.

## Important current boundary

This is the durable scheduler and approval foundation, not a deployed cloud execution service or a working Zomato/Swiggy checkout adapter. The approval API and capability contract are ready for an executor, but no merchant order submission is enabled in the current Chrome extension.

The existing Chrome extension currently supports read-only Flipkart search, opening HTTPS tabs, and reading a site only after its origin permission is granted. It does not yet automate food-delivery menus, cart editing, addresses, checkout, or payment. The new commerce capability is intentionally not added to the Chrome extension's registered capabilities until a site adapter is implemented and tested.

A task can continue while VOSI's chat window is closed only if the backend and a capable executor remain online. With the current local setup, switching off or sleeping the laptop stops the local backend and Chrome extension. True overnight execution while the laptop is off requires a deployed always-on cloud backend, durable hosted database, cloud browser worker, secure merchant-session handling, and a notification/approval channel to the phone. Those deployment credentials and service accounts are not present in this repository, so this milestone does not claim cloud-offline execution.

## Safe execution sequence for a delivery order

1. Interpret the requested merchant, food/item, budget, and delivery timing.
2. Search and compare menu/product options using a supported merchant adapter.
3. Prepare the cart and resolve unavailable items or substitutions.
4. Read back the exact merchant, items, quantities, address, fees, total, and payment method.
5. Wait for explicit approval from the originating phone or desktop.
6. Submit only the approved checkout snapshot, then verify the merchant confirmation/order ID.
7. If the merchant changes the amount or items, invalidate approval and request review again.

OTP, UPI PIN, CVV, passwords, and other authentication secrets must be entered by the user directly in the merchant's trusted UI. VOSI must never ask the user to disclose them in chat or store them in task memory.

## Next deployment milestone

Deploy the backend with PostgreSQL (or another managed durable database), a queue/worker service, and a cloud browser runtime. Then implement and test merchant-specific adapters, starting with one site and one region. The worker must persist checkpoints, retry only idempotent steps, stop on login/OTP/captcha/payment barriers, and notify the originating device when approval is required.
