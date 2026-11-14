#!/usr/bin/env python3
"""Create a secret-free VOSI backup using SQLite's online backup API."""
from __future__ import annotations
import json, os, shutil, sqlite3, sys, tarfile, tempfile
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.getenv("VOSI_BACKUP_DATA_DIR", "/data")).resolve()
OUTPUT_DIR = Path(os.getenv("VOSI_BACKUP_OUTPUT_DIR", "/backups")).resolve()
UPLOAD_DIR = Path(os.getenv("VOSI_ACCOUNT_UPLOAD_DIR", str(DATA_DIR / "account_uploads"))).resolve()
DATABASES = {
    "agent": Path(os.getenv("VOSI_AGENT_DB_PATH", str(DATA_DIR / "vosi_agent.db"))),
    "companion": Path(os.getenv("VOSI_COMPANION_DB_PATH", str(DATA_DIR / "vosi_companion.sqlite3"))),
    "screen": Path(os.getenv("VOSI_SCREEN_DB_PATH", str(DATA_DIR / "screen_ai.db"))),
}

def snapshot_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=30) as src:
        with sqlite3.connect(destination, timeout=30) as dst:
            src.backup(dst)
            check = dst.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise RuntimeError(f"SQLite integrity check failed for {source.name}: {check}")

def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = OUTPUT_DIR / f"vosi-backup-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="vosi-backup-") as temp:
        root = Path(temp) / "vosi"
        root.mkdir()
        entries = []
        for name, configured in DATABASES.items():
            source = configured if configured.is_absolute() else DATA_DIR / configured
            if source.exists():
                relative = f"databases/{name}.sqlite3"
                snapshot_database(source, root / relative)
                entries.append({"name": name, "file": relative})
        if UPLOAD_DIR.is_dir():
            shutil.copytree(UPLOAD_DIR, root / "account_uploads", dirs_exist_ok=True)
        manifest = {
            "format": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "databases": entries,
            "account_uploads_included": (root / "account_uploads").is_dir(),
            "secrets_included": False,
        }
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary = archive.with_suffix(archive.suffix + ".tmp")
        try:
            with tarfile.open(temporary, "w:gz") as bundle:
                bundle.add(root, arcname="vosi")
            os.chmod(temporary, 0o600)
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps({"backup": str(archive), "databases": [x["name"] for x in entries], "uploads_included": UPLOAD_DIR.is_dir()}))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VOSI backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
