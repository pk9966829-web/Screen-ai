from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from uuid import uuid4
from datetime import datetime
import re
from docx import Document
from docx.shared import Inches, Pt

from pipeline import ScreenPipeline
from brain import analyze_screen_question, draft_letter
from database import save_interaction, get_recent_interactions, get_recent_tasks, get_recent_observations, save_task_state

app = FastAPI(title="VOSI Screen AI")

# Local bridge used only by the VOSI Chrome extension.
browser_pending_command = None
browser_results = {}

class BrowserSearchRequest(BaseModel):
    request_id: str
    query: str
    budget: Optional[float] = None

class BrowserResultsRequest(BaseModel):
    request_id: str
    products: list[dict] = []

@app.post("/browser/search")
def queue_browser_search(req: BrowserSearchRequest):
    global browser_pending_command
    query = (req.query or "").strip()
    if not query or len(query) > 180 or len(req.request_id) > 100:
        return {"success": False, "error": "Enter a product search under 180 characters."}
    browser_pending_command = {"request_id": req.request_id, "query": query, "budget": req.budget}
    browser_results.pop(req.request_id, None)
    return {"success": True, "message": "Waiting for the VOSI Chrome extension."}

@app.get("/browser/command")
def get_browser_command():
    return {"success": True, "command": browser_pending_command}

@app.post("/browser/ack/{request_id}")
def acknowledge_browser_command(request_id: str):
    global browser_pending_command
    if browser_pending_command and browser_pending_command.get("request_id") == request_id:
        browser_pending_command = None
    return {"success": True}

@app.post("/browser/results")
def receive_browser_results(req: BrowserResultsRequest):
    if len(req.products) > 30:
        req.products = req.products[:30]
    browser_results[req.request_id] = {"products": req.products}
    return {"success": True}

@app.get("/browser/results/{request_id}")
def read_browser_results(request_id: str):
    result = browser_results.get(request_id)
    if not result:
        return {"success": False, "pending": True}
    return {"success": True, "results": result}


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
LETTER_DIR = Path.home() / "Documents" / "VOSI" / "Letters"
LETTER_DIR.mkdir(parents=True, exist_ok=True)
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


class LetterDraftRequest(BaseModel):
    recipient: str = ""
    sender: str = ""
    subject: str = ""
    purpose: str
    tone: str = "professional"


@app.get("/")
def root():
    return {
        "success": True,
        "message": "VOSI backend is running",
        "version": "0.4.0",
        "ai": "OpenAI Responses API",
        "endpoints": ["GET /", "GET /state", "GET /workflow", "GET /history", "POST /screen", "POST /ask", "POST /letter/draft", "GET /letter/file/{filename}", "POST /task", "POST /awareness"],
    }


@app.get("/state")
def get_state():
    return {"success": True, **pipeline.get_state()}


@app.get("/history")
def get_history(limit: int = 20):
    """Return persisted VOSI chat interactions, task history, and screen observation metadata."""
    safe_limit = max(1, min(limit, 100))
    return {
        "success": True,
        "interactions": get_recent_interactions(safe_limit),
        "tasks": get_recent_tasks(safe_limit),
        "observations": get_recent_observations(safe_limit),
        "privacy_note": "The database stores chat text, task progress, and screenshot metadata; image files themselves are not stored in SQLite.",
    }


