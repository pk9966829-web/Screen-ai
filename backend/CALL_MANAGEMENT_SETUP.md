# CHERRY AI Call Management — Setup & Operations

This document covers the opt-in live receptionist, call history, summaries, callbacks, and Android call-history screen.

## What is implemented

- **Live receptionist bridge:** Exotel media WebSocket `/call-receptionist/exotel/media` streams caller PCM audio to the configured GPT-Live session and sends generated PCM back to Exotel.
- **Consent gate:** the bridge will not open an AI audio session until the Exotel `start` event contains `custom_parameters.consent=granted` (or `custom parameters` with the same value).
- **AI disclosure:** the receptionist identifies itself as CHERRY AI; it never impersonates the owner, promises a callback, claims delivery, or takes payment/credential details.
- **Call history:** owner-account scoped records with transcript, summary, caller/destination, duration, outcomes, structured caller name/purpose/urgency/callback fields.
- **Dashboard API:** metrics, search/filter/pagination, detail view, status updates, and individual record deletion.
- **Android:** Call Assistant setup, optional Android call-screening role (metadata only), call-history cards, detail/transcript view, review/callback-complete status, urgent/callback notifications.
- **Optional AI summary enrichment:** sends caller-only transcript text (not audio) to the configured provider chain when explicitly enabled; otherwise uses deterministic extraction.
- **Optional Fish Audio speech:** opt-in TTS adapter and emotion cues; GPT-Live speech remains fallback.

## Important platform boundary

Android Call Screening is not the live receptionist audio route. It does not answer or capture normal SIM-call audio. The live AI receptionist currently requires an Exotel/PSTN call flow that forwards/streams the call to this backend. No universal WhatsApp/Telegram/Meet audio capture is implemented.

## Backend configuration

Copy `backend/.env.example` to `backend/.env` and set these values privately:

```dotenv
CHERRY_CALL_RECEPTIONIST_ENABLED=true
CHERRY_EXOTEL_STREAM_USER=cherry
CHERRY_EXOTEL_STREAM_PASSWORD=<random secret of at least 32 characters>
CHERRY_LIVE_API_KEY=<live voice API key>
CHERRY_LIVE_MODEL=gpt-live-1.1
CHERRY_LIVE_VOICE=marin

# Required for protected call-history APIs:
CHERRY_CALL_OWNER_USER_ID=<user_id from the signed-in account>

# Optional; caller-only text is sent to the configured VOSI provider chain:
CHERRY_CALL_SUMMARY_AI_ENABLED=false

# Optional Fish Audio TTS. GPT-Live is the default/fallback:
CHERRY_TTS_PROVIDER=gpt-live
CHERRY_FISH_API_KEY=
CHERRY_FISH_VOICE_ID=
CHERRY_FISH_MODEL=s2.1-pro
CHERRY_FISH_SAMPLE_RATE=16000
CHERRY_FISH_EMOTION_TAGS=true
```

Generate the Exotel streaming password with a secure password generator. Never commit `.env`, API keys, call transcripts, caller numbers, OAuth files, or speaker samples.

Restart the backend after configuration. Check `GET /call-receptionist/status`; it returns configuration state and missing-variable names, but never secret values. The receptionist stays disabled unless the enable flag is true and all required streaming/API settings are present.

## Exotel deployment

1. Provision an Exotel number and create the inbound Voice/Voicebot flow that forwards the call to the CHERRY AI receptionist.
2. Before connecting the AI stream, disclose that the caller is speaking with an AI and that their speech will be transcribed/processed. Collect explicit DTMF consent (for example, press 1 to continue); route non-consenting callers to a non-AI fallback or end the AI route.
3. In the Exotel stream applet, configure the secure WebSocket endpoint `wss://<your-host>/call-receptionist/exotel/media` and HTTP Basic credentials matching `CHERRY_EXOTEL_STREAM_USER` / `CHERRY_EXOTEL_STREAM_PASSWORD`.
4. Pass a custom stream parameter `consent=granted` only on the consent-approved route. The bridge rejects missing consent.
5. Ensure the stream is mono PCM16 / 16 kHz as expected. The bridge validates the declared media format and packets audio in 100 ms chunks.
6. Deploy behind a TLS reverse proxy that supports WebSocket upgrades. Keep the backend private behind the proxy/firewall; do not expose a development server directly.
7. Place a controlled test call. Confirm the AI disclosure, consent branch, two-way audio, transcript, outcome, and saved record. Do not enable the production number until a real test call has passed.

