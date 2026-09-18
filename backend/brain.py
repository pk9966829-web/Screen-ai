from typing import Dict, Any


def analyze_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock AI brain.

    Takes the current Screen AI context and produces
    a simple interpretation and suggested action.
    """

    observation = context.get("observation", {})

    filename = observation.get("filename")
    status = observation.get("status")

    if status == "image_received":
        return {
            "success": True,
            "understanding": f"I received the screen image: {filename}",
            "suggestion": "I can analyze what is currently happening on the screen.",
            "action": "observe",
            "confidence": 0.80,
        }

    return {
        "success": True,
        "understanding": "I am waiting for a screen observation.",
        "suggestion": "Show me what is happening on the screen.",
        "action": "wait",
        "confidence": 0.50,
    }