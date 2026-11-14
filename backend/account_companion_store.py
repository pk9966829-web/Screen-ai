"""Account-scoped companion conversation storage."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("VOSI_AGENT_DB_PATH", str(Path(__file__).with_name("vosi_agent.db"))))


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 10000")
    return db


def initialize():
    with _connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS account_companion_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_account_companion_turns_user_id ON account_companion_turns(user_id, id)")


def save_turn(user_id: str, question: str, answer: str) -> dict[str, Any]:
    from datetime import datetime, timezone
    initialize()
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        cursor = db.execute(
            "INSERT INTO account_companion_turns (user_id, timestamp, question, answer) VALUES (?, ?, ?, ?)",
            (user_id, timestamp, str(question)[:1000], str(answer)[:4000]),
        )
        turn_id = cursor.lastrowid
    return {"id": turn_id, "timestamp": timestamp, "question": str(question)[:1000], "answer": str(answer)[:4000]}


def get_recent_turns(user_id: str, limit: int = 30) -> list[dict[str, Any]]:
    initialize()
    safe_limit = max(1, min(int(limit), 100))
    with _connect() as db:
        rows = db.execute(
            "SELECT id, timestamp, question, answer FROM account_companion_turns WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, safe_limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]
