import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
import call_summary_store
import identity_api


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(call_summary_store, "DB_PATH", tmp_path / "calls.db")
    monkeypatch.setenv("CHERRY_CALL_OWNER_USER_ID", "owner-1")
    monkeypatch.delenv("CHERRY_CALL_SUMMARY_AI_ENABLED", raising=False)

    def account(authorization):
        if authorization != "Bearer valid-session":
            raise HTTPException(status_code=401, detail="Invalid session")
        return {"user_id": "owner-1"}

    monkeypatch.setattr(identity_api, "_account", account)
    app = FastAPI()
    app.include_router(call_summary_store.router)
    return TestClient(app), {"Authorization": "Bearer valid-session"}


def _seed():
    urgent_id = call_summary_store.store_call(
        "2026-11-28T10:00:00Z", "2026-11-28T10:01:00Z",
        "+911111111111", "+912222222222", "completed", 60,
        "Caller: This is urgent. Please call me tomorrow."
    )
    normal_id = call_summary_store.store_call(
        "2026-11-27T10:00:00Z", "2026-11-27T10:02:00Z",
        "+913333333333", "+912222222222", "caller_disconnected", 120,
        "Caller: I am asking about a product."
    )
    return urgent_id, normal_id


def test_dashboard_stats_are_owner_scoped_and_do_not_return_transcripts(monkeypatch, tmp_path):
    c, headers = _client(monkeypatch, tmp_path)
    urgent_id, normal_id = _seed()
    response = c.get("/call-receptionist/calls/stats", headers=headers)
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["total"] == 2
    assert stats["new_count"] == 2
    assert stats["urgent_count"] == 1
    assert stats["callback_requested_count"] == 1
    assert "transcript" not in response.json()


def test_call_history_filters_and_pagination(monkeypatch, tmp_path):
    c, headers = _client(monkeypatch, tmp_path)
    urgent_id, normal_id = _seed()
    filtered = c.get("/call-receptionist/calls?urgency=urgent&callback_only=true", headers=headers)
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["calls"][0]["id"] == urgent_id
    searched = c.get("/call-receptionist/calls?q=3333&limit=1", headers=headers)
    assert searched.json()["total"] == 1
    assert searched.json()["calls"][0]["id"] == normal_id
    page = c.get("/call-receptionist/calls?limit=1&offset=1", headers=headers)
    assert page.json()["total"] == 2
    assert len(page.json()["calls"]) == 1


def test_call_delete_removes_owner_record_and_rejects_missing(monkeypatch, tmp_path):
    c, headers = _client(monkeypatch, tmp_path)
    urgent_id, _ = _seed()
    deleted = c.delete(f"/call-receptionist/calls/{urgent_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert c.get(f"/call-receptionist/calls/{urgent_id}", headers=headers).status_code == 404
    assert c.delete("/call-receptionist/calls/99999", headers=headers).status_code == 404
