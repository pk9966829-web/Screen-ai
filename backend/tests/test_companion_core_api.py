from fastapi import FastAPI
from fastapi.testclient import TestClient

import companion_core_api as api


def _client():
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_chat_requires_a_paired_device(monkeypatch):
    monkeypatch.setattr(api.agent_api.devices, "authenticate", lambda token: (_ for _ in ()).throw(api.AgentRuntimeError("Invalid token.")))
    response = _client().post("/companion/chat", headers={"Authorization": "Bearer invalid"}, json={"message": "Hello"})
    assert response.status_code == 401


def test_android_chat_uses_shared_companion_brain(monkeypatch):
    monkeypatch.setattr(api.agent_api.devices, "authenticate", lambda token: {
        "device_id": "android-device-1", "platform": "android"
    })
    monkeypatch.setattr(api.agent_api.devices, "list_devices", lambda: [])
    monkeypatch.setattr(api, "get_recent_interactions", lambda limit=8: [])
    monkeypatch.setattr(api, "get_companion_memories", lambda: [{"id": 1}])
    monkeypatch.setattr(api, "answer_companion", lambda *args, **kwargs: {
        "success": True, "understanding": "Hey! I'm here.", "provider": "test",
        "memory_count": 1, "task_plan": None,
    })
    saved = []
    monkeypatch.setattr(api, "save_interaction", lambda *args, **kwargs: saved.append(args))

    response = _client().post(
        "/companion/chat",
        headers={"Authorization": "Bearer valid"},
        json={"message": "Hello VOSI"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["response"] == "Hey! I'm here."
    assert body["device_id"] == "android-device-1"
    assert body["interaction_recorded"] is True
    assert len(saved) == 1


def test_history_is_available_to_paired_desktop(monkeypatch):
    monkeypatch.setattr(api.agent_api.devices, "authenticate", lambda token: {
        "device_id": "desktop-device-1", "platform": "desktop"
    })
    monkeypatch.setattr(api, "get_recent_interactions", lambda limit=30: [{"question": "Hi", "answer": "Hello"}])
    monkeypatch.setattr(api, "get_companion_memories", lambda: [])

    response = _client().get("/companion/chat/history", headers={"Authorization": "Bearer valid"})

    assert response.status_code == 200
    assert response.json()["interactions"][0]["question"] == "Hi"
