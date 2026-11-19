import json

import call_assistant_api as calls


def test_identity_response_discloses_ai():
    result = calls._classify("Who are you?")
    reply = calls._reply("Who are you?", result["intent"], result["urgent"])
    assert result["intent"] == "identity"
    assert "AI assistant" in reply


def test_scheduling_request_does_not_promise_availability():
    result = calls._classify("Can he attend the meeting tomorrow?")
    reply = calls._reply("Can he attend the meeting tomorrow?", result["intent"], result["urgent"])
    assert result["intent"] == "scheduling_request"
    assert "can't see or promise" in reply


def test_urgent_caller_is_flagged_for_human_attention():
    result = calls._classify("There has been an accident and we need an ambulance.")
    reply = calls._reply("There has been an accident and we need an ambulance.", result["intent"], result["urgent"])
    assert result["urgent"] is True
    assert "flag it" in reply


def test_message_intent_prompts_for_exact_message():
    result = calls._classify("Please tell him to call me back.")
    reply = calls._reply("Please tell him to call me back.", result["intent"], result["urgent"])
    assert result["intent"] == "message"
    assert "exact message" in reply


def test_unknown_general_caller_gets_disclosure():
    result = calls._classify("I am calling about the project.")
    reply = calls._reply("I am calling about the project.", result["intent"], result["urgent"])
    assert "I'm VOSI, an AI assistant" in reply


def test_detects_and_replies_in_hindi():
    text = "आप कौन हैं?"
    result = calls._classify(text)
    reply = calls._reply(text, result["intent"], result["urgent"], result["language"])
    assert result["language"] == "hi"
    assert "मैं VOSI हूँ" in reply


def test_detects_and_replies_in_kannada():
    text = "ನೀವು ಯಾರು?"
    result = calls._classify(text)
    reply = calls._reply(text, result["intent"], result["urgent"], result["language"])
    assert result["language"] == "kn"
    assert "ನಾನು VOSI" in reply


def test_honours_explicit_language_override():
    result = calls._classify("Who are you?", "hi")
    reply = calls._reply("Who are you?", result["intent"], result["urgent"], result["language"])
    assert result["language"] == "hi"
    assert "मैं VOSI हूँ" in reply


def test_detects_kannada_urgent_call():
    result = calls._classify("ಇದು ತುರ್ತು ಅಪಘಾತ, ಆಸ್ಪತ್ರೆಗೆ ಆಂಬುಲೆನ್ಸ್ ಬೇಕು.")
    assert result["urgent"] is True
    assert result["language"] == "kn"

def test_hindi_message_intent_is_recognised():
    result = calls._classify("कृपया उन्हें मेरा संदेश दे दीजिए।")
    assert result["intent"] == "message"
    assert result["language"] == "hi"


def test_kannada_message_intent_is_recognised():
    result = calls._classify("ದಯವಿಟ್ಟು ಅವರಿಗೆ ನನ್ನ ಸಂದೇಶ ತಿಳಿಸಿ.")
    assert result["intent"] == "message"
    assert result["language"] == "kn"
