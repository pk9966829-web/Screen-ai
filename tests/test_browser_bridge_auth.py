import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import main  # noqa: E402
from device_registry import DeviceRegistry  # noqa: E402


def test_browser_bridge_rejects_unpaired_and_non_browser_devices(tmp_path, monkeypatch):
    registry = DeviceRegistry(tmp_path / "browser-auth.sqlite3")
    monkeypatch.setattr(main, "agent_devices", registry)
    main.browser_pending_command = {"request_id": "request-1", "query": "body spray"}
    client = TestClient(main.app)

    assert client.get("/browser/command").status_code == 401

    android_code = registry.create_pairing("android", "Phone")
    android = registry.complete_pairing(android_code["pairing_code"], ["phone.contacts.read"])
    android_headers = {"Authorization": f"Bearer {android['device_token']}"}
    assert client.get("/browser/command", headers=android_headers).status_code == 403

    browser_code = registry.create_pairing("browser", "Chrome")
    browser = registry.complete_pairing(browser_code["pairing_code"], ["browser.search_products"])
    headers = {"Authorization": f"Bearer {browser['device_token']}"}

    command = client.get("/browser/command", headers=headers)
    assert command.status_code == 200
    assert command.json()["command"]["request_id"] == "request-1"

    results = client.post(
        "/browser/results",
        headers=headers,
        json={"request_id": "request-1", "products": [{"name": "Example spray", "price": "₹499"}]},
    )
    assert results.status_code == 200

    ack = client.post("/browser/ack/request-1", headers=headers)
    assert ack.status_code == 200
    assert main.browser_pending_command is None
