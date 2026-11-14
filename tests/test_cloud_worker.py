import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

import cloud_worker
from agent_runtime import AgentRuntime


def make_client(tmp_path, monkeypatch):
    runtime = AgentRuntime(tmp_path / "cloud-worker.db")
    monkeypatch.setattr(cloud_worker, "runtime", runtime)
    monkeypatch.setenv("VOSI_CLOUD_WORKER_TOKEN", "test-worker-secret")
    monkeypatch.setenv("VOSI_CLOUD_WORKER_ID", "test")
    monkeypatch.setenv("VOSI_CLOUD_WORKER_PLATFORM", "browser")
    monkeypatch.setenv("VOSI_CLOUD_WORKER_CAPABILITIES", "browser.search_products,commerce.order.place")
    app = FastAPI()
    app.include_router(cloud_worker.router)
    return runtime, TestClient(app), {"Authorization": "Bearer test-worker-secret"}


def test_cloud_worker_claims_only_configured_low_risk_work(tmp_path, monkeypatch):
    runtime, client, headers = make_client(tmp_path, monkeypatch)
    task = runtime.create_task("Find public products", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "Search public listings", "arguments": {"query": "body spray under 1000"},
    }])

    health = client.get("/cloud-worker/health", headers=headers)
    assert health.status_code == 200
    assert "commerce.order.place" not in health.json()["capabilities"]

    claimed = client.post("/cloud-worker/claim", headers=headers)
    assert claimed.status_code == 200
    assert claimed.json()["task"]["task_id"] == task["task_id"]
    assert claimed.json()["step"]["state"] == "running"


def test_cloud_worker_heartbeat_and_verified_receipt(tmp_path, monkeypatch):
    runtime, client, headers = make_client(tmp_path, monkeypatch)
    task = runtime.create_task("Search", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "Search", "arguments": {"query": "soap"},
    }])
    claim = client.post("/cloud-worker/claim", headers=headers).json()
    step_id = claim["step"]["step_id"]

    heartbeat = client.post(f"/cloud-worker/{task['task_id']}/steps/{step_id}/heartbeat", headers=headers)
    assert heartbeat.status_code == 200
    result = client.post(
        f"/cloud-worker/{task['task_id']}/steps/{step_id}/result",
        headers=headers,
        json={"success": True, "verified": True, "receipt": {"results_count": 3}},
    )
    assert result.status_code == 200
    assert result.json()["task"]["state"] == "completed"


def test_expired_safe_claim_is_requeued_but_order_is_not_replayed(tmp_path, monkeypatch):
    runtime, client, headers = make_client(tmp_path, monkeypatch)
    safe = runtime.create_task("Search", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "Search", "arguments": {"query": "shampoo"},
    }])
    claim = client.post("/cloud-worker/claim", headers=headers).json()
    old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with runtime._connect() as db:
        db.execute("UPDATE agent_steps SET claimed_at = ? WHERE task_id = ?", (old, safe["task_id"]))

    reclaimed = client.post("/cloud-worker/claim", headers=headers).json()
    assert reclaimed["step"]["step_id"] == claim["step"]["step_id"]
    assert reclaimed["step"]["state"] == "running"
    runtime.record_step_result(safe["task_id"], claim["step"]["step_id"], "cloud-worker:test", True, True, {"ok": True})

    order = runtime.create_task("Place approved order", [{
        "capability": "commerce.order.place", "target_platform": "browser",
        "title": "Submit approved checkout",
        "arguments": {"checkout_summary": {
            "merchant": "Example", "items": [{"name": "Item", "quantity": 1}],
            "delivery_address": "User-entered address", "total": 100,
            "currency": "INR", "payment_method": "UPI",
        }},
    }])
    runtime.approve_step(order["task_id"], "step-1")
    # Simulate a legacy/misconfigured executor that already held the irreversible claim.
    # The cloud-worker API must neither opt into this capability nor replay it after expiry.
    runtime.claim_next_step(order["task_id"], "cloud-worker:test", "browser", {"commerce.order.place"})
    with runtime._connect() as db:
        db.execute("UPDATE agent_steps SET claimed_at = ? WHERE task_id = ?", (old, order["task_id"]))

    idle = client.post("/cloud-worker/claim", headers=headers).json()
    assert idle["task"] is None
    assert runtime.get_step(order["task_id"], "step-1")["state"] == "running"


