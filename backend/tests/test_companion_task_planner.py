from companion_brain import IMPLEMENTED_EXECUTORS, _safe_task_plan, _validate_plan_arguments
from agent_runtime import AgentRuntime


class FakeRuntime:
    def __init__(self):
        self.created = None

    def list_capabilities(self):
        return [
            {"name": "device.volume.set", "platforms": ["android", "desktop"]},
            {"name": "device.volume.action", "platforms": ["android", "desktop"]},
            {"name": "browser.search_products", "platforms": ["browser"]},
            {"name": "device.alarm.create", "platforms": ["android", "desktop"]},
        ]

    def create_task(self, **kwargs):
        self.created = kwargs
        return {"task_id": "task-1", "state": "planned", **kwargs}


def test_volume_plan_requires_bounded_integer():
    assert _validate_plan_arguments("device.volume.set", {"volume": 70})
    assert not _validate_plan_arguments("device.volume.set", {"volume": 101})
    assert not _validate_plan_arguments("device.volume.set", {"volume": "70"})
    assert not _validate_plan_arguments("device.volume.set", {"volume": True})


def test_browser_plan_rejects_non_https_or_embedded_credentials():
    assert _validate_plan_arguments("browser.search_products", {"query": "body spray under 1000"})
    assert not _validate_plan_arguments("browser.search_products", {"query": ""})
    assert _validate_plan_arguments("browser.open_tab", {"url": "https://example.com"})
    assert not _validate_plan_arguments("browser.open_tab", {"url": "http://example.com"})
    assert not _validate_plan_arguments("browser.open_tab", {"url": "https://user:pass@example.com"})


def test_alarm_plan_requires_valid_24_hour_time():
    assert _validate_plan_arguments("device.alarm.create", {"hour": 17, "minute": 0})
    assert not _validate_plan_arguments("device.alarm.create", {"hour": 25, "minute": 0})
    assert not _validate_plan_arguments("device.alarm.create", {"hour": 17})


def test_plan_requires_a_registered_matching_executor():
    runtime = FakeRuntime()
    plan = {
        "goal": "Set phone volume to 70 percent",
        "steps": [{
            "step_id": "step-1", "capability": "device.volume.set",
            "target_platform": "android", "title": "Set media volume",
            "arguments": {"volume": 70},
        }],
    }
    devices = [{"device_id": "phone-1", "platform": "android", "status": "paired",
                "capabilities": ["device.volume.set"]}]
    result = _safe_task_plan(plan, "Set phone volume to 70 percent", runtime, devices, "phone-1")
    assert result["task_id"] == "task-1"
    assert runtime.created["origin_device_id"] == "phone-1"

    assert _safe_task_plan(plan, "Set phone volume to 70 percent", runtime, [], "phone-1") is None


def test_plan_rejects_platform_and_argument_mismatch():
    runtime = FakeRuntime()
    devices = [{"device_id": "phone-1", "platform": "android", "status": "paired",
                "capabilities": ["device.volume.set"]}]
    invalid_platform = {
        "goal": "Set volume", "steps": [{
            "capability": "device.volume.set", "target_platform": "browser",
            "title": "Set volume", "arguments": {"volume": 50},
        }],
    }
    invalid_args = {
        "goal": "Set volume", "steps": [{
            "capability": "device.volume.set", "target_platform": "android",
            "title": "Set volume", "arguments": {"volume": 500},
        }],
    }
    assert _safe_task_plan(invalid_platform, "Set volume", runtime, devices, "phone-1") is None
    assert _safe_task_plan(invalid_args, "Set volume", runtime, devices, "phone-1") is None


def test_runtime_exposes_progress_and_next_step(tmp_path):
    runtime = AgentRuntime(tmp_path / "agent.db")
    task = runtime.create_task(
        goal="Set volume then create an alarm",
        steps=[
            {"step_id": "volume", "capability": "device.volume.set",
             "target_platform": "android", "title": "Set volume", "arguments": {"volume": 50}},
            {"step_id": "alarm", "capability": "device.alarm.create",
             "target_platform": "android", "title": "Create alarm", "arguments": {"hour": 17, "minute": 0}},
        ],
    )
    assert task["progress"] == {"completed": 0, "total": 2, "percent": 0, "remaining": 2}
    assert task["next_step"]["step_id"] == "volume"
    assert task["current_step"] is None
    assert task["waiting_for_approval"] is False


def test_planner_never_queues_capabilities_without_an_installed_executor():
    assert "phone.call" not in IMPLEMENTED_EXECUTORS["android"]
    assert "phone.whatsapp.quick_reply" not in IMPLEMENTED_EXECUTORS["android"]
    assert "email.send" not in IMPLEMENTED_EXECUTORS["desktop"]
    assert "commerce.order.place" not in IMPLEMENTED_EXECUTORS["browser"]


def test_failed_step_error_is_visible_and_does_not_suggest_later_steps(tmp_path):
    runtime = AgentRuntime(tmp_path / "agent-failure.db")
    task = runtime.create_task(
        goal="Set volume then create alarm",
        steps=[
            {"step_id": "volume", "capability": "device.volume.set",
             "target_platform": "android", "title": "Set volume", "arguments": {"volume": 50}},
            {"step_id": "alarm", "capability": "device.alarm.create",
             "target_platform": "android", "title": "Create alarm", "arguments": {"hour": 17, "minute": 0}},
        ],
    )
    claimed = runtime.claim_next_step(task["task_id"], "phone-1", "android", {"device.volume.set"})
    runtime.record_step_result(task["task_id"], claimed["step_id"], "phone-1",
                                False, False, {}, "Android denied the volume change.")
    failed = runtime.get_task(task["task_id"])
    assert failed["state"] == "failed"
    assert failed["error"] == "Android denied the volume change."
    assert failed["next_step"] is None


def test_volume_actions_accept_only_supported_commands():
    assert "device.volume.action" in IMPLEMENTED_EXECUTORS["android"]
    for action in ("up", "down", "mute", "unmute"):
        assert _validate_plan_arguments("device.volume.action", {"action": action})
    assert not _validate_plan_arguments("device.volume.action", {"action": "max"})

def test_android_volume_action_plan_requires_matching_phone_capability():
    runtime = FakeRuntime()
    plan = {
        "goal": "Mute my phone",
        "steps": [{
            "step_id": "step-1", "capability": "device.volume.action",
            "target_platform": "android", "title": "Mute phone media audio",
            "arguments": {"action": "mute"},
        }],
    }
    devices = [{"device_id": "phone-1", "platform": "android", "status": "paired",
                "capabilities": ["device.volume.action"]}]
    result = _safe_task_plan(plan, "Mute my phone", runtime, devices, "phone-1")
    assert result["task_id"] == "task-1"
    assert runtime.created["steps"][0]["capability"] == "device.volume.action"
