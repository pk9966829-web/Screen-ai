import sqlite3
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


def test_browser_inspection_is_registered_as_permissioned_low_risk_capability(tmp_path):
    agent = runtime(tmp_path)
    capabilities = {item["name"]: item for item in agent.list_capabilities()}
    inspection = capabilities["browser.inspect_page"]
    assert inspection["risk"] == "low"
    assert inspection["requires_permission"] is True
    assert inspection["requires_approval"] is False
    task = agent.create_task("Inspect the current webpage", [step("browser.inspect_page", "browser")])
    assert task["state"] == "planned"
    assert agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.inspect_page"})["state"] == "running"


def test_browser_interaction_is_registered_and_permissioned(tmp_path):
    agent = runtime(tmp_path)
    capabilities = {item["name"]: item for item in agent.list_capabilities()}
    interaction = capabilities["browser.interact"]
    assert interaction["risk"] == "low"
    assert interaction["requires_permission"] is True
    assert interaction["requires_approval"] is False
    task = agent.create_task("Interact with a webpage", [step("browser.interact", "browser", arguments={"action":"click","target":"Search"})])
    assert task["state"] == "planned"
    claimed = agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.interact"})
    assert claimed["state"] == "running"


def test_low_risk_task_can_be_claimed_only_with_granted_capability(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Find a body spray", [step()])
    assert task["state"] == "planned"

    assert agent.claim_next_step(task["task_id"], "chrome-1", "browser", set()) is None
    claimed = agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.search_products"})
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
    assert agent.claim_next_step(task["task_id"], "phone-1", "android", {"phone.call"}) is None

    approved = agent.approve_step(task["task_id"], "search")
    assert approved["state"] == "ready"
    assert approved["steps"][0]["approved_at"]


def test_device_cannot_claim_a_capability_for_another_platform(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search", [step()])
    assert agent.claim_next_step(task["task_id"], "android-1", "android", {"browser.search_products"}) is None


def test_unknown_capability_and_wrong_platform_are_rejected(tmp_path):
    agent = runtime(tmp_path)
    with pytest.raises(AgentRuntimeError, match="Unsupported capability"):
        agent.create_task("Do anything", [step("system.run_shell", "desktop")])
    with pytest.raises(AgentRuntimeError, match="not available"):
        agent.create_task("Search", [step("browser.search_products", "android")])


def test_step_is_not_completed_without_verified_receipt(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search", [step()])
    agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.search_products"})

    result = agent.record_step_result(
        task["task_id"], "search", "chrome-1",
        success=True, verified=False, receipt={"status": "queued"},
    )
    assert result["state"] == "failed"
    assert result["steps"][0]["state"] == "failed"


def test_only_claiming_device_can_submit_execution_receipt(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search", [step()])
    agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.search_products"})

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
    agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.search_products"})
    result = agent.record_step_result(
        task["task_id"], "search", "chrome-1",
        success=True, verified=True,
        receipt={"status": "completed", "observed_result_count": 8},
    )
    assert result["state"] == "completed"
    assert result["steps"][0]["receipt"]["status"] == "completed"


def test_stale_execution_claim_can_be_recovered_after_worker_crash(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Set phone volume", [step("device.volume.set", "android")])
    claimed = agent.claim_next_step(task["task_id"], "phone-1", "android", {"device.volume.set"})
    assert claimed["state"] == "running"

    with sqlite3.connect(agent.database_path) as db:
        db.execute(
            "UPDATE agent_steps SET claimed_at = ? WHERE task_id = ? AND step_id = ?",
            ("2000-01-01T00:00:00+00:00", task["task_id"], "search"),
        )

    available = agent.get_task(task["task_id"])["steps"][0]
    assert agent.is_claim_stale(available)
    recovered = agent.claim_next_step(task["task_id"], "phone-1", "android", {"device.volume.set"})
    assert recovered["state"] == "running"
    assert recovered["claimed_by"] == "phone-1"
    assert recovered["claimed_at"] != "2000-01-01T00:00:00+00:00"


def test_explicit_retry_is_bounded_for_allowlisted_idempotent_actions(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Set phone volume", [step("device.volume.set", "android")])

    first = agent.claim_next_step(task["task_id"], "phone-1", "android", {"device.volume.set"})
    assert first["attempt_count"] == 1
    assert first["max_attempts"] == 2
    retry = agent.record_step_result(
        task["task_id"], "search", "phone-1",
        success=False, verified=False, error="Temporary device service error.",
        retryable=True,
    )
    assert retry["state"] == "ready"
    assert retry["steps"][0]["state"] == "pending"
    assert retry["steps"][0]["attempt_count"] == 1

    second = agent.claim_next_step(task["task_id"], "phone-1", "android", {"device.volume.set"})
    assert second["attempt_count"] == 2
    exhausted = agent.record_step_result(
        task["task_id"], "search", "phone-1",
        success=False, verified=False, error="The retry also failed.",
        retryable=True,
    )
    assert exhausted["state"] == "failed"
    assert exhausted["steps"][0]["state"] == "failed"
    assert exhausted["steps"][0]["attempt_count"] == 2


def test_retry_signal_cannot_repeat_non_idempotent_alarm_creation(tmp_path):
    agent = runtime(tmp_path)
    alarm = {
        "step_id": "alarm",
        "capability": "device.alarm.create",
        "target_platform": "android",
        "title": "Create alarm",
        "arguments": {"hour": 7, "minute": 30},
    }
    task = agent.create_task("Create alarm", [alarm])
    claimed = agent.claim_next_step(task["task_id"], "phone-1", "android", {"device.alarm.create"})
    assert claimed["max_attempts"] == 1
    result = agent.record_step_result(
        task["task_id"], "alarm", "phone-1",
        success=False, verified=False, error="Uncertain whether alarm was created.",
        retryable=True,
    )
    assert result["state"] == "failed"
    assert result["steps"][0]["attempt_count"] == 1


def test_retryable_failure_can_finish_on_verified_second_attempt(tmp_path):
    agent = runtime(tmp_path)
    task = agent.create_task("Search products", [step()])
    agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.search_products"})
    pending = agent.record_step_result(
        task["task_id"], "search", "chrome-1",
        success=False, verified=False, error="Temporary network error.", retryable=True,
    )
    assert pending["state"] == "ready"
    agent.claim_next_step(task["task_id"], "chrome-1", "browser", {"browser.search_products"})
    done = agent.record_step_result(
        task["task_id"], "search", "chrome-1",
        success=True, verified=True, receipt={"status": "completed", "result_count": 5},
    )
    assert done["state"] == "completed"
    assert done["steps"][0]["attempt_count"] == 2
    assert done["steps"][0]["error"] is None
