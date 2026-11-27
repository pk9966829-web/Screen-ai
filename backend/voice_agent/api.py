"""Authenticated-by-local-origin voice API for the CHERRY AI desktop backend.

The desktop app records audio only after the user clicks the microphone. This
router is intended for the existing loopback-only local backend, not public
internet deployment. Keep the backend bound to 127.0.0.1.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from .agent import VoiceAgent, VoiceAgentError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])
MAX_AUDIO_BYTES = 20 * 1024 * 1024
VOICE_OUTPUT_DIR = Path(tempfile.gettempdir()) / "cherry_ai_voice"
VOICE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_voice_agent: VoiceAgent | None = None

SUPPORTED_AUDIO_TYPES = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/m4a": ".m4a",
}


def get_voice_agent() -> VoiceAgent:
    global _voice_agent
    if _voice_agent is None:
        _voice_agent = VoiceAgent()
    return _voice_agent


@router.post("/voice")
async def process_voice(file: UploadFile = File(...)):
    """Accept a short user-recorded audio clip and return text plus generated speech."""
    suffix = SUPPORTED_AUDIO_TYPES.get((file.content_type or "").split(";")[0].lower())
    if not suffix:
        raise HTTPException(status_code=415, detail="Unsupported audio format. Record audio as WAV, WebM, OGG, or MP4.")

    audio_bytes = await file.read(MAX_AUDIO_BYTES + 1)
    await file.close()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio recording is empty.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio recording exceeds the 20 MB limit.")

    try:
        agent = get_voice_agent()
        transcript = await run_in_threadpool(agent.transcribe, audio_bytes, suffix)
        if not transcript:
            raise VoiceAgentError("No speech was detected in the recording.")
        reply = await run_in_threadpool(agent.respond, transcript)
        generated_path = await run_in_threadpool(agent.synthesize, reply)
    except VoiceAgentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ImportError as exc:
        logger.exception("Voice-agent dependency is missing")
        raise HTTPException(status_code=503, detail="Voice agent dependencies are not installed. Follow backend/voice_agent/README.md.") from exc
    except Exception as exc:
        logger.exception("Unexpected voice processing error")
        raise HTTPException(status_code=500, detail="Voice processing failed. Check the backend log for details.") from exc

    filename = f"{uuid.uuid4().hex}.wav"
    destination = VOICE_OUTPUT_DIR / filename
    try:
        shutil.move(str(generated_path), str(destination))
    except Exception:
        Path(generated_path).unlink(missing_ok=True)
        logger.exception("Could not store generated voice response")
        raise HTTPException(status_code=500, detail="Could not store the generated audio response.")

    return {
        "success": True,
        "transcript": transcript,
        "text": reply,
        "audio_url": f"/voice/audio/{filename}",
    }


@router.get("/voice/audio/{filename}")
def get_voice_audio(filename: str):
    """Serve one generated response, then remove it after the client finishes downloading."""
    if not filename.endswith(".wav") or len(filename) != 36 or not all(
        char in "0123456789abcdef" for char in filename[:-4]
    ):
        raise HTTPException(status_code=404, detail="Audio response not found.")
    audio_path = VOICE_OUTPUT_DIR / filename
    if not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio response not found.")
    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=filename,
        background=BackgroundTask(lambda: audio_path.unlink(missing_ok=True)),
    )
