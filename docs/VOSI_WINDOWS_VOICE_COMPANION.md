# VOSI Windows Voice Companion

## What it adds

The Windows desktop app gets a separate, compact voice companion window. The existing main VOSI screen and its layout are not changed.

- Press Ctrl + Shift + Space while the VOSI main window is focused to open the voice panel.
- Press Start speaking to request one speech-recognition turn.
- VOSI sends only the recognized transcript to the local backend at http://127.0.0.1:8001/companion/voice.
- The paired desktop device credential is read from Windows Credential Manager and is never placed in browser storage.
- VOSI speaks the reply through the Windows WebView speech-synthesis service.
- A text input remains available if speech recognition is unavailable.

## Requirements

1. Start the VOSI FastAPI backend on port 8001.
2. Pair this Windows PC from the existing VOSI Connectors / desktop pairing section.
3. Allow microphone access when Windows or WebView2 asks.
4. Keep the PC awake and the backend running while using the voice panel.

## Privacy and safety

The microphone is used only after the user presses Start speaking. Speech recognition is performed by the platform WebView speech service; the VOSI backend receives the recognized transcript, not raw microphone audio. The desktop voice endpoint accepts only paired Android and desktop devices. Browser devices are not accepted.

Voice replies use the same companion brain, interaction history, memory policy, task planner, and approval rules as Android voice. A task is not described as completed unless a paired executor returns a verified receipt.

## Current limitations

This is push-to-talk, one utterance at a time. It is not a wake word, always-listening microphone, background transcription service, or full-duplex conversation. WebView2 speech-recognition availability depends on the installed Windows speech service and privacy settings; typed chat is the fallback. The VOSI backend must be reachable at 127.0.0.1:8001.
