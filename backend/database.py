import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime


# Keep the database beside this module so launching the API from a different
# working directory does not silently create a second, empty database.
DATABASE_PATH = Path(__file__).resolve().parent / "screen_ai.db"


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                screens_considered INTEGER NOT NULL DEFAULT 0,
                task_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        # Store task snapshots as an event history. The latest event for a
        # task_key tells us whether that task is still active or was stopped.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_key TEXT NOT NULL,
                task_name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT NOT NULL,
                current_step TEXT,
                next_step TEXT,
                completed_steps_json TEXT NOT NULL DEFAULT '[]'
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_task_events_key_id ON task_events(task_key, id)")


def save_observation(observation):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO observations (timestamp, filename, file_size, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                observation.get("timestamp", datetime.now().isoformat()),
                observation["filename"],
                observation["file_size"],
                observation["status"],
            ),
        )


def get_recent_observations(limit=5):
    limit = max(0, min(int(limit), 100))
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, timestamp, filename, file_size, status
            FROM observations ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_interaction(question, answer, screens_considered=0, task=None):
    timestamp = datetime.now().isoformat()
    task_data = task or {}
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO interactions (timestamp, question, answer, screens_considered, task_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                str(question)[:1000],
                str(answer)[:4000],
                max(0, int(screens_considered or 0)),
                json.dumps(task_data, ensure_ascii=False),
            ),
        )
        interaction_id = cursor.lastrowid
    return {
        "id": interaction_id,
        "timestamp": timestamp,
        "question": str(question)[:1000],
        "answer": str(answer)[:4000],
        "screens_considered": max(0, int(screens_considered or 0)),
        "task": task_data,
    }


def get_recent_interactions(limit=20):
    limit = max(0, min(int(limit), 100))
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, timestamp, question, answer, screens_considered, task_json
            FROM interactions ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = []
    for row in reversed(rows):
        try:
            task_data = json.loads(row["task_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            task_data = {}
        results.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "question": row["question"],
            "answer": row["answer"],
            "screens_considered": row["screens_considered"],
            "task": task_data,
        })
    return results


def save_task_state(task_state, status="active"):
    if not isinstance(task_state, dict) or not task_state.get("task"):
        return None
    task_key = str(task_state.get("task_key") or "")
    if not task_key:
        return None
    status = status if status in {"active", "stopped", "completed"} else "active"
    now = datetime.now().isoformat()
    created_at = task_state.get("created_at") or now
    completed_steps = task_state.get("completed_steps") or []
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO task_events
                (task_key, task_name, status, created_at, updated_at,
                 current_step, next_step, completed_steps_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_key,
                str(task_state["task"])[:200],
                status,
                created_at,
                now,
                str(task_state.get("current_step") or "")[:300] or None,
                str(task_state.get("next_step") or "")[:300] or None,
                json.dumps(completed_steps[-30:], ensure_ascii=False),
            ),
        )
        return cursor.lastrowid


def _task_from_row(row):
    try:
        completed_steps = json.loads(row["completed_steps_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        completed_steps = []
    return {
        "task_key": row["task_key"],
        "task": row["task_name"],
        "status": row["status"],
        "current_step": row["current_step"],
        "next_step": row["next_step"],
        "completed_steps": completed_steps if isinstance(completed_steps, list) else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_active_task():
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT event.* FROM task_events AS event
            WHERE event.id = (
                SELECT MAX(latest.id) FROM task_events AS latest
                WHERE latest.task_key = event.task_key
            ) AND event.status = 'active'
            ORDER BY event.id DESC LIMIT 1
            """
        ).fetchone()
    return _task_from_row(row) if row else None


def get_recent_tasks(limit=20):
    limit = max(0, min(int(limit), 100))
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT event.* FROM task_events AS event
            WHERE event.id = (
                SELECT MAX(latest.id) FROM task_events AS latest
                WHERE latest.task_key = event.task_key
            )
            ORDER BY event.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_task_from_row(row) for row in rows]
