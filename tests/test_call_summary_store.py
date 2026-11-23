import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
import call_summary_store
import identity_api


def client():
    app = FastAPI()
    app.include_router(call_summary_store.router)
    return TestClient(app)


def auth(monkeypatch, user_id="owner-1"):
    def account(authorization):
        if authorization != "Bearer valid-session":
            raise HTTPException(status_code=401, detail="Invalid session")
        return {"user_id": user_id}
    monkeypatch.setattr(identity_api, "_account", account)


def test_call_history_requires_authentication(tmp_path, monkeypatch):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    monkeypatch.setenv("CHERRY_CALL_OWNER_USER_ID", "owner-1")
    response = client().get("/call-receptionist/calls")
    assert response.status_code == 401


def test_call_history_is_scoped_to_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    monkeypatch.setenv("CHERRY_CALL_OWNER_USER_ID", "owner-1")
    auth(monkeypatch, "other-user")
    response = client().get("/call-receptionist/calls", headers={"Authorization": "Bearer valid-session"})
    assert response.status_code == 403


def test_owner_can_list_detail_and_update_status(tmp_path, monkeypatch):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    monkeypatch.setenv("CHERRY_CALL_OWNER_USER_ID", "owner-1")
    auth(monkeypatch)
    call_id = call_summary_store.store_call(
        "2026-01-01T10:00:00Z", "2026-01-01T10:02:00Z",
        "+911234567890", "+919876543210", "completed", 120,
        "Caller: I need an urgent callback. CHERRY AI: I will take a message."
    )
    c = client()
    headers = {"Authorization": "Bearer valid-session"}
    listed = c.get("/call-receptionist/calls", headers=headers)
    assert listed.status_code == 200
    item = listed.json()["calls"][0]
    assert item["id"] == call_id
    assert item["urgency"] == "urgent"
    assert item["callback_requested"] == 1
    detail = c.get(f"/call-receptionist/calls/{call_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["call"]["transcript"].startswith("Caller:")
    updated = c.patch(f"/call-receptionist/calls/{call_id}/status?status=reviewed", headers=headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "reviewed"


def test_unconfigured_owner_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    monkeypatch.delenv("CHERRY_CALL_OWNER_USER_ID", raising=False)
    response = client().get("/call-receptionist/calls", headers={"Authorization": "Bearer valid-session"})
    assert response.status_code == 503
