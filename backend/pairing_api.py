"""Email-approved QR pairing between an authenticated CHERRY AI web account and Android.

QR secrets, email approval tokens and Android polling tokens are random, single-use
credentials. Only their SHA-256 digests are stored. Loading the email link is read-only;
the account owner must explicitly press Approve or Deny.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from agent_runtime import AgentRuntimeError
from device_registry import DeviceRegistry
from identity_api import store
from identity_store import IdentityError
import email_delivery

router = APIRouter(prefix="/identity/pairing", tags=["VOSI QR Account Pairing"])
DB_PATH = Path(os.getenv("VOSI_AGENT_DB_PATH", str(Path(__file__).with_name("vosi_agent.db"))))
devices = DeviceRegistry(DB_PATH)

QR_TTL_SECONDS = 120
APPROVAL_TTL_SECONDS = 300
ANDROID_CAPABILITIES = [
    "phone.contacts.read",
    "phone.call",
    "phone.whatsapp.quick_reply",
    "agent.task.request",
    "device.alarm.create",
    "device.volume.set",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH), timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 10000")
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _init_schema() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_db()) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS identity_qr_pairings (
                request_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                qr_token_hash TEXT,
                qr_expires_at TEXT NOT NULL,
                state TEXT NOT NULL,
                device_label TEXT,
                approval_token_hash TEXT,
                approval_expires_at TEXT,
                poll_token_hash TEXT,
                created_at TEXT NOT NULL,
                scanned_at TEXT,
                approved_at TEXT,
                consumed_at TEXT,
                device_id TEXT,
                api_base TEXT
            )
            """
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(identity_qr_pairings)").fetchall()}
        if "api_base" not in columns:
            db.execute("ALTER TABLE identity_qr_pairings ADD COLUMN api_base TEXT")
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_identity_qr_user_created "
            "ON identity_qr_pairings(user_id, created_at)"
        )


_init_schema()


class CreatePairingRequest(BaseModel):
    label: str = Field(default="Android phone", min_length=1, max_length=80)


class ScanPairingRequest(BaseModel):
    request_id: str = Field(min_length=32, max_length=32)
    qr_token: str = Field(min_length=32, max_length=128)
    platform: str = Field(default="android", min_length=1, max_length=20)
    label: str = Field(default="Android phone", min_length=1, max_length=80)


class PairingExchangeRequest(BaseModel):
    request_id: str = Field(min_length=32, max_length=32)
    poll_token: str = Field(min_length=32, max_length=128)


class ApprovalDecisionRequest(BaseModel):
    request_id: str = Field(min_length=32, max_length=32)
    token: str = Field(min_length=32, max_length=128)
    decision: str = Field(pattern="^(approve|deny)$")


def _account(authorization: str | None) -> dict[str, Any]:
    scheme, sep, token = (authorization or "").partition(" ")
    supplied = token.strip() if sep and scheme.lower() == "bearer" else None
    try:
        return store.authenticate(supplied)
    except IdentityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _api_base(request: Request) -> str:
    configured = os.getenv("VOSI_PUBLIC_API_URL", "").strip()
    base = configured or str(request.base_url).rstrip("/")
    if not (base.startswith("https://") or base.startswith("http://")):
        raise HTTPException(status_code=503, detail="Configure VOSI_PUBLIC_API_URL with the public HTTPS backend URL.")
    return base.rstrip("/")


def _send_approval_email(email: str, label: str, approval_url: str) -> None:
    body = (
        "A request was made to connect " + label + " to your CHERRY AI account.\n\n"
        "To approve or deny this request, open this secure page and choose an action: "
        + approval_url
        + "\n\nThe approval page does not approve the request just by opening it. "
        "You must press Approve or Deny. This link expires in 5 minutes. "
        "If you did not start this connection, choose Deny or ignore this email."
    )
    email_delivery.send_email(
        "Approve a new CHERRY AI device connection",
        email,
        body,
    )


