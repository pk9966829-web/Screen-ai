import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from companion import router  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VOSI_COMPANION_TOKEN", "test-pairing-token")
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def auth():
    return {"Authorization": "Bearer test-pairing-token"}


def preview(key, posted_at):
    return {
        "key": key,
        "sender": "Test sender",
        "message": f"Preview {key}",
        "postedAt": posted_at,
    }


def test_sync_requires_valid_bearer_token(client):
    response = client.post(
        "/companion/whatsapp/sync",
        json={"messages": [preview("a", 1)]},
    )
    assert response.status_code == 401


def test_sync_and_read_latest_messages(client):
    response = client.post(
        "/companion/whatsapp/sync",
        headers=auth(),
        json={"messages": [preview("old", 1), preview("new", 2)]},
    )
    assert response.status_code == 200
    assert response.json()["received"] == 2

    read = client.get("/companion/whatsapp", headers=auth())
    assert read.status_code == 200
    assert [item["key"] for item in read.json()["messages"]] == ["new", "old"]


def test_sync_rejects_more_than_thirty_previews(client):
    response = client.post(
        "/companion/whatsapp/sync",
        headers=auth(),
        json={"messages": [preview(str(i), i) for i in range(31)]},
    )
    assert response.status_code == 422


def test_missing_server_token_disables_pairing(client, monkeypatch):
    monkeypatch.setenv("VOSI_COMPANION_TOKEN", "")
    response = client.get("/companion/whatsapp", headers=auth())
    assert response.status_code == 503
