from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from uuid import uuid4

from pipeline import ScreenPipeline
from brain import analyze_screen_question

app = FastAPI(title="VOSI Screen AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
pipeline = ScreenPipeline()


class AskRequest(BaseModel):
    message: str
    include_screen: bool = False


class TaskRequest(BaseModel):
    task_name: Optional[str] = None
    step: Optional[str] = None
    action: str


class AwarenessRequest(BaseModel):
    enabled: bool


@app.get("/")
def root():
    return {
        "success": True,
        "message": "VOSI backend is running",
        "version": "0.4.0",
        "ai": "OpenAI Responses API",
        "endpoints": ["GET /", "GET /state", "GET /workflow", "POST /screen", "POST /ask", "POST /task", "POST /awareness"],
    }


@app.get("/state")
def get_state():
    return {"success": True, **pipeline.get_state()}


@app.get("/workflow")
def get_workflow():
    """Return recent screen context, task tracker state, and recent Q&A for this backend session."""
    return {
        "success": True,
        "task_state": pipeline.task.get_task_state(),
        "recent_screens": pipeline.get_state().get("recent_screens", []),
        "recent_interactions": pipeline.context.get_recent_interactions(limit=20),
        "note": "Workflow interaction history is temporary and resets when the backend restarts.",
    }


@app.post("/screen")
async def receive_screen(file: UploadFile = File(...)):
    # Generate a server-side filename so client filenames cannot become paths.
    suffix = ".png" if file.content_type == "image/png" else ".jpg"
    file_path = UPLOAD_DIR / f"screen_{uuid4().hex}{suffix}"
    file_path.write_bytes(await file.read())
    return pipeline.process_image(str(file_path))


@app.post("/ask")
def ask_screen_ai(req: AskRequest):
    message = (req.message or "").strip()
    if not message:
        return {"success": False, "error": "Message cannot be empty"}

    state = pipeline.get_state()
    recent_frames = pipeline.get_recent_screen_frames() if req.include_screen else []
    recent_paths = [frame["path"] for frame in recent_frames]
    latest_path = recent_paths[-1] if recent_paths else (
        pipeline.latest_screen_path if req.include_screen else None
    )
    prior_interactions = pipeline.context.get_recent_interactions(limit=8)

    result = analyze_screen_question(
        message,
        latest_path,
        state.get("recent_context") or [],
        state.get("task") or {},
        image_paths=recent_paths if req.include_screen else [],
        interactions=prior_interactions,
    )
    answer = result.get("understanding", "")
    # Save both successful answers and failures so follow-up questions retain context.
    interaction = pipeline.context.add_interaction(
        message,
        answer,
        screens_considered=result.get("screens_considered", 0),
        task=state.get("task") or {},
    )

    return {
        "success": result.get("success", False),
        "message": message,
        "brain": result,
        "task_state": state.get("task") or {},
        "recent_context": state.get("recent_context") or [],
        "recent_screens": state.get("recent_screens") or [],
        "recent_interactions": pipeline.context.get_recent_interactions(limit=8),
        "interaction_recorded": bool(interaction),
        "screen_used": bool(latest_path and req.include_screen),
    }


@app.post("/task")
def manage_task(req: TaskRequest):
    action = (req.action or "").lower().strip()
    if action == "start":
        return {"success": True, "action": "start", "task_state": pipeline.start_task(req.task_name or "Untitled task")}
    if action == "stop":
        pipeline.task.task = None
        pipeline.task.current_step = None
        pipeline.task.completed_steps = []
        pipeline.task.next_step = None
        pipeline.task.created_at = None
        return {"success": True, "action": "stop", "task_state": pipeline.task.get_task_state()}
    if action == "set_step":
        if not req.step:
            return {"success": False, "error": "step is required"}
        return {"success": True, "action": "set_step", "task_state": pipeline.set_current_step(req.step)}
    if action == "complete_step":
        if not req.step:
            return {"success": False, "error": "step is required"}
        return {"success": True, "action": "complete_step", "task_state": pipeline.complete_step(req.step)}
    if action == "next_step":
        if not req.step:
            return {"success": False, "error": "step is required"}
        return {"success": True, "action": "next_step", "task_state": pipeline.set_next_step(req.step)}
    return {"success": False, "error": "Unknown action. Use start|stop|set_step|complete_step|next_step"}


@app.post("/awareness")
def set_awareness(req: AwarenessRequest):
    return {
        "success": True,
        "awareness_enabled": req.enabled,
        "message": "Screen awareness enabled. Client should start capturing." if req.enabled else "Screen awareness disabled.",
        "state": pipeline.get_state(),
    }
