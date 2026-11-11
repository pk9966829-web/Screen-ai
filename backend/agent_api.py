"""Authenticated HTTP surface for VOSI agent planning and paired-device management."""
import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agent_runtime import AgentRuntime, AgentRuntimeError
from device_registry import DeviceRegistry

router = APIRouter(prefix="/agent", tags=["VOSI Agent"])

_database_path = Path(os.getenv("VOSI_AGENT_DB_PATH", str(Path(__file__).with_name("vosi_agent.db"))))
runtime = AgentRuntime(_database_path)
devices = DeviceRegistry(_database_path)


def _bearer(authorization: str | None) -> str | None:
    scheme, separator, supplied = (authorization or "").partition(" ")
    return supplied.strip() if separator and scheme.lower() == "bearer" else None


def _authorize(authorization: str | None) -> None:
    expected = os.getenv("VOSI_AGENT_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="VOSI agent API is disabled until VOSI_AGENT_TOKEN is configured.")
    supplied = _bearer(authorization)
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid VOSI agent token.")


def _authorize_device(authorization: str | None) -> dict[str, Any]:
    try:
        return devices.authenticate(_bearer(authorization))
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _runtime_call(callback, *args, **kwargs):
    try:
        return callback(*args, **kwargs)
    except AgentRuntimeError as exc:
        message = str(exc)
        status = 404 if message in {"Task not found.", "Step not found.", "Device not found."} else 422
        raise HTTPException(status_code=status, detail=message) from exc


class AgentTaskCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=30)
    origin_device_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=128)
    expires_at: str | None = None


class DevicePairingRequest(BaseModel):
    platform: str
    label: str = Field(min_length=1, max_length=80)


class DevicePairCompleteRequest(BaseModel):
    pairing_code: str = Field(min_length=20, max_length=128)
    capabilities: list[str] = Field(default_factory=list, max_length=50)


class DeviceStepResultRequest(BaseModel):
    success: bool
    verified: bool
    receipt: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None, max_length=2000)


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


@router.post("/devices/pairing")
def create_device_pairing(
    request: DevicePairingRequest,
    authorization: str | None = Header(default=None),
):
    _authorize(authorization)
    pairing = _runtime_call(devices.create_pairing, request.platform, request.label)
    return {"success": True, "pairing": pairing}


@router.post("/devices/pair")
def complete_device_pairing(request: DevicePairCompleteRequest):
    # The short-lived, single-use pairing code is the bootstrap credential.
    paired = _runtime_call(devices.complete_pairing, request.pairing_code, request.capabilities)
    return {"success": True, "device": paired}


@router.get("/devices")
def list_paired_devices(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    return {"success": True, "devices": devices.list_devices()}


@router.delete("/devices/{device_id}")
def revoke_paired_device(device_id: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    result = _runtime_call(devices.revoke_device, device_id)
    return {"success": True, **result}


@router.post("/devices/{device_id}/heartbeat")
def device_heartbeat(device_id: str, authorization: str | None = Header(default=None)):
    device = _authorize_device(authorization)
    result = _runtime_call(devices.heartbeat, device_id, _bearer(authorization) or "")
    return {"success": True, "device": {**result, "platform": device["platform"], "label": device["label"]}}


@router.post("/tasks/{task_id}/claim")
def claim_agent_task_step(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    device = _authorize_device(authorization)
    step = _runtime_call(
        runtime.claim_next_step,
        task_id,
        device["device_id"],
        device["platform"],
        set(device["capabilities"]),
    )
    return {"success": True, "step": step}


@router.post("/tasks/{task_id}/steps/{step_id}/result")
def record_agent_step_result(
    task_id: str,
    step_id: str,
    request: DeviceStepResultRequest,
    authorization: str | None = Header(default=None),
):
    device = _authorize_device(authorization)
    task = _runtime_call(
        runtime.record_step_result,
        task_id,
        step_id,
        device["device_id"],
        request.success,
        request.verified,
        request.receipt,
        request.error,
    )
    return {"success": True, "task": task}
