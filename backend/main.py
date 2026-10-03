from fastapi import FastAPI, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from pathlib import Path

from pipeline import ScreenPipeline


app = FastAPI(title="Screen AI")


# Allow the Screen AI desktop app to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Folder where uploaded screenshots are stored
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# Make uploaded screenshots accessible through:
# http://127.0.0.1:8001/uploads/<filename>
app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads"
)


# Initialize Screen AI processing pipeline
pipeline = ScreenPipeline()


# ------------------------------------------------------------
# Request models
# ------------------------------------------------------------

class AskRequest(BaseModel):
    message: str
    include_screen: bool = False


class TaskRequest(BaseModel):
    task_name: Optional[str] = None
    step: Optional[str] = None
    action: str  # start | stop | set_step | complete_step | next_step


class AwarenessRequest(BaseModel):
    enabled: bool


# ------------------------------------------------------------
# Root
# ------------------------------------------------------------

@app.get("/")
def root():
    return {
        "success": True,
        "message": "Screen AI backend is running",
        "version": "0.1.0",
        "endpoints": [
            "GET  /",
            "GET  /state",
            "POST /screen",
            "POST /ask",
            "POST /task",
            "POST /awareness",
        ]
    }


# ------------------------------------------------------------
# Full current state (task + context + history)
# ------------------------------------------------------------

@app.get("/state")
def get_state():
    return {
        "success": True,
        **pipeline.get_state()
    }


# ------------------------------------------------------------
# Receive screenshot (existing)
# ------------------------------------------------------------

@app.post("/screen")
async def receive_screen(file: UploadFile = File(...)):
    # Save uploaded screenshot
    file_path = UPLOAD_DIR / file.filename

    contents = await file.read()
    file_path.write_bytes(contents)

    # Process screenshot through Screen AI pipeline
    result = pipeline.process_image(str(file_path))

    return result


# ------------------------------------------------------------
# Ask Screen AI (text question)
# ------------------------------------------------------------

@app.post("/ask")
def ask_screen_ai(req: AskRequest):
    message = (req.message or "").strip()

    if not message:
        return {
            "success": False,
            "error": "Message cannot be empty"
        }

    state = pipeline.get_state()
    task = state.get("task") or {}
    recent = state.get("recent_context") or []

    # Simple mock reasoning that uses current context
    understanding = f"You asked: \"{message}\""
    suggestion = "I can help once I observe your screen or you start a task."
    action = "wait"
    confidence = 0.65

    if task.get("task"):
        understanding = (
            f"Regarding your task '{task['task']}': {message}"
        )
        suggestion = (
            f"Current step: {task.get('current_step') or 'not set'}. "
            f"Completed: {', '.join(task.get('completed_steps') or []) or 'none'}."
        )
        action = "guide"
        confidence = 0.85

    if recent:
        last = recent[-1].get("observation", {})
        understanding += f" (Last screen: {last.get('filename', 'unknown')})"
        action = "observe_and_answer"
        confidence = 0.9

    return {
        "success": True,
        "message": message,
        "brain": {
            "understanding": understanding,
            "suggestion": suggestion,
            "action": action,
            "confidence": confidence,
        },
        "task_state": task,
        "recent_context": recent,
    }


# ------------------------------------------------------------
# Task control
# ------------------------------------------------------------

@app.post("/task")
def manage_task(req: TaskRequest):
    action = (req.action or "").lower().strip()

    if action == "start":
        name = req.task_name or "Untitled task"
        state = pipeline.start_task(name)
        return {"success": True, "action": "start", "task_state": state}

    if action == "stop":
        # Reset by clearing task state
        pipeline.task.task = None
        pipeline.task.current_step = None
        pipeline.task.completed_steps = []
        pipeline.task.next_step = None
        pipeline.task.created_at = None
        return {
            "success": True,
            "action": "stop",
            "task_state": pipeline.task.get_task_state()
        }

    if action == "set_step":
        if not req.step:
            return {"success": False, "error": "step is required"}
        state = pipeline.set_current_step(req.step)
        return {"success": True, "action": "set_step", "task_state": state}

    if action == "complete_step":
        if not req.step:
            return {"success": False, "error": "step is required"}
        state = pipeline.complete_step(req.step)
        return {"success": True, "action": "complete_step", "task_state": state}

    if action == "next_step":
        if not req.step:
            return {"success": False, "error": "step is required"}
        state = pipeline.set_next_step(req.step)
        return {"success": True, "action": "next_step", "task_state": state}

    return {
        "success": False,
        "error": f"Unknown action: {action}. Use start|stop|set_step|complete_step|next_step"
    }


# ------------------------------------------------------------
# Awareness toggle (records intent; real capture is client-side)
# ------------------------------------------------------------

@app.post("/awareness")
def set_awareness(req: AwarenessRequest):
    # For now we just acknowledge and return current pipeline state.
    # Real screen capture stays on the client (getDisplayMedia).
    return {
        "success": True,
        "awareness_enabled": req.enabled,
        "message": (
            "Screen awareness enabled. Client should start capturing."
            if req.enabled
            else "Screen awareness disabled."
        ),
        "state": pipeline.get_state()
    }
