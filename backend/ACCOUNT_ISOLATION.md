# VOSI account-isolated companion

## What is protected

- Companion chat requires a valid paired-device token and a valid VOSI account session.
- The first successful request links the paired device to the authenticated account.
- A device linked to another account is rejected; device ownership cannot be silently transferred by signing in as another user.
- Conversation turns are stored in the shared VOSI database with a user ID and queried only for that user.
- Companion memories created through authenticated companion chat are stored in a separate per-account table with a unique key scoped to the account.
- Android sends its encrypted account session in the `X-VOSI-Account-Token` header alongside its encrypted device credential.

## Current limitation

Companion-created tasks now carry an account owner. Device task feeds are filtered by the linked account, and a device from another account cannot claim or submit results for that task. Approval feeds and device approvals are likewise filtered to the task owner. Legacy tasks created through the local admin-token API remain unowned and are visible only to the legacy local-device queue. The legacy desktop `/ask` memory/history and observation storage have not yet been migrated to account ownership. Do not deploy the entire backend as a multi-tenant hosted service until those remaining paths are scoped.

## Rollout

1. Deploy the backend update.
2. Sign in to the VOSI account in the Android Profile tab.
3. Open Chat while the phone is paired. The first authenticated chat request links that device to the account.
4. Pair each additional device and link it to the same account through the identity device-link flow before it can claim that account's tasks. The Android chat's first authenticated use links the phone automatically.

Existing legacy chat history is not copied into account-scoped tables automatically. This avoids assigning previously global data to an account without explicit ownership confirmation.