def test_cloud_worker_rejects_invalid_token_and_missing_configuration(tmp_path, monkeypatch):
    _, client, _ = make_client(tmp_path, monkeypatch)
    assert client.get("/cloud-worker/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    monkeypatch.delenv("VOSI_CLOUD_WORKER_TOKEN")
    assert client.get("/cloud-worker/health").status_code == 503


def test_cloud_worker_claims_only_the_authenticated_account_tasks(tmp_path, monkeypatch):
    runtime, client, headers = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("VOSI_MULTI_TENANT", "true")
    monkeypatch.setattr(
        cloud_worker.identity_api.store,
        "authenticate",
        lambda token: {"user_id": token},
    )
    headers = {**headers, "X-VOSI-Account-Token": "account-a"}

    account_a = runtime.create_task("A search", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "A products", "arguments": {"query": "body spray"},
    }], owner_user_id="account-a")
    account_b = runtime.create_task("B search", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "B products", "arguments": {"query": "shoes"},
    }], owner_user_id="account-b")

    old_claim = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with runtime._connect() as db:
        db.execute(
            "UPDATE agent_tasks SET state = 'running' WHERE task_id = ?",
            (account_b["task_id"],),
        )
        db.execute(
            """UPDATE agent_steps SET state = 'running', claimed_by = ?, claimed_at = ?
               WHERE task_id = ? AND step_id = 'step-1'""",
            ("cloud-worker:test", old_claim, account_b["task_id"]),
        )

    health = client.get("/cloud-worker/health", headers=headers)
    assert health.status_code == 200
    assert health.json()["account_scoped"] is True

    claim = client.post("/cloud-worker/claim", headers=headers)
    assert claim.status_code == 200
    assert claim.json()["task"]["task_id"] == account_a["task_id"]
    assert runtime.get_step(account_b["task_id"], "step-1")["state"] == "running"

    wrong_account_headers = {**headers, "X-VOSI-Account-Token": "account-b"}
    heartbeat = client.post(
        f"/cloud-worker/{account_a['task_id']}/steps/step-1/heartbeat",
        headers=wrong_account_headers,
    )
    assert heartbeat.status_code == 404
    result = client.post(
        f"/cloud-worker/{account_a['task_id']}/steps/step-1/result",
        headers=wrong_account_headers,
        json={"success": True, "verified": True, "receipt": {"leaked": True}},
    )
    assert result.status_code == 404
    assert runtime.get_task(account_a["task_id"])["state"] == "running"


def test_multi_tenant_cloud_worker_requires_a_valid_account_session(tmp_path, monkeypatch):
    _, client, headers = make_client(tmp_path, monkeypatch)
    monkeypatch.setenv("VOSI_MULTI_TENANT", "true")
    response = client.post("/cloud-worker/claim", headers=headers)
    assert response.status_code == 401


def test_legacy_cloud_worker_cannot_claim_account_owned_tasks(tmp_path, monkeypatch):
    runtime, client, headers = make_client(tmp_path, monkeypatch)
    runtime.create_task("Private account task", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "Private search", "arguments": {"query": "private"},
    }], owner_user_id="account-a")
    runtime.create_task("Legacy local task", [{
        "capability": "browser.search_products", "target_platform": "browser",
        "title": "Local search", "arguments": {"query": "local"},
    }])

    claim = client.post("/cloud-worker/claim", headers=headers)
    assert claim.status_code == 200
    assert claim.json()["task"]["goal"] == "Legacy local task"
