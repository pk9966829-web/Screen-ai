"""Account authentication and opaque encrypted-profile sync for VOSI."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from device_registry import DeviceRegistry
from identity_store import IdentityError, IdentityStore

router = APIRouter(prefix="/identity", tags=["VOSI Personal Identity"])
_db_path = Path(os.getenv("VOSI_AGENT_DB_PATH", str(Path(__file__).with_name("vosi_agent.db"))))
store = IdentityStore(_db_path)
devices = DeviceRegistry(_db_path)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=256)


class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class EncryptedProfileRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    encrypted_profile: dict[str, Any]

    @classmethod
    def __get_validators__(cls):
        yield from super().__get_validators__()


def _challenge_secret() -> str:
    secret = os.getenv("VOSI_IDENTITY_CHALLENGE_SECRET", "").strip()
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="VOSI identity verification is not configured. Set VOSI_IDENTITY_CHALLENGE_SECRET.")
    return secret


def _session_token(authorization: str | None) -> str | None:
    scheme, separator, token = (authorization or "").partition(" ")
    return token.strip() if separator and scheme.lower() == "bearer" else None


def _account(authorization: str | None) -> dict[str, Any]:
    try:
        return store.authenticate(_session_token(authorization))
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _send_verification_email(email: str, code: str) -> None:
    host = os.getenv("VOSI_SMTP_HOST", "").strip()
    username = os.getenv("VOSI_SMTP_USERNAME", "").strip()
    password = os.getenv("VOSI_SMTP_PASSWORD", "")
    sender = os.getenv("VOSI_SMTP_FROM", username).strip()
    port = int(os.getenv("VOSI_SMTP_PORT", "587"))
    if not host or not username or not password or not sender:
        raise HTTPException(status_code=503, detail="Email delivery is not configured. Set VOSI_SMTP_HOST, VOSI_SMTP_PORT, VOSI_SMTP_USERNAME, VOSI_SMTP_PASSWORD and VOSI_SMTP_FROM.")
    message = EmailMessage()
    message["Subject"] = "Verify your VOSI account"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "Your VOSI verification code is: " + code +
        "\n\nThis code expires in 10 minutes. If you did not create a VOSI account, ignore this email."
    )
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(status_code=502, detail="VOSI could not send the verification email. Check the SMTP configuration.") from exc


def _raise_identity(exc: IdentityError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/register")
def register_account(request: RegisterRequest):
    try:
        user, code = store.create_account(request.email, request.password, _challenge_secret())
        _send_verification_email(user["email"], code)
        return {"success": True, "account": user, "verification_required": True, "message": "Check your email for a six-digit verification code."}
    except IdentityError as exc:
        _raise_identity(exc)


@router.post("/verify-email")
def verify_account_email(request: VerifyEmailRequest):
    try:
        account = store.verify_email(request.email, request.code, _challenge_secret())
        return {"success": True, "account": account, "message": "Email verified. You can now sign in to VOSI."}
    except IdentityError as exc:
        _raise_identity(exc)


@router.post("/login")
def login_account(request: LoginRequest):
    try:
        account, token = store.login(request.email, request.password)
        return {"success": True, "account": account, "access_token": token, "token_type": "bearer"}
    except IdentityError as exc:
        _raise_identity(exc)


@router.post("/logout")
def logout_account(authorization: str | None = Header(default=None)):
    account = _account(authorization)
    token = _session_token(authorization)
    store.revoke_session(token)
    return {"success": True, "user_id": account["user_id"], "logged_out": True}


@router.get("/me")
def get_current_account(authorization: str | None = Header(default=None)):
    account = _account(authorization)
    return {"success": True, "account": {
        "user_id": account["user_id"], "email": account["email"],
        "email_verified": account["email_verified"],
        "session_expires_at": account["session_expires_at"],
    }}


@router.post("/devices/link")
def link_current_device(
    device_id: str = __import__("fastapi").Query(min_length=16, max_length=64),
    authorization: str | None = Header(default=None),
    x_vosi_device_token: str | None = Header(default=None),
):
    account = _account(authorization)
    try:
        device = devices.authenticate(x_vosi_device_token)
        if device["device_id"] != device_id:
            raise IdentityError("Device token does not match the requested device.", 403)
        store.link_device(account["user_id"], device_id)
        return {"success": True, "device": {"device_id": device_id, "platform": device["platform"], "label": device["label"]}}
    except IdentityError as exc:
        _raise_identity(exc)
    except Exception as exc:
        from agent_runtime import AgentRuntimeError
        if isinstance(exc, AgentRuntimeError):
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        raise


@router.get("/devices")
def list_linked_devices(authorization: str | None = Header(default=None)):
    account = _account(authorization)
    return {"success": True, "devices": store.list_devices(account["user_id"])}


@router.delete("/devices/{device_id}")
def unlink_current_device(device_id: str, authorization: str | None = Header(default=None)):
    account = _account(authorization)
    try:
        store.unlink_device(account["user_id"], device_id)
        return {"success": True, "device_id": device_id, "unlinked": True}
    except IdentityError as exc:
        _raise_identity(exc)


@router.get("/profile")
def get_encrypted_profile(authorization: str | None = Header(default=None)):
    account = _account(authorization)
    return {"success": True, **store.get_profile(account["user_id"])}


@router.put("/profile")
def save_encrypted_profile(request: EncryptedProfileRequest, authorization: str | None = Header(default=None)):
    account = _account(authorization)
    envelope = request.encrypted_profile
    if set(envelope) - {"version", "algorithm", "nonce", "ciphertext", "key_id"}:
        raise HTTPException(status_code=422, detail="Encrypted profile envelope contains unsupported fields.")
    if envelope.get("version") != 1 or envelope.get("algorithm") != "AES-256-GCM":
        raise HTTPException(status_code=422, detail="Profile must use the supported AES-256-GCM envelope version.")
    import base64
    try:
        nonce = base64.b64decode(envelope.get("nonce", ""), validate=True)
        ciphertext = base64.b64decode(envelope.get("ciphertext", ""), validate=True)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Profile nonce and ciphertext must be valid base64.")
    if len(nonce) != 12 or not 16 <= len(ciphertext) <= 32768:
        raise HTTPException(status_code=422, detail="Encrypted profile nonce or ciphertext has an invalid size.")
    if "key_id" in envelope and (not isinstance(envelope["key_id"], str) or len(envelope["key_id"]) > 80):
        raise HTTPException(status_code=422, detail="Profile key identifier is invalid.")
    try:
        saved = store.put_profile(account["user_id"], request.expected_revision, envelope)
        return {"success": True, **saved}
    except IdentityError as exc:
        _raise_identity(exc)
