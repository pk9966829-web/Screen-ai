"""Opt-in Exotel PSTN voice bridge for the CHERRY AI call receptionist.

The module does not record calls. It streams live call audio to GPT-Live and returns
generated speech to Exotel. It remains disabled until explicit server configuration.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
import json
import os
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/call-receptionist", tags=["CHERRY AI Call Receptionist"])
EXOTEL_SAMPLE_RATE = 16000
EXOTEL_FRAME_BYTES = 3200  # 100 ms of mono PCM16 at 16 kHz.
MAX_MEDIA_BYTES = 128_000


def _enabled() -> bool:
    return os.getenv("CHERRY_CALL_RECEPTIONIST_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def _configuration() -> tuple[str, str, str, str, str]:
    return (
        os.getenv("CHERRY_EXOTEL_STREAM_USER", "").strip(),
        os.getenv("CHERRY_EXOTEL_STREAM_PASSWORD", "").strip(),
        os.getenv("CHERRY_LIVE_API_KEY", "").strip(),
        os.getenv("CHERRY_LIVE_MODEL", "gpt-live-1.1").strip(),
        os.getenv("CHERRY_LIVE_VOICE", "marin").strip(),
    )


def _configured() -> bool:
    username, password, api_key, model, voice = _configuration()
    return _enabled() and bool(username and len(password) >= 32 and api_key and model and voice)


def _authorized_websocket(websocket: WebSocket) -> bool:
    username, password, _, _, _ = _configuration()
    supplied = websocket.headers.get("authorization", "")
    expected = "Basic " + base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return bool(username and password) and hmac.compare_digest(supplied, expected)


def _exotel_stream_id(message: dict[str, Any]) -> str:
    return str(message.get("stream_sid") or message.get("stream sid") or "")


def decode_exotel_media(message: dict[str, Any]) -> bytes:
    media = message.get("media")
    if not isinstance(media, dict):
        return b""
    payload = media.get("payload")
    if not isinstance(payload, str) or not payload or len(payload) > 4 * MAX_MEDIA_BYTES // 3 + 8:
        return b""
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return b""
    if not decoded or len(decoded) > MAX_MEDIA_BYTES or len(decoded) % 2:
        return b""
    return decoded


def exotel_media_messages(stream_sid: str, pcm: bytes, first_chunk: int = 1) -> list[dict[str, Any]]:
    """Split PCM into Exotel's documented 100 ms minimum chunks."""
    if not stream_sid or not pcm or len(pcm) % 2:
        return []
    messages = []
    offset = 0
    chunk = first_chunk
    while len(pcm) - offset >= EXOTEL_FRAME_BYTES:
        payload = pcm[offset:offset + EXOTEL_FRAME_BYTES]
        messages.append({
            "event": "media",
            "sequence_number": chunk,
            "stream_sid": stream_sid,
            "media": {
                "chunk": chunk,
                "timestamp": int((chunk - first_chunk) * 100),
                "payload": base64.b64encode(payload).decode("ascii"),
            },
        })
        offset += EXOTEL_FRAME_BYTES
        chunk += 1
    return messages


def live_session_start(model: str, voice: str, caller: str, destination: str) -> dict[str, Any]:
    caller_label = caller if caller else "unavailable"
    destination_label = destination if destination else "unavailable"
    instructions = (
        "You are CHERRY AI, an AI receptionist answering a call forwarded to the owner's "
        "receptionist line because the owner could not take the call. Identify yourself clearly "
        "as an AI assistant; never pretend to be the owner or a human. Start with a brief, warm "
        "greeting, then explain that the caller's speech is processed by an AI service to take "
        "a message for the owner, and ask whether they consent to continue. Do not collect a "
        "message or personal details unless they agree. If they decline, thank them and politely "
        "end the interaction. After consent, ask the caller's name and what they are calling "
        "about. Ask for a callback number only if it is not available or they offer a different "
        "one. Clarify urgency and the best time to call back. Be concise and polite. Do not promise that the owner will "
        "call, do not claim a message was delivered, and do not take payments or sensitive "
        "credentials. Caller ID supplied by the phone network: " + caller_label +
        ". Called number: " + destination_label +
        ". The caller may withhold or spoof caller ID; ask them to confirm details."
    )
    return {
        "type": "session.start",
        "event_id": "cherry_call_start",
        "session": {
            "model": model,
            "instructions": instructions,
            "audio": {
                "format": {"type": "audio/pcm", "rate": EXOTEL_SAMPLE_RATE},
                "output": {"voice": voice},
            },
            "delegation": {"type": "client"},
        },
    }


@router.get("/status")
def receptionist_status():
    username, password, api_key, model, voice = _configuration()
    return {
        "success": True,
        "enabled": _enabled(),
        "configured": _configured(),
        "telephony_provider": "exotel",
        "voice_provider": "gpt-live",
        "missing": [
            name for name, ready in (
                ("CHERRY_CALL_RECEPTIONIST_ENABLED", _enabled()),
                ("CHERRY_EXOTEL_STREAM_USER", bool(username)),
                ("CHERRY_EXOTEL_STREAM_PASSWORD (32+ characters)", len(password) >= 32),
                ("CHERRY_LIVE_API_KEY", bool(api_key)),
                ("CHERRY_LIVE_MODEL", bool(model)),
                ("CHERRY_LIVE_VOICE", bool(voice)),
            ) if not ready
        ],
        "call_recording": False,
    }


