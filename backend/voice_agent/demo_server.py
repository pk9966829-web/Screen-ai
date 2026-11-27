"""Optional localhost-only Flask demo for the CHERRY AI voice agent.

POST /voice with Content-Type: audio/wav and raw WAV bytes.
GET /temp/<filename> retrieves a generated WAV file.
Set CHERRY_VOICE_DEMO_TOKEN to require Bearer-token authentication.
Do not expose this development server directly to the public internet.
"""
from __future__ import annotations

import hmac
import os
import uuid
from pathlib import Path
from flask import Flask, abort, jsonify, request, send_from_directory

from .agent import VoiceAgent, VoiceAgentError

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
TEMP_DIR = Path(os.getenv("CHERRY_VOICE_TEMP_DIR", Path.cwd() / "voice_agent_tmp")).resolve()
TEMP_DIR.mkdir(parents=True, exist_ok=True)
voice = VoiceAgent()


@app.before_request
def require_demo_token():
    expected = os.getenv("CHERRY_VOICE_DEMO_TOKEN")
    if expected:
        supplied = request.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {expected}"):
            abort(401, description="A valid Bearer token is required.")


@app.errorhandler(VoiceAgentError)
def handle_voice_error(error):
    return jsonify({"success": False, "error": str(error)}), 422


@app.errorhandler(413)
def handle_too_large(_error):
    return jsonify({"success": False, "error": "Audio upload exceeds the 20 MB limit."}), 413


@app.get("/health")
def health():
    return jsonify({"success": True, "service": "CHERRY AI voice agent"})


@app.post("/voice")
def voice_endpoint():
    if request.mimetype not in {"audio/wav", "audio/x-wav"}:
        abort(415, description="Send raw WAV bytes with Content-Type: audio/wav.")
    audio_bytes = request.get_data(cache=False)
    if not audio_bytes:
        abort(400, description="Audio body is empty.")
    reply_text, wav_path = voice.handle_audio(audio_bytes)
    filename = f"{uuid.uuid4().hex}.wav"
    destination = TEMP_DIR / filename
    destination.write_bytes(wav_path.read_bytes())
    wav_path.unlink(missing_ok=True)
    return jsonify({"success": True, "text": reply_text, "audio_url": f"/temp/{filename}"})


@app.get("/temp/<path:filename>")
def serve_temp(filename):
    # send_from_directory prevents path traversal outside TEMP_DIR.
    return send_from_directory(TEMP_DIR, filename, mimetype="audio/wav", as_attachment=False)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("CHERRY_VOICE_PORT", "8080")), debug=False)
