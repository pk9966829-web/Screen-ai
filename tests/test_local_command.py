import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
from local_command import route_local_command, _calc

def test_youtube_search_routed_locally(monkeypatch):
    opened = []
    monkeypatch.setattr("local_command._open_target", lambda url: opened.append(url) or True)
    result = route_local_command("Search YouTube for best chest workout")
    assert result["local_command"] is True and result["success"] is True
    assert "youtube.com/results" in opened[0] and "chest" in opened[0]

def test_compound_open_youtube_and_search(monkeypatch):
    opened = []
    monkeypatch.setattr("local_command._open_target", lambda url: opened.append(url) or True)
    result = route_local_command("open YouTube and search for xyz song")
    assert result["local_command"] is True and result["success"] is True
    assert "youtube.com/results" in opened[0] and "xyz+song" in opened[0]


def test_open_whitelisted_app(monkeypatch):
    monkeypatch.setattr("local_command._open_target", lambda target: target == "notepad")
    result = route_local_command("open notepad")
    assert result["success"] and result["local_command"]

def test_calculator_safe_expression():
    assert _calc("12 * (4 + 3)") == 84

def test_calculator_rejects_code():
    import pytest
    with pytest.raises(ValueError):
        _calc("__import__('os').system('whoami')")

def test_unknown_message_falls_through():
    assert route_local_command("Explain quantum computing") is None

def test_shutdown_requires_confirmation():
    result = route_local_command("shutdown my pc")
    assert result["requires_confirmation"] is True

def test_timer_schedules_real_windows_timer(monkeypatch):
    import datetime
    scheduled = []
    monkeypatch.setattr("local_command.platform.system", lambda: "Windows")
    monkeypatch.setattr("local_command._schedule_windows_alarm", lambda target, label: scheduled.append((target, label)) or (True, "scheduled"))
    result = route_local_command("set timer for 20 minutes")
    assert result["success"] and result["local_command"]
    assert "Timer set for 20 minutes" in result["understanding"]
    assert scheduled[0][1] == "Timer"
    assert 1190 <= (scheduled[0][0] - datetime.datetime.now().astimezone()).total_seconds() <= 1210


def test_alarm_5pm_schedules_local_alarm(monkeypatch):
    scheduled = []
    monkeypatch.setattr("local_command.platform.system", lambda: "Windows")
    monkeypatch.setattr("local_command._schedule_windows_alarm", lambda target, label: scheduled.append((target, label)) or (True, "scheduled"))
    result = route_local_command("set alarm for 5 PM")
    assert result["success"] and result["local_command"]
    assert scheduled[0][0].hour == 17 and scheduled[0][0].minute == 0
    assert scheduled[0][1] == "Alarm"


def test_alarm_without_meridiem_asks_for_am_or_pm():
    result = route_local_command("set alarm for 5")
    assert result["success"] is False
    assert "AM or PM" in result["understanding"]


def test_windows_task_scheduler_alarm_command_is_encoded_and_shell_safe(monkeypatch):
    import base64
    import datetime
    from types import SimpleNamespace
    captured = []
    monkeypatch.setattr("local_command.platform.system", lambda: "Windows")
    monkeypatch.setattr("local_command.subprocess.run", lambda args, **kwargs: captured.append((args, kwargs)) or SimpleNamespace(returncode=0, stdout="", stderr=""))
    target = datetime.datetime.now().astimezone() + datetime.timedelta(minutes=5)
    ok, detail = __import__("local_command")._schedule_windows_alarm(target, "Timer")
    assert ok and "Task Scheduler" in detail
    args, kwargs = captured[0]
    assert kwargs["shell"] is not True
    task_action = args[args.index("/TR") + 1]
    encoded = task_action.split("-EncodedCommand ", 1)[1]
    script = base64.b64decode(encoded).decode("utf-16le")
    assert "Start-Sleep" in script and "CHERRY AI" in script
    assert args[args.index("/SD") + 1] == target.replace(second=0, microsecond=0).strftime("%x")
