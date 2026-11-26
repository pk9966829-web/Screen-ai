"""Shared transactional email delivery for account verification and device approval."""
from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
import tempfile
from email.message import EmailMessage
from pathlib import Path

from fastapi import HTTPException

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _configured_path(env_name: str, default_name: str) -> Path:
    value = os.getenv(env_name, default_name).strip()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def gmail_oauth_paths() -> tuple[Path, Path]:
    return (
        _configured_path("VOSI_GMAIL_OAUTH_CLIENT_FILE", "gmail_oauth_credentials.json"),
        _configured_path("VOSI_GMAIL_OAUTH_TOKEN_FILE", "gmail_oauth_token.json"),
    )


def _gmail_sender() -> str:
    return os.getenv("VOSI_GMAIL_FROM", "").strip()


def _smtp_settings() -> tuple[str, int, str, str, str] | None:
    host = os.getenv("VOSI_SMTP_HOST", "").strip()
    username = os.getenv("VOSI_SMTP_USERNAME", "").strip()
    password = os.getenv("VOSI_SMTP_PASSWORD", "")
    sender = os.getenv("VOSI_SMTP_FROM", username).strip()
    try:
        port = int(os.getenv("VOSI_SMTP_PORT", "587"))
    except ValueError:
        return None
    if not (1 <= port <= 65535) or not all((host, username, password, sender)):
        return None
    return host, port, username, password, sender


def is_email_delivery_configured() -> bool:
    """Return whether the selected provider has the files/settings it needs."""
    provider = os.getenv("VOSI_EMAIL_PROVIDER", "smtp").strip().lower()
    if provider == "smtp":
        return _smtp_settings() is not None
    if provider == "gmail_oauth":
        client_file, token_file = gmail_oauth_paths()
        if not client_file.is_file() or not token_file.is_file() or not _gmail_sender():
            return False
        try:
            token_data = json.loads(token_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        scopes = token_data.get("scopes", [])
        return bool(token_data.get("refresh_token")) and GMAIL_SEND_SCOPE in scopes
    return False


def _write_token_file(token_file: Path, contents: str) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=token_file.parent,
            prefix=".gmail-oauth-", suffix=".tmp", delete=False,
        ) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        if os.name != "nt":
            os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, token_file)
        if os.name != "nt":
            os.chmod(token_file, 0o600)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def authorize_gmail_oauth() -> None:
    """Run the one-time local-browser authorization and save a send-only token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_file, token_file = gmail_oauth_paths()
    if not client_file.is_file():
        raise RuntimeError(
            f"OAuth client JSON was not found at {client_file}. "
            "Set VOSI_GMAIL_OAUTH_CLIENT_FILE to its local path."
        )
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_file), [GMAIL_SEND_SCOPE]
    )
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        authorization_prompt_message=(
            "Approve CHERRY AI's permission to send account and device-security emails."
        ),
        success_message=(
            "Gmail email delivery is authorized. You can close this browser tab."
        ),
        access_type="offline",
        prompt="consent",
    )
    if not credentials.refresh_token:
        raise RuntimeError(
            "Google did not return a refresh token. Revoke this app's access in your "
            "Google Account and run authorization again."
        )
    _write_token_file(token_file, credentials.to_json())


def _gmail_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    _, token_file = gmail_oauth_paths()
    if not token_file.is_file():
        raise HTTPException(
            status_code=503,
            detail="Gmail email delivery is not authorized. Run python authorize_gmail_email.py in the backend folder.",
        )
    try:
        credentials = Credentials.from_authorized_user_file(
            str(token_file), [GMAIL_SEND_SCOPE]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="The Gmail email-delivery token is invalid. Run python authorize_gmail_email.py again.",
        ) from exc
    if not credentials.has_scopes([GMAIL_SEND_SCOPE]):
        raise HTTPException(
            status_code=503,
            detail="The Gmail token lacks the send-only permission. Run python authorize_gmail_email.py again.",
        )
    if credentials.expired:
        if not credentials.refresh_token:
            raise HTTPException(
                status_code=503,
                detail="The Gmail authorization expired. Run python authorize_gmail_email.py again.",
            )
        try:
            credentials.refresh(Request())
            _write_token_file(token_file, credentials.to_json())
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Gmail authorization could not be refreshed. Reauthorize Gmail and try again.",
            ) from exc
    if not credentials.valid:
        raise HTTPException(
            status_code=503,
            detail="Gmail authorization is no longer valid. Run python authorize_gmail_email.py again.",
        )
    return credentials


def _gmail_service(credentials):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _build_message(subject: str, recipient: str, body: str, sender: str) -> EmailMessage:
    if any("\r" in value or "\n" in value for value in (subject, recipient, sender)):
        raise HTTPException(status_code=422, detail="Email headers contain invalid characters.")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    return message


def _send_smtp(message: EmailMessage) -> None:
    settings = _smtp_settings()
    if not settings:
        raise HTTPException(
            status_code=503,
            detail="SMTP email delivery is not configured. Set VOSI_SMTP_HOST, VOSI_SMTP_PORT, VOSI_SMTP_USERNAME, VOSI_SMTP_PASSWORD and VOSI_SMTP_FROM.",
        )
    host, port, username, password, _ = settings
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(
            status_code=502,
            detail="CHERRY AI could not send the email through SMTP. Check the SMTP settings.",
        ) from exc


def _send_gmail(message: EmailMessage) -> None:
    credentials = _gmail_credentials()
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    try:
        _gmail_service(credentials).users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="CHERRY AI could not send the email through Gmail. Check the Gmail authorization and sender address.",
        ) from exc


def send_email(subject: str, recipient: str, body: str) -> None:
    """Send a transactional message through the configured provider."""
    provider = os.getenv("VOSI_EMAIL_PROVIDER", "smtp").strip().lower()
    if provider == "smtp":
        settings = _smtp_settings()
        if not settings:
            raise HTTPException(
                status_code=503,
                detail="Email delivery is not configured. Set the SMTP host, port, username, password and sender.",
            )
        message = _build_message(subject, recipient, body, settings[4])
        _send_smtp(message)
        return
    if provider == "gmail_oauth":
        sender = _gmail_sender()
        client_file, token_file = gmail_oauth_paths()
        if not sender or not client_file.is_file() or not token_file.is_file():
            raise HTTPException(
                status_code=503,
                detail="Gmail OAuth email delivery is not configured. Set VOSI_GMAIL_FROM and the OAuth client/token file paths, then authorize Gmail.",
            )
        message = _build_message(subject, recipient, body, sender)
        _send_gmail(message)
        return
    raise HTTPException(
        status_code=503,
        detail="VOSI_EMAIL_PROVIDER must be either 'gmail_oauth' or 'smtp'.",
    )
