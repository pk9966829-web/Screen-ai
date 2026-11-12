"""Persistent VOSI user accounts, email verification, sessions and encrypted profile envelopes."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)


class IdentityError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class IdentityStore:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS identity_users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    email_verified_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS identity_challenges (
                    user_id TEXT PRIMARY KEY,
                    code_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id) ON DELETE CASCADE
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS identity_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id) ON DELETE CASCADE
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS identity_device_links (
                    user_id TEXT NOT NULL,
                    device_id TEXT NOT NULL UNIQUE,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY(user_id, device_id),
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id) ON DELETE CASCADE
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS identity_profiles (
                    user_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    encrypted_profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES identity_users(user_id) ON DELETE CASCADE
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_identity_sessions_user ON identity_sessions(user_id, expires_at)")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _challenge_hash(code: str, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), code.encode("ascii"), hashlib.sha256).hexdigest()

    def create_account(self, email: str, password: str, challenge_secret: str) -> tuple[dict[str, Any], str]:
        email = email.strip().lower()
        if len(email) > 254 or not __import__("re").fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise IdentityError("Enter a valid email address.")
        if len(password) < 10 or len(password) > 256:
            raise IdentityError("Password must contain 10 to 256 characters.")
        salt = secrets.token_bytes(16)
        digest = _password_hash(password, salt)
        user_id = uuid.uuid4().hex
        now = _now()
        code = f"{secrets.randbelow(1_000_000):06d}"
        with self._connect() as db:
            try:
                db.execute(
                    """INSERT INTO identity_users
                       (user_id, email, password_salt, password_hash, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, email, salt, digest, _iso(now), _iso(now)),
                )
            except sqlite3.IntegrityError as exc:
                raise IdentityError("An account with this email already exists.", 409) from exc
            db.execute(
                """INSERT INTO identity_challenges (user_id, code_hash, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, self._challenge_hash(code, challenge_secret), _iso(now + timedelta(minutes=10)), _iso(now)),
            )
        return {"user_id": user_id, "email": email, "email_verified": False, "created_at": _iso(now)}, code

    def delete_unverified_account(self, email: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM identity_users WHERE email = ? AND email_verified_at IS NULL", (email.strip().lower(),))

    def verify_email(self, email: str, code: str, challenge_secret: str) -> dict[str, Any]:
        email = email.strip().lower()
        if not (len(code) == 6 and code.isdigit()):
            raise IdentityError("Enter the six-digit verification code.")
        now = _now()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT u.user_id, u.email, c.code_hash, c.expires_at, c.attempts
                   FROM identity_users u JOIN identity_challenges c ON c.user_id = u.user_id
                   WHERE u.email = ? AND u.email_verified_at IS NULL""",
                (email,),
            ).fetchone()
            if not row:
                db.rollback()
                raise IdentityError("No pending email verification was found.", 404)
            if row["attempts"] >= 5 or datetime.fromisoformat(row["expires_at"]) <= now:
                db.rollback()
                raise IdentityError("Verification code expired or attempt limit reached. Register again or contact support.", 410)
            supplied = self._challenge_hash(code, challenge_secret)
            if not hmac.compare_digest(row["code_hash"], supplied):
                db.execute("UPDATE identity_challenges SET attempts = attempts + 1 WHERE user_id = ?", (row["user_id"],))
                db.commit()
                raise IdentityError("Incorrect verification code.")
            db.execute("UPDATE identity_users SET email_verified_at = ?, updated_at = ? WHERE user_id = ?", (_iso(now), _iso(now), row["user_id"]))
            db.execute("DELETE FROM identity_challenges WHERE user_id = ?", (row["user_id"],))
            db.commit()
        return {"user_id": row["user_id"], "email": row["email"], "email_verified": True}

    def login(self, email: str, password: str) -> tuple[dict[str, Any], str]:
        email = email.strip().lower()
        with self._connect() as db:
            row = db.execute("SELECT * FROM identity_users WHERE email = ?", (email,)).fetchone()
        if not row:
            # Keep the response the same for unknown users and wrong passwords.
            raise IdentityError("Email or password is incorrect.", 401)
        candidate = _password_hash(password, row["password_salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            raise IdentityError("Email or password is incorrect.", 401)
        if not row["email_verified_at"]:
            raise IdentityError("Verify your email before signing in.", 403)
        token = secrets.token_urlsafe(48)
        now = _now()
        expires = now + timedelta(days=30)
        with self._connect() as db:
            db.execute(
                """INSERT INTO identity_sessions (session_id, user_id, token_hash, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (uuid.uuid4().hex, row["user_id"], _token_hash(token), _iso(now), _iso(expires)),
            )
        return {"user_id": row["user_id"], "email": row["email"], "email_verified": True, "session_expires_at": _iso(expires)}, token

    def authenticate(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise IdentityError("A VOSI account session is required.", 401)
        now = _iso(_now())
        with self._connect() as db:
            row = db.execute(
                """SELECT u.user_id, u.email, u.email_verified_at, s.session_id, s.expires_at
                   FROM identity_sessions s JOIN identity_users u ON u.user_id = s.user_id
                   WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?""",
                (_token_hash(token), now),
            ).fetchone()
        if not row:
            raise IdentityError("VOSI account session is invalid, expired or revoked.", 401)
        return {"user_id": row["user_id"], "email": row["email"], "email_verified": bool(row["email_verified_at"]), "session_id": row["session_id"], "session_expires_at": row["expires_at"]}

    def revoke_session(self, token: str) -> None:
        now = _iso(_now())
        with self._connect() as db:
            db.execute("UPDATE identity_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL", (now, _token_hash(token)))

    def list_devices(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT d.device_id, d.platform, d.label, d.capabilities_json, d.created_at,
                          d.last_seen_at, d.revoked_at
                   FROM identity_device_links l JOIN paired_devices d ON d.device_id = l.device_id
                   WHERE l.user_id = ? ORDER BY l.linked_at DESC""",
                (user_id,),
            ).fetchall()
        return [{
            "device_id": row["device_id"], "platform": row["platform"], "label": row["label"],
            "capabilities": __import__("json").loads(row["capabilities_json"]),
            "created_at": row["created_at"], "last_seen_at": row["last_seen_at"],
            "revoked_at": row["revoked_at"],
            "status": "revoked" if row["revoked_at"] else "linked",
        } for row in rows]

    def link_device(self, user_id: str, device_id: str) -> None:
        now = _iso(_now())
        with self._connect() as db:
            device = db.execute("SELECT device_id, revoked_at FROM paired_devices WHERE device_id = ?", (device_id,)).fetchone()
            if not device or device["revoked_at"]:
                raise IdentityError("Device is not paired or has been revoked.", 404)
            try:
                db.execute("INSERT INTO identity_device_links (user_id, device_id, linked_at) VALUES (?, ?, ?)", (user_id, device_id, now))
            except sqlite3.IntegrityError as exc:
                existing = db.execute("SELECT user_id FROM identity_device_links WHERE device_id = ?", (device_id,)).fetchone()
                if existing and existing["user_id"] == user_id:
                    return
                raise IdentityError("This device is already linked to another VOSI account.", 409) from exc

    def unlink_device(self, user_id: str, device_id: str) -> None:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM identity_device_links WHERE user_id = ? AND device_id = ?", (user_id, device_id))
            if cursor.rowcount == 0:
                raise IdentityError("This device is not linked to your account.", 404)

    def get_profile(self, user_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT revision, encrypted_profile_json, updated_at FROM identity_profiles WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {"revision": 0, "encrypted_profile": None, "updated_at": None}
        return {"revision": row["revision"], "encrypted_profile": __import__("json").loads(row["encrypted_profile_json"]), "updated_at": row["updated_at"]}

    def put_profile(self, user_id: str, expected_revision: int, encrypted_profile: dict[str, Any]) -> dict[str, Any]:
        import json
        now = _iso(_now())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision FROM identity_profiles WHERE user_id = ?", (user_id,)).fetchone()
            current = row["revision"] if row else 0
            if expected_revision != current:
                db.rollback()
                raise IdentityError("Profile changed on another device. Fetch the latest revision before saving.", 409)
            revision = current + 1
            db.execute(
                """INSERT INTO identity_profiles (user_id, revision, encrypted_profile_json, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET revision = excluded.revision,
                     encrypted_profile_json = excluded.encrypted_profile_json, updated_at = excluded.updated_at""",
                (user_id, revision, json.dumps(encrypted_profile, sort_keys=True, separators=(",", ":")), now),
            )
            db.commit()
        return {"revision": revision, "updated_at": now}
