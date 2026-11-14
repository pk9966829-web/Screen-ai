import sys
from pathlib import Path

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
