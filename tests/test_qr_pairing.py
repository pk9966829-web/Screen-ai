"""Security-focused tests for account-owned QR device pairing.

Run from the repository root with:
    python -m unittest discover -s tests -p "test_qr_pairing.py"
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException
from starlette.requests import Request

import pairing_api
from device_registry import DeviceRegistry
from identity_store import IdentityStore


class QrPairingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "pairing-test.sqlite3")
        self.db_path_patch = patch.object(pairing_api, "DB_PATH", Path(self.db_path))
        self.db_path_patch.start()
        pairing_api.store = IdentityStore(self.db_path)
        pairing_api.devices = DeviceRegistry(self.db_path)
        pairing_api._init_schema()
        self.account, code = pairing_api.store.create_account(
            "owner@example.test", "a-secure-test-password", "test-challenge-secret"
        )
        pairing_api.store.verify_email("owner@example.test", code, "test-challenge-secret")
        _, self.session_token = pairing_api.store.login(
            "owner@example.test", "a-secure-test-password"
        )
        self.authorization = "Bearer " + self.session_token
        self.request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/identity/pairing/requests",
            "raw_path": b"/identity/pairing/requests",
            "query_string": b"",
            "headers": [(b"host", b"api.example.test")],
            "client": ("127.0.0.1", 12345),
            "server": ("api.example.test", 443),
        })

    def tearDown(self):
        self.db_path_patch.stop()
        self.temp_dir.cleanup()

    def create_qr(self):
        with patch.dict(os.environ, {"VOSI_PUBLIC_API_URL": "https://api.example.test"}):
            created = pairing_api.create_pairing_request(
                pairing_api.CreatePairingRequest(label="Test Android"),
                self.request,
                self.authorization,
            )
        return created

    def scan(self, created):
        with patch.object(pairing_api, "_send_approval_email") as send_email:
            scanned = pairing_api.scan_pairing_qr(
                pairing_api.ScanPairingRequest(
                    request_id=created["request_id"],
                    qr_token=created["qr_payload"]["qr_token"],
                    platform="android",
                    label="Test Android",
                )
            )
        approval_url = send_email.call_args.args[2]
        query = parse_qs(urlparse(approval_url).query)
        approval_token = query["token"][0]
        return scanned, approval_token

    def test_getting_approval_page_does_not_approve(self):
        created = self.create_qr()
        scanned, approval_token = self.scan(created)
        page = pairing_api.approval_page(created["request_id"], approval_token)
        self.assertEqual(page.status_code, 200)
        status = pairing_api.get_web_pairing_status(created["request_id"], self.authorization)
        self.assertEqual(status["state"], "pending_approval")
        self.assertIn("Approve device", page.body.decode("utf-8"))

    def test_explicit_approval_links_android_and_exchange_is_single_use(self):
        created = self.create_qr()
        scanned, approval_token = self.scan(created)
        decision = pairing_api.decide_pairing_approval(
            pairing_api.ApprovalDecisionRequest(
                request_id=created["request_id"],
                token=approval_token,
                decision="approve",
            )
        )
        self.assertEqual(decision["state"], "approved")
        mobile_status = pairing_api.get_mobile_pairing_status(
            created["request_id"], scanned["poll_token"]
        )
        self.assertEqual(mobile_status["state"], "approved")
        exchanged = pairing_api.exchange_approved_pairing(
            pairing_api.PairingExchangeRequest(
                request_id=created["request_id"],
                poll_token=scanned["poll_token"],
            )
        )
        self.assertTrue(exchanged["device"]["device_token"])
        linked = pairing_api.store.list_devices(self.account["user_id"])
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["device_id"], exchanged["device"]["device_id"])
        with self.assertRaises(HTTPException) as error:
            pairing_api.exchange_approved_pairing(
                pairing_api.PairingExchangeRequest(
                    request_id=created["request_id"],
                    poll_token=scanned["poll_token"],
                )
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_denial_does_not_create_a_linked_device(self):
        created = self.create_qr()
        scanned, approval_token = self.scan(created)
        decision = pairing_api.decide_pairing_approval(
            pairing_api.ApprovalDecisionRequest(
                request_id=created["request_id"],
                token=approval_token,
                decision="deny",
            )
        )
        self.assertEqual(decision["state"], "denied")
        self.assertEqual(
            pairing_api.get_mobile_pairing_status(created["request_id"], scanned["poll_token"])["state"],
            "denied",
        )
        with self.assertRaises(HTTPException):
            pairing_api.exchange_approved_pairing(
                pairing_api.PairingExchangeRequest(
                    request_id=created["request_id"],
                    poll_token=scanned["poll_token"],
                )
            )
        self.assertEqual(pairing_api.store.list_devices(self.account["user_id"]), [])

    def test_qr_is_single_use_and_expires_after_two_minutes(self):
        created = self.create_qr()
        self.scan(created)
        with self.assertRaises(HTTPException) as duplicate:
            pairing_api.scan_pairing_qr(
                pairing_api.ScanPairingRequest(
                    request_id=created["request_id"],
                    qr_token=created["qr_payload"]["qr_token"],
                )
            )
        self.assertEqual(duplicate.exception.status_code, 410)

        expired = self.create_qr()
        future = datetime.now(timezone.utc) + timedelta(seconds=121)
        with patch.object(pairing_api, "_now", return_value=future):
            with self.assertRaises(HTTPException) as error:
                pairing_api.scan_pairing_qr(
                    pairing_api.ScanPairingRequest(
                        request_id=expired["request_id"],
                        qr_token=expired["qr_payload"]["qr_token"],
                    )
                )
        self.assertEqual(error.exception.status_code, 410)


if __name__ == "__main__":
    unittest.main()
