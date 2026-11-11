import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import agent_api  # noqa: E402
from device_registry import DeviceRegistry  # noqa: E402
from agent_runtime import AgentRuntimeError  # noqa: E402


def registry(tmp_path):
    return DeviceRegistry(tmp_path / "devices.sqlite3")


def test_pairing_code_is_single_use_and_device_token_is_not_listed(tmp_path):
    devices = registry(tmp_path)
    pairing = devices.create_pairing("android", "My Android")
    paired = devices.complete_pairing(pairing["pairing_code"], ["phone.contacts.read"])

    assert paired["platform"] == "android"
    assert paired["device_id"]
    assert paired["device_token"]
    assert devices.authenticate(paired["device_token"])["device_id"] == paired["device_id"]
    assert "device_token" not in devices.list_devices()[0]

    with pytest.raises(AgentRuntimeError, match="Invalid or expired"):
        devices.complete_pairing(pairing["pairing_code"], ["phone.contacts.read"])


def test_pairing_rejects_capabilities_from_another_platform(tmp_path):
    devices = registry(tmp_path)
    pairing = devices.create_pairing("android", "Phone")
    with pytest.raises(AgentRuntimeError, match="not supported"):
        devices.complete_pairing(pairing["pairing_code"], ["browser.search_products"])
    # A rejected attempt does not consume the valid pairing code.
    paired = devices.complete_pairing(pairing["pairing_code"], ["phone.contacts.read"])
    assert paired["platform"] == "android"


def test_invalid_or_expired_pairing_code_is_rejected(tmp_path):
    devices = registry(tmp_path)
    with pytest.raises(AgentRuntimeError, match="Invalid or expired"):
        devices.complete_pairing("x" * 24, [])


def test_device_heartbeat_is_bound_to_device_identity_and_revoke(tmp_path):
    devices = registry(tmp_path)
    pairing = devices.create_pairing("desktop", "Windows PC")
    paired = devices.complete_pairing(pairing["pairing_code"], ["device.volume.set"])

    assert devices.heartbeat(paired["device_id"], paired["device_token"])["status"] == "online"
    with pytest.raises(AgentRuntimeError, match="does not belong"):
        devices.heartbeat("different-device", paired["device_token"])

    devices.revoke_device(paired["device_id"])
    with pytest.raises(AgentRuntimeError, match="Invalid or revoked"):
        devices.authenticate(paired["device_token"])


def test_device_registry_survives_restart_and_revocation_is_visible(tmp_path):
    first = registry(tmp_path)
    pairing = first.create_pairing("browser", "Chrome")
    paired = first.complete_pairing(pairing["pairing_code"], ["browser.read_visible_page"])

    second = registry(tmp_path)
    assert second.list_devices()[0]["device_id"] == paired["device_id"]
    second.revoke_device(paired["device_id"])
    assert second.list_devices()[0]["status"] == "revoked"


def make_client():
    app = FastAPI()
    app.include_router(agent_api.router)
    return TestClient(app)


def test_pairing_api_requires_admin_token_and_device_token_for_heartbeat(monkeypatch, tmp_path):
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "admin-secret")
    agent_api.devices = DeviceRegistry(tmp_path / "api.sqlite3")
    client = make_client()

    denied = client.post("/agent/devices/pairing", json={"platform": "android", "label": "Phone"})
    assert denied.status_code == 401

    admin = {"Authorization": "Bearer admin-secret"}
    response = client.post(
        "/agent/devices/pairing",
        json={"platform": "android", "label": "Phone"},
        headers=admin,
    )
    assert response.status_code == 200
    code = response.json()["pairing"]["pairing_code"]

    paired = client.post(
        "/agent/devices/pair",
        json={"pairing_code": code, "capabilities": ["phone.contacts.read"]},
    )
    assert paired.status_code == 200
    device = paired.json()["device"]
    heartbeat = client.post(
        f"/agent/devices/{device['device_id']}/heartbeat",
        headers={"Authorization": f"Bearer {device['device_token']}"},
    )
    assert heartbeat.status_code == 200

    listing = client.get("/agent/devices", headers=admin)
    assert listing.status_code == 200
    assert "device_token" not in listing.text

    revoked = client.delete(f"/agent/devices/{device['device_id']}", headers=admin)
    assert revoked.status_code == 200
    denied_heartbeat = client.post(
        f"/agent/devices/{device['device_id']}/heartbeat",
        headers={"Authorization": f"Bearer {device['device_token']}"},
    )
    assert denied_heartbeat.status_code == 401
