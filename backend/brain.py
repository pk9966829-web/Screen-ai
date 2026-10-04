import base64
import os
from pathlib import Path
from typing import Dict, Any

from openai import OpenAI

MODEL = os.getenv("VOSI_MODEL", "gpt-6-luna")

def _data_url(image_path: str) -> str:
    path = Path(image_path)
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"

def analyze_screen_question(question: str, image_path: str | None, context: list | None = None, task: Dict[str, Any] | None = None) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"success": False, "error": "OPENAI_API_KEY is not configured.", "understanding": "VOSI can see the screen, but the AI key is not configured yet.", "suggestion": "Set OPENAI_API_KEY in the backend environment and restart the server.", "action": "configure_ai", "confidence": 0.0}
    client = OpenAI(api_key=api_key)
    recent_context = context[-5:] if context else []
    task_state = task or {}
    prompt = f"""You are VOSI, a friendly screen-aware AI assistant.

Answer the user's question using the latest screen image when one is provided.
Do not pretend you can see something that is not visible.
Give practical, direct instructions based on what is actually visible.
If the question is unrelated to the screen, answer normally.
If the user asks what to click, identify the visible control as precisely as possible.

User question:
{question}

Current task:
{task_state}

Recent screen context:
{recent_context}
""".strip()
    content = [{"type": "input_text", "text": prompt}]
    if image_path and Path(image_path).exists():
        content.append({"type": "input_image", "image_url": _data_url(image_path), "detail": "auto"})
    try:
        response = client.responses.create(model=MODEL, input=[{"role": "user", "content": content}])
        answer = (response.output_text or "").strip() or "I couldn't generate an answer from the current screen."
        return {"success": True, "understanding": answer, "suggestion": "", "action": "answer", "confidence": 0.95 if image_path else 0.85}
    except Exception as exc:
        return {"success": False, "error": f"AI request failed: {exc}", "understanding": "VOSI couldn't reach the AI brain.", "suggestion": "Check the API key, model name, internet connection, and backend terminal.", "action": "error", "confidence": 0.0}

def analyze_context(context: Dict[str, Any]) -> Dict[str, Any]:
    observation = context.get("observation", {})
    return {"success": True, "understanding": f"Screen frame received: {observation.get('filename', 'unknown')}", "suggestion": "The latest screen is ready for VOSI to analyze when you ask a question.", "action": "observe", "confidence": 0.80}
