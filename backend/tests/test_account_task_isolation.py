from fastapi import FastAPI
from fastapi.testclient import TestClient

import agent_api
from agent_runtime import AgentRuntime


def _client():
    app = FastAPI()
    app.include_router(agent_api.router)
    return TestClient(app)


def _step():
    return [{
        "step_id": "volume",
        "capability": "device.volume.set",
        "target_platform": "android",
        "title": "Set phone volume",
        "arguments": {"volume": 50},
    }]


def test_task_history_is_partitioned_by_account(tmp_path):
    runtime = AgentRuntime(tmp_path / "agent.db")
    task_a = runtime.create_task("Account A task", _step(), owner_user_id="user-a")
    task_b = runtime.create_task("Account B task", _step(), owner_user_id="user-b")

    assert [task["task_id"] for task in runtime.list_tasks(user_id="user-a")] == [task_a["task_id"]]
    assert [task["task_id"] for task in runtime.list_tasks(user_id="user-b")] == [task_b["task_id"]]
    assert runtime.list_tasks(user_id="user-c") == []
    assert task_a["owner_user_id"] == "user-a"


def test_unlinked_legacy_devices_cannot_list_account_owned_tasks(tmp_path):
    runtime = AgentRuntime(tmp_path / "agent.db")
    runtime.create_task("Account A task", _step(), owner_user_id="user-a")
    runtime.create_task("Legacy local task", _step())

    assert [task["goal"] for task in runtime.list_tasks(user_id="")] == ["Legacy local task"]


def test_device_from_another_account_cannot_claim_task(tmp_path, monkeypatch):
    agent_api.runtime = AgentRuntime(tmp_path / "agent.db")
    task = agent_api.runtime.create_task(
        "Private account task",
        _step(),
        origin_device_id="device-a",
        owner_user_id="user-a",
    )
    monkeypatch.setattr(agent_api, "_authorize_device", lambda authorization: {
        "device_id": "device-b",
        "user_id": "user-b",
        "platform": "android",
        "capabilities": ["device.volume.set"],
    })

    response = _client().post(f"/agent/tasks/{task['task_id']}/claim", headers={"Authorization": "Bearer device-b"})

    assert response.status_code == 403
    assert agent_api.runtime.get_task(task["task_id"])["steps"][0]["state"] == "pending"


def test_account_device_task_feed_does_not_include_other_accounts(tmp_path, monkeypatch):
    agent_api.runtime = AgentRuntime(tmp_path / "agent.db")
    agent_api.runtime.create_task("Private account task", _step(), owner_user_id="user-a")
    monkeypatch.setattr(agent_api, "_authorize_device", lambda authorization: {
        "device_id": "device-b",
        "user_id": "user-b",
        "platform": "android",
        "capabilities": ["device.volume.set"],
    })

    response = _client().get("/agent/tasks/available", headers={"Authorization": "Bearer device-b"})

    assert response.status_code == 200
    assert response.json()["tasks"] == []
