"""Secure pairing and registration for VOSI's cross-device device bridges.

Pairing codes are short-lived and single-use. Device bearer tokens are returned once;
only SHA-256 hashes are persisted. Device claims are scoped to the registered platform
and to the capability allow-list.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agent_runtime import CAPABILITIES, AgentRuntimeError

PLATFORMS = {"android", "desktop", "browser"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class DeviceRegistry:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS device_pairings (
                    pairing_id TEXT PRIMARY KEY,
                    code_hash TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS paired_devices (
                    device_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    label TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    capabilities_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    revoked_at TEXT
                )
                """
            )

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        return db

    @staticmethod
    def _validate_platform(platform: str) -> str:
        if platform not in PLATFORMS:
            raise AgentRuntimeError("Platform must be android, desktop, or browser.")
        return platform

    def create_pairing(self, platform: str, label: str) -> dict[str, Any]:
        platform = self._validate_platform(platform)
        label = str(label or "").strip()
        if not label or len(label) > 80:
            raise AgentRuntimeError("Device label must contain 1 to 80 characters.")
        code = secrets.token_urlsafe(24)
        now = _now()
        expires = now + timedelta(minutes=5)
        pairing_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute(
                """INSERT INTO device_pairings
                   (pairing_id, code_hash, platform, label, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (pairing_id, _hash(code), platform, label, _iso(now), _iso(expires)),
            )
        return {
            "pairing_id": pairing_id,
            "pairing_code": code,
            "platform": platform,
            "label": label,
            "created_at": _iso(now),
            "expires_at": _iso(expires),
        }

    def complete_pairing(self, pairing_code: str, capabilities: list[str]) -> dict[str, Any]:
        if not isinstance(pairing_code, str) or not 20 <= len(pairing_code) <= 128:
            raise AgentRuntimeError("Invalid or expired pairing code.")
        if not isinstance(capabilities, list) or len(capabilities) > 50:
            raise AgentRuntimeError("Capabilities must be a list containing at most 50 entries.")
        if any(not isinstance(item, str) for item in capabilities):
            raise AgentRuntimeError("Capabilities must be strings.")
        if len(set(capabilities)) != len(capabilities):
            raise AgentRuntimeError("Capabilities must be unique strings.")

        now = _now()
        token = secrets.token_urlsafe(32)
        device_id = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pairing = db.execute(
                """SELECT * FROM device_pairings
                   WHERE code_hash = ? AND consumed_at IS NULL AND expires_at > ?""",
                (_hash(pairing_code), _iso(now)),
            ).fetchone()
            if not pairing:
                db.rollback()
                raise AgentRuntimeError("Invalid or expired pairing code.")

            platform = pairing["platform"]
            for capability in capabilities:
                metadata = CAPABILITIES.get(capability)
                if not metadata or platform not in metadata["platforms"]:
                    db.rollback()
                    raise AgentRuntimeError(
                        f"Capability {capability!r} is not supported by the {platform} platform."
                    )

            db.execute(
                "UPDATE device_pairings SET consumed_at = ? WHERE pairing_id = ? AND consumed_at IS NULL",
                (_iso(now), pairing["pairing_id"]),
            )
            db.execute(
                """INSERT INTO paired_devices
                   (device_id, platform, label, token_hash, capabilities_json, created_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id, platform, pairing["label"], _hash(token),
                    json.dumps(sorted(capabilities)), _iso(now), _iso(now),
                ),
            )
            db.commit()

        return {
            "device_id": device_id,
            "device_token": token,
            "platform": platform,
            "label": pairing["label"],
            "capabilities": sorted(capabilities),
            "paired_at": _iso(now),
        }

    def authenticate(self, token: str | None) -> dict[str, Any]:
        if not isinstance(token, str) or not token:
            raise AgentRuntimeError("A device bearer token is required.")
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM paired_devices
                   WHERE revoked_at IS NULL AND token_hash = ?""",
                (_hash(token),),
            ).fetchall()
        # Compare the hash again using constant-time comparison before accepting it.
        for row in rows:
            if hmac.compare_digest(row["token_hash"], _hash(token)):
                return self._device_dict(row)
        raise AgentRuntimeError("Invalid or revoked device token.")

    def heartbeat(self, device_id: str, token: str) -> dict[str, Any]:
        device = self.authenticate(token)
        if not hmac.compare_digest(device["device_id"], device_id):
            raise AgentRuntimeError("Device token does not belong to this device ID.")
        now = _iso(_now())
        with self._connect() as db:
            db.execute(
                "UPDATE paired_devices SET last_seen_at = ? WHERE device_id = ? AND revoked_at IS NULL",
                (now, device_id),
            )
        return {"device_id": device_id, "last_seen_at": now, "status": "online"}

    def list_devices(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM paired_devices ORDER BY created_at DESC"
            ).fetchall()
        return [self._device_dict(row) for row in rows]

    def revoke_device(self, device_id: str) -> dict[str, Any]:
        now = _iso(_now())
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE paired_devices SET revoked_at = ? WHERE device_id = ? AND revoked_at IS NULL",
                (now, device_id),
            )
            if cursor.rowcount == 0:
                exists = db.execute("SELECT 1 FROM paired_devices WHERE device_id = ?", (device_id,)).fetchone()
                if not exists:
                    raise AgentRuntimeError("Device not found.")
        return {"device_id": device_id, "revoked": True, "revoked_at": now}

    @staticmethod
    def _device_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "device_id": row["device_id"],
            "platform": row["platform"],
            "label": row["label"],
            "capabilities": json.loads(row["capabilities_json"]),
            "created_at": row["created_at"],
            "last_seen_at": row["last_seen_at"],
            "revoked_at": row["revoked_at"],
            "status": "revoked" if row["revoked_at"] else "online",
        }
