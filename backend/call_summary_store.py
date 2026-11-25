"""Account-protected SQLite call history for the CHERRY AI receptionist."""
from __future__ import annotations
import os
import re
import sqlite3
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException
import identity_api

DB_PATH = Path(__file__).resolve().parent / "cherry_calls.db"
router = APIRouter(prefix="/call-receptionist", tags=["CHERRY AI Call Receptionist"])


def _owner_id() -> str:
    return os.getenv("CHERRY_CALL_OWNER_USER_ID", "").strip()


def _require_owner(authorization: str | None) -> str:
    owner = _owner_id()
    if not owner:
        raise HTTPException(status_code=503, detail="Call history is not configured. Set CHERRY_CALL_OWNER_USER_ID.")
    account = identity_api._account(authorization)
    user_id = str(account.get("user_id", ""))
    if not user_id or user_id != owner:
        raise HTTPException(status_code=403, detail="This account cannot access these call records.")
    return owner


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS call_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, ended_at TEXT NOT NULL,
            caller_number TEXT, destination_number TEXT, outcome TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0, transcript TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '', caller_name TEXT NOT NULL DEFAULT '',
            purpose TEXT NOT NULL DEFAULT '', urgency TEXT NOT NULL DEFAULT 'unknown',
            callback_requested INTEGER NOT NULL DEFAULT 0, callback_time TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'new', owner_user_id TEXT NOT NULL DEFAULT '')""")
        columns = {row[1] for row in db.execute("PRAGMA table_info(call_summaries)")}
        if "owner_user_id" not in columns:
            db.execute("ALTER TABLE call_summaries ADD COLUMN owner_user_id TEXT NOT NULL DEFAULT ''")
        owner = _owner_id()
        if owner:
            db.execute("UPDATE call_summaries SET owner_user_id=? WHERE owner_user_id=''", (owner,))
        db.execute("CREATE INDEX IF NOT EXISTS idx_cherry_calls_owner ON call_summaries(owner_user_id, id DESC)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_cherry_calls_started ON call_summaries(started_at DESC)")


def extract_call_details(transcript: str) -> dict[str, str | int]:
    """Extract cautious structured fields from caller speech only; never infer a name."""
    text = " ".join((transcript or "").split())
    caller_parts = re.findall(r"Caller:\s*(.*?)(?=CHERRY AI:|Caller:|$)", text, flags=re.I)
    caller_text = " ".join(caller_parts).strip()
    caller_low = caller_text.lower()

    name = ""
    name_patterns = (
        r"\bmy name is\s+([A-Z][a-zA-Z'’-]{1,40}(?:\s+[A-Z][a-zA-Z'’-]{1,40}){0,2})",
        r"\bthis is\s+([A-Z][a-zA-Z'’-]{1,40}(?:\s+[A-Z][a-zA-Z'’-]{1,40}){0,2})",
        r"\bI am\s+([A-Z][a-zA-Z'’-]{1,40}(?:\s+[A-Z][a-zA-Z'’-]{1,40}){0,2})",
        r"\bI'm\s+([A-Z][a-zA-Z'’-]{1,40}(?:\s+[A-Z][a-zA-Z'’-]{1,40}){0,2})",
    )
    for pattern in name_patterns:
        match = re.search(pattern, caller_text, flags=re.I)
        if match:
            candidate = match.group(1).strip(" .,!?:;")
            if candidate.lower() not in {"calling", "call", "looking", "here", "just", "trying"}:
                name = candidate[:80]
                break

    callback_match = re.search(
        r"\b(call(?:\s+me)?\s+back|callback|return(?:\s+the)?\s+call|reach\s+me)\b",
        caller_low,
    )
    callback_requested = 0
    if callback_match:
        before_callback = caller_low[max(0, callback_match.start() - 40):callback_match.start()]
        # Avoid treating explicit refusals as callback requests.
        negated_callback = re.search(r"\b(?:don't|do not|never|no|not|without)\s*$", before_callback) or re.search(
            r"\b(?:don't|do not|doesn't|does not)\s+(?:want|need)\s+(?:a\s+)?$",
            before_callback,
        )
        callback_requested = int(not bool(negated_callback))
    time_text = ""
    if callback_requested:
        time_patterns = (
            r"\b(?:call(?:\s+me)?\s+back|callback|return(?:\s+the)?\s+call|reach\s+me)\s+(?:at|around|after|before|in)\s+([^,.!?;]{1,50})",
            r"\b(?:call(?:\s+me)?\s+back|callback|return(?:\s+the)?\s+call|reach\s+me)\s+(tomorrow(?:\s+(?:morning|afternoon|evening))?|today(?:\s+(?:morning|afternoon|evening))?|(?:this|next)\s+(?:morning|afternoon|evening|week|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))",
        )
        for pattern in time_patterns:
            match = re.search(pattern, caller_text, flags=re.I)
            if match:
                time_text = re.sub(r"\s+", " ", match.group(1)).strip()[:80]
                break

    urgency = "unknown" if not caller_text else "normal"
    urgent_match = re.search(r"\b(urgent|emergency|immediately|as soon as possible)\b", caller_low)
    if urgent_match:
        before = caller_low[max(0, urgent_match.start() - 18):urgent_match.start()]
        if not re.search(r"\b(not|no|isn't|is not)\s*$", before):
            urgency = "urgent"

    purpose = ""
    purpose_patterns = (
        r"\b(?:I'm|I am)\s+calling\s+(?:about|regarding)\s+([^.!?]{3,180})",
        r"\bcalling\s+(?:about|regarding)\s+([^.!?]{3,180})",
        r"\b(?:need help with|would like to discuss|the reason is|regarding)\s+([^.!?]{3,180})",
    )
    for pattern in purpose_patterns:
        match = re.search(pattern, caller_text, flags=re.I)
        if match:
            purpose = re.sub(r"\s+", " ", match.group(1)).strip(" ,;:")[:180]
            break
    if not purpose:
        # Use a short caller sentence as a fallback, excluding greeting/name-only phrases.
        sentences = re.split(r"(?<=[.!?])\s+", caller_text)
        for sentence in sentences:
            candidate = sentence.strip()
            if candidate and not re.search(r"\b(?:hello|hi|my name is|this is|call me back|callback)\b", candidate, flags=re.I):
                purpose = candidate[:180]
                break

    return {
        "caller_name": name,
        "purpose": purpose,
        "urgency": urgency,
        "callback_requested": callback_requested,
        "callback_time": time_text,
    }


def store_call(started_at, ended_at, caller, destination, outcome, duration, transcript):
    owner = _owner_id()
    if not owner:
        raise RuntimeError("Set CHERRY_CALL_OWNER_USER_ID before accepting receptionist calls.")
    init_db()
    clean = " ".join((transcript or "").split())
    details = extract_call_details(transcript or "")
    parts = []
    if details["caller_name"]:
        parts.append(f"Caller {details['caller_name']}")
    if details["purpose"]:
        parts.append(f"called about {details['purpose']}")
    if details["urgency"] == "urgent":
        parts.append("marked urgent")
    if details["callback_requested"]:
        callback_text = "requested a callback"
        if details["callback_time"]:
            callback_text += f" ({details['callback_time']})"
        parts.append(callback_text)
    summary = ". ".join(parts).strip()
    if summary:
        summary += "."
    else:
        summary = clean[:1200] if clean else "No transcript captured; caller details need manual review."
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute("""INSERT INTO call_summaries
            (started_at,ended_at,caller_number,destination_number,outcome,duration_seconds,
             transcript,summary,caller_name,purpose,urgency,callback_requested,callback_time,status,owner_user_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?)""",
            (started_at, ended_at, caller, destination, outcome, max(0, int(duration)),
             transcript or "", summary, details["caller_name"], details["purpose"], details["urgency"],
             details["callback_requested"], details["callback_time"], owner))
        return cur.lastrowid


@router.get("/calls")
def history(limit: int = 25, authorization: str | None = Header(default=None)):
    owner = _require_owner(authorization)
    init_db()
    limit = max(1, min(limit, 100))
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("""SELECT id,started_at,ended_at,caller_number,outcome,duration_seconds,
            summary,caller_name,purpose,urgency,callback_requested,callback_time,status
            FROM call_summaries WHERE owner_user_id=? ORDER BY id DESC LIMIT ?""",
            (owner, limit)).fetchall()
    return {"success": True, "calls": [dict(row) for row in rows]}


@router.get("/calls/{call_id}")
def detail(call_id: int, authorization: str | None = Header(default=None)):
    owner = _require_owner(authorization)
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM call_summaries WHERE id=? AND owner_user_id=?",
                         (call_id, owner)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"success": True, "call": dict(row)}


@router.patch("/calls/{call_id}/status")
def update_status(call_id: int, status: str, authorization: str | None = Header(default=None)):
    owner = _require_owner(authorization)
    if status not in {"new", "reviewed", "callback_done"}:
        raise HTTPException(status_code=400, detail="Status must be new, reviewed, or callback_done")
    init_db()
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute("UPDATE call_summaries SET status=? WHERE id=? AND owner_user_id=?",
                         (status, call_id, owner))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"success": True, "id": call_id, "status": status}
