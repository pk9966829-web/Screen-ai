import json
import sqlite3
import tarfile
from pathlib import Path

import backup_vosi


def test_backup_contains_integrity_checked_databases_and_account_uploads(tmp_path, monkeypatch):
    data = tmp_path / "data"
    output = tmp_path / "backups"
    uploads = data / "account_uploads"
    uploads.mkdir(parents=True)
    (uploads / "screen.jpg").write_bytes(b"private-screen-frame")

    db_paths = {}
    for name in ("agent", "companion", "screen"):
        path = data / f"{name}.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE sample (value TEXT)")
            db.execute("INSERT INTO sample VALUES (?)", (name,))
        db_paths[name] = path

    monkeypatch.setattr(backup_vosi, "DATA_DIR", data)
    monkeypatch.setattr(backup_vosi, "OUTPUT_DIR", output)
    monkeypatch.setattr(backup_vosi, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(backup_vosi, "DATABASES", db_paths)

    assert backup_vosi.main() == 0
    archives = list(output.glob("vosi-backup-*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        names = set(archive.getnames())
        assert "vosi/manifest.json" in names
        assert "vosi/account_uploads/screen.jpg" in names
        manifest = json.load(archive.extractfile("vosi/manifest.json"))
        assert {item["name"] for item in manifest["databases"]} == set(db_paths)
        assert manifest["secrets_included"] is False
        for name in db_paths:
            member = archive.extractfile(f"vosi/databases/{name}.sqlite3")
            restored = tmp_path / f"{name}-restored.sqlite3"
            restored.write_bytes(member.read())
            with sqlite3.connect(restored) as db:
                assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert db.execute("SELECT value FROM sample").fetchone()[0] == name
