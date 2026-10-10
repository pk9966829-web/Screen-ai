import base64
import os
import json
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
    interactions: list | None = None,
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
    recent_interactions = interactions[-8:] if interactions else []
    task_state = task or {}

    selected_paths = image_paths if image_paths is not None else ([image_path] if image_path else [])
    usable_paths = [str(path) for path in selected_paths if path and Path(path).is_file()]
    if len(usable_paths) > 4:
        usable_paths = usable_paths[-4:]

    prompt = f"""You are VOSI, a friendly screen-aware AI assistant that helps users through multi-step workflows.

Use the recent interaction history to maintain continuity: remember what the user asked, what guidance you gave, and what they were trying to accomplish. Treat older answers as context, not as proof that the current screen is unchanged. The newest screen is authoritative for the current visible state.
Use screen images in oldest-to-newest order to understand transitions.
Do not claim a task step was completed unless the screen or user confirms it.
Give practical, direct instructions based on what is visible. If the user asks what to click, identify the control precisely.
If the question is unrelated to the screen, answer normally.
If the screen and history do not provide enough information, say what is missing and ask one focused follow-up question.
When useful for an ongoing workflow, briefly state the likely current step and one sensible next step; distinguish observations from assumptions.

At the end of your answer, append a final line beginning exactly with VOSI_WORKFLOW_JSON: followed by one valid JSON object with keys task_name, current_step, confirmed_completed_steps, next_step. Use null for unknown values and [] for confirmed_completed_steps unless completion is explicitly confirmed by the user or clearly visible on screen. Never count your own recommendations as completed steps. Put no text after the JSON footer.

User question:
{question}

Current task tracker:
{task_state}

Recent screen observation records:
{recent_context}

Recent VOSI interaction history (oldest to newest):
{recent_interactions}

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
        raw_answer = (response.output_text or "").strip() or "I couldn't generate an answer from the current screen."
        workflow_update = {}
        marker = "VOSI_WORKFLOW_JSON:"
        if marker in raw_answer:
            visible_answer, footer = raw_answer.rsplit(marker, 1)
            try:
                parsed = json.loads(footer.strip())
                if isinstance(parsed, dict):
                    workflow_update = {key: parsed.get(key) for key in ("task_name", "current_step", "confirmed_completed_steps", "next_step")}
                    raw_answer = visible_answer.strip()
            except (json.JSONDecodeError, TypeError):
                pass
        answer = raw_answer
        return {
            "success": True,
            "understanding": answer,
            "workflow_update": workflow_update,
            "suggestion": "",
            "action": "answer",
            "confidence": 0.95 if usable_paths else 0.85,
            "screens_considered": len(usable_paths),
            "interactions_considered": len(recent_interactions),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"AI request failed: {exc}",
            "understanding": "VOSI couldn't reach the AI brain.",
            "suggestion": "Check the API key, model name, internet connection, and backend terminal.",
            "action": "error",
            "confidence": 0.0,
            "workflow_update": {},
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
