import account_companion_store as turns
import companion_brain as brain


def test_conversation_turns_are_isolated_by_account(tmp_path, monkeypatch):
    monkeypatch.setattr(turns, "DB_PATH", tmp_path / "vosi.db")
    turns.save_turn("user-a", "A question", "A answer")
    turns.save_turn("user-b", "B question", "B answer")

    assert [row["question"] for row in turns.get_recent_turns("user-a")] == ["A question"]
    assert [row["question"] for row in turns.get_recent_turns("user-b")] == ["B question"]
    assert turns.get_recent_turns("user-c") == []


def test_companion_memories_are_isolated_by_account(tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "MEMORY_DB", tmp_path / "memory.db")
    candidates_a = [{"key": "favorite_editor", "category": "preference", "content": "Uses editor A"}]
    candidates_b = [{"key": "favorite_editor", "category": "preference", "content": "Uses editor B"}]

    assert brain._save_memory_candidates(candidates_a, user_id="user-a") == 1
    assert brain._save_memory_candidates(candidates_b, user_id="user-b") == 1

    memories_a = brain.get_companion_memories(user_id="user-a")
    memories_b = brain.get_companion_memories(user_id="user-b")
    assert [item["content"] for item in memories_a] == ["Uses editor A"]
    assert [item["content"] for item in memories_b] == ["Uses editor B"]
    assert brain.get_companion_memories(user_id="user-c") == []
