"""Context-aware Fish Audio S2 emotion cues for receptionist speech."""
from __future__ import annotations

import os
import re


def _emotion_for_sentence(sentence: str, caller_context: str = "") -> str:
    text = sentence.lower()
    context = caller_context.lower()

    if any(term in context for term in ("emergency", "urgent", "as soon as possible")):
        if any(term in text for term in ("help", "stay", "understand", "connect", "right away")):
            return "calm and reassuring"
    if any(term in text for term in (
        "i'm sorry", "i am sorry", "i understand", "that sounds difficult",
        "that must be", "i can understand", "apolog",
    )):
        return "empathetic"
    if any(term in text for term in ("thank you", "thanks for", "appreciate")):
        return "grateful"
    if re.search(r"\b(hello|good morning|good afternoon|good evening|welcome)\b", text):
        return "friendly"
    if any(term in text for term in ("congratulations", "that's great", "that is great", "glad to hear")):
        return "happy"
    if "?" in sentence:
        return "curious"
    return "warm and professional"


def apply_fish_emotion_cues(text: str, caller_context: str = "") -> str:
    """Add one restrained S2 bracket cue at each sentence start.

    The spoken words are not rewritten. Cues are only added when enabled and are
    intended for Fish Audio S2-family models, not legacy S1 parenthesis syntax.
    """
    if os.getenv("CHERRY_FISH_EMOTION_TAGS", "true").strip().lower() not in {"1", "true", "yes"}:
        return text
    raw = (text or "").strip()
    if not raw:
        return raw
    if re.search(r"^\[[^\]]+\]\s*", raw):
        return raw

    sentences = re.split(r"(?<=[.!?])\s+", raw)
    tagged = []
    for sentence in sentences:
        clean = sentence.strip()
        if not clean:
            continue
        emotion = _emotion_for_sentence(clean, caller_context)
        tagged.append(f"[{emotion}] {clean}")
    return " ".join(tagged)
