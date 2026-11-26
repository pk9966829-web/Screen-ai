"""Tests for shared transactional email delivery."""
from __future__ import annotations

import base64
import os
import tempfile
import unittest
from email import message_from_bytes
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import email_delivery


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


class FakeRequest:
    def execute(self):
        return {"id": "sent-message-id"}


class FakeMessages:
    def __init__(self):
        self.payload = None

    def send(self, **kwargs):
        self.payload = kwargs
        return FakeRequest()


class FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class FakeGmailService:
    def __init__(self):
        self.sent = FakeMessages()

    def users(self):
        return FakeUsers(self.sent)


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.client_file = self.root / "client.json"
        self.token_file = self.root / "token.json"
        self.client_file.write_text("{}", encoding="utf-8")
        self.token_file.write_text(
            '{"refresh_token":"fake-refresh","scopes":["https://www.googleapis.com/auth/gmail.send"]}',
            encoding="utf-8",
        )
        self.env = patch.dict(os.environ, {
            "VOSI_EMAIL_PROVIDER": "gmail_oauth",
            "VOSI_GMAIL_OAUTH_CLIENT_FILE": str(self.client_file),
            "VOSI_GMAIL_OAUTH_TOKEN_FILE": str(self.token_file),
            "VOSI_GMAIL_FROM": "owner@example.test",
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()

    def test_gmail_oauth_configuration_requires_client_token_and_sender(self):
        self.assertTrue(email_delivery.is_email_delivery_configured())
        self.token_file.unlink()
        self.assertFalse(email_delivery.is_email_delivery_configured())

    def test_gmail_send_uses_send_only_authorized_service(self):
        service = FakeGmailService()
        with (
            patch.object(email_delivery, "_gmail_credentials", return_value=object()),
            patch.object(email_delivery, "_gmail_service", return_value=service),
        ):
            email_delivery.send_email(
                "Verify your account", "person@example.test", "Your code is 123456"
            )
        raw = service.sent.payload["body"]["raw"]
        decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
        message = message_from_bytes(decoded)
        self.assertEqual(message["To"], "person@example.test")
        self.assertEqual(message["From"], "owner@example.test")
        self.assertEqual(message["Subject"], "Verify your account")
        self.assertIn("123456", message.get_payload(decode=True).decode())

    def test_smtp_fallback_remains_available(self):
        os.environ["VOSI_EMAIL_PROVIDER"] = "smtp"
        os.environ["VOSI_SMTP_HOST"] = "smtp.example.test"
        os.environ["VOSI_SMTP_PORT"] = "587"
        os.environ["VOSI_SMTP_USERNAME"] = "owner@example.test"
        os.environ["VOSI_SMTP_PASSWORD"] = "test-password"
        os.environ["VOSI_SMTP_FROM"] = "owner@example.test"
        FakeSMTP.sent = []
        with patch.object(email_delivery.smtplib, "SMTP", FakeSMTP):
            email_delivery.send_email(
                "Device approval", "person@example.test", "Approve this device"
            )
        self.assertEqual(len(FakeSMTP.sent), 1)
        self.assertEqual(FakeSMTP.sent[0]["To"], "person@example.test")

    def test_unknown_provider_is_not_treated_as_configured(self):
        os.environ["VOSI_EMAIL_PROVIDER"] = "unsupported"
        self.assertFalse(email_delivery.is_email_delivery_configured())


if __name__ == "__main__":
    unittest.main()
