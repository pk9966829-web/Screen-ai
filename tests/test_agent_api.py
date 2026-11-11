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