@router.websocket("/exotel/media")
async def exotel_media_bridge(websocket: WebSocket):
    _, _, api_key, model, voice = _configuration()
    if not _configured() or not _authorized_websocket(websocket):
        await websocket.close(code=4403)
        return

    await websocket.accept()
    try:
        # Exotel sends connected and then start before media. Do not open a model
        # session until the call metadata and configured media format are known.
        start: dict[str, Any] | None = None
        for _ in range(3):
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            event = json.loads(raw)
            if event.get("event") == "stop":
                return
            if event.get("event") == "start":
                start = event.get("start") if isinstance(event.get("start"), dict) else {}
                stream_sid = _exotel_stream_id(event) or _exotel_stream_id(start)
                break
        if start is None:
            await websocket.close(code=4400)
            return
        media_format = start.get("media_format") or start.get("media format") or {}
        sample_rate = int(media_format.get("sample_rate") or media_format.get("sample rate") or 0)
        encoding = str(media_format.get("encoding") or "").lower()
        if sample_rate != EXOTEL_SAMPLE_RATE or encoding not in {"", "base64", "raw", "slin"}:
            await websocket.close(code=4406)
            return

        # Imported lazily so backend text/API features work without the optional
        # telephony dependency being loaded at module import time.
        from websockets.asyncio.client import connect as websocket_connect

        async with websocket_connect(
            "wss://api.openai.com/v1/live/sessions",
            additional_headers={"Authorization": f"Bearer {api_key}"},
            max_size=2_000_000,
            open_timeout=15,
            close_timeout=3,
        ) as live:
            caller = str(start.get("from") or start.get("callfrom") or "")
            destination = str(start.get("to") or start.get("callto") or "")
            await live.send(json.dumps(live_session_start(model, voice, caller, destination)))
            ready = False
            for _ in range(12):
                event = json.loads(await asyncio.wait_for(live.recv(), timeout=15))
                if event.get("type") == "session.started":
                    ready = True
                    break
                if event.get("type") == "error":
                    await websocket.close(code=1011)
                    return
            if not ready:
                await websocket.close(code=1011)
                return

            if not stream_sid:
                stream_sid = str(start.get("stream_sid") or start.get("stream sid") or "")
            if not stream_sid:
                await websocket.close(code=4400)
                return

            await live.send(json.dumps({"type": "response.create"}))
            output_buffer = bytearray()
            sequence = 1

            async def caller_to_model():
                nonlocal stream_sid
                while True:
                    incoming = json.loads(await websocket.receive_text())
                    event_type = incoming.get("event")
                    if event_type == "stop":
                        return
                    if event_type == "media":
                        audio = decode_exotel_media(incoming)
                        if audio:
                            await live.send(json.dumps({
                                "type": "session.input_audio.append",
                                "audio": base64.b64encode(audio).decode("ascii"),
                            }))
                    elif event_type == "dtmf":
                        # Do not interpret keypad input as authorization or payment.
                        continue

            async def model_to_caller():
                nonlocal sequence
                while True:
                    message = json.loads(await live.recv())
                    event_type = message.get("type")
                    if event_type == "session.output_audio.delta":
                        try:
                            output_buffer.extend(base64.b64decode(message.get("delta", ""), validate=True))
                        except (binascii.Error, ValueError):
                            continue
                        while len(output_buffer) >= EXOTEL_FRAME_BYTES:
                            chunk = bytes(output_buffer[:EXOTEL_FRAME_BYTES])
                            del output_buffer[:EXOTEL_FRAME_BYTES]
                            outgoing = {
                                "event": "media",
                                "sequence_number": sequence,
                                "stream_sid": stream_sid,
                                "media": {
                                    "chunk": sequence,
                                    "timestamp": (sequence - 1) * 100,
                                    "payload": base64.b64encode(chunk).decode("ascii"),
                                },
                            }
                            await websocket.send_text(json.dumps(outgoing))
                            sequence += 1
                    elif event_type == "session.input_audio.speech_started":
                        await websocket.send_text(json.dumps({"event": "clear", "stream_sid": stream_sid}))
                    elif event_type in {"session.closed", "error"}:
                        return

            inbound = asyncio.create_task(caller_to_model())
            outbound = asyncio.create_task(model_to_caller())
            done, pending = await asyncio.wait({inbound, outbound}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exception = task.exception()
                if exception:
                    raise exception
            if output_buffer:
                # Exotel's voicebot stream expects at least 100 ms (3.2 KB) per frame.
                output_buffer.extend(b"\x00" * (EXOTEL_FRAME_BYTES - len(output_buffer) % EXOTEL_FRAME_BYTES))
                while output_buffer:
                    chunk = bytes(output_buffer[:EXOTEL_FRAME_BYTES])
                    del output_buffer[:EXOTEL_FRAME_BYTES]
                    await websocket.send_text(json.dumps({
                        "event": "media", "sequence_number": sequence, "stream_sid": stream_sid,
                        "media": {"chunk": sequence, "timestamp": (sequence - 1) * 100,
                                  "payload": base64.b64encode(chunk).decode("ascii")},
                    }))
                    sequence += 1
    except (WebSocketDisconnect, asyncio.TimeoutError, json.JSONDecodeError, ValueError):
        return
    except Exception:
        # Do not leak provider keys, caller audio, or exception text to the phone.
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