The exact applet fields and audio format options can differ by Exotel account/product version; verify the stream configuration in the current Exotel console and test against the provider rather than assuming a setting.

## Call history API

All call-history routes require the signed-in account's bearer session and the server must be configured with `CHERRY_CALL_OWNER_USER_ID`. The caller's owner ID is checked before records are returned or changed.

- `GET /call-receptionist/status` — configuration status (no secret values).
- `GET /call-receptionist/calls/stats` — account-scoped dashboard counts and outcome breakdown.
- `GET /call-receptionist/calls?limit=25&offset=0` — paginated recent calls.
- Filters: `status=new|reviewed|callback_done`, `urgency=urgent|normal|unknown`, `outcome=completed|caller_disconnected|ai_ended|ai_error|bridge_error`, `callback_only=true`, `q=<search>`.
- `GET /call-receptionist/calls/{id}` — protected detail/transcript.
- `PATCH /call-receptionist/calls/{id}/status?status=reviewed` — status is `new`, `reviewed`, or `callback_done`.
- `DELETE /call-receptionist/calls/{id}` — delete the call record, including transcript.

Example:

```powershell
$headers = @{ Authorization = "Bearer $env:CHERRY_ACCOUNT_SESSION" }
Invoke-RestMethod "http://127.0.0.1:8001/call-receptionist/status"
Invoke-RestMethod "http://127.0.0.1:8001/call-receptionist/calls/stats" -Headers $headers
Invoke-RestMethod "http://127.0.0.1:8001/call-receptionist/calls?limit=20&callback_only=true" -Headers $headers
```

Do not paste account session tokens into chat or commit them to source control.

## Data and privacy

- Call audio is streamed for live processing and is **not stored as an audio recording** by this implementation.
- Text transcript, metadata, summary and callback/urgency fields are stored locally in SQLite. Call detail requires the owner account.
- Optional summary AI uses caller transcript lines only and is disabled by default. Transcript content is treated as untrusted input.
- Android notifications are locally duplicate-suppressed. Notification permission is needed on Android 13+.
- Delete a call record when it is no longer needed. Define an appropriate retention period before production; automatic retention deletion is not yet configured.
- AI calls do not perform payments, credential collection, commitments, or automatically place callbacks. Callback status is a manual workflow marker.

## Acceptance test checklist

- [ ] Backend status shows disabled before configuration; no API keys are returned.
- [ ] Status reports configured only when the enable flag, stream username/password, Live API key, model and voice are present.
- [ ] WebSocket rejects wrong Basic credentials, disabled configuration, and consent not granted.
- [ ] Exotel start event and media format are validated; malformed/oversized packets are ignored.
- [ ] Real inbound test call passes AI disclosure and consent before AI audio starts.
- [ ] Both audio directions work; caller speech interrupts generated speech as expected.
- [ ] Transcript captures caller and CHERRY turns; no audio file is saved.
- [ ] Call ends/disconnect/errors map to stable outcome values and record persistence is attempted.
- [ ] Owner authentication is required for history; another account cannot read/update/delete records.
- [ ] Search, filters, pagination, dashboard stats, detail, status updates and deletion behave as expected.
- [ ] Urgent/callback notifications work with Android permission granted.
- [ ] Optional summary provider and Fish Audio are tested with live credentials before enabling.
- [ ] Android build and physical device tests pass.
- [ ] Real Exotel call end-to-end tests pass before production enablement.

## Current verification boundary

Code and automated tests from the call-receptionist stack are integrated in the completion branch. This environment cannot run the local backend, build the Android APK, provision Exotel, or make a real phone call. Treat live telephony, account credentials, and Android device checks as required release gates—not as completed tests.
