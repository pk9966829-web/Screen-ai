# VOSI Unified Companion Brain

The unified companion brain is integrated behind the existing `POST /ask` endpoint.
The current frontend request/response contract is preserved; no frontend layout or component
changes are required.

## What it does

- Uses recent persisted chat history and up to 50 durable, non-sensitive memories for continuity.
- Stores stable preferences, goals, projects, and workflow facts in SQLite.
- Exposes `GET /companion/memories` and `DELETE /companion/memories/{memory_id}`
  so the user can inspect and remove individual memories.
- Routes text-only chat through the companion brain. Requests with `include_screen: true`
  continue to use the existing visual screen-analysis pipeline.
- Accepts authenticated Android voice turns at `POST /companion/voice`. Android uses its
  system speech recognizer for tap-to-talk input and local TextToSpeech for spoken replies.
  Recognized transcripts enter the same persisted conversation history and companion brain
  used by desktop chat, so context can continue across paired devices.
- Can produce a task plan for a clear execution request. Every proposed step is validated
  by the existing `AgentRuntime` capability and platform allow-lists before it is queued.
- Keeps high-risk steps approval-gated by the existing runtime. Planning a task is not proof
  that a device has executed it; only verified device receipts complete tasks.

## Provider configuration

The existing `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `VOSI_MODEL` settings remain
supported as the final fallback.

For multiple OpenAI-compatible chat-completions providers, set a comma-separated
`VOSI_PROVIDER_CHAIN` and provide all three settings for each provider:

- `VOSI_GROQ_API_KEY`, `VOSI_GROQ_BASE_URL`, `VOSI_GROQ_MODEL`
- `VOSI_OPENROUTER_API_KEY`, `VOSI_OPENROUTER_BASE_URL`, `VOSI_OPENROUTER_MODEL`

Example:
```dotenv
VOSI_PROVIDER_CHAIN=groq,openrouter
VOSI_GROQ_BASE_URL=https://api.groq.com/openai/v1
VOSI_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Provider keys must remain in the backend environment and must never be committed.
Only configured providers in the chain are attempted. The fallback uses the existing
project settings.

## Memory and privacy

Memory candidates must be explicitly stated, stable, and non-sensitive. The service rejects
common credential, financial-account, health, identity, religion, caste, and political terms.
The model is instructed not to propose sensitive facts, but automated filtering is not perfect;
review stored memories through the endpoint and delete anything that should not be retained.
The database is local to the backend unless the operator configures another path. Existing
chat history is still stored by the pre-existing interaction-history system.

## Current boundaries

This is the first brain integration, not a fully autonomous general-purpose agent. It does not
grant new device permissions, invent unsupported capabilities, bypass approvals, or guarantee
provider availability. Browser and device work still depends on a paired, online executor.
Screen-aware questions still use the existing screen-analysis pipeline. Voice is currently
foreground tap-to-talk, not an always-listening wake word. Android's configured speech-recognition
service may process audio according to that provider's own privacy terms; VOSI sends the recognized
transcript, not a microphone recording, to its backend. Background wake-word listening, continuous
full-duplex audio, broad browser navigation, and multi-step self-recovery remain future milestones.


## Windows voice companion

The Windows desktop app includes a separate voice panel opened with Ctrl + Shift + Space
while the main VOSI window is focused. It uses the paired desktop credential from Windows
Credential Manager, sends recognized text to the authenticated /companion/voice endpoint,
and speaks replies using the Windows WebView speech-synthesis service. The main VOSI page
layout is unchanged. Push-to-talk requires microphone permission and an available WebView2
speech-recognition service; typed input is available as a fallback. The endpoint accepts
paired Android and desktop devices, but not browser devices.
