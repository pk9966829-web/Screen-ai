# CHERRY AI SIM-call receptionist setup

This feature uses Exotel's bidirectional VoiceBot WebSocket stream and GPT-Live speech-to-speech. It is separate from Android's CallScreeningService: Android call screening can identify an incoming call, but the AI conversation runs on the Exotel/PSTN audio path.

## Required services

- An Exotel account with a provisioned inbound virtual number and a VoiceBot Applet enabled for bidirectional streaming.
- A publicly reachable backend with HTTPS/WSS. A backend listening only on `127.0.0.1` is not reachable from Exotel.
- A GPT-Live API key stored only on the backend.
- A carrier-supported conditional call-forwarding option on the SIM being protected. Carrier availability, activation codes and forwarding charges vary.

## Backend environment

Set these values in the deployed backend environment (never commit real credentials):

- `CHERRY_CALL_RECEPTIONIST_ENABLED=true`
- `CHERRY_EXOTEL_STREAM_USER=cherry`
- `CHERRY_EXOTEL_STREAM_PASSWORD=<long random password, at least 32 characters>`
- `CHERRY_LIVE_API_KEY=<server-side API key>`
- `CHERRY_LIVE_MODEL=gpt-live-1.1`
- `CHERRY_LIVE_VOICE=marin`

Check readiness with `GET /call-receptionist/status`. It reports missing configuration without returning secret values.

## Exotel call flow

1. Route the inbound virtual number to a pre-stream greeting/disclosure step.
2. Tell the caller clearly that CHERRY AI is an AI receptionist and their speech will be processed by an AI service to take a message.
3. Ask the caller to press **1** to continue. Route any other key or no response away from the AI stream (for example, to a hang-up or voicemail branch).
4. Only after the caller presses 1, route to the VoiceBot Applet. Add the custom parameter `consent=granted`. The backend rejects a stream that does not carry this consent marker.
5. Configure the VoiceBot WebSocket URL as:

```text
wss://<stream-user>:<stream-password>@<public-host>/call-receptionist/exotel/media?sample_rate=16000&consent=granted
```

The sample rate must be 16 kHz mono PCM16. Keep Exotel call recording disabled unless the account owner separately enables and configures a compliant recording workflow.

## Forward the SIM calls

After the Exotel number and flow have been tested independently, configure the SIM's conditional forwarding (such as busy or no-answer) to the Exotel virtual number using the mobile carrier's supported settings. Do not enable forwarding until you have confirmed the Exotel number, call flow, and any carrier charges.

## Current implementation boundary

The backend bridge streams audio both ways and asks CHERRY AI to identify itself and collect the caller's name, reason, urgency and callback details. It does not record audio or persist transcripts yet, and the app does not yet send a caller-summary push notification. Those are the next implementation tasks before treating this as a finished receptionist. Real SIM testing also requires the deployed WSS endpoint, Exotel account/number, valid GPT-Live key and carrier forwarding setup.
