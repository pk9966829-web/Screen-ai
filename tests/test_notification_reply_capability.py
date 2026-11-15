import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from companion_brain import IMPLEMENTED_EXECUTORS, _validate_plan_arguments
from agent_runtime import AgentRuntime


def test_generic_notification_reply_is_android_only_and_approval_gated(tmp_path):
    runtime = AgentRuntime(tmp_path / "runtime.sqlite3")
    capability = next(item for item in runtime.list_capabilities() if item["name"] == "phone.notification.quick_reply")
    assert capability["platforms"] == ["android"]
    assert capability["risk"] == "high"
    assert capability["requires_approval"] is True
    assert "phone.notification.quick_reply" in IMPLEMENTED_EXECUTORS["android"]
    assert "phone.notification.quick_reply" not in IMPLEMENTED_EXECUTORS["desktop"]


def test_generic_notification_reply_requires_valid_target_package():
    valid = {
        "notification_key": "active-notification-key",
        "package_name": "com.example.messaging",
        "sender": "A contact",
        "message": "I will call you later.",
    }
    assert _validate_plan_arguments("phone.notification.quick_reply", valid)
    invalid = {**valid, "package_name": "com.example;malicious"}
    assert not _validate_plan_arguments("phone.notification.quick_reply", invalid)
    invalid = {**valid, "message": " "}
    assert not _validate_plan_arguments("phone.notification.quick_reply", invalid)
