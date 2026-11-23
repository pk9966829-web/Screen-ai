import sqlite3
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
import call_summary_store

def client():
    app = FastAPI()
    app.include_router(call_summary_store.router)
    return TestClient(app)

def test_store_and_list_call_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    call_id = call_summary_store.store_call(
        "2026-01-01T10:00:00Z", "2026-01-01T10:02:00Z",
        "+911234567890", "+919876543210", "completed", 120,
        "Caller: I need an urgent callback. CHERRY AI: I will take a message."
    )
    result = client().get("/call-receptionist/calls")
    assert result.status_code == 200
    item = result.json()["calls"][0]
    assert item["id"] == call_id
    assert item["urgency"] == "urgent"
    assert item["callback_requested"] == 1
    assert item["status"] == "new"

def test_call_detail_and_status_update(tmp_path, monkeypatch):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    call_id = call_summary_store.store_call("start", "end", "caller", "dest", "completed", 42, "Transcript sample")
    c = client()
    detail = c.get(f"/call-receptionist/calls/{call_id}")
    assert detail.status_code == 200
    assert detail.json()["call"]["transcript"] == "Transcript sample"
    updated = c.patch(f"/call-receptionist/calls/{call_id}/status?status=reviewed")
    assert updated.json()["status"] == "reviewed"
    assert c.patch(f"/call-receptionist/calls/{call_id}/status?status=bad").status_code == 400
    assert c.get("/call-receptionist/calls/999").status_code == 404
