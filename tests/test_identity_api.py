import base64
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import identity_api  # noqa: E402
import email_delivery  # noqa: E402
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
    monkeypatch.setenv("VOSI_EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("VOSI_SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("VOSI_SMTP_PORT", "587")
    monkeypatch.setenv("VOSI_SMTP_USERNAME", "vosi@example.test")
    monkeypatch.setenv("VOSI_SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("VOSI_SMTP_FROM", "vosi@example.test")
    FakeSMTP.sent = []
    def fake_send_email(subject, recipient, body):
        from email.message import EmailMessage
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = "vosi@example.test"
        message["To"] = recipient
        message.set_content(body)
        FakeSMTP.sent.append(message)

    monkeypatch.setattr(email_delivery, "send_email", fake_send_email)
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


def test_registration_accepts_configured_gmail_oauth_without_smtp(client, monkeypatch, tmp_path):
    client_file = tmp_path / "gmail-client.json"
    token_file = tmp_path / "gmail-token.json"
    client_file.write_text("{}", encoding="utf-8")
    token_file.write_text(
        '{"refresh_token":"test-refresh-token","scopes":["https://www.googleapis.com/auth/gmail.send"]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("VOSI_EMAIL_PROVIDER", "gmail_oauth")
    monkeypatch.setenv("VOSI_GMAIL_OAUTH_CLIENT_FILE", str(client_file))
    monkeypatch.setenv("VOSI_GMAIL_OAUTH_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("VOSI_GMAIL_FROM", "vosi@example.test")
    response = client.post(
        "/identity/register",
        json={"email": "gmail-person@example.test", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    assert FakeSMTP.sent[-1]["To"] == "gmail-person@example.test"


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


def test_google_signin_creates_verified_account_and_session(client, monkeypatch):
    monkeypatch.setenv("VOSI_GOOGLE_CLIENT_ID", "public-google-client-id")
    monkeypatch.setattr(
        identity_api,
        "_verify_google_credential",
        lambda credential: {"email": "google-user@example.test", "sub": "google-sub-123"},
    )
    response = client.post("/identity/google-login", json={"credential": "fake-google-id-token-value"})
    assert response.status_code == 200
    data = response.json()
    assert data["account"]["email"] == "google-user@example.test"
    assert data["account"]["email_verified"] is True
    assert data["access_token"]
    authenticated = client.get("/identity/me", headers={"Authorization": "Bearer " + data["access_token"]})
    assert authenticated.status_code == 200
    assert authenticated.json()["account"]["email"] == "google-user@example.test"
    assert client.post("/identity/login", json={"email": "google-user@example.test", "password": "random-password"}).status_code == 401


def test_google_signin_links_existing_verified_email_account(client, monkeypatch):
    register_and_verify(client, email="linked-google@example.test")
    monkeypatch.setattr(
        identity_api,
        "_verify_google_credential",
        lambda credential: {"email": "linked-google@example.test", "sub": "google-sub-linked"},
    )
    response = client.post("/identity/google-login", json={"credential": "fake-google-id-token-value"})
    assert response.status_code == 200
    assert response.json()["account"]["email"] == "linked-google@example.test"
    with identity_api.store._connect() as db:
        row = db.execute("SELECT google_sub FROM identity_users WHERE email = ?", ("linked-google@example.test",)).fetchone()
    assert row["google_sub"] == "google-sub-linked"


def test_google_signin_rejects_conflicting_google_identity(client, monkeypatch):
    monkeypatch.setattr(
        identity_api,
        "_verify_google_credential",
        lambda credential: {"email": "conflict@example.test", "sub": "first-google-sub"},
    )
    first = client.post("/identity/google-login", json={"credential": "fake-google-id-token-value"})
    assert first.status_code == 200
    monkeypatch.setattr(
        identity_api,
        "_verify_google_credential",
        lambda credential: {"email": "conflict@example.test", "sub": "second-google-sub"},
    )
    second = client.post("/identity/google-login", json={"credential": "fake-google-id-token-value"})
    assert second.status_code == 409


def test_identity_config_exposes_only_public_google_client_id(client, monkeypatch):
    monkeypatch.setenv("VOSI_GOOGLE_CLIENT_ID", "public-google-client-id")
    response = client.get("/identity/config")
    assert response.status_code == 200
    assert response.json() == {"google_client_id": "public-google-client-id"}
