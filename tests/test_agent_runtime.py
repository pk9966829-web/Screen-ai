import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from agent_runtime import AgentRuntime, AgentRuntimeError


def runtime(tmp_path):
    return AgentRuntime(tmp_path / "agent.sqlite3")


def step(capability="browser.search_products", platform="browser", **extra):
    return {
        "step_id": "search",
        "capability": capability,
        "target_platform": platform,
        "title": "Search for relevant products",
        "arguments": {"query": "body spray under 1000"},
        **extra,
    }


def test_low_risk_task_can_be_claimed_only_with_granted_capability(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Find a body spray", [step()])
    assert task["state"] == "planned"

    assert agent.claim_next_step(task["task_id"], "chrome-1", set()) is None
    claimed = agent.claim_next_step(task["task_id"], "chrome-1", {"browser.search_products"})
    assert claimed["state"] == "running"
    assert claimed["claimed_by"] == "chrome-1"


def test_external_action_waits_for_explicit_approval(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task(
        "Call my contact",
        [step("phone.call", "android", arguments={"number": "+910000000000"})],
    )
    assert task["state"] == "awaiting_approval"
    assert task["steps"][0]["state"] == "awaiting_approval"
    assert agent.claim_next_step(task["task_id"], "phone-1", {"phone.call"}) is None

    approved = agent.approve_step(task["task_id"], "search")
    assert approved["state"] == "ready"
    assert approved["steps"][0]["approved_at"]


def test_unknown_capability_and_wrong_platform_are_rejected(tmp_path):
    agent = runtime(tmp_path)
    with pytest.raises(AgentRuntimeError, match="Unsupported capability"):
        agent.create_task("Do anything", [step("system.run_shell", "desktop")])
    with pytest.raises(AgentRuntimeError, match="not available"):
        agent.create_task("Search", [step("browser.search_products", "android")])


def test_step_is_not_completed_without_verified_receipt(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search", [step()])
    agent.claim_next_step(task["task_id"], "chrome-1", {"browser.search_products"})

    result = agent.record_step_result(
        task["task_id"], "search", "chrome-1",
        success=True, verified=False, receipt={"status": "queued"},
    )
    assert result["state"] == "failed"
    assert result["steps"][0]["state"] == "failed"


def test_only_claiming_device_can_submit_execution_receipt(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search", [step()])
    agent.claim_next_step(task["task_id"], "chrome-1", {"browser.search_products"})

    with pytest.raises(AgentRuntimeError, match="active execution claim"):
        agent.record_step_result(
            task["task_id"], "search", "android-1",
            success=True, verified=True, receipt={"status": "done"},
        )


def test_idempotency_key_prevents_duplicate_task_creation(tmp_path):
    agent = runtime(tmp_path)
    first = agent.create_task("Search", [step()], idempotency_key="request-123")
    second = agent.create_task("Search again", [step()], idempotency_key="request-123")
    assert first["task_id"] == second["task_id"]
    assert second["goal"] == "Search"


def test_task_survives_runtime_restart(tmp_path):
    first_runtime = runtime(tmp_path)
    task = first_runtime.create_task("Search", [step()])
    restarted_runtime = runtime(tmp_path)
    restored = restarted_runtime.get_task(task["task_id"])
    assert restored["goal"] == "Search"
    assert restored["steps"][0]["capability"] == "browser.search_products"


def test_verified_receipt_completes_task(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search", [step()])
    agent.claim_next_step(task["task_id"], "chrome-1", {"browser.search_products"})
    result = agent.record_step_result(
        task["task_id"], "search", "chrome-1",
        success=True, verified=True,
        receipt={"status": "completed", "observed_result_count": 8},
    )
    assert result["state"] == "completed"
    assert result["steps"][0]["receipt"]["status"] == "completed"
