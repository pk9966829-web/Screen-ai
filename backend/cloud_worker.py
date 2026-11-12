"""Authenticated lease API for VOSI's separately deployed cloud executors.

The API only leases capabilities explicitly enabled by deployment configuration.
It does not itself browse, sign in, submit forms, or place orders.
"""
from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agent_api import runtime
from agent_runtime import CAPABILITIES, AgentRuntimeError

router = APIRouter(prefix="/cloud-worker", tags=["VOSI Cloud Worker"])


def _worker_config() -> tuple[str, str, str, set[str], int]:
    token = os.getenv("VOSI_CLOUD_WORKER_TOKEN", "").strip()
    worker_id = os.getenv("VOSI_CLOUD_WORKER_ID", "primary").strip()
    platform = os.getenv("VOSI_CLOUD_WORKER_PLATFORM", "browser").strip()
    configured = {
        item.strip() for item in os.getenv("VOSI_CLOUD_WORKER_CAPABILITIES", "browser.search_products").split(",")
        if item.strip()
    }
    # A cloud worker may never opt itself into an approval-gated or irreversible action.
    allowed = {
        name for name in configured
        if name in CAPABILITIES
        and platform in CAPABILITIES[name]["platforms"]
        and CAPABILITIES[name]["risk"] == "low"
        and not CAPABILITIES[name]["requires_approval"]
        and CAPABILITIES[name]["reversible"]
    }
    lease_seconds = max(30, min(int(os.getenv("VOSI_CLOUD_WORKER_LEASE_SECONDS", "180")), 900))
    return token, worker_id, platform, allowed, lease_seconds


def _authorize(authorization: str | None) -> tuple[str, str, set[str], int]:
    token, worker_id, platform, capabilities, lease_seconds = _worker_config()
    scheme, _, supplied = (authorization or "").partition(" ")
    if not token:
        raise HTTPException(status_code=503, detail="Cloud worker API is disabled until VOSI_CLOUD_WORKER_TOKEN is configured.")
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied.strip(), token):
        raise HTTPException(status_code=401, detail="Invalid cloud worker credential.")
    if not worker_id or len(worker_id) > 80 or not capabilities:
        raise HTTPException(status_code=503, detail="Configure a worker ID and at least one supported low-risk capability.")
    return f"cloud-worker:{worker_id}", platform, capabilities, lease_seconds


def _recover_expired_safe_claims(lease_seconds: int) -> int:
    """Requeue only low-risk reversible cloud claims; never replay an order or other irreversible action."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)).isoformat()
    recovered = 0
    with runtime._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            """SELECT s.task_id, s.step_id, s.capability, s.approval_required
               FROM agent_steps s
               WHERE s.state = 'running' AND s.claimed_by LIKE 'cloud-worker:%'
                 AND s.claimed_at IS NOT NULL AND s.claimed_at < ?""",
            (cutoff,),
        ).fetchall()
        for row in rows:
            metadata = CAPABILITIES.get(row["capability"], {})
            if row["approval_required"] or metadata.get("risk") != "low" or not metadata.get("reversible"):
                # Ambiguous outcome: leave it running for manual reconciliation.
                continue
            db.execute(
                """UPDATE agent_steps SET state = 'pending', claimed_by = NULL, claimed_at = NULL
                   WHERE task_id = ? AND step_id = ? AND state = 'running'""",
                (row["task_id"], row["step_id"]),
            )
            db.execute(
                """UPDATE agent_tasks SET state = 'ready', updated_at = ?
                   WHERE task_id = ? AND state = 'running'""",
                (datetime.now(timezone.utc).isoformat(), row["task_id"]),
            )
            recovered += 1
        db.commit()
    return recovered


class CloudWorkerResult(BaseModel):
    success: bool
    verified: bool
    receipt: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=2000)


@router.get("/health")
def cloud_worker_health(authorization: str | None = Header(default=None)):
    worker_id, platform, capabilities, lease_seconds = _authorize(authorization)
    return {
        "success": True, "worker_id": worker_id, "platform": platform,
        "capabilities": sorted(capabilities), "lease_seconds": lease_seconds,
        "execution_mode": "external-adapter-required",
    }


@router.post("/claim")
def claim_cloud_task(authorization: str | None = Header(default=None)):
    worker_id, platform, capabilities, lease_seconds = _authorize(authorization)
    recovered = _recover_expired_safe_claims(lease_seconds)
    for task in runtime.list_tasks(100):
        if task["state"] in {"completed", "failed", "cancelled"}:
            continue
        if task.get("scheduled_at") and task["scheduled_at"] > datetime.now(timezone.utc).isoformat():
            continue
        try:
            step = runtime.claim_next_step(task["task_id"], worker_id, platform, capabilities)
        except AgentRuntimeError:
            continue
        if step:
            return {
                "success": True, "recovered_expired_claims": recovered,
                "lease_seconds": lease_seconds,
                "task": {"task_id": task["task_id"], "goal": task["goal"]},
                "step": step,
                "idempotency_key": step["idempotency_key"],
            }
    return {"success": True, "task": None, "step": None, "recovered_expired_claims": recovered}


@router.post("/{task_id}/steps/{step_id}/heartbeat")
def heartbeat_cloud_claim(task_id: str, step_id: str, authorization: str | None = Header(default=None)):
    worker_id, _, _, _ = _authorize(authorization)
    with runtime._connect() as db:
        cursor = db.execute(
            """UPDATE agent_steps SET claimed_at = ?
               WHERE task_id = ? AND step_id = ? AND state = 'running' AND claimed_by = ?""",
            (datetime.now(timezone.utc).isoformat(), task_id, step_id, worker_id),
        )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=409, detail="This worker no longer holds the active task lease.")
    return {"success": True, "lease_renewed": True}


@router.post("/{task_id}/steps/{step_id}/result")
def submit_cloud_result(
    task_id: str, step_id: str, request: CloudWorkerResult,
    authorization: str | None = Header(default=None),
):
    worker_id, _, _, _ = _authorize(authorization)
    try:
        task = runtime.record_step_result(
            task_id, step_id, worker_id, request.success, request.verified,
            request.receipt, request.error,
        )
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"success": True, "task": task}
