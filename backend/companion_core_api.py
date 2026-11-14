"""Authenticated shared chat API for VOSI's paired companion devices.

The desktop /ask contract remains unchanged. Android and desktop companion clients
can use these routes to share the same conversation history and companion memory.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import agent_api
from agent_runtime import AgentRuntimeError
from companion_brain import answer_companion, get_companion_memories
from database import get_recent_interactions, save_interaction

router = APIRouter(prefix="/companion", tags=["VOSI Companion Core"])


class CompanionChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def _paired_device(authorization: str | None) -> dict[str, Any]:
    scheme, separator, token = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Pair this device with VOSI first.")
    try:
        device = agent_api.devices.authenticate(token.strip())
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=401, detail="The paired-device credential is invalid or revoked.") from exc
    if device.get("platform") not in {"android", "desktop"}:
        raise HTTPException(status_code=403, detail="Companion chat is available only to paired Android and desktop devices.")
    return device


@router.post("/chat")
def companion_chat(
    request: CompanionChatRequest,
    authorization: str | None = Header(default=None),
):
    """Create a friend-style chat turn shared by the user's paired devices."""
    device = _paired_device(authorization)
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Write a message before sending it to VOSI.")

    recent = get_recent_interactions(limit=8)
    result = answer_companion(
        message,
        recent_interactions=recent,
        task_state={},
        runtime=agent_api.runtime,
        paired_devices=agent_api.devices.list_devices(),
        origin_device_id=device.get("device_id"),
    )
    response_text = str(result.get("understanding") or "I'm here, but I couldn't prepare a response. Please try again.")
    recorded = False
    if result.get("success"):
        save_interaction(message, response_text, screens_considered=0, task={})
        recorded = True

    return {
        "success": bool(result.get("success")),
        "device_id": device.get("device_id"),
        "platform": device.get("platform"),
        "message": message,
        "response": response_text[:12000],
        "task": result.get("task_plan"),
        "provider": result.get("provider"),
        "memory_count": result.get("memory_count", len(get_companion_memories())),
        "interaction_recorded": recorded,
    }


@router.get("/chat/history")
def companion_chat_history(
    limit: int = 30,
    authorization: str | None = Header(default=None),
):
    """Return recent shared companion turns to a paired Android or desktop device."""
    device = _paired_device(authorization)
    safe_limit = max(1, min(int(limit), 100))
    return {
        "success": True,
        "device_id": device.get("device_id"),
        "interactions": get_recent_interactions(limit=safe_limit),
        "memory_count": len(get_companion_memories()),
    }
