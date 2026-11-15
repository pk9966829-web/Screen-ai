import json
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import call_assistant_api  # noqa: E402
from device_registry import DeviceRegistry  # noqa: E402


def make_client():
    app = FastAPI()
    app.include_router(call_assistant_api.router)
    return TestClient(app)


def pair_android(tmp_path):
    registry = DeviceRegistry(tmp_path / "calls.sqlite3")
    pairing = registry.create_pairing("android", "Test phone")
    device = registry.complete_pairing(pairing["pairing_code"], ["phone.call"])
    return registry, device


def test_call_report_requires_paired_device(monkeypatch, tmp_path):
    registry, device = pair_android(tmp_path)
    monkeypatch.setattr(call_assistant_api.agent_api, "devices", registry)
    monkeypatch.setattr(call_assistant_api, "_DB_PATH", tmp_path / "calls.sqlite3")
    response = make_client().post("/companion/calls/report", json={
        "call_id": "call-12345678",
        "started_at": "2026-11-16T10:00:00Z",
        "ended_at": "2026-11-16T10:02:00Z",
    })
    assert response.status_code == 401


def test_call_transcript_requires_disclosure_and_consent(monkeypatch, tmp_path):
    registry, device = pair_android(tmp_path)
    monkeypatch.setattr(call_assistant_api.agent_api, "devices", registry)
    monkeypatch.setattr(call_assistant_api, "_DB_PATH", tmp_path / "calls.sqlite3")
    headers = {"Authorization": f"Bearer {device['device_token']}"}
    response = make_client().post("/companion/calls/report", headers=headers, json={
        "call_id": "call-12345678",
        "started_at": "2026-11-16T10:00:00Z",
        "ended_at": "2026-11-16T10:02:00Z",
        "transcript": "Caller: Please call me tomorrow.",
    })
    assert response.status_code == 403


def test_call_report_stores_summary_not_raw_transcript(monkeypatch, tmp_path):
    db_path = tmp_path / "calls.sqlite3"
    registry, device = pair_android(tmp_path)
    monkeypatch.setattr(call_assistant_api.agent_api, "devices", registry)
    monkeypatch.setattr(call_assistant_api, "_DB_PATH", db_path)
    monkeypatch.setattr(call_assistant_api, "_provider_candidates", lambda: [])
    client = make_client()
    headers = {"Authorization": f"Bearer {device['device_token']}"}
    transcript = "The caller asked for a callback tomorrow about the delivery."
    response = client.post("/companion/calls/report", headers=headers, json={
        "call_id": "call-12345678",
        "caller_number": "+919876543210",
        "caller_name": "Test Caller",
        "started_at": "2026-11-16T10:00:00Z",
        "ended_at": "2026-11-16T10:02:00Z",
        "transcript": transcript,
        "caller_was_told_ai": True,
        "transcription_consent": True,
    })
    assert response.status_code == 200
    assert response.json()["summary"]["duration_seconds"] == 120
    assert response.json()["summary"]["ai_summary"] is False

    listed = client.get("/companion/calls", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["calls"][0]["caller_name"] == "Test Caller"
    with sqlite3.connect(db_path) as db:
        stored = db.execute("SELECT summary_json FROM call_summaries").fetchone()[0]
    assert transcript not in stored


def test_call_report_rejects_negative_duration(monkeypatch, tmp_path):
    registry, device = pair_android(tmp_path)
    monkeypatch.setattr(call_assistant_api.agent_api, "devices", registry)
    monkeypatch.setattr(call_assistant_api, "_DB_PATH", tmp_path / "calls.sqlite3")
    headers = {"Authorization": f"Bearer {device['device_token']}"}
    response = make_client().post("/companion/calls/report", headers=headers, json={
        "call_id": "call-12345678",
        "started_at": "2026-11-16T10:02:00Z",
        "ended_at": "2026-11-16T10:00:00Z",
    })
    assert response.status_code == 422
