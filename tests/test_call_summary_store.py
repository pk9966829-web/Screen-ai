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
    # Caller facts must not be inferred from CHERRY AI speech.
    assert item["purpose"] == "I need an urgent callback."
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



def test_ai_call_summary_enrichment_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv('CHERRY_CALL_SUMMARY_AI_ENABLED', raising=False)
    assert call_summary_store._ai_summary('caller wants callback') is None


def test_caller_transcript_excludes_ai_voice():
    transcript = 'Caller: I need an urgent callback.\\nCHERRY AI: I will call back urgently.'
    assert call_summary_store._caller_only(transcript) == 'I need an urgent callback.'


def test_ai_summary_provider_failover_and_validation(monkeypatch):
    import json
    from types import SimpleNamespace
    import openai
    monkeypatch.setenv('CHERRY_CALL_SUMMARY_AI_ENABLED', 'true')
    monkeypatch.setattr('companion_brain._provider_candidates', lambda: [
        {'name':'first','api_key':'k1','base_url':'https://first.example/v1','model':'m1'},
        {'name':'second','api_key':'k2','base_url':'https://second.example/v1','model':'m2'}])
    payload = {'summary':'Invoice follow-up','caller_name':'Ramesh','purpose':'invoice','urgency':'normal','callback_requested':True,'callback_time':'tomorrow'}
    class FakeClient:
        def __init__(self, **kwargs): self.model = kwargs['base_url']
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    if kwargs['model'] == 'm1': raise RuntimeError('provider unavailable')
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
    monkeypatch.setattr(openai, 'OpenAI', FakeClient)
    result = call_summary_store._ai_summary('Caller: invoice inquiry')
    assert result['caller_name'] == 'Ramesh'
    assert result['purpose'] == 'invoice'
    assert result['callback_requested'] is True
    assert result['callback_time'] == 'tomorrow'
