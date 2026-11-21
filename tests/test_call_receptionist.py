import base64
import os
import sys
import pytest
from starlette.websockets import WebSocketDisconnect
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import call_receptionist


def test_status_does_not_expose_secrets(monkeypatch):
    monkeypatch.setenv("CHERRY_CALL_RECEPTIONIST_ENABLED", "true")
    monkeypatch.setenv("CHERRY_EXOTEL_STREAM_USER", "cherry")
    monkeypatch.setenv("CHERRY_EXOTEL_STREAM_PASSWORD", "p" * 40)
    monkeypatch.setenv("CHERRY_LIVE_API_KEY", "private-api-key")
    result = call_receptionist.receptionist_status()
    assert result["configured"] is True
    assert result["call_recording"] is False
    assert "private-api-key" not in str(result)
    assert "p" * 40 not in str(result)


def test_status_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CHERRY_CALL_RECEPTIONIST_ENABLED", raising=False)
    monkeypatch.delenv("CHERRY_EXOTEL_STREAM_USER", raising=False)
    monkeypatch.delenv("CHERRY_EXOTEL_STREAM_PASSWORD", raising=False)
    monkeypatch.delenv("CHERRY_LIVE_API_KEY", raising=False)
    assert call_receptionist.receptionist_status()["configured"] is False


def test_exotel_media_parser_rejects_invalid_and_oversized_payloads():
    assert call_receptionist.decode_exotel_media({"media": {"payload": "not base64!"}}) == b""
    assert call_receptionist.decode_exotel_media({"media": {"payload": base64.b64encode(b"x").decode()}}) == b""
    assert call_receptionist.decode_exotel_media({"media": {"payload": base64.b64encode(b"x" * 130000).decode()}}) == b""


def test_exotel_media_parser_accepts_even_pcm16_bytes():
    payload = base64.b64encode(b"\x01\x00" * 160).decode()
    assert call_receptionist.decode_exotel_media({"media": {"payload": payload}}) == b"\x01\x00" * 160


def test_output_chunks_follow_exotel_frame_size():
    pcm = b"\x00\x00" * 1600
    messages = call_receptionist.exotel_media_messages("stream-1", pcm)
    assert len(messages) == 1
    assert len(base64.b64decode(messages[0]["media"]["payload"])) == 3200
    assert messages[0]["stream_sid"] == "stream-1"


def test_live_prompt_identifies_ai_and_gathers_caller_details():
    session = call_receptionist.live_session_start("gpt-live-1.1", "marin", "+911234567890", "+918765432100")
    instructions = session["session"]["instructions"]
    assert "Identify yourself clearly as an AI assistant" in instructions
    assert "pressed 1 to consent" in instructions
    assert "ask the caller's name" in instructions
    assert "do not promise" in instructions.lower()
    assert session["session"]["audio"]["format"]["rate"] == 16000


def make_client():
    app = FastAPI()
    app.include_router(call_receptionist.router)
    return TestClient(app)


def test_websocket_rejects_when_feature_disabled(monkeypatch):
    monkeypatch.delenv("CHERRY_CALL_RECEPTIONIST_ENABLED", raising=False)
    with pytest.raises(WebSocketDisconnect):
        with make_client().websocket_connect("/call-receptionist/exotel/media"):
            pass


def test_caller_consent_requires_exotel_flow_grant():
    assert call_receptionist.has_caller_consent({"custom_parameters": {"consent": "granted"}})
    assert call_receptionist.has_caller_consent({"custom parameters": {"consent": "GRANTED"}})
    assert not call_receptionist.has_caller_consent({"custom_parameters": {"consent": "denied"}})
    assert not call_receptionist.has_caller_consent({})
