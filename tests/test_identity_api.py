import base64
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import identity_api  # noqa: E402
from device_registry import DeviceRegistry  # noqa: E402
from agent_runtime import AgentRuntimeError  # noqa: E402
from identity_store import IdentityStore  # noqa: E402


class FakeSMTP:
    sent = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self, **kwargs):
        pass

    def login(self, *args):
        pass

    def send_message(self, message):
        self.sent.append(message)


@pytest.fixture
def client(monkeypatch, tmp_path):
    db = tmp_path / "identity.sqlite3"
    identity_api.store = IdentityStore(db)
    identity_api.devices = DeviceRegistry(db)
    monkeypatch.setenv("VOSI_IDENTITY_CHALLENGE_SECRET", "test-identity-challenge-secret-32")
    monkeypatch.setenv("VOSI_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("VOSI_SMTP_PORT", "587")
    monkeypatch.setenv("VOSI_SMTP_USERNAME", "vosi@example.test")
    monkeypatch.setenv("VOSI_SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("VOSI_SMTP_FROM", "vosi@example.test")
    FakeSMTP.sent = []
    monkeypatch.setattr(identity_api.smtplib, "SMTP", FakeSMTP)
    app = FastAPI()
    app.include_router(identity_api.router)
    return TestClient(app)


def register_and_verify(client, email="person@example.test", password="correct horse battery"):
    created = client.post("/identity/register", json={"email": email, "password": password})
    assert created.status_code == 200
    message = FakeSMTP.sent[-1]
    code = next(part for part in message.get_content().split() if len(part) == 6 and part.isdigit())
    verified = client.post("/identity/verify-email", json={"email": email, "code": code})
    assert verified.status_code == 200
    return password


def login(client, email="person@example.test", password="correct horse battery"):
    response = client.post("/identity/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_register_requires_email_verification_before_login(client):
    response = client.post("/identity/register", json={"email": "person@example.test", "password": "correct horse battery"})
    assert response.status_code == 200
    assert client.post("/identity/login", json={"email": "person@example.test", "password": "correct horse battery"}).status_code == 403
    code = next(part for part in FakeSMTP.sent[-1].get_content().split() if len(part) == 6 and part.isdigit())
    assert client.post("/identity/verify-email", json={"email": "person@example.test", "code": code}).status_code == 200
    assert client.post("/identity/login", json={"email": "person@example.test", "password": "correct horse battery"}).status_code == 200


def test_registration_rejects_duplicate_email_and_weak_password(client):
    assert client.post("/identity/register", json={"email": "person@example.test", "password": "short"}).status_code == 422
    register_and_verify(client)
    assert client.post("/identity/register", json={"email": "PERSON@example.test", "password": "correct horse battery"}).status_code == 409


def test_verification_code_attempt_limit(client):
    client.post("/identity/register", json={"email": "person@example.test", "password": "correct horse battery"})
    actual_code = next(part for part in FakeSMTP.sent[-1].get_content().split() if len(part) == 6 and part.isdigit())
    wrong_code = "000000" if actual_code != "000000" else "000001"
    for _ in range(5):
        response = client.post("/identity/verify-email", json={"email": "person@example.test", "code": wrong_code})
    assert response.status_code == 400
    assert client.post("/identity/verify-email", json={"email": "person@example.test", "code": wrong_code}).status_code == 410


def test_account_session_logout_revokes_token(client):
    register_and_verify(client)
    headers = login(client)
    assert client.get("/identity/me", headers=headers).status_code == 200
    assert client.post("/identity/logout", headers=headers).status_code == 200
    assert client.get("/identity/me", headers=headers).status_code == 401


def test_encrypted_profile_sync_is_opaque_and_uses_revision_conflicts(client):
    register_and_verify(client)
    headers = login(client)
    envelope = {
        "version": 1,
        "algorithm": "AES-256-GCM",
        "nonce": base64.b64encode(b"n" * 12).decode(),
        "ciphertext": base64.b64encode(b"c" * 32).decode(),
        "key_id": "profile-key-v1",
    }
    saved = client.put("/identity/profile", headers=headers, json={"expected_revision": 0, "encrypted_profile": envelope})
    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert client.get("/identity/profile", headers=headers).json()["encrypted_profile"] == envelope
    conflict = client.put("/identity/profile", headers=headers, json={"expected_revision": 0, "encrypted_profile": envelope})
    assert conflict.status_code == 409
    assert "person@example.test" not in str(envelope)


def test_profile_rejects_plaintext_or_malformed_envelope(client):
    register_and_verify(client)
    headers = login(client)
    response = client.put("/identity/profile", headers=headers, json={
        "expected_revision": 0, "encrypted_profile": {"display_name": "Plaintext"}
    })
    assert response.status_code == 422


def test_account_can_link_only_a_valid_paired_device(client):
    register_and_verify(client)
    headers = login(client)
    # Pair through the same persisted device registry used by the identity service.
    pairing_record = identity_api.devices.create_pairing("android", "My phone")
    paired = identity_api.devices.complete_pairing(pairing_record["pairing_code"], ["agent.task.request"])
    linked = client.post("/identity/devices/link", headers={**headers, "X-VOSI-Device-Token": paired["device_token"]},
                         params={"device_id": paired["device_id"]})
    assert linked.status_code == 200
    listing = client.get("/identity/devices", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["devices"][0]["device_id"] == paired["device_id"]
    revoked = client.delete(f"/identity/devices/{paired['device_id']}", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True
    assert client.get("/identity/devices", headers=headers).json()["devices"] == []
    with pytest.raises(AgentRuntimeError, match="Invalid or revoked"):
        identity_api.devices.authenticate(paired["device_token"])
