"""Reusable speech pipeline: Whisper ASR -> Gemini response -> Coqui XTTS-v2 TTS.

Configuration is read from environment variables:
  WHISPER_MODEL=base.en
  GEMINI_API_KEY=... (or GOOGLE_API_KEY)
  GEMINI_MODEL=gemini-2.5-flash
  CHERRY_XTTS_SPEAKER_WAV=C:/path/to/reference-speaker.wav
  CHERRY_XTTS_LANGUAGE=en
  CHERRY_XTTS_MODEL=tts_models/multilingual/multi-dataset/xtts_v2

XTTS-v2 requires a reference speaker WAV. The agent reports a clear error if it
has not been configured; it never silently produces a voice with unknown identity.
Heavy models are loaded lazily and cached per VoiceAgent instance.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional


class VoiceAgentError(RuntimeError):
    """A recoverable error in one of the voice pipeline stages."""


class VoiceAgent:
    def __init__(self, *, whisper_model: Optional[str] = None,
                 gemini_model: Optional[str] = None,
                 speaker_wav: Optional[str] = None) -> None:
        self.whisper_model = whisper_model or os.getenv("WHISPER_MODEL", "base.en")
        self.gemini_model = gemini_model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        configured_speaker = speaker_wav or os.getenv("CHERRY_XTTS_SPEAKER_WAV")
        self.speaker_wav = Path(configured_speaker).expanduser() if configured_speaker else None
        self._tts = None
        self._model_lock = threading.Lock()

    def transcribe(self, audio_bytes: bytes, audio_suffix: str = ".wav") -> str:
        """Transcribe browser-recorded audio; Whisper/FFmpeg handles supported formats."""
        if not audio_bytes:
            raise VoiceAgentError("Audio input is empty.")
        if audio_suffix not in {".wav", ".webm", ".ogg", ".mp4", ".m4a"}:
            audio_suffix = ".wav"
        with tempfile.TemporaryDirectory(prefix="cherry-asr-") as temp_dir:
            audio_path = Path(temp_dir) / f"input{audio_suffix}"
            audio_path.write_bytes(audio_bytes)
            command = [
                "whisper", str(audio_path), "--model", self.whisper_model,
                "--output_format", "txt", "--language", "en", "--fp16", "False",
                "--verbose", "False",
            ]
            try:
                subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
            except FileNotFoundError as exc:
                raise VoiceAgentError("Whisper CLI was not found. Install openai-whisper and ensure its Scripts folder is on PATH.") from exc
            except subprocess.TimeoutExpired as exc:
                raise VoiceAgentError("Speech recognition timed out.") from exc
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or "").strip()[-1000:]
                raise VoiceAgentError("Whisper transcription failed." + (f" {detail}" if detail else "")) from exc
            transcript_path = audio_path.with_suffix(".txt")
            if not transcript_path.is_file():
                raise VoiceAgentError("Whisper completed without creating a transcript.")
            return transcript_path.read_text(encoding="utf-8").strip()

    def respond(self, user_text: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise VoiceAgentError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) before using Gemini.")
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self.gemini_model,
                contents=(
                    "You are CHERRY AI, a helpful and polite voice assistant. "
                    "Reply naturally and concisely, usually in 1-3 sentences. "
                    "Ask one short clarification question when needed.\n\n"
                    f"User said: {user_text}"
                ),
                config=types.GenerateContentConfig(temperature=0.6, max_output_tokens=180),
            )
            answer = (response.text or "").strip()
        except Exception as exc:
            raise VoiceAgentError(f"Gemini response failed: {exc}") from exc
        if not answer:
            raise VoiceAgentError("Gemini returned an empty response.")
        return answer

    def synthesize(self, text: str) -> Path:
        if not text.strip():
            raise VoiceAgentError("Cannot synthesize empty text.")
        if not self.speaker_wav or not self.speaker_wav.is_file():
            raise VoiceAgentError(
                "XTTS-v2 needs a reference speaker WAV. Set CHERRY_XTTS_SPEAKER_WAV "
                "to a short, clear recording you are authorized to use."
            )
        with self._model_lock:
            if self._tts is None:
                try:
                    from TTS.api import TTS
                    model_name = os.getenv(
                        "CHERRY_XTTS_MODEL",
                        "tts_models/multilingual/multi-dataset/xtts_v2",
                    )
                    self._tts = TTS(model_name)
                except Exception as exc:
                    raise VoiceAgentError(f"Could not load Coqui XTTS-v2: {exc}") from exc
            output_path = Path(tempfile.gettempdir()) / f"cherry_voice_{uuid.uuid4().hex}.wav"
            try:
                self._tts.tts_to_file(
                    text=text,
                    speaker_wav=str(self.speaker_wav),
                    language=os.getenv("CHERRY_XTTS_LANGUAGE", "en"),
                    file_path=str(output_path),
                )
            except Exception as exc:
                output_path.unlink(missing_ok=True)
                raise VoiceAgentError(f"XTTS-v2 synthesis failed: {exc}") from exc
        return output_path

    def handle_audio(self, audio_bytes: bytes, audio_suffix: str = ".wav") -> tuple[str, Path]:
        """Return (assistant_text, generated_wav_path) for supported audio bytes."""
        transcript = self.transcribe(audio_bytes, audio_suffix)
        if not transcript:
            raise VoiceAgentError("Whisper did not detect any speech.")
        reply = self.respond(transcript)
        audio_path = self.synthesize(reply)
        return reply, audio_path


def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Run the CHERRY AI voice pipeline on a WAV file.")
    parser.add_argument("wav_file", help="Path to an input WAV file.")
    args = parser.parse_args()
    reply, output = VoiceAgent().handle_audio(Path(args.wav_file).read_bytes())
    print("Transcript processed; assistant reply:")
    print(reply)
    print(f"Audio saved to: {output}")


if __name__ == "__main__":
    _main()
