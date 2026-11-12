import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import companion_brain as brain


def test_memory_store_is_persistent_and_user_deletable(tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "MEMORY_DB", tmp_path / "memory.sqlite3")
    assert brain._save_memory_candidates([
        {"key": "preferred_tone", "category": "preference", "content": "Prefers calm, natural explanations."}
    ]) == 1
    memories = brain.get_companion_memories()
    assert memories[0]["content"] == "Prefers calm, natural explanations."
    assert brain.delete_companion_memory(memories[0]["id"]) is True
    assert brain.get_companion_memories() == []


def test_memory_store_rejects_sensitive_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "MEMORY_DB", tmp_path / "memory.sqlite3")
    assert brain._save_memory_candidates([
        {"key": "api_secret", "category": "other", "content": "My API key is secret-value"}
    ]) == 0
    assert brain.get_companion_memories() == []


def test_memory_store_rejects_sensitive_categories(tmp_path, monkeypatch):
    monkeypatch.setattr(brain, "MEMORY_DB", tmp_path / "memory.sqlite3")
    assert brain._save_memory_candidates([
        {"key": "health_fact", "category": "health", "content": "Has a chronic condition."}
    ]) == 0
    assert brain.get_companion_memories() == []


def test_model_json_decoder_accepts_fenced_and_plain_json():
    assert brain._decode_model_json('{"answer":"hello"}')["answer"] == "hello"
    assert brain._decode_model_json('```json\n{"answer":"hello"}\n```')["answer"] == "hello"


def test_task_plan_is_checked_by_runtime_allow_list(tmp_path):
    from agent_runtime import AgentRuntime
    runtime = AgentRuntime(tmp_path / "agent.sqlite3")
    plan = {
        "goal": "Search for body spray",
        "steps": [{
            "step_id": "search",
            "capability": "browser.search_products",
            "target_platform": "browser",
            "title": "Search public product listings",
            "arguments": {"query": "body spray"},
        }],
    }
    task = brain._safe_task_plan(plan, "Search body spray on Flipkart", runtime)
    assert task["state"] == "planned"
    assert task["steps"][0]["capability"] == "browser.search_products"


def test_task_plan_rejects_unsupported_capability(tmp_path):
    from agent_runtime import AgentRuntime
    runtime = AgentRuntime(tmp_path / "agent.sqlite3")
    plan = {"goal": "Do anything", "steps": [{
        "step_id": "danger", "capability": "system.run_shell",
        "target_platform": "desktop", "title": "Run arbitrary shell", "arguments": {},
    }]}
    assert brain._safe_task_plan(plan, "Do anything", runtime) is None


def test_companion_answer_uses_system_policy_and_queues_validated_task(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from agent_runtime import AgentRuntime

    monkeypatch.setattr(brain, "MEMORY_DB", tmp_path / "memory.sqlite3")
    monkeypatch.setattr(brain, "_provider_candidates", lambda: [{
        "name": "test", "api_key": "test-key",
        "base_url": "https://example.invalid/v1", "model": "test-model",
    }])

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            payload = {
                "answer": "I can search that for you.",
                "memory_candidates": [],
                "task_plan": {
                    "goal": "Search body spray listings",
                    "steps": [{
                        "step_id": "search",
                        "capability": "browser.search_products",
                        "target_platform": "browser",
                        "title": "Search public body spray listings",
                        "arguments": {"query": "body spray"},
                    }],
                },
            }
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload))
            )])

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(brain, "OpenAI", FakeClient)
    runtime = AgentRuntime(tmp_path / "agent.sqlite3")
    result = brain.answer_companion(
        "Search for body spray on Flipkart",
        recent_interactions=[],
        task_state={},
        runtime=runtime,
    )

    assert result["success"] is True
    assert result["task_plan"]["state"] == "planned"
    assert "queued" in result["understanding"]
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][1]["role"] == "user"
    assert "Search for body spray on Flipkart" in captured["messages"][1]["content"]
