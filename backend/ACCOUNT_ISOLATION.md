# VOSI account-isolated companion

## What is protected

- Companion chat requires a valid paired-device token and a valid VOSI account session.
- The first successful request links the paired device to the authenticated account.
- A device linked to another account is rejected; device ownership cannot be silently transferred by signing in as another user.
- Conversation turns are stored in the shared VOSI database with a user ID and queried only for that user.
- Companion memories created through authenticated companion chat are stored in a separate per-account table with a unique key scoped to the account.
- Android sends its encrypted account session in the `X-VOSI-Account-Token` header alongside its encrypted device credential.

## Current limitation

The existing agent task ledger and legacy desktop `/ask` memory/history paths have not yet been migrated to account ownership. The account-isolated companion chat therefore runs in conversation-only mode and does not enqueue tasks. Do not deploy the entire backend as a multi-tenant hosted service until task ownership, device claims, approvals, receipts, observations, and legacy interaction storage are also scoped to the account.

## Rollout

1. Deploy the backend update.
2. Sign in to the VOSI account in the Android Profile tab.
3. Open Chat while the phone is paired. The first authenticated chat request links that device to the account.
4. Pair and authenticate each additional device with the same account before using private shared chat.

Existing legacy chat history is not copied into account-scoped tables automatically. This avoids assigning previously global data to an account without explicit ownership confirmation.
