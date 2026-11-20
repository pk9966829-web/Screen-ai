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
