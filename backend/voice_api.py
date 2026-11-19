"""Authenticated tap-to-talk voice turns for paired VOSI Android and desktop companions.

Each platform performs speech recognition and speech playback locally; only the recognized
transcript is sent to this API. Raw microphone audio is not uploaded by this module.
"""
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import agent_api
from agent_runtime import AgentRuntimeError
from companion_brain import answer_companion
from database import get_active_task, get_recent_interactions, save_interaction
from account_companion_store import get_recent_turns, save_turn
from companion_core_api import _paired_account_device

router = APIRouter(prefix="/companion", tags=["VOSI Companion Voice"])


class VoiceTurnRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)


def _authenticate_voice_device(authorization: str | None) -> dict[str, Any]:
    scheme, separator, token = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Pair this device with VOSI first.")
    try:
        device = agent_api.devices.authenticate(token.strip())
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=401, detail="The paired-device credential is invalid or revoked.") from exc
    if device.get("platform") not in {"android", "desktop"}:
        raise HTTPException(status_code=403, detail="Voice companion turns are available only to paired Android and desktop devices.")
    return device


@router.post("/voice")
def create_voice_turn(
    request: VoiceTurnRequest,
    authorization: str | None = Header(default=None),
    x_vosi_account_token: str | None = Header(default=None),
):
    """Process one transcript with account-owned history when a session is supplied."""
    transcript = request.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=422, detail="Speak a message before sending it to VOSI.")

    user_id = None
    if x_vosi_account_token:
        device, account = _paired_account_device(
            authorization,
            f"Bearer {x_vosi_account_token.strip()}",
        )
        user_id = account["user_id"]
        recent = get_recent_turns(user_id, limit=8)
        account_tasks = agent_api.runtime.list_tasks(100, user_id=user_id)
        task_state = next(
            (task for task in account_tasks if task["state"] not in {"completed", "failed", "cancelled"}),
            {},
        )
        paired_devices = agent_api.devices.list_devices(user_id=user_id)
    else:
        if os.getenv("VOSI_MULTI_TENANT", "").strip().lower() in {"1", "true", "yes"}:
            raise HTTPException(status_code=401, detail="Sign in to your VOSI account before using shared voice chat.")
        device = _authenticate_voice_device(authorization)
        recent = get_recent_interactions(limit=8)
        task_state = get_active_task() or {}
        paired_devices = agent_api.devices.list_devices()

    result = answer_companion(
        transcript,
        recent_interactions=recent,
        task_state=task_state,
        runtime=agent_api.runtime,
        paired_devices=paired_devices,
        origin_device_id=device.get("device_id"),
        user_id=user_id,
    )
    response_text = str(result.get("understanding") or "I couldn't prepare a response. Please try again.")
    if result.get("success"):
        if user_id:
            save_turn(user_id, transcript, response_text)
        else:
            save_interaction(transcript, response_text, screens_considered=0, task={}, user_id=None)

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