@router.post("/requests")
def create_pairing_request(
    payload: CreatePairingRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    account = _account(authorization)
    now = _now()
    request_id = uuid.uuid4().hex
    qr_token = secrets.token_urlsafe(32)
    expires = now + timedelta(seconds=QR_TTL_SECONDS)
    base = _api_base(request)
    with closing(_db()) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """UPDATE identity_qr_pairings SET state = 'expired'
               WHERE user_id = ? AND state IN ('pending_scan', 'pending_approval')
               AND (qr_expires_at <= ? OR (approval_expires_at IS NOT NULL AND approval_expires_at <= ?))""",
            (account["user_id"], _iso(now), _iso(now)),
        )
        active = db.execute(
            """SELECT COUNT(*) AS n FROM identity_qr_pairings
               WHERE user_id = ? AND state IN ('pending_scan', 'pending_approval', 'approved', 'exchanging')
               AND created_at > ?""",
            (account["user_id"], _iso(now - timedelta(minutes=10))),
        ).fetchone()["n"]
        if active >= 3:
            db.rollback()
            raise HTTPException(status_code=429, detail="You already have several active pairing requests. Wait for them to expire or finish.")
        db.execute(
            """INSERT INTO identity_qr_pairings
               (request_id, user_id, qr_token_hash, qr_expires_at, state, device_label, created_at, api_base)
               VALUES (?, ?, ?, ?, 'pending_scan', ?, ?, ?)""",
            (request_id, account["user_id"], _digest(qr_token), _iso(expires), payload.label.strip(), _iso(now), base),
        )
        db.commit()
    return {
        "success": True,
        "request_id": request_id,
        "expires_at": _iso(expires),
        "qr_payload": {
            "version": 1,
            "api": base,
            "request_id": request_id,
            "qr_token": qr_token,
        },
        "message": "Scan this QR code with CHERRY AI on Android. It expires in two minutes.",
    }


@router.post("/scan")
def scan_pairing_qr(payload: ScanPairingRequest):
    if payload.platform != "android":
        raise HTTPException(status_code=422, detail="This QR pairing flow currently supports Android phones only.")
    now = _now()
    approval_token = secrets.token_urlsafe(32)
    poll_token = secrets.token_urlsafe(32)
    approval_expires = now + timedelta(seconds=APPROVAL_TTL_SECONDS)
    with closing(_db()) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM identity_qr_pairings WHERE request_id = ?",
            (payload.request_id,),
        ).fetchone()
        if (
            not row
            or row["state"] != "pending_scan"
            or not row["qr_token_hash"]
            or datetime.fromisoformat(row["qr_expires_at"]) <= now
            or not hmac.compare_digest(row["qr_token_hash"], _digest(payload.qr_token))
        ):
            db.rollback()
            raise HTTPException(status_code=410, detail="This QR code is invalid, expired, or has already been scanned.")
        db.execute(
            """UPDATE identity_qr_pairings
               SET qr_token_hash = NULL, state = 'pending_approval', device_label = ?,
                   approval_token_hash = ?, approval_expires_at = ?, poll_token_hash = ?, scanned_at = ?
               WHERE request_id = ? AND state = 'pending_scan'""",
            (
                payload.label.strip(), _digest(approval_token), _iso(approval_expires),
                _digest(poll_token), _iso(now), payload.request_id,
            ),
        )
        account_row = db.execute(
            "SELECT email FROM identity_users WHERE user_id = ?",
            (row["user_id"],),
        ).fetchone()
        db.commit()
    if not account_row:
        raise HTTPException(status_code=404, detail="The CHERRY AI account for this pairing request no longer exists.")
    # Use a configured public backend origin in production; request data never supplies this URL.
    base = os.getenv("VOSI_PUBLIC_API_URL", "").strip().rstrip("/") or (row["api_base"] or "").rstrip("/")
    if not base:
        with closing(_db()) as db:
            db.execute(
                "UPDATE identity_qr_pairings SET state = 'email_failed' WHERE request_id = ? AND state = 'pending_approval'",
                (payload.request_id,),
            )
        raise HTTPException(status_code=503, detail="Set VOSI_PUBLIC_API_URL to the public backend URL so CHERRY AI can email a secure approval link.")
    approval_url = (
        f"{base}/identity/pairing/approval?request_id={payload.request_id}"
        f"&token={approval_token}"
    )
    try:
        _send_approval_email(account_row["email"], payload.label.strip(), approval_url)
    except HTTPException:
        with closing(_db()) as db:
            db.execute(
                "UPDATE identity_qr_pairings SET state = 'email_failed' WHERE request_id = ? AND state = 'pending_approval'",
                (payload.request_id,),
            )
        raise
    return {
        "success": True,
        "request_id": payload.request_id,
        "poll_token": poll_token,
        "approval_expires_at": _iso(approval_expires),
        "message": "Approval email sent. Open the email and explicitly approve this Android device.",
    }


