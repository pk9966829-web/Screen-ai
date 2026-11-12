import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import voice_api


class FakeDevices:
    def __init__(self, platform="android"):
        self.platform = platform

    def authenticate(self, token):
        if token != "phone-token":
            from agent_runtime import AgentRuntimeError
            raise AgentRuntimeError("Invalid device token.")
        return {"device_id": "phone-1", "platform": self.platform}

    def list_devices(self):
        return [{"device_id": "phone-1", "platform": self.platform, "status": "online", "capabilities": []}]


def make_client():
    app = FastAPI()
    app.include_router(voice_api.router)
    return TestClient(app)


def test_voice_turn_requires_a_paired_device(monkeypatch):
    monkeypatch.setattr(voice_api.agent_api, "devices", FakeDevices())
    response = make_client().post("/companion/voice", json={"transcript": "Hello VOSI"})
    assert response.status_code == 401


def test_voice_turn_rejects_browser_devices(monkeypatch):
    monkeypatch.setattr(voice_api.agent_api, "devices", FakeDevices(platform="browser"))
    response = make_client().post(
        "/companion/voice",
        headers={"Authorization": "Bearer phone-token"},
        json={"transcript": "Hello VOSI"},
    )
    assert response.status_code == 403


def test_voice_turn_accepts_a_paired_desktop(monkeypatch):
    monkeypatch.setattr(voice_api.agent_api, "devices", FakeDevices(platform="desktop"))
    monkeypatch.setattr(voice_api, "answer_companion", lambda *args, **kwargs: {
        "success": True, "understanding": "Hello from desktop.", "task_plan": None,
        "provider": "test-provider", "memory_count": 1,
    })
    monkeypatch.setattr(voice_api, "get_recent_interactions", lambda limit: [])
    monkeypatch.setattr(voice_api, "save_interaction", lambda *args, **kwargs: None)
    response = make_client().post(
        "/companion/voice",
        headers={"Authorization": "Bearer phone-token"},
        json={"transcript": "Hello from my PC"},
    )
    assert response.status_code == 200
    assert response.json()["response"] == "Hello from desktop."
    assert response.json()["device_id"] == "phone-1"


def test_voice_turn_uses_shared_brain_and_persists_the_transcript(monkeypatch):
    monkeypatch.setattr(voice_api.agent_api, "devices", FakeDevices())
    captured = {}
    saved = []

    def fake_answer(message, **kwargs):
        captured["message"] = message
        captured.update(kwargs)
        return {
            "success": True,
            "understanding": "Hello. I'm here with you.",
            "task_plan": None,
            "provider": "test-provider",
            "memory_count": 2,
        }

    monkeypatch.setattr(voice_api, "answer_companion", fake_answer)
    monkeypatch.setattr(voice_api, "get_recent_interactions", lambda limit: [{"question": "Earlier chat"}])
    monkeypatch.setattr(voice_api, "save_interaction", lambda *args, **kwargs: saved.append((args, kwargs)))

    response = make_client().post(
        "/companion/voice",
        headers={"Authorization": "Bearer phone-token"},
        json={"transcript": "What were we working on?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["response"] == "Hello. I'm here with you."
    assert payload["voice_mode"] == "tap_to_talk"
    assert captured["message"] == "What were we working on?"
    assert captured["recent_interactions"] == [{"question": "Earlier chat"}]
    assert saved and saved[0][0][0] == "What were we working on?"


def test_voice_turn_rejects_empty_or_oversized_transcripts(monkeypatch):
    monkeypatch.setattr(voice_api.agent_api, "devices", FakeDevices())
    client = make_client()
    headers = {"Authorization": "Bearer phone-token"}
    assert client.post("/companion/voice", headers=headers, json={"transcript": "  "}).status_code == 422
    assert client.post("/companion/voice", headers=headers, json={"transcript": "x" * 4001}).status_code == 422
