from fastapi import FastAPI
from fastapi.testclient import TestClient

import companion_core_api as api


def _client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def _headers():
    return {"Authorization": "Bearer device-token", "X-VOSI-Account-Token": "account-token"}


def _authenticate(monkeypatch, user_id="account-a", device_id="android-device-a"):
    monkeypatch.setattr(api.agent_api.devices, "authenticate", lambda token: {
        "device_id": device_id, "platform": "android"
    })
    monkeypatch.setattr(api.identity_api.store, "authenticate", lambda token: {
        "user_id": user_id, "email": user_id + "@example.test"
    })
    monkeypatch.setattr(api.identity_api.store, "get_linked_device_user", lambda device: None)
    linked = []
    monkeypatch.setattr(api.identity_api.store, "link_device", lambda user, device: linked.append((user, device)))
    return linked


def test_chat_requires_both_device_and_account_credentials(monkeypatch):
    monkeypatch.setattr(api.agent_api.devices, "authenticate", lambda token: (_ for _ in ()).throw(api.AgentRuntimeError("Invalid token.")))
    response = _client().post("/companion/chat", headers=_headers(), json={"message": "Hello"})
    assert response.status_code == 401
    response = _client().post(
        "/companion/chat",
        headers={"Authorization": "Bearer device-token"},
        json={"message": "Hello"},
    )
    assert response.status_code == 401


def test_chat_uses_account_scoped_history_and_memory(monkeypatch):
    linked = _authenticate(monkeypatch)
    class FakeRuntime:
        def list_tasks(self, limit, user_id=None):
            assert user_id == "account-a"
            return []

    fake_runtime = FakeRuntime()
    monkeypatch.setattr(api.agent_api, "runtime", fake_runtime)
    monkeypatch.setattr(api.agent_api.devices, "list_devices", lambda user_id=None: [
        {"device_id": "android-device-a", "user_id": user_id, "platform": "android", "status": "online", "capabilities": []}
    ])
    monkeypatch.setattr(api, "get_recent_turns", lambda user_id, limit=8: [])
    monkeypatch.setattr(
        api, "get_companion_memories",
        lambda limit=50, user_id=None: [{"content": "private"}] if user_id == "account-a" else [],
    )
    observed = {}

    def fake_answer(*args, **kwargs):
        observed["user_id"] = kwargs.get("user_id")
        observed["runtime"] = kwargs.get("runtime")
        return {
            "success": True, "understanding": "Hello from VOSI.", "provider": "test",
            "memory_count": 1, "task_plan": None,
        }

    monkeypatch.setattr(api, "answer_companion", fake_answer)
    saved = []
    monkeypatch.setattr(api, "save_turn", lambda user, question, answer: saved.append((user, question, answer)))

    response = _client().post("/companion/chat", headers=_headers(), json={"message": "Hello VOSI"})

    assert response.status_code == 200
    assert response.json()["response"] == "Hello from VOSI."
    assert response.json()["interaction_recorded"] is True
    assert observed == {"user_id": "account-a", "runtime": fake_runtime}
    assert saved == [("account-a", "Hello VOSI", "Hello from VOSI.")]
    assert linked == [("account-a", "android-device-a")]


def test_device_linked_to_another_account_is_rejected(monkeypatch):
    monkeypatch.setattr(api.agent_api.devices, "authenticate", lambda token: {
        "device_id": "android-device-a", "platform": "android"
    })
    monkeypatch.setattr(api.identity_api.store, "authenticate", lambda token: {"user_id": "account-b"})
    monkeypatch.setattr(api.identity_api.store, "get_linked_device_user", lambda device: "account-a")

    response = _client().get("/companion/chat/history", headers=_headers())

    assert response.status_code == 403


def test_history_is_private_to_authenticated_account(monkeypatch):
    _authenticate(monkeypatch, user_id="account-b", device_id="android-device-b")
    monkeypatch.setattr(
        api, "get_recent_turns",
        lambda user_id, limit=30: [{"question": "B only", "answer": "Private"}] if user_id == "account-b" else [],
    )
    monkeypatch.setattr(api, "get_companion_memories", lambda limit=50, user_id=None: [])

    response = _client().get("/companion/chat/history", headers=_headers())

    assert response.status_code == 200
    assert response.json()["interactions"][0]["question"] == "B only"
