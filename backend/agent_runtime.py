"""Durable, permission-aware task state for VOSI's cross-device agent foundation.

This module deliberately does not execute operating-system or browser actions.
Adapters must be registered separately and must return verified execution receipts.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CAPABILITIES: dict[str, dict[str, Any]] = {
    "screen.observe": {
        "platforms": ["desktop"],
        "risk": "low",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Read the screen currently shared with VOSI.",
    },
    "browser.read_visible_page": {
        "platforms": ["browser"],
        "risk": "low",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Read visible content from the active, user-authorized page.",
    },
    "browser.search_products": {
        "platforms": ["browser"],
        "risk": "low",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Search public product listings on a supported site.",
    },
    "browser.open_tab": {
        "platforms": ["browser"],
        "risk": "low",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Open a requested page in a new browser tab.",
    },
    "phone.contacts.read": {
        "platforms": ["android"],
        "risk": "medium",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Look up a contact after Android contacts permission is granted.",
    },
    "phone.call": {
        "platforms": ["android"],
        "risk": "high",
        "requires_permission": True,
        "requires_approval": True,
        "reversible": False,
        "description": "Place a phone call after the user confirms the target number.",
    },
    "phone.whatsapp.quick_reply": {
        "platforms": ["android"],
        "risk": "high",
        "requires_permission": True,
        "requires_approval": True,
        "reversible": False,
        "description": "Send a WhatsApp reply through a supported notification action.",
    },
    "email.send": {
        "platforms": ["desktop"],
        "risk": "high",
        "requires_permission": True,
        "requires_approval": True,
        "reversible": False,
        "description": "Send an email after the user reviews and confirms it.",
    },
    "device.alarm.create": {
        "platforms": ["desktop", "android"],
        "risk": "low",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Create a local alarm using the platform's supported API.",
    },
    "device.volume.set": {
        "platforms": ["desktop", "android"],
        "risk": "low",
        "requires_permission": True,
        "requires_approval": False,
        "reversible": True,
        "description": "Set device volume within the platform's supported limits.",
    },
}

TASK_STATES = {"planned", "awaiting_approval", "ready", "running", "completed", "failed", "cancelled"}
STEP_STATES = {"pending", "awaiting_approval", "ready", "running", "completed", "failed", "skipped"}
_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentRuntimeError(ValueError):
    """Raised when a task or step violates the VOSI agent contract."""


class AgentRuntime:
    """SQLite-backed task plan, approval, and execution-receipt ledger."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    goal TEXT NOT NULL,
                    origin_device_id TEXT,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    error TEXT
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_steps (
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    capability TEXT NOT NULL,
                    target_platform TEXT NOT NULL,
                    title TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    approval_required INTEGER NOT NULL,
                    approved_at TEXT,
                    idempotency_key TEXT NOT NULL,
                    claimed_by TEXT,
                    claimed_at TEXT,
                    finished_at TEXT,
                    receipt_json TEXT,
                    error TEXT,
                    PRIMARY KEY (task_id, step_id),
                    FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id)
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_agent_steps_ready ON agent_steps(task_id, position, state)")

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    @staticmethod
    def list_capabilities() -> list[dict[str, Any]]:
        return [{"name": name, **details} for name, details in CAPABILITIES.items()]

    def create_task(
        self,
        goal: str,
        steps: list[dict[str, Any]],
        origin_device_id: str | None = None,
        idempotency_key: str | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        goal = str(goal or "").strip()
        if not goal or len(goal) > 2000:
            raise AgentRuntimeError("Goal must contain 1 to 2000 characters.")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 30:
            raise AgentRuntimeError("A task must contain between 1 and 30 steps.")
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128):
            raise AgentRuntimeError("Invalid idempotency key.")

        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for position, raw in enumerate(steps):
            if not isinstance(raw, dict):
                raise AgentRuntimeError("Each step must be an object.")
            step_id = raw.get("step_id") or f"step-{position + 1}"
            capability = raw.get("capability")
            platform = raw.get("target_platform")
            title = str(raw.get("title") or "").strip()
            arguments = raw.get("arguments") or {}
            if not isinstance(step_id, str) or not _ID_RE.fullmatch(step_id) or step_id in seen_ids:
                raise AgentRuntimeError("Step IDs must be unique and use letters, numbers, '.', '_', ':', or '-'.")
            if capability not in CAPABILITIES:
                raise AgentRuntimeError(f"Unsupported capability: {capability!r}.")
            metadata = CAPABILITIES[capability]
            if platform not in metadata["platforms"]:
                raise AgentRuntimeError(f"Capability {capability} is not available on {platform!r}.")
            if not title or len(title) > 200:
                raise AgentRuntimeError("Each step needs a title of 1 to 200 characters.")
            if not isinstance(arguments, dict) or len(json.dumps(arguments, ensure_ascii=False)) > 10000:
                raise AgentRuntimeError("Step arguments must be an object under 10 KB.")
            seen_ids.add(step_id)
            normalized.append({
                "step_id": step_id,
                "position": position,
                "capability": capability,
                "target_platform": platform,
                "title": title,
                "arguments": arguments,
                "approval_required": bool(metadata["requires_approval"]),
                "state": "awaiting_approval" if metadata["requires_approval"] else "pending",
                "idempotency_key": uuid.uuid4().hex,
            })

        task_id = uuid.uuid4().hex
        now = _now()
        initial_state = "awaiting_approval" if any(s["approval_required"] for s in normalized) else "planned"
        with self._connect() as db:
            if idempotency_key:
                existing = db.execute(
                    "SELECT task_id FROM agent_tasks WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if existing:
                    return self.get_task(existing["task_id"])
            db.execute(
                """INSERT INTO agent_tasks
                   (task_id, idempotency_key, goal, origin_device_id, state, created_at, updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, idempotency_key, goal, origin_device_id, initial_state, now, now, expires_at),
            )
            for step in normalized:
                db.execute(
                    """INSERT INTO agent_steps
                       (task_id, step_id, position, capability, target_platform, title, arguments_json,
                        state, approval_required, idempotency_key)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id, step["step_id"], step["position"], step["capability"],
                        step["target_platform"], step["title"],
                        json.dumps(step["arguments"], ensure_ascii=False),
                        step["state"], int(step["approval_required"]), step["idempotency_key"],
                    ),
                )
        return self.get_task(task_id)

    def approve_step(self, task_id: str, step_id: str) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT state FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not task:
                raise AgentRuntimeError("Task not found.")
            step = db.execute(
                "SELECT state, approval_required FROM agent_steps WHERE task_id = ? AND step_id = ?",
                (task_id, step_id),
            ).fetchone()
            if not step:
                raise AgentRuntimeError("Step not found.")
            if not step["approval_required"]:
                raise AgentRuntimeError("This step does not require an approval override.")
            if step["state"] != "awaiting_approval":
                raise AgentRuntimeError("This step is not awaiting approval.")
            db.execute(
                "UPDATE agent_steps SET state = 'ready', approved_at = ? WHERE task_id = ? AND step_id = ?",
                (_now(), task_id, step_id),
            )
            remaining = db.execute(
                "SELECT COUNT(*) AS count FROM agent_steps WHERE task_id = ? AND state = 'awaiting_approval'",
                (task_id,),
            ).fetchone()["count"]
            state = "awaiting_approval" if remaining else "ready"
            db.execute("UPDATE agent_tasks SET state = ?, updated_at = ? WHERE task_id = ?", (state, _now(), task_id))
            db.commit()
        return self.get_task(task_id)

    def claim_next_step(self, task_id: str, device_id: str, device_platform: str, granted_capabilities: set[str]) -> dict[str, Any] | None:
        if not device_id or len(device_id) > 100:
            raise AgentRuntimeError("A valid device ID is required.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            task = db.execute("SELECT state, expires_at FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not task:
                raise AgentRuntimeError("Task not found.")
            if task["state"] in {"completed", "failed", "cancelled", "awaiting_approval"}:
                db.commit()
                return None
            if task["expires_at"] and task["expires_at"] <= _now():
                db.execute("UPDATE agent_tasks SET state = 'failed', error = 'Task expired', updated_at = ? WHERE task_id = ?", (_now(), task_id))
                db.commit()
                return None
            row = db.execute(
                """SELECT * FROM agent_steps
                   WHERE task_id = ? AND state IN ('pending', 'ready')
                   ORDER BY position LIMIT 1""",
                (task_id,),
            ).fetchone()
            if not row:
                db.commit()
                return None
            if row["approval_required"] and row["state"] != "ready":
                db.commit()
                return None
            # Platform identity must come from the paired-device registry, not the model plan.
            if row["target_platform"] != device_platform or row["capability"] not in granted_capabilities:
                db.commit()
                return None
            db.execute(
                """UPDATE agent_steps SET state = 'running', claimed_by = ?, claimed_at = ?
                   WHERE task_id = ? AND step_id = ? AND state IN ('pending', 'ready')""",
                (device_id, _now(), task_id, row["step_id"]),
            )
            db.execute("UPDATE agent_tasks SET state = 'running', updated_at = ? WHERE task_id = ?", (_now(), task_id))
            db.commit()
        return self.get_step(task_id, row["step_id"])

    def record_step_result(
        self,
        task_id: str,
        step_id: str,
        device_id: str,
        success: bool,
        verified: bool,
        receipt: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(receipt or {}, dict) or len(json.dumps(receipt or {}, ensure_ascii=False)) > 10000:
            raise AgentRuntimeError("Execution receipt must be an object under 10 KB.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            step = db.execute(
                "SELECT state, claimed_by FROM agent_steps WHERE task_id = ? AND step_id = ?",
                (task_id, step_id),
            ).fetchone()
            if not step:
                raise AgentRuntimeError("Step not found.")
            if step["state"] != "running" or step["claimed_by"] != device_id:
                raise AgentRuntimeError("Only the device holding the active execution claim can submit a result.")
            completed = bool(success and verified and receipt)
            state = "completed" if completed else "failed"
            db.execute(
                """UPDATE agent_steps SET state = ?, finished_at = ?, receipt_json = ?, error = ?
                   WHERE task_id = ? AND step_id = ?""",
                (state, _now(), json.dumps(receipt or {}, ensure_ascii=False), None if completed else (error or "Execution was not verified."), task_id, step_id),
            )
            task_row = db.execute("SELECT state FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not task_row:
                raise AgentRuntimeError("Task not found.")
            if task_row["state"] == "cancelled":
                raise AgentRuntimeError("Cancelled tasks cannot accept execution results.")
            remaining = db.execute(
                "SELECT COUNT(*) AS count FROM agent_steps WHERE task_id = ? AND state IN ('pending', 'ready', 'awaiting_approval', 'running')",
                (task_id,),
            ).fetchone()["count"]
            waiting_approval = db.execute(
                "SELECT COUNT(*) AS count FROM agent_steps WHERE task_id = ? AND state = 'awaiting_approval'",
                (task_id,),
            ).fetchone()["count"]
            failed = db.execute(
                "SELECT COUNT(*) AS count FROM agent_steps WHERE task_id = ? AND state = 'failed'",
                (task_id,),
            ).fetchone()["count"]
            task_state = (
                "failed" if failed else
                "awaiting_approval" if waiting_approval else
                "completed" if remaining == 0 else
                "ready"
            )
            db.execute("UPDATE agent_tasks SET state = ?, updated_at = ? WHERE task_id = ?", (task_state, _now(), task_id))
            db.commit()
        return self.get_task(task_id)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE agent_tasks SET state = 'cancelled', updated_at = ? WHERE task_id = ? AND state NOT IN ('completed', 'failed', 'cancelled')",
                (_now(), task_id),
            )
            if cursor.rowcount == 0 and not db.execute("SELECT 1 FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone():
                raise AgentRuntimeError("Task not found.")
            db.execute(
                "UPDATE agent_steps SET state = 'skipped' WHERE task_id = ? AND state IN ('pending', 'ready', 'awaiting_approval')",
                (task_id,),
            )
        return self.get_task(task_id)

    def get_step(self, task_id: str, step_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM agent_steps WHERE task_id = ? AND step_id = ?",
                (task_id, step_id),
            ).fetchone()
        return self._step_dict(row) if row else None

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as db:
            task = db.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not task:
                raise AgentRuntimeError("Task not found.")
            steps = db.execute(
                "SELECT * FROM agent_steps WHERE task_id = ? ORDER BY position",
                (task_id,),
            ).fetchall()
        return {
            "task_id": task["task_id"],
            "goal": task["goal"],
            "origin_device_id": task["origin_device_id"],
            "state": task["state"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
            "expires_at": task["expires_at"],
            "error": task["error"],
            "steps": [self._step_dict(row) for row in steps],
        }

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._connect() as db:
            rows = db.execute("SELECT task_id FROM agent_tasks ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self.get_task(row["task_id"]) for row in rows]

    @staticmethod
    def _step_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "step_id": row["step_id"],
            "position": row["position"],
            "capability": row["capability"],
            "target_platform": row["target_platform"],
            "title": row["title"],
            "arguments": json.loads(row["arguments_json"]),
            "state": row["state"],
            "approval_required": bool(row["approval_required"]),
            "approved_at": row["approved_at"],
            "idempotency_key": row["idempotency_key"],
            "claimed_by": row["claimed_by"],
            "claimed_at": row["claimed_at"],
            "finished_at": row["finished_at"],
            "receipt": json.loads(row["receipt_json"]) if row["receipt_json"] else None,
            "error": row["error"],
        }
