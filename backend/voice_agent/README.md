# CHERRY AI Voice Agent

This is an optional, reusable voice pipeline. It does not change or replace the existing FastAPI screen-analysis API.

## Pipeline

1. **Whisper** converts incoming WAV audio to text locally.
2. **Gemini** generates a concise assistant reply using the Google Gen AI SDK.
3. **Coqui XTTS-v2** converts the reply into a WAV file using a configured reference speaker recording.

The package lives under `backend/voice_agent`; import it when the backend needs it:

```python
from voice_agent import VoiceAgent

voice = VoiceAgent()
reply_text, reply_wav_path = voice.handle_audio(raw_wav_bytes)
```

Run imports with the backend directory on Python's import path (for example, from the `backend` directory).

## Windows setup

Use the Python environment already used by the backend. From `backend`:

```powershell
python -m pip install -r .\voice_agent\requirements-voice-agent.txt
```

Whisper requires FFmpeg. Install a Windows FFmpeg build and add the folder containing `ffmpeg.exe` to PATH, then open a new terminal and verify:

```powershell
ffmpeg -version
python -m whisper --help
```

Set the Gemini API key and XTTS reference WAV in the environment. Do not commit API keys or private voice recordings:

```powershell
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
$env:CHERRY_XTTS_SPEAKER_WAV = "C:\path\to\authorized-reference.wav"
$env:WHISPER_MODEL = "base.en"
$env:GEMINI_MODEL = "gemini-2.5-flash"
```

The reference WAV should be a clean recording of a speaker whose voice you have permission to use. XTTS-v2 requires this reference audio; the agent will return a clear configuration error if it is missing.

## CLI test

```powershell
python -m voice_agent.agent .\test.wav
```

The first run downloads model files and may take time. Model storage and compute requirements depend on the selected Whisper and XTTS models.

## Optional Flask HTTP demo

From `backend`:

```powershell
python -m pip install Flask
$env:CHERRY_VOICE_DEMO_TOKEN = "replace-with-a-long-random-token"
python -m voice_agent.demo_server
```

The demo binds to `127.0.0.1` only, accepts WAV uploads up to 20 MB, and requires a Bearer token when `CHERRY_VOICE_DEMO_TOKEN` is set. It is a local development demo, not a production public API. Do not tunnel or expose it publicly without adding production authentication, TLS termination, request throttling, storage cleanup, and deployment hardening.

Example request (PowerShell):

```powershell
$headers = @{ Authorization = "Bearer $env:CHERRY_VOICE_DEMO_TOKEN" }
Invoke-WebRequest -Uri http://127.0.0.1:8080/voice -Method Post -Headers $headers -ContentType "audio/wav" -InFile .\test.wav
```

## Configuration

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Gemini API credential |
| `GEMINI_MODEL` | Model ID; defaults to `gemini-2.5-flash` |
| `WHISPER_MODEL` | Whisper model; defaults to `base.en` |
| `CHERRY_XTTS_SPEAKER_WAV` | Required reference WAV for XTTS-v2 |
| `CHERRY_XTTS_LANGUAGE` | XTTS language code; defaults to `en` |
| `CHERRY_XTTS_MODEL` | XTTS model identifier |
| `CHERRY_VOICE_DEMO_TOKEN` | Optional Bearer token for the demo server |

## Important integration note

The plugin manifest is metadata; it does not automatically register the package with the existing FastAPI application or the desktop UI. The current commit adds the reusable engine and isolated demo only. A later integration step should add authenticated audio endpoints, streaming/audio playback, user consent, retention controls, and frontend controls after the existing app's auth and API patterns are reviewed.
