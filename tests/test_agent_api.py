import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import agent_api  # noqa: E402
from agent_runtime import AgentRuntime  # noqa: E402
from device_registry import DeviceRegistry  # noqa: E402


def make_client():
    app = FastAPI()
    app.include_router(agent_api.router)
    return TestClient(app)


def test_agent_api_requires_configured_token(monkeypatch):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "")
    response = make_client().get("/agent/capabilities")
    assert response.status_code == 503


def test_agent_api_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "secret-token")
    response = make_client().get(
        "/agent/capabilities",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


def test_agent_api_creates_and_reads_task(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "secret-token")
    agent_api.runtime = AgentRuntime(tmp_path / "api.sqlite3")
    client = make_client()
    headers = {"Authorization": "Bearer secret-token"}
    payload = {
        "goal": "Find a body spray under 1000 rupees",
        "origin_device_id": "desktop-1",
        "idempotency_key": "goal-001",
        "steps": [{
            "step_id": "search-products",
            "capability": "browser.search_products",
            "target_platform": "browser",
            "title": "Search supported product listings",
            "arguments": {"query": "body spray under 1000 rupees"},
        }],
    }

    created = client.post("/agent/tasks", json=payload, headers=headers)
    assert created.status_code == 200
    task_id = created.json()["task"]["task_id"]

    fetched = client.get(f"/agent/tasks/{task_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["task"]["goal"] == payload["goal"]


def test_device_task_queue_is_scoped_to_paired_platform_and_capabilities(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "admin-secret")
    db_path = tmp_path / "device-queue.sqlite3"
    agent_api.devices = DeviceRegistry(db_path)
    agent_api.runtime = AgentRuntime(db_path)
    client = make_client()
    admin = {"Authorization": "Bearer admin-secret"}

    def pair(platform, label, capabilities):
        pairing = client.post(
            "/agent/devices/pairing",
            headers=admin,
            json={"platform": platform, "label": label},
        ).json()["pairing"]
        return client.post(
            "/agent/devices/pair",
            json={"pairing_code": pairing["pairing_code"], "capabilities": capabilities},
        ).json()["device"]

    browser = pair("browser", "Chrome", ["browser.search_products"])
    android = pair("android", "Phone", ["phone.contacts.read"])
    created = client.post(
        "/agent/tasks",
        headers=admin,
        json={
            "goal": "Search body spray",
            "steps": [{
                "step_id": "search",
                "capability": "browser.search_products",
                "target_platform": "browser",
                "title": "Search product listings",
                "arguments": {"query": "body spray under 1000"},
            }],
        },
    ).json()["task"]

    browser_headers = {"Authorization": f"Bearer {browser['device_token']}"}
    android_headers = {"Authorization": f"Bearer {android['device_token']}"}
    assert client.get("/agent/tasks/available", headers=android_headers).json()["tasks"] == []
    available = client.get("/agent/tasks/available", headers=browser_headers)
    assert available.status_code == 200
    assert available.json()["tasks"][0]["task_id"] == created["task_id"]

    claim = client.post(
        f"/agent/tasks/{created['task_id']}/claim",
        headers=browser_headers,
    )
    assert claim.status_code == 200
    assert claim.json()["step"]["step_id"] == "search"
    assert client.get("/agent/tasks/available", headers=browser_headers).json()["tasks"] == []


def test_device_queue_does_not_skip_an_earlier_step_for_another_platform(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "admin-secret")
    db_path = tmp_path / "ordered-device-queue.sqlite3"
    agent_api.devices = DeviceRegistry(db_path)
    agent_api.runtime = AgentRuntime(db_path)
    client = make_client()
    admin = {"Authorization": "Bearer admin-secret"}
    pairing = client.post(
        "/agent/devices/pairing",
        headers=admin,
        json={"platform": "browser", "label": "Chrome"},
    ).json()["pairing"]
    browser = client.post(
        "/agent/devices/pair",
        json={"pairing_code": pairing["pairing_code"], "capabilities": ["browser.search_products"]},
    ).json()["device"]
    task = client.post(
        "/agent/tasks",
        headers=admin,
        json={
            "goal": "First inspect phone, then search products",
            "steps": [
                {
                    "step_id": "phone-first",
                    "capability": "phone.contacts.read",
                    "target_platform": "android",
                    "title": "Read the selected contact",
                    "arguments": {"name": "Alex"},
                },
                {
                    "step_id": "browser-second",
                    "capability": "browser.search_products",
                    "target_platform": "browser",
                    "title": "Search products",
                    "arguments": {"query": "body spray"},
                },
            ],
        },
    ).json()["task"]
    browser_headers = {"Authorization": f"Bearer {browser['device_token']}"}

    response = client.get("/agent/tasks/available", headers=browser_headers)
    assert response.status_code == 200
    assert response.json()["tasks"] == []
    # Even a direct claim request cannot skip the earlier phone step.
    claim = client.post(f"/agent/tasks/{task['task_id']}/claim", headers=browser_headers)
    assert claim.status_code == 200
    assert claim.json()["step"] is None


def test_paired_phone_can_request_only_low_risk_device_tasks(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "admin-secret")
    db_path = tmp_path / "phone-task-request.sqlite3"
    agent_api.devices = DeviceRegistry(db_path)
    agent_api.runtime = AgentRuntime(db_path)
    client = make_client()
    admin = {"Authorization": "Bearer admin-secret"}
    pairing = client.post(
        "/agent/devices/pairing",
        headers=admin,
        json={"platform": "android", "label": "VOSI phone"},
    ).json()["pairing"]
    phone = client.post(
        "/agent/devices/pair",
        json={
            "pairing_code": pairing["pairing_code"],
            "capabilities": ["agent.task.request"],
        },
    ).json()["device"]
    phone_headers = {"Authorization": f"Bearer {phone['device_token']}"}

    accepted = client.post(
        "/agent/tasks/request",
        headers=phone_headers,
        json={
            "goal": "Search Flipkart for body spray",
            "idempotency_key": "phone-request-001",
            "steps": [{
                "step_id": "search",
                "capability": "browser.search_products",
                "target_platform": "browser",
                "title": "Search Flipkart",
                "arguments": {"query": "body spray under 1000"},
            }],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["task"]["origin_device_id"] == phone["device_id"]

    unsupported = client.post(
        "/agent/tasks/request",
        headers=phone_headers,
        json={
            "goal": "Set PC volume",
            "steps": [{
                "step_id": "volume",
                "capability": "device.volume.set",
                "target_platform": "desktop",
                "title": "Set PC volume",
                "arguments": {"volume": 50},
            }],
        },
    )
    assert unsupported.status_code == 403

    blocked = client.post(
        "/agent/tasks/request",
        headers=phone_headers,
        json={
            "goal": "Call a contact",
            "steps": [{
                "step_id": "call",
                "capability": "phone.call",
                "target_platform": "android",
                "title": "Call contact",
                "arguments": {"number": "+10000000000"},
            }],
        },
    )
    assert blocked.status_code == 403


def test_phone_without_task_request_capability_cannot_create_tasks(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "admin-secret")
    db_path = tmp_path / "phone-task-request-denied.sqlite3"
    agent_api.devices = DeviceRegistry(db_path)
    agent_api.runtime = AgentRuntime(db_path)
    client = make_client()
    admin = {"Authorization": "Bearer admin-secret"}
    pairing = client.post(
        "/agent/devices/pairing",
        headers=admin,
        json={"platform": "android", "label": "Limited phone"},
    ).json()["pairing"]
    phone = client.post(
        "/agent/devices/pair",
        json={"pairing_code": pairing["pairing_code"], "capabilities": ["phone.contacts.read"]},
    ).json()["device"]

    response = client.post(
        "/agent/tasks/request",
        headers={"Authorization": f"Bearer {phone['device_token']}"},
        json={
            "goal": "Search Flipkart",
            "steps": [{
                "step_id": "search",
                "capability": "browser.search_products",
                "target_platform": "browser",
                "title": "Search",
                "arguments": {"query": "headphones"},
            }],
        },
    )
    assert response.status_code == 403
