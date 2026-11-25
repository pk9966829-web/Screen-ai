import json
import sys
from pathlib import Path
from urllib.error import HTTPError

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import fish_audio_tts


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


def test_fish_tts_is_opt_in_and_requires_key_and_voice(monkeypatch):
    monkeypatch.delenv("CHERRY_TTS_PROVIDER", raising=False)
    monkeypatch.setenv("CHERRY_FISH_API_KEY", "secret")
    monkeypatch.setenv("CHERRY_FISH_VOICE_ID", "voice-1")
    assert fish_audio_tts.fish_tts_configured() is False

    monkeypatch.setenv("CHERRY_TTS_PROVIDER", "fish")
    assert fish_audio_tts.fish_tts_configured() is True
    monkeypatch.delenv("CHERRY_FISH_VOICE_ID")
    assert fish_audio_tts.fish_tts_configured() is False


def test_fish_tts_requests_raw_pcm16_at_16khz(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_API_KEY", "test-key")
    monkeypatch.setenv("CHERRY_FISH_VOICE_ID", "voice-123")
    monkeypatch.setenv("CHERRY_FISH_EMOTION_TAGS", "true")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse(b"\x00\x00" * 160)

    monkeypatch.setattr(fish_audio_tts, "urlopen", fake_urlopen)
    audio = fish_audio_tts.synthesize_pcm("Hello caller.")
    assert len(audio) == 320
    assert captured["url"] == "https://api.fish.audio/v1/tts"
    assert captured["payload"]["text"] == "[warm and professional] Hello caller."
    assert captured["payload"]["format"] == "pcm"
    assert captured["payload"]["sample_rate"] == 16000
    assert captured["payload"]["reference_id"] == "voice-123"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["timeout"] == 15


def test_fish_tts_rejects_mismatched_sample_rate(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_API_KEY", "test-key")
    monkeypatch.setenv("CHERRY_FISH_VOICE_ID", "voice-123")
    monkeypatch.setenv("CHERRY_FISH_SAMPLE_RATE", "8000")
    try:
        fish_audio_tts.synthesize_pcm("Hello.")
    except RuntimeError as exc:
        assert "16000 Hz" in str(exc)
    else:
        raise AssertionError("Expected sample-rate validation error")


def test_fish_tts_rejects_odd_length_pcm(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_API_KEY", "test-key")
    monkeypatch.setenv("CHERRY_FISH_VOICE_ID", "voice-123")
    monkeypatch.setattr(fish_audio_tts, "urlopen", lambda *args, **kwargs: FakeResponse(b"\x00"))
    try:
        fish_audio_tts.synthesize_pcm("Hello.")
    except RuntimeError as exc:
        assert "invalid PCM16" in str(exc)
    else:
        raise AssertionError("Expected invalid PCM16 error")


def test_fish_tts_does_not_leak_provider_error_body(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_API_KEY", "test-key")
    monkeypatch.setenv("CHERRY_FISH_VOICE_ID", "voice-123")

    def fail(*args, **kwargs):
        raise HTTPError("https://api.fish.audio/v1/tts", 401, "unauthorized", {}, None)

    monkeypatch.setattr(fish_audio_tts, "urlopen", fail)
    try:
        fish_audio_tts.synthesize_pcm("Hello.")
    except RuntimeError as exc:
        assert "401" in str(exc)
        assert "test-key" not in str(exc)
    else:
        raise AssertionError("Expected Fish Audio HTTP error")
