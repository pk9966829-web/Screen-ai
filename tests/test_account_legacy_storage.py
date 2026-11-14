import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import database
from pipeline import ScreenPipeline


def test_legacy_storage_is_partitioned_by_account_and_local_rows_stay_local(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "screen-ai.sqlite3")
    database.initialize_database()

    database.save_interaction("A question", "A answer", user_id="account-a")
    database.save_interaction("B question", "B answer", user_id="account-b")
    database.save_interaction("Local question", "Local answer")

    assert [item["question"] for item in database.get_recent_interactions(user_id="account-a")] == ["A question"]
    assert [item["question"] for item in database.get_recent_interactions(user_id="account-b")] == ["B question"]
    assert [item["question"] for item in database.get_recent_interactions()] == ["Local question"]


def test_observations_and_task_events_are_partitioned_by_account(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "screen-ai.sqlite3")
    database.initialize_database()

    database.save_observation({"filename": "a.png", "file_size": 10, "status": "image_received"}, user_id="account-a")
    database.save_observation({"filename": "b.png", "file_size": 20, "status": "image_received"}, user_id="account-b")
    task_a = {"task": "Account A task", "task_key": "same-key", "created_at": "2026-11-14T10:00:00"}
    task_b = {"task": "Account B task", "task_key": "same-key", "created_at": "2026-11-14T10:01:00"}
    database.save_task_state(task_a, user_id="account-a")
    database.save_task_state(task_b, user_id="account-b")

    assert [item["filename"] for item in database.get_recent_observations(user_id="account-a")] == ["a.png"]
    assert [item["filename"] for item in database.get_recent_observations(user_id="account-b")] == ["b.png"]
    assert database.get_active_task(user_id="account-a")["task"] == "Account A task"
    assert database.get_active_task(user_id="account-b")["task"] == "Account B task"
    assert database.get_active_task() is None


def test_screen_pipelines_keep_live_context_separate_per_account(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "screen-ai.sqlite3")
    first = ScreenPipeline(user_id="account-a")
    second = ScreenPipeline(user_id="account-b")

    first.context.add_observation({"filename": "a.png"})
    first.start_task("Private A workflow")

    assert first.context.get_recent_observations()
    assert second.context.get_recent_observations() == []
    assert first.task.get_task_state()["task"] == "Private A workflow"
    assert second.task.get_task_state()["task"] is None


def test_companion_memory_deletion_cannot_cross_account_boundary(tmp_path, monkeypatch):
    import companion_brain

    monkeypatch.setattr(companion_brain, "MEMORY_DB", tmp_path / "memories.sqlite3")
    companion_brain._save_memory_candidates([{
        "key": "project", "category": "project", "content": "Account A project",
    }], user_id="account-a")
    companion_brain._save_memory_candidates([{
        "key": "project", "category": "project", "content": "Account B project",
    }], user_id="account-b")
    memory_a = companion_brain.get_companion_memories(user_id="account-a")[0]
    memory_b = companion_brain.get_companion_memories(user_id="account-b")[0]

    assert companion_brain.delete_companion_memory(memory_a["id"], user_id="account-b") is False
    assert companion_brain.get_companion_memories(user_id="account-a")[0]["content"] == "Account A project"
    assert companion_brain.get_companion_memories(user_id="account-b")[0]["id"] == memory_b["id"]
    assert companion_brain.delete_companion_memory(memory_a["id"], user_id="account-a") is True


def test_existing_legacy_sqlite_tables_receive_additive_owner_columns(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, filename TEXT NOT NULL, file_size INTEGER NOT NULL, status TEXT NOT NULL)")
        db.execute("CREATE TABLE interactions (id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, screens_considered INTEGER NOT NULL DEFAULT 0, task_json TEXT NOT NULL DEFAULT '{}')")
        db.execute("CREATE TABLE task_events (id INTEGER PRIMARY KEY, task_key TEXT NOT NULL, task_name TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT, updated_at TEXT NOT NULL, current_step TEXT, next_step TEXT, completed_steps_json TEXT NOT NULL DEFAULT '[]')")
        db.execute("INSERT INTO interactions (timestamp, question, answer) VALUES ('2026-01-01', 'Old local question', 'Old local answer')")
    monkeypatch.setattr(database, "DATABASE_PATH", path)

    database.initialize_database()

    with sqlite3.connect(path) as db:
        for table in ("observations", "interactions", "task_events"):
            columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            assert "user_id" in columns
        assert db.execute("SELECT user_id, question FROM interactions").fetchone() == (None, "Old local question")


def test_multi_tenant_legacy_routes_require_a_valid_account_session(monkeypatch):
    import main

    monkeypatch.setenv("VOSI_MULTI_TENANT", "true")
    with pytest.raises(HTTPException) as missing:
        main._account_user_id(None)
    assert missing.value.status_code == 401

    monkeypatch.setattr(main.identity_api.store, "authenticate", lambda token: {"user_id": "account-a"})
    assert main._account_user_id("valid-session") == "account-a"
    with pytest.raises(HTTPException) as blocked:
        main._require_single_tenant_local_integration()
    assert blocked.value.status_code == 503


def test_legacy_history_route_reads_only_the_authenticated_account(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "screen-ai.sqlite3")
    database.initialize_database()
    database.save_interaction("A private question", "A answer", user_id="account-a")
    database.save_interaction("B private question", "B answer", user_id="account-b")
    monkeypatch.setattr(main.identity_api.store, "authenticate", lambda token: {"user_id": token})

    response = main.get_history(limit=20, x_vosi_account_token="account-a")
    assert [item["question"] for item in response["interactions"]] == ["A private question"]


def test_production_readiness_rejects_wildcard_cors_for_multi_tenant(monkeypatch):
    import main

    monkeypatch.setenv("VOSI_MULTI_TENANT", "true")
    monkeypatch.setenv("VOSI_AGENT_TOKEN", "configured-agent-token")
    monkeypatch.setenv("VOSI_IDENTITY_CHALLENGE_SECRET", "x" * 40)
    monkeypatch.setenv("VOSI_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("VOSI_SMTP_USERNAME", "user")
    monkeypatch.setenv("VOSI_SMTP_PASSWORD", "secret")
    monkeypatch.setenv("VOSI_SMTP_FROM", "noreply@example.com")
    monkeypatch.setattr(main, "_cors_origins", ["*"])

    with pytest.raises(HTTPException) as blocked:
        main.health_ready()
    assert blocked.value.status_code == 503
    assert "VOSI_CORS_ORIGINS" in blocked.value.detail
