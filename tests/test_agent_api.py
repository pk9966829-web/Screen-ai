import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import agent_api  # noqa: E402
from agent_runtime import AgentRuntime  # noqa: E402


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
