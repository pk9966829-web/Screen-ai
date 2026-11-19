# VOSI account-isolated companion

## What is protected

- Companion chat requires a valid paired-device token and a valid VOSI account session.
- The first successful request links the paired device to the authenticated account.
- A device linked to another account is rejected; device ownership cannot be silently transferred by signing in as another user.
- Conversation turns are stored in the shared VOSI database with a user ID and queried only for that user.
- Companion memories created through authenticated companion chat are stored in a separate per-account table with a unique key scoped to the account.
- Android sends its encrypted account session in the `X-VOSI-Account-Token` header alongside its encrypted device credential.

## Account-scoped legacy desktop state

The legacy desktop `/ask`, `/screen`, `/history`, `/workflow`, `/state`, `/task`, and `/awareness` routes now accept `X-VOSI-Account-Token`. The backend validates that session and selects a separate `ScreenPipeline` for the account. Conversation history, screen-observation metadata, legacy task events, live screen frames, and companion memory reads/deletes are partitioned by user ID. SQLite receives additive `user_id` columns; pre-existing rows remain unowned and are not assigned to the first account that signs in.

Set `VOSI_MULTI_TENANT=true` to require an account session on those legacy data routes. The local desktop workflow remains unchanged when this flag is unset. Account screenshots are stored outside the public `/uploads` static directory.

## Multi-tenant safety boundary

The legacy Gmail OAuth integration, shared browser command bridge, shared WhatsApp inbox, and shared letter-file routes still use local/global credentials or storage. They are therefore disabled when `VOSI_MULTI_TENANT=true` rather than exposed across accounts. Use the account-authenticated companion/task APIs for supported cross-device work. These blocked legacy integrations need separate account-scoped connector authorization before they can be re-enabled.

Account screen pipelines keep live frames and context in process memory, with a bounded cache of 32 active accounts. Durable observations and task events are stored per account; transient frame buffers reset when the API process restarts. A multi-instance production deployment still needs the Stage 3 shared cache/object storage and PostgreSQL work.

## Rollout

1. Deploy the backend update.
2. Sign in to the VOSI account in the Android Profile tab.
3. Open Chat while the phone is paired. The first authenticated chat request links that device to the account.
4. Pair each additional device and link it to the same account through the identity device-link flow before it can claim that account's tasks. The Android chat's first authenticated use links the phone automatically.
5. For a hosted multi-tenant deployment, set `VOSI_MULTI_TENANT=true` and ensure every client calling the legacy screen/history/task routes sends its account session in `X-VOSI-Account-Token`. Do not enable this flag until desktop clients have their account-session header wired and tested.

Existing legacy chat history is not copied into account-scoped tables automatically. This avoids assigning previously global data to an account without explicit ownership confirmation.
