from datetime import datetime, timedelta, timezone
import hashlib
import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import agent_api
from agent_runtime import AgentRuntime
from device_registry import DeviceRegistry


def make_client():
    app = FastAPI()
    app.include_router(agent_api.router)
    return TestClient(app)


def pair(client, admin, db_path, platform, label, capabilities):
    pairing = client.post(
        "/agent/devices/pairing",
        headers=admin,
        json={"platform": platform, "label": label},
    ).json()["pairing"]
    return client.post(
        "/agent/devices/pair",
        json={"pairing_code": pairing["pairing_code"], "capabilities": capabilities},
    ).json()["device"]


def auth(device):
    return {"Authorization": "Bearer " + device["device_token"]}


def setup_api(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "admin-secret")
    db_path = tmp_path / "orchestrator.sqlite3"
    agent_api.devices = DeviceRegistry(db_path)
    agent_api.runtime = AgentRuntime(db_path)
    client = make_client()
    admin = {"Authorization": "Bearer admin-secret"}
    return client, admin, db_path


def test_scheduled_task_is_persisted_and_not_claimable_early(tmp_path):
    runtime = AgentRuntime(tmp_path / "schedule.sqlite3")
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    task = runtime.create_task(
        "Search tomorrow's deals",
        [{
            "step_id": "search",
            "capability": "browser.search_products",
            "target_platform": "browser",
            "title": "Search product listings",
            "arguments": {"query": "wireless headphones"},
        }],
        scheduled_at=future,
    )
    assert task["state"] == "scheduled"
    assert task["scheduled_at"] == future
    assert runtime.claim_next_step(
        task["task_id"], "chrome-1", "browser", {"browser.search_products"}
    ) is None
    restarted = AgentRuntime(tmp_path / "schedule.sqlite3")
    assert restarted.get_task(task["task_id"])["scheduled_at"] == future


def test_scheduled_at_requires_timezone(tmp_path):
    runtime = AgentRuntime(tmp_path / "bad-schedule.sqlite3")
    try:
        runtime.create_task(
            "Search later",
            [{
                "step_id": "search",
                "capability": "browser.search_products",
                "target_platform": "browser",
                "title": "Search",
                "arguments": {"query": "headphones"},
            }],
            scheduled_at="2026-11-13T08:00:00",
        )
    except ValueError as exc:
        assert "timezone" in str(exc)
    else:
        raise AssertionError("A timezone-naive schedule must be rejected.")


def test_order_checkout_is_approval_gated_after_preparation_and_bound_to_origin_device(monkeypatch, tmp_path):
    client, admin, db_path = setup_api(monkeypatch, tmp_path)
    phone = pair(client, admin, db_path, "android", "VOSI phone", ["agent.task.request"])
    chrome = pair(
        client, admin, db_path, "browser", "VOSI Chrome",
        ["browser.search_products", "commerce.order.place"],
    )
    other_phone = pair(client, admin, db_path, "android", "Other phone", ["agent.task.request"])

    checkout = {
        "merchant": "Example food merchant",
        "items": [{"name": "Vegetable meal", "quantity": 1, "unit_price": 180}],
        "delivery_address": "Address selected in merchant checkout",
        "total": 224,
        "currency": "INR",
        "payment_method": "UPI",
    }
    created = client.post(
        "/agent/tasks/request",
        headers=auth(phone),
        json={
            "goal": "Prepare an order and ask me before paying",
            "steps": [
                {
                    "step_id": "search",
                    "capability": "browser.search_products",
                    "target_platform": "browser",
                    "title": "Find matching menu items",
                    "arguments": {"query": "vegetable meal"},
                },
                {
                    "step_id": "place-order",
                    "capability": "commerce.order.place",
                    "target_platform": "browser",
                    "title": "Submit the reviewed order",
                    "arguments": {"checkout_summary": checkout},
                },
            ],
        },
    )
    assert created.status_code == 200
    task = created.json()["task"]
    assert task["state"] == "awaiting_approval"

    # An approval later in the plan must not block safe preparation steps.
    available = client.get("/agent/tasks/available", headers=auth(chrome))
    assert available.status_code == 200
    assert available.json()["tasks"][0]["step_id"] == "search"
    claim = client.post(f"/agent/tasks/{task['task_id']}/claim", headers=auth(chrome))
    assert claim.json()["step"]["step_id"] == "search"
    result = client.post(
        f"/agent/tasks/{task['task_id']}/steps/search/result",
        headers=auth(chrome),
        json={"success": True, "verified": True, "receipt": {"items_reviewed": 1}},
    )
    assert result.status_code == 200
    assert result.json()["task"]["state"] == "awaiting_approval"

    approvals = client.get("/agent/tasks/pending-approvals", headers=auth(phone))
    assert approvals.status_code == 200
    approval = approvals.json()["approvals"][0]
    assert approval["arguments"]["checkout_summary"]["total"] == 224

    wrong = client.post(
        f"/agent/tasks/{task['task_id']}/steps/place-order/approve-origin",
        headers=auth(phone),
        json={"confirmation_digest": "0" * 64},
    )
    assert wrong.status_code == 409

    stolen = client.post(
        f"/agent/tasks/{task['task_id']}/steps/place-order/approve-origin",
        headers=auth(other_phone),
        json={"confirmation_digest": approval["confirmation_digest"]},
    )
    assert stolen.status_code == 403

    approved = client.post(
        f"/agent/tasks/{task['task_id']}/steps/place-order/approve-origin",
        headers=auth(phone),
        json={"confirmation_digest": approval["confirmation_digest"]},
    )
    assert approved.status_code == 200
    assert approved.json()["task"]["steps"][1]["state"] == "ready"
    next_step = client.post(f"/agent/tasks/{task['task_id']}/claim", headers=auth(chrome))
    assert next_step.json()["step"]["capability"] == "commerce.order.place"


def test_order_request_requires_a_complete_checkout_summary(monkeypatch, tmp_path):
    client, admin, db_path = setup_api(monkeypatch, tmp_path)
    phone = pair(client, admin, db_path, "android", "VOSI phone", ["agent.task.request"])
    response = client.post(
        "/agent/tasks/request",
        headers=auth(phone),
        json={
            "goal": "Place an order",
            "steps": [{
                "step_id": "order",
                "capability": "commerce.order.place",
                "target_platform": "browser",
                "title": "Submit order",
                "arguments": {"checkout_summary": {"merchant": "Swiggy"}},
            }],
        },
    )
    assert response.status_code == 422


def test_scheduled_phone_task_is_not_offered_to_executor_before_due(monkeypatch, tmp_path):
    client, admin, db_path = setup_api(monkeypatch, tmp_path)
    phone = pair(client, admin, db_path, "android", "VOSI phone", ["agent.task.request"])
    chrome = pair(client, admin, db_path, "browser", "VOSI Chrome", ["browser.search_products"])
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    created = client.post(
        "/agent/tasks/request",
        headers=auth(phone),
        json={
            "goal": "Search for deals in one hour",
            "scheduled_at": future,
            "steps": [{
                "step_id": "search",
                "capability": "browser.search_products",
                "target_platform": "browser",
                "title": "Search deals",
                "arguments": {"query": "deals"},
            }],
        },
    )
    assert created.status_code == 200
    assert created.json()["task"]["state"] == "scheduled"
    available = client.get("/agent/tasks/available", headers=auth(chrome))
    assert available.status_code == 200
    assert available.json()["tasks"] == []
