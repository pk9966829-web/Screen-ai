# CHERRY AI Voice Agent

This optional voice pipeline is now connected to the existing FastAPI backend and the desktop microphone button on the feature branch.

## How the integrated flow works

1. The user clicks the microphone and grants microphone permission.
2. The desktop app records until the user clicks the microphone again.
3. The app sends the recording to the local FastAPI `POST /voice` endpoint.
4. Whisper transcribes the audio locally (FFmpeg handles browser WebM/Opus input).
5. Gemini generates a concise CHERRY AI reply.
6. Coqui XTTS-v2 generates the spoken reply.
7. The app displays the transcript and reply, then plays the generated WAV audio.

The existing screen-observation and text-chat endpoints are unchanged. The voice model is initialized only when the voice endpoint is first used.

## Windows setup

From the repository's `backend` directory, use the same Python environment as the existing backend:

```powershell
python -m pip install -r .\requirements.txt
python -m pip install -r .\voice_agent\requirements-voice-agent.txt
```

Whisper requires FFmpeg. Install a Windows FFmpeg build, add the folder containing `ffmpeg.exe` to PATH, open a new terminal, and verify:

```powershell
ffmpeg -version
python -m whisper --help
```

Set the Gemini API key and a reference WAV recording for the voice you are authorized to use. Do not commit API keys or private voice recordings:

```powershell
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
$env:CHERRY_XTTS_SPEAKER_WAV = "C:\path\to\authorized-reference.wav"
$env:WHISPER_MODEL = "base.en"
$env:GEMINI_MODEL = "gemini-2.5-flash"
```

XTTS-v2 requires a reference speaker WAV. Use a clear recording from a speaker whose voice you have permission to use.

## Run CHERRY AI

Start the existing backend from `backend`:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Start the desktop frontend as usual from `screen ai`:

```powershell
npm.cmd run tauri dev
```

Click the microphone once to start recording and again to stop and send the recording. The app will show the transcript and answer and attempt to play the generated reply.

## API behavior and safeguards

- `POST /voice` accepts a multipart field named `file`, up to 20 MB.
- Supported browser audio formats include WebM, WAV, OGG, and MP4/M4A.
- `GET /voice/audio/{filename}` serves a generated WAV reply.
- Audio output is stored in the operating system temporary directory and stale files older than 30 minutes are cleaned up on the next voice request.
- Requests require an allowed desktop-app Origin. Add a development origin, if necessary, through `CHERRY_VOICE_ALLOWED_ORIGINS` as a comma-separated list.
- Keep the backend bound to `127.0.0.1`. Do not expose this local API through ngrok or bind it to `0.0.0.0` without a production authentication design, TLS, rate limiting, and deployment hardening.
- Microphone access starts only after the user clicks the microphone; the user stops recording with a second click.

## Troubleshooting

- **FFmpeg not found:** install FFmpeg and add its `bin` directory to PATH, then restart the terminal.
- **Gemini key missing:** set `GEMINI_API_KEY` in the same terminal that starts the backend.
- **XTTS reference missing:** set `CHERRY_XTTS_SPEAKER_WAV` to an authorized WAV file.
- **Voice dependencies missing:** install `voice_agent/requirements-voice-agent.txt` in the backend's active virtual environment.
- **403 from /voice:** confirm the desktop app Origin is listed above or add it to `CHERRY_VOICE_ALLOWED_ORIGINS`.

## Optional standalone demo

`demo_server.py` remains available for local development only. It is not used by the integrated desktop app and should not be publicly exposed.
