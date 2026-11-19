"""Safe, account-scoped call receptionist conversation sessions.

This API is a text-turn simulation layer. It does not answer cellular calls, capture audio,
or provide a telephony bridge. A future audio adapter must call these session functions only
after a supported, consented call transport is available.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from companion_core_api import _paired_account_device

router = APIRouter(prefix="/companion/calls", tags=["VOSI Call Assistant"])
DB_PATH = Path(os.getenv("VOSI_CALL_DB_PATH", str(Path(__file__).with_name("vosi_calls.sqlite3"))))

URGENT_TERMS = (
    "emergency", "urgent", "accident", "hospital", "ambulance", "police",
    "danger", "critical", "unconscious", "life threatening",
)
SUPPORTED_LANGUAGES = {"auto", "en", "hi", "kn"}


def _detect_language(text: str, requested: str = "auto") -> str:
    """Detect Hindi/Kannada from Unicode script; otherwise use English."""
    requested = (requested or "auto").strip().lower()
    if requested in {"english", "en"}:
        return "en"
    if requested in {"hindi", "hi"}:
        return "hi"
    if requested in {"kannada", "kn"}:
        return "kn"
    if requested != "auto":
        requested = "auto"
    devanagari = sum("\\u0900" <= ch <= "\\u097f" for ch in text)
    kannada = sum("\\u0c80" <= ch <= "\\u0cff" for ch in text)
    if kannada > 0 and kannada >= devanagari:
        return "kn"
    if devanagari > 0:
        return "hi"
    return "en"


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 10000")
    return db


def _initialize():
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS call_sessions (
            session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, caller_name TEXT,
            caller_number TEXT, status TEXT NOT NULL, transcript TEXT NOT NULL,
            message TEXT NOT NULL, urgent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_call_sessions_user ON call_sessions(user_id, updated_at)")


def _account(authorization: str | None, account_token: str | None) -> str:
    _, account = _paired_account_device(
        authorization,
        f"Bearer {account_token.strip()}" if account_token and account_token.strip() else None,
    )
    return str(account["user_id"])


def _classify(text: str) -> dict[str, Any]:
    normalized = re.sub(r"\s+", " ", text).strip()
    lower = normalized.lower()
    urgent = any(term in lower for term in URGENT_TERMS)
    if any(term in lower for term in ("call me", "tell him", "tell her", "message", "let them know")):
        intent = "message"
    elif any(term in lower for term in ("meeting", "appointment", "schedule", "available", "free")):
        intent = "scheduling_request"
    elif any(term in lower for term in ("who are you", "are you an ai", "are you real")):
        intent = "identity"
    else:
        intent = "general"
    return {"intent": intent, "urgent": urgent}


def _reply(text: str, intent: str, urgent: bool) -> str:
    if urgent:
        return ("I'm VOSI, an AI assistant. This sounds urgent. I will flag it for the account holder. "
                "Please tell me briefly what happened and the best way for them to reach you.")
    if intent == "identity":
        return "I'm VOSI, an AI assistant answering on the account holder's behalf. How can I help?"
    if intent == "scheduling_request":
        return ("I can't see or promise the account holder's availability. I can take your requested "
                "date, time, and purpose and pass the details along.")
    if intent == "message":
        return "Of course. Please tell me the exact message, your name, and the best way to contact you."
    return ("I'm VOSI, an AI assistant. The account holder may be busy right now. "
            "What are you calling about? I can take a message and pass it along.")


class CallStartRequest(BaseModel):
    caller_name: str | None = Field(default=None, max_length=120)
    caller_number: str | None = Field(default=None, max_length=40)


class CallTurnRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    transcript: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="auto", max_length=12)


class CallFinishRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)


@router.post("/sessions")
def start_call_session(
    request: CallStartRequest,
    authorization: str | None = Header(default=None),
    x_vosi_account_token: str | None = Header(default=None),
):
    user_id = _account(authorization, x_vosi_account_token)
    _initialize()
    now = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid4())
    with _connect() as db:
        db.execute(
            "INSERT INTO call_sessions(session_id,user_id,caller_name,caller_number,status,transcript,message,urgent,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (session_id, user_id, (request.caller_name or "").strip()[:120],
             (request.caller_number or "").strip()[:40], "active", "[]", "", 0, now, now),
        )
    return {"success": True, "session_id": session_id, "status": "active",
            "disclosure": "I'm VOSI, an AI assistant answering on the account holder's behalf.",
            "transport": "simulation_only", "cellular_audio_connected": False}


@router.post("/turn")
def call_turn(
    request: CallTurnRequest,
    authorization: str | None = Header(default=None),
    x_vosi_account_token: str | None = Header(default=None),
):
    user_id = _account(authorization, x_vosi_account_token)
    _initialize()
    text = request.transcript.strip()
    if not text:
        raise HTTPException(status_code=422, detail="A caller transcript is required.")
    with _connect() as db:
        row = db.execute("SELECT * FROM call_sessions WHERE session_id=? AND user_id=?",
                         (request.session_id, user_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Call session not found.")
        if row["status"] != "active":
            raise HTTPException(status_code=409, detail="This call session has ended.")
        history = json.loads(row["transcript"] or "[]")
        requested_language = request.language.strip().lower()
        if requested_language not in SUPPORTED_LANGUAGES:
            requested_language = "auto"
        classification = _classify(text, requested_language)
        reply = _reply(text, classification["intent"], classification["urgent"], classification["language"])
        history.append({"caller": text[:2000], "assistant": reply, "intent": classification["intent"]})
        # A message is captured only when the caller explicitly supplies one.
        message = row["message"]
        if classification["intent"] == "message":
            message = (message + "\n" + text).strip()[-4000:]
        urgent = bool(row["urgent"] or classification["urgent"])
        now = datetime.now(timezone.utc).isoformat()
        db.execute("UPDATE call_sessions SET transcript=?,message=?,urgent=?,updated_at=? WHERE session_id=? AND user_id=?",
                   (json.dumps(history[-30:]), message, int(urgent), now, request.session_id, user_id))
    return {"success": True, "session_id": request.session_id, "response": reply,
            "intent": classification["intent"], "language": classification["language"], "urgent": urgent,
            "message_captured": bool(message), "requires_human_attention": urgent}


@router.post("/finish")
def finish_call_session(
    request: CallFinishRequest,
    authorization: str | None = Header(default=None),
    x_vosi_account_token: str | None = Header(default=None),
):
    user_id = _account(authorization, x_vosi_account_token)
    _initialize()
    with _connect() as db:
        row = db.execute("SELECT * FROM call_sessions WHERE session_id=? AND user_id=?",
                         (request.session_id, user_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Call session not found.")
        history = json.loads(row["transcript"] or "[]")
        summary = " ".join(item["caller"] for item in history)[-1000:]
        db.execute("UPDATE call_sessions SET status='ended',updated_at=? WHERE session_id=? AND user_id=?",
                   (datetime.now(timezone.utc).isoformat(), request.session_id, user_id))
    return {"success": True, "session_id": request.session_id, "status": "ended",
            "summary": summary, "message": row["message"], "urgent": bool(row["urgent"]),
            "requires_human_attention": bool(row["urgent"]), "transcript_turns": len(history)}
