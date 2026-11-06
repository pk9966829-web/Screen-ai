from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import json
import os
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from pathlib import Path
from uuid import uuid4
from datetime import datetime
import re
from docx import Document
from docx.shared import Inches, Pt

from pipeline import ScreenPipeline
from brain import analyze_screen_question, draft_letter, summarize_hotel_research, summarize_web_research
from database import save_interaction, get_recent_interactions, get_recent_tasks, get_recent_observations, save_task_state

app = FastAPI(title="VOSI Screen AI")
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


class HotelResearchRequest(BaseModel):
    city: str
    check_in: str = ""
    check_out: str = ""
    budget: str = ""
    guests: int = 2
    preferences: str = ""
    source_count: int = 20


class YouTubePlayRequest(BaseModel):
    query: str


class WebResearchRequest(BaseModel):
    query: str
    source_count: int = 20


@app.get("/")
def root():
    return {
        "success": True,
        "message": "VOSI backend is running",
        "version": "0.4.0",
        "ai": "OpenAI Responses API",
        "endpoints": ["GET /", "GET /state", "GET /workflow", "GET /history", "POST /screen", "POST /ask", "POST /letter/draft", "GET /letter/file/{filename}", "POST /research/web", "POST /research/hotels", "POST /youtube/play", "POST /task", "POST /awareness"],
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


@app.post("/research/hotels")
def research_hotels(req: HotelResearchRequest):
    city = req.city.strip()
    if not city or len(city) > 160:
        return {"success": False, "error": "Enter a city or destination (up to 160 characters)."}
    if req.source_count not in {10, 20, 30}:
        return {"success": False, "error": "Choose 10, 20, or 30 sources."}
    if not 1 <= req.guests <= 6:
        return {"success": False, "error": "Choose between 1 and 6 travelers."}
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return {"success": False, "error": "Hotel research needs a Tavily search key. Add TAVILY_API_KEY to backend/.env and restart the backend."}

    travel_details = " ".join(part for part in [
        f"check-in {req.check_in}" if req.check_in else "",
        f"check-out {req.check_out}" if req.check_out else "",
        f"budget {req.budget.strip()} per night" if req.budget.strip() else "",
        f"for {req.guests} travelers",
        req.preferences.strip(),
    ] if part)
    queries = [
        f"best hotels in {city} {travel_details}",
        f"hotel reviews and best places to stay in {city} {travel_details}",
    ]
    found = []
    seen = set()
    try:
        for query in queries:
            payload = json.dumps({"query": query, "max_results": 20, "search_depth": "basic", "include_answer": False}).encode("utf-8")
            request = Request("https://api.tavily.com/search", data=payload, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            for item in result.get("results", []):
                url = str(item.get("url", ""))
                if not url.startswith(("https://", "http://")) or url in seen:
                    continue
                seen.add(url)
                found.append({"title": str(item.get("title", "Source"))[:240], "url": url, "snippet": str(item.get("content", ""))[:1800], "published_date": str(item.get("published_date") or "")[:40]})
                if len(found) >= req.source_count:
                    break
            if len(found) >= req.source_count:
                break
        if not found:
            return {"success": False, "error": "The search service returned no usable results. Try again with another city or phrase."}
        report = summarize_hotel_research(city, travel_details, found)
        return {"success": True, "report": report, "sources": found, "source_count": len(found), "requested_source_count": req.source_count}
    except Exception as exc:
        return {"success": False, "error": f"Hotel research failed: {exc}"}


@app.post("/research/web")
def research_web(req: WebResearchRequest):
    query = req.query.strip()
    if not query or len(query) > 500:
        return {"success": False, "error": "Enter a search question or topic up to 500 characters."}
    if req.source_count not in {10, 20, 30}:
        return {"success": False, "error": "Choose 10, 20, or 30 sources."}
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return {"success": False, "error": "Web research needs a Tavily search key. Add TAVILY_API_KEY to backend/.env and restart the server."}

    found = []
    seen = set()
    try:
        # Tavily returns up to 20 results per request. A related second query lets
        # VOSI collect up to 30 distinct links when the user selects that option.
        queries = [query, f"{query} additional sources and perspectives"] if req.source_count > 20 else [query]
        for search_query in queries:
            payload = json.dumps({"query": search_query, "max_results": 20, "search_depth": "basic", "include_answer": False}).encode("utf-8")
            request = Request("https://api.tavily.com/search", data=payload, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
            with urlopen(request, timeout=35) as response:
                result = json.loads(response.read().decode("utf-8"))
            for item in result.get("results", []):
                url = str(item.get("url", ""))
                if urlsplit(url).scheme not in {"https", "http"} or not urlsplit(url).netloc or url in seen:
                    continue
                seen.add(url)
                found.append({"title": str(item.get("title", "Source"))[:240], "url": url, "snippet": str(item.get("content", ""))[:1600], "published_date": str(item.get("published_date") or "")[:40]})
                if len(found) >= req.source_count:
                    break
            if len(found) >= req.source_count:
                break
        if not found:
            return {"success": False, "error": "The search service returned no usable results. Try a more specific phrase."}
        report = summarize_web_research(query, found)
        return {"success": True, "query": query, "report": report, "sources": found, "source_count": len(found), "requested_source_count": req.source_count}
    except Exception as exc:
        return {"success": False, "error": f"Web research failed: {exc}"}


@app.post("/youtube/play")
def search_youtube_to_play(req: YouTubePlayRequest):
    query = req.query.strip()
    if not query or len(query) > 200:
        return {"success": False, "error": "Tell VOSI the song or video name (up to 200 characters)."}
    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist"}) as ydl:
            result = ydl.extract_info(f"ytsearch1:{query}", download=False)
        entries = result.get("entries") or []
        video = next((entry for entry in entries if entry), None)
        video_id = str((video or {}).get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return {"success": False, "error": "No playable YouTube result was found. Try a more specific song title."}
        return {"success": True, "video_id": video_id, "title": str(video.get("title") or query)[:240], "channel": str(video.get("channel") or video.get("uploader") or "")[:160]}
    except Exception as exc:
        return {"success": False, "error": f"YouTube search failed: {exc}. Check yt-dlp is installed and update backend dependencies."}


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
