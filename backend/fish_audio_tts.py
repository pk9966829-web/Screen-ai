"""Fish Audio text-to-speech adapter for the CHERRY Exotel voice bridge.

The adapter returns headerless mono PCM16 so the bridge can packetize it directly.
It is opt-in; GPT-Live remains the default and fallback voice provider.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from voice_expression import apply_fish_emotion_cues

FISH_TTS_URL = "https://api.fish.audio/v1/tts"
DEFAULT_SAMPLE_RATE = 16000
MAX_TTS_TEXT_CHARS = 4000
MAX_PCM_BYTES = 2_000_000


def fish_tts_configured() -> bool:
    """True only when Fish Audio is explicitly selected and fully configured."""
    provider = os.getenv("CHERRY_TTS_PROVIDER", "gpt-live").strip().lower()
    return bool(
        provider == "fish"
        and os.getenv("CHERRY_FISH_API_KEY", "").strip()
        and os.getenv("CHERRY_FISH_VOICE_ID", "").strip()
    )


def synthesize_pcm(text: str, caller_context: str = "") -> bytes:
    """Synthesize text as raw mono PCM16 at the configured bridge sample rate."""
    text = (text or "").strip()
    if not text:
        return b""
    if len(text) > MAX_TTS_TEXT_CHARS:
        text = text[:MAX_TTS_TEXT_CHARS]
    text = apply_fish_emotion_cues(text, caller_context)

    api_key = os.getenv("CHERRY_FISH_API_KEY", "").strip()
    voice_id = os.getenv("CHERRY_FISH_VOICE_ID", "").strip()
    if not api_key or not voice_id:
        raise RuntimeError("Fish Audio TTS is not configured.")

    try:
        sample_rate = int(os.getenv("CHERRY_FISH_SAMPLE_RATE", str(DEFAULT_SAMPLE_RATE)))
    except ValueError as exc:
        raise RuntimeError("Invalid Fish Audio sample rate configuration.") from exc
    if sample_rate != DEFAULT_SAMPLE_RATE:
        raise RuntimeError("Fish Audio sample rate must match the Exotel bridge (16000 Hz).")

    model = os.getenv("CHERRY_FISH_MODEL", "s2.1-pro").strip() or "s2.1-pro"
    payload = json.dumps({
        "text": text,
        "reference_id": voice_id,
        "format": "pcm",
        "sample_rate": sample_rate,
        "latency": "low",
    }).encode("utf-8")
    request = Request(
        FISH_TTS_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "model": model,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            audio = response.read(MAX_PCM_BYTES + 1)
    except HTTPError as exc:
        # Do not include response text: it could echo request data or secrets.
        raise RuntimeError(f"Fish Audio TTS request failed (HTTP {exc.code}).") from None
    except (URLError, TimeoutError, OSError):
        raise RuntimeError("Fish Audio TTS request failed.") from None

    if not audio or len(audio) > MAX_PCM_BYTES or len(audio) % 2:
        raise RuntimeError("Fish Audio returned an invalid PCM16 audio payload.")
    return audio
