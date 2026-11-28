import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

import voice_expression


def test_fish_emotion_cues_are_disabled_when_requested(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_EMOTION_TAGS", "false")
    text = "Hello. Thank you."
    assert voice_expression.apply_fish_emotion_cues(text) == text


def test_emotion_cues_are_added_at_sentence_starts(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_EMOTION_TAGS", "true")
    result = voice_expression.apply_fish_emotion_cues(
        "Hello. Thank you for waiting. What is your name?"
    )
    assert result == (
        "[friendly] Hello. [grateful] Thank you for waiting. "
        "[curious] What is your name?"
    )


def test_urgent_caller_context_produces_calm_reassurance(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_EMOTION_TAGS", "true")
    result = voice_expression.apply_fish_emotion_cues(
        "I understand. I can help you right away.",
        "Caller: This is an emergency and it is urgent.",
    )
    assert result == (
        "[calm and reassuring] I understand. "
        "[calm and reassuring] I can help you right away."
    )


def test_empathy_and_professional_default(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_EMOTION_TAGS", "true")
    result = voice_expression.apply_fish_emotion_cues(
        "I'm sorry this happened. I will take a message."
    )
    assert result == (
        "[empathetic] I'm sorry this happened. "
        "[warm and professional] I will take a message."
    )


def test_existing_emotion_cue_is_not_duplicated(monkeypatch):
    monkeypatch.setenv("CHERRY_FISH_EMOTION_TAGS", "true")
    text = "[empathetic] I understand. Please tell me more."
    assert voice_expression.apply_fish_emotion_cues(text) == text
