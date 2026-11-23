"""Account-protected SQLite call history for the CHERRY AI receptionist."""
from __future__ import annotations
import os
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


def store_call(started_at, ended_at, caller, destination, outcome, duration, transcript):
    owner = _owner_id()
    if not owner:
        raise RuntimeError("Set CHERRY_CALL_OWNER_USER_ID before accepting receptionist calls.")
    init_db()
    clean = " ".join((transcript or "").split())
    low = clean.lower()
    urgency = "urgent" if any(k in low for k in ("urgent", "emergency", "immediately", "as soon as possible")) else ("normal" if clean else "unknown")
    callback = int(any(k in low for k in ("call back", "callback", "call me", "return the call")))
    summary = clean[:1200] if clean else "No transcript captured; caller details need manual review."
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute("""INSERT INTO call_summaries
            (started_at,ended_at,caller_number,destination_number,outcome,duration_seconds,
             transcript,summary,purpose,urgency,callback_requested,status,owner_user_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'new',?)""",
            (started_at, ended_at, caller, destination, outcome, max(0, int(duration)),
             transcript or "", summary, clean[:500], urgency, callback, owner))
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