@app.get("/workflow")
def get_workflow():
    """Return recent screen context, task tracker state, and recent Q&A for this backend session."""
    return {
        "success": True,
        "task_state": pipeline.task.get_task_state(),
        "recent_screens": pipeline.get_state().get("recent_screens", []),
        "screen_changes": pipeline.get_recent_screen_changes(limit=10),
        "recent_interactions": get_recent_interactions(limit=20),
        "note": "Chat interactions and task progress are persisted in the local SQLite database.",
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
    prior_interactions = get_recent_interactions(limit=8)

    result = analyze_screen_question(
        message,
        latest_path,
        state.get("recent_context") or [],
        state.get("task") or {},
        image_paths=recent_paths if req.include_screen else [],
        interactions=prior_interactions,
        screen_changes=pipeline.get_recent_screen_changes(limit=10),
    )
    progress_data = result.get("workflow_update") or {}
    if result.get("success") and progress_data:
        state["task"] = pipeline.task.apply_workflow_update(progress_data)
        if state["task"].get("task"):
            save_task_state(state["task"], status="active")

    answer = result.get("understanding", "")
    # Save both successful answers and failures so follow-up questions retain context.
    interaction = pipeline.context.add_interaction(
        message,
        answer,
        screens_considered=result.get("screens_considered", 0),
        task=state.get("task") or {},
    )
    persisted_interaction = save_interaction(
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
        "screen_changes": pipeline.get_recent_screen_changes(limit=10),
        "recent_interactions": get_recent_interactions(limit=8),
        "interaction_recorded": bool(interaction) and bool(persisted_interaction),
        "screen_used": bool(latest_path and req.include_screen),
    }


@app.post("/letter/draft")
def create_letter_draft(req: LetterDraftRequest):
    recipient = (req.recipient or "").strip()
    purpose = (req.purpose or "").strip()
    if not recipient:
        return {"success": False, "error": "Tell VOSI who the letter should be addressed to."}
    if not purpose:
        return {"success": False, "error": "Describe what the letter should say."}
    if len(purpose) > 5000 or any(len(value) > 240 for value in (req.recipient, req.sender, req.subject, req.tone)):
        return {"success": False, "error": "Letter details are too long. Shorten them and try again."}
    allowed_tones = {"professional", "friendly", "formal", "appreciative", "firm but respectful"}
    tone = req.tone.strip().lower() or "professional"
    if tone not in allowed_tones:
        return {"success": False, "error": "Choose one of the available letter tones."}

    try:
        letter_text = draft_letter(
            recipient=recipient,
            sender=req.sender.strip(),
            subject=req.subject.strip(),
            purpose=purpose,
            tone=tone,
        )
        filename = f"VOSI-Letter-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}.docx"
        file_path = LETTER_DIR / filename

        document = Document()
        section = document.sections[0]
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        normal = document.styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(11)
        for line in letter_text.splitlines():
            document.add_paragraph(line if line.strip() else "")
        document.core_properties.title = req.subject.strip() or "VOSI Letter Draft"
        document.save(file_path)
        return {
            "success": True,
            "letter_text": letter_text,
            "filename": filename,
            "file_path": str(file_path.resolve()),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.get("/letter/file/{filename}")
def download_letter_draft(filename: str):
    if not re.fullmatch(r"VOSI-Letter-\d{8}-\d{6}-[a-f0-9]{6}\.docx", filename):
        return {"success": False, "error": "Invalid letter file name."}
    file_path = (LETTER_DIR / filename).resolve()
    if file_path.parent != LETTER_DIR.resolve() or not file_path.is_file():
        return {"success": False, "error": "Letter file was not found."}
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@app.post("/task")
def manage_task(req: TaskRequest):
    action = (req.action or "").lower().strip()
    if action == "start":
        state = pipeline.start_task(req.task_name or "Untitled task")
        save_task_state(state, status="active")
        return {"success": True, "action": "start", "task_state": state}
    if action == "stop":
        previous_state = pipeline.task.get_task_state()
        if previous_state.get("task"):
            save_task_state(previous_state, status="stopped")
        pipeline.task.task = None
        pipeline.task.current_step = None
        pipeline.task.completed_steps = []
        pipeline.task.next_step = None
        pipeline.task.created_at = None
        pipeline.task.task_key = None
        return {"success": True, "action": "stop", "task_state": pipeline.task.get_task_state()}
    if action in {"set_step", "complete_step", "next_step"}:
        if not req.step:
            return {"success": False, "error": "step is required"}
        if action == "set_step":
            state = pipeline.set_current_step(req.step)
        elif action == "complete_step":
            state = pipeline.complete_step(req.step)
        else:
            state = pipeline.set_next_step(req.step)
        if state.get("task"):
            save_task_state(state, status="active")
        return {"success": True, "action": action, "task_state": state}
    return {"success": False, "error": "Unknown action. Use start|stop|set_step|complete_step|next_step"}


@app.post("/awareness")
def set_awareness(req: AwarenessRequest):
    return {
        "success": True,
        "awareness_enabled": req.enabled,
        "message": "Screen awareness enabled. Client should start capturing." if req.enabled else "Screen awareness disabled.",
        "state": pipeline.get_state(),
    }
