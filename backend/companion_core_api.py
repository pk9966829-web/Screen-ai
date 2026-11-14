"""Account-isolated companion chat for authenticated, paired VOSI devices."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

import agent_api
import identity_api
from agent_runtime import AgentRuntimeError
from identity_store import IdentityError
from account_companion_store import get_recent_turns, save_turn
from companion_brain import answer_companion, get_companion_memories

router = APIRouter(prefix="/companion", tags=["VOSI Companion Core"])


class CompanionChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def _paired_account_device(
    device_authorization: str | None,
    account_authorization: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scheme, separator, token = (device_authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Pair this device with VOSI first.")
    account_scheme, account_separator, account_token = (account_authorization or "").partition(" ")
    if not account_separator or account_scheme.lower() != "bearer" or not account_token.strip():
        raise HTTPException(status_code=401, detail="Sign in to your VOSI account to use shared companion chat.")
    try:
        device = agent_api.devices.authenticate(token.strip())
        account = identity_api.store.authenticate(account_token.strip())
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=401, detail="The paired-device credential is invalid or revoked.") from exc
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if device.get("platform") not in {"android", "desktop"}:
        raise HTTPException(status_code=403, detail="Companion chat is available only to paired Android and desktop devices.")
    try:
        linked_user = identity_api.store.get_linked_device_user(device["device_id"])
        if linked_user is None:
            # Possession of both valid credentials proves account and device control.
            identity_api.store.link_device(account["user_id"], device["device_id"])
        elif linked_user != account["user_id"]:
            raise HTTPException(status_code=403, detail="This device is linked to a different VOSI account.")
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return device, account


@router.post("/chat")
def companion_chat(
    request: CompanionChatRequest,
    authorization: str | None = Header(default=None),
    x_vosi_account_token: str | None = Header(default=None),
):
    """Create a private chat turn shared only by devices linked to this account."""
    device, account = _paired_account_device(authorization, f"Bearer {x_vosi_account_token}" if x_vosi_account_token else None)
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Write a message before sending it to VOSI.")
    user_id = account["user_id"]
    recent = get_recent_turns(user_id, limit=8)
    # The task ledger is not yet account-scoped. Do not create cross-account tasks
    # from this account-isolated chat until the runtime migration is complete.
    result = answer_companion(
        message,
        recent_interactions=recent,
        task_state={},
        runtime=None,
        paired_devices=[],
        origin_device_id=device.get("device_id"),
        user_id=user_id,
    )
    response_text = str(result.get("understanding") or "I'm here, but I couldn't prepare a response. Please try again.")
    recorded = False
    if result.get("success"):
        save_turn(user_id, message, response_text)
        recorded = True
    return {
        "success": bool(result.get("success")),
        "device_id": device.get("device_id"),
        "platform": device.get("platform"),
        "message": message,
        "response": response_text[:12000],
        "task": None,
        "provider": result.get("provider"),
        "memory_count": result.get("memory_count", len(get_companion_memories(user_id=user_id))),
        "interaction_recorded": recorded,
    }


@router.get("/chat/history")
def companion_chat_history(
    limit: int = 30,
    authorization: str | None = Header(default=None),
    x_vosi_account_token: str | None = Header(default=None),
):
    """Return only this account's shared companion turns."""
    device, account = _paired_account_device(authorization, f"Bearer {x_vosi_account_token}" if x_vosi_account_token else None)
    safe_limit = max(1, min(int(limit), 100))
    user_id = account["user_id"]
    return {
        "success": True,
        "device_id": device.get("device_id"),
        "interactions": get_recent_turns(user_id, limit=safe_limit),
        "memory_count": len(get_companion_memories(user_id=user_id)),
    }
