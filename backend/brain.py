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


def analyze_screen_question(
    question: str,
    image_path: str | None,
    context: list | None = None,
    task: Dict[str, Any] | None = None,
    image_paths: list[str] | None = None,
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "OPENAI_API_KEY is not configured.",
            "understanding": "VOSI can see the screen, but the AI key is not configured yet.",
            "suggestion": "Set OPENAI_API_KEY in the backend environment and restart the server.",
            "action": "configure_ai",
            "confidence": 0.0,
        }

    client = OpenAI(api_key=api_key)
    recent_context = context[-5:] if context else []
    task_state = task or {}

    # Use the rolling screen history when available, falling back to the
    # previous single-image behavior for existing callers.
    selected_paths = image_paths if image_paths is not None else ([image_path] if image_path else [])
    usable_paths = [str(path) for path in selected_paths if path and Path(path).is_file()]
    if len(usable_paths) > 4:
        usable_paths = usable_paths[-4:]

    prompt = f"""You are VOSI, a friendly screen-aware AI assistant.

Answer the user's question using the screen images provided, which are ordered from oldest to newest.
Use the sequence to understand what changed between recent screens, but prioritize the newest image for the current state.
Do not pretend you can see something that is not visible.
Give practical, direct instructions based on what is actually visible.
If the question is unrelated to the screen, answer normally.
If the user asks what to click, identify the visible control as precisely as possible.
If the images do not provide enough context, say what is missing and ask a focused follow-up question.

User question:
{question}

Current task:
{task_state}

Recent observation records:
{recent_context}

Number of recent screen images attached: {len(usable_paths)}
""".strip()

    content = [{"type": "input_text", "text": prompt}]
    for index, path in enumerate(usable_paths, start=1):
        content.append({
            "type": "input_text",
            "text": f"Screen frame {index} of {len(usable_paths)} (ordered oldest to newest).",
        })
        content.append({
            "type": "input_image",
            "image_url": _data_url(path),
            "detail": "auto",
        })

    try:
        response = client.responses.create(
            model=MODEL,
            input=[{"role": "user", "content": content}],
        )
        answer = (response.output_text or "").strip() or "I couldn't generate an answer from the current screen."
        return {
            "success": True,
            "understanding": answer,
            "suggestion": "",
            "action": "answer",
            "confidence": 0.95 if usable_paths else 0.85,
            "screens_considered": len(usable_paths),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"AI request failed: {exc}",
            "understanding": "VOSI couldn't reach the AI brain.",
            "suggestion": "Check the API key, model name, internet connection, and backend terminal.",
            "action": "error",
            "confidence": 0.0,
        }


def analyze_context(context: Dict[str, Any]) -> Dict[str, Any]:
    observation = context.get("observation", {})
    screens = context.get("recent_screens", [])
    return {
        "success": True,
        "understanding": f"Screen frame received: {observation.get('filename', 'unknown')}",
        "suggestion": "Recent screen frames are kept temporarily so VOSI can compare the latest screen with the preceding frames when you ask a question.",
        "action": "observe",
        "confidence": 0.80,
        "screens_in_memory": len(screens),
    }