@router.get("/requests/{request_id}")
def get_web_pairing_status(request_id: str, authorization: str | None = Header(default=None)):
    account = _account(authorization)
    now = _now()
    with closing(_db()) as db:
        row = db.execute(
            "SELECT user_id, state, qr_expires_at, approval_expires_at, device_id FROM identity_qr_pairings WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if not row or row["user_id"] != account["user_id"]:
            raise HTTPException(status_code=404, detail="Pairing request not found.")
        if row["state"] == "pending_scan" and datetime.fromisoformat(row["qr_expires_at"]) <= now:
            db.execute("UPDATE identity_qr_pairings SET state = 'expired' WHERE request_id = ?", (request_id,))
            return {"success": True, "state": "expired"}
        if row["state"] in {"pending_approval", "approved"} and row["approval_expires_at"] and datetime.fromisoformat(row["approval_expires_at"]) <= now:
            db.execute("UPDATE identity_qr_pairings SET state = 'expired' WHERE request_id = ?", (request_id,))
            return {"success": True, "state": "expired"}
        return {
            "success": True,
            "state": row["state"],
            "device_id": row["device_id"],
        }


@router.get("/requests/{request_id}/mobile-status")
def get_mobile_pairing_status(
    request_id: str,
    x_vosi_pairing_poll_token: str | None = Header(default=None),
):
    now = _now()
    with closing(_db()) as db:
        row = db.execute(
            "SELECT state, approval_expires_at, poll_token_hash FROM identity_qr_pairings WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if not row or not x_vosi_pairing_poll_token or not row["poll_token_hash"] or not hmac.compare_digest(row["poll_token_hash"], _digest(x_vosi_pairing_poll_token)):
            raise HTTPException(status_code=401, detail="Invalid pairing status credential.")
        if row["state"] in {"pending_approval", "approved"} and row["approval_expires_at"] and datetime.fromisoformat(row["approval_expires_at"]) <= now:
            db.execute("UPDATE identity_qr_pairings SET state = 'expired' WHERE request_id = ?", (request_id,))
            return {"success": True, "state": "expired"}
        return {"success": True, "state": row["state"]}


@router.post("/exchange")
def exchange_approved_pairing(payload: PairingExchangeRequest):
    now = _now()
    with closing(_db()) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM identity_qr_pairings WHERE request_id = ?",
            (payload.request_id,),
        ).fetchone()
        if (
            not row
            or row["state"] != "approved"
            or row["consumed_at"] is not None
            or not row["poll_token_hash"]
            or not hmac.compare_digest(row["poll_token_hash"], _digest(payload.poll_token))
        ):
            db.rollback()
            raise HTTPException(status_code=409, detail="Pairing has not been approved, has expired, or was already exchanged.")
        if row["approval_expires_at"] and datetime.fromisoformat(row["approval_expires_at"]) <= now:
            db.execute("UPDATE identity_qr_pairings SET state = 'expired' WHERE request_id = ?", (payload.request_id,))
            db.commit()
            raise HTTPException(status_code=410, detail="The email approval expired. Generate a new QR code.")
        db.execute("UPDATE identity_qr_pairings SET state = 'exchanging' WHERE request_id = ?", (payload.request_id,))
        db.commit()
    device = None
    try:
        pairing = devices.create_pairing("android", row["device_label"] or "Android phone")
        device = devices.complete_pairing(pairing["pairing_code"], ANDROID_CAPABILITIES)
        store.link_device(row["user_id"], device["device_id"])
    except (AgentRuntimeError, IdentityError) as exc:
        if device:
            try:
                devices.revoke_device(device["device_id"])
            except AgentRuntimeError:
                pass
        with closing(_db()) as db:
            db.execute(
                "UPDATE identity_qr_pairings SET state = 'approved' WHERE request_id = ? AND state = 'exchanging'",
                (payload.request_id,),
            )
        status = getattr(exc, "status_code", 422)
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception:
        if device:
            try:
                devices.revoke_device(device["device_id"])
            except AgentRuntimeError:
                pass
        with closing(_db()) as db:
            db.execute(
                "UPDATE identity_qr_pairings SET state = 'approved' WHERE request_id = ? AND state = 'exchanging'",
                (payload.request_id,),
            )
        raise
    with closing(_db()) as db:
        db.execute(
            """UPDATE identity_qr_pairings SET state = 'exchanged', consumed_at = ?, device_id = ?,
               poll_token_hash = NULL, approval_token_hash = NULL
               WHERE request_id = ? AND state = 'exchanging'""",
            (_iso(_now()), device["device_id"], payload.request_id),
        )
    return {
        "success": True,
        "device": {
            "device_id": device["device_id"],
            "device_token": device["device_token"],
            "platform": device["platform"],
            "label": device["label"],
            "capabilities": device["capabilities"],
            "paired_at": device["paired_at"],
        },
        "message": "Android device securely linked to the approved CHERRY AI account.",
    }


@router.get("/approval", response_class=HTMLResponse)
def approval_page(request_id: str, token: str):
    if len(request_id) != 32 or len(token) < 32 or len(token) > 128:
        raise HTTPException(status_code=404, detail="Approval link is invalid.")
    # GET is intentionally read-only. The browser must send an explicit POST after a button click.
    with closing(_db()) as db:
        row = db.execute(
            "SELECT state, approval_expires_at, approval_token_hash FROM identity_qr_pairings WHERE request_id = ?",
            (request_id,),
        ).fetchone()
    if not row or row["state"] != "pending_approval" or not row["approval_token_hash"] or not hmac.compare_digest(row["approval_token_hash"], _digest(token)) or not row["approval_expires_at"] or datetime.fromisoformat(row["approval_expires_at"]) <= _now():
        return HTMLResponse(
            "<!doctype html><html><meta name='viewport' content='width=device-width'><title>CHERRY AI approval</title>"
            "<body style='font:16px system-ui;max-width:520px;margin:12vh auto;padding:24px;background:#10121c;color:white'>"
            "<h2>Approval link expired</h2><p>Return to CHERRY AI and generate a new QR code.</p></body></html>",
            status_code=410,
        )
    # Token is generated by secrets.token_urlsafe and cannot contain HTML delimiters.
    safe_id = html.escape(request_id, quote=True)
    safe_token = html.escape(token, quote=True)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Approve CHERRY AI device</title></head>
<body style="font:16px system-ui;max-width:520px;margin:10vh auto;padding:24px;background:#10121c;color:#f8fafc">
<h1 style="font-size:24px">Connect an Android device?</h1>
<p>A phone scanned a QR code to connect to your CHERRY AI account.</p>
<p>Choose an action below. Opening this page alone does not approve the connection.</p>
<div style="display:flex;gap:12px;margin-top:24px">
<button id="approve" style="padding:14px 18px;border:0;border-radius:10px;background:#0d9488;color:white;font-weight:700">Approve device</button>
<button id="deny" style="padding:14px 18px;border:1px solid #64748b;border-radius:10px;background:transparent;color:white">Deny</button>
</div><p id="status" role="status" style="margin-top:20px;color:#cbd5e1">This approval expires in five minutes.</p>
<script>
const requestId="{safe_id}", token="{safe_token}", statusNode=document.getElementById("status");
async function decide(decision) {{
 document.getElementById("approve").disabled=true; document.getElementById("deny").disabled=true;
 statusNode.textContent="Submitting your choice…";
 try {{
  const response=await fetch("/identity/pairing/approval/decision",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{request_id:requestId,token,decision}})}});
  const data=await response.json();
  if(!response.ok) throw new Error(data.detail||"Could not save your choice.");
  statusNode.textContent=decision==="approve"?"Approved. The Android phone can now finish connecting.":"Request denied. The phone will not be connected.";
 }} catch(error) {{
  statusNode.textContent=String(error.message||error);
  document.getElementById("approve").disabled=false; document.getElementById("deny").disabled=false;
 }}
}}
document.getElementById("approve").addEventListener("click",()=>decide("approve"));
document.getElementById("deny").addEventListener("click",()=>decide("deny"));
</script></body></html>"""
    return HTMLResponse(page, headers={
        "Cache-Control": "no-store, max-age=0",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    })


@router.post("/approval/decision")
def decide_pairing_approval(payload: ApprovalDecisionRequest):
    now = _now()
    with closing(_db()) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT state, approval_token_hash, approval_expires_at FROM identity_qr_pairings WHERE request_id = ?",
            (payload.request_id,),
        ).fetchone()
        if (
            not row
            or row["state"] != "pending_approval"
            or not row["approval_token_hash"]
            or not hmac.compare_digest(row["approval_token_hash"], _digest(payload.token))
        ):
            db.rollback()
            raise HTTPException(status_code=409, detail="This approval request is invalid or has already been handled.")
        if not row["approval_expires_at"] or datetime.fromisoformat(row["approval_expires_at"]) <= now:
            db.execute("UPDATE identity_qr_pairings SET state = 'expired' WHERE request_id = ?", (payload.request_id,))
            db.commit()
            raise HTTPException(status_code=410, detail="This approval request expired. Generate a new QR code.")
        state = "approved" if payload.decision == "approve" else "denied"
        db.execute(
            "UPDATE identity_qr_pairings SET state = ?, approved_at = ?, approval_token_hash = NULL WHERE request_id = ?",
            (state, _iso(now), payload.request_id),
        )
        db.commit()
    return {"success": True, "state": state, "message": "Your choice has been saved."}
