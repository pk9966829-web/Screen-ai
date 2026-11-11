"""Authenticated HTTP surface for VOSI's task-planning foundation.

Execution is intentionally not exposed here until paired-device authentication and
capability-specific adapters are implemented.
"""
import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agent_runtime import AgentRuntime, AgentRuntimeError

router = APIRouter(prefix="/agent", tags=["VOSI Agent"])

_database_path = Path(os.getenv("VOSI_AGENT_DB_PATH", str(Path(__file__).with_name("vosi_agent.db"))))
runtime = AgentRuntime(_database_path)


def _authorize(authorization: str | None) -> None:
    expected = os.getenv("VOSI_AGENT_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="VOSI agent API is disabled until VOSI_AGENT_TOKEN is configured.")
    scheme, separator, supplied = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or not hmac.compare_digest(supplied.strip(), expected):
        raise HTTPException(status_code=401, detail="Invalid VOSI agent token.")


def _runtime_call(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except AgentRuntimeError as exc:
        message = str(exc)
        status = 404 if message in {"Task not found.", "Step not found."} else 422
        raise HTTPException(status_code=status, detail=message) from exc


class AgentTaskCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=30)
    origin_device_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=128)
    expires_at: str | None = None


@router.get("/capabilities")
def get_agent_capabilities(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    return {"success": True, "capabilities": runtime.list_capabilities()}


@router.post("/tasks")
def create_agent_task(
    request: AgentTaskCreateRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    task = _runtime_call(
        runtime.create_task,
        goal=request.goal,
        steps=request.steps,
        origin_device_id=request.origin_device_id,
        idempotency_key=request.idempotency_key,
        expires_at=request.expires_at,
    )
    return {"success": True, "task": task}


@router.get("/tasks")
def list_agent_tasks(
    limit: int = 20,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    return {"success": True, "tasks": runtime.list_tasks(limit)}


@router.get("/tasks/{task_id}")
def get_agent_task(task_id: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    task = _runtime_call(runtime.get_task, task_id)
    return {"success": True, "task": task}


@router.post("/tasks/{task_id}/steps/{step_id}/approve")
def approve_agent_step(
    task_id: str,
    step_id: str,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    task = _runtime_call(runtime.approve_step, task_id, step_id)
    return {"success": True, "task": task}


@router.post("/tasks/{task_id}/cancel")
def cancel_agent_task(task_id: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    task = _runtime_call(runtime.cancel_task, task_id)
    return {"success": True, "task": task}
