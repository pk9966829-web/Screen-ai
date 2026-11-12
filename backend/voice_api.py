"""Authenticated tap-to-talk voice turns for the VOSI Android companion.

Android performs speech recognition locally through the platform recognizer and
speaks replies locally with TextToSpeech. Only the recognized transcript is sent
to this API; microphone audio is not uploaded by this module.
"""
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import agent_api
from agent_runtime import AgentRuntimeError
from companion_brain import answer_companion
from database import get_recent_interactions, save_interaction

router = APIRouter(prefix="/companion", tags=["VOSI Companion Voice"])


class VoiceTurnRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)


def _authenticate_android(authorization: str | None) -> dict[str, Any]:
    scheme, separator, token = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Pair this Android phone with VOSI first.")
    try:
        device = agent_api.devices.authenticate(token.strip())
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=401, detail="The paired-device credential is invalid or revoked.") from exc
    if device.get("platform") != "android":
        raise HTTPException(status_code=403, detail="Voice companion turns are available to paired Android devices.")
    return device


@router.post("/voice")
def create_voice_turn(
    request: VoiceTurnRequest,
    authorization: str | None = Header(default=None),
):
    """Process one recognized utterance through the same brain and history as desktop chat."""
    device = _authenticate_android(authorization)
    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="Speak a message before sending it to VOSI.")

    recent = get_recent_interactions(limit=8)
    result = answer_companion(
        transcript,
        recent_interactions=recent,
        task_state={},
        runtime=agent_api.runtime,
        paired_devices=agent_api.devices.list_devices(),
    )
    response_text = str(result.get("understanding") or "I couldn't prepare a response. Please try again.")
    if result.get("success"):
        save_interaction(transcript, response_text, screens_considered=0, task={})

    return {
        "success": bool(result.get("success")),
        "device_id": device.get("device_id"),
        "transcript": transcript,
        "response": response_text[:12000],
        "task": result.get("task_plan"),
        "provider": result.get("provider"),
        "memory_count": result.get("memory_count", 0),
        "voice_mode": "tap_to_talk",
    }
