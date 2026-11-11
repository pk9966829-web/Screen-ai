import os
import secrets
import threading
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/companion", tags=["Android Companion"])

_lock = threading.Lock()
_messages = []
_last_sync = None


class WhatsAppPreview(BaseModel):
    key: str = Field(max_length=500)
    sender: str = Field(max_length=300)
    message: str = Field(max_length=5000)
    postedAt: int


class WhatsAppSyncRequest(BaseModel):
    messages: List[WhatsAppPreview] = Field(max_length=30)


def _authorize(authorization: Optional[str]):
    expected = os.getenv("VOSI_COMPANION_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Companion pairing is not configured.")

    scheme, separator, supplied = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer":
        supplied = ""
    supplied = supplied.strip()

    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid companion token.")


@router.post("/whatsapp/sync")
def sync_whatsapp(
    request: WhatsAppSyncRequest,
    authorization: Optional[str] = Header(default=None),
):
    _authorize(authorization)

    global _messages, _last_sync
    safe_messages = [
        item.dict()
        for item in sorted(
            request.messages,
            key=lambda item: item.postedAt,
            reverse=True,
        )
    ]

    with _lock:
        _messages = safe_messages[:30]
        _last_sync = datetime.now(timezone.utc).isoformat()
        received = len(_messages)

    return {
        "success": True,
        "received": received,
        "synced_at": _last_sync,
    }


@router.get("/whatsapp")
def get_whatsapp_messages(
    authorization: Optional[str] = Header(default=None),
):
    _authorize(authorization)

    with _lock:
        return {
            "success": True,
            "messages": list(_messages),
            "synced_at": _last_sync,
        }
