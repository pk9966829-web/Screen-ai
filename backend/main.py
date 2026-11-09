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
import base64
from email.mime.text import MIMEText
from docx import Document
from docx.shared import Inches, Pt

app = FastAPI(title="VOSI Screen AI")

# Gmail access is handled locally by this backend; no VOSI AI provider is used.
import os
import threading
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build

load_dotenv(Path(__file__).resolve().parent / ".env")
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SCOPES = [GMAIL_READ_SCOPE, GMAIL_SEND_SCOPE]
GMAIL_TOKEN_FILE = Path(__file__).resolve().parent / "gmail_token.json"
gmail_auth_state = {"status": "disconnected", "error": None}
gmail_auth_lock = threading.Lock()


def _gmail_client_config():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env, then restart VOSI backend.")
    return {"installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }}


def _gmail_credentials():
    if not GMAIL_TOKEN_FILE.is_file():
        return None
    credentials = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), GMAIL_SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleAuthRequest())
        GMAIL_TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    return credentials if credentials.valid else None


def _run_gmail_oauth():
    try:
        flow = InstalledAppFlow.from_client_config(_gmail_client_config(), GMAIL_SCOPES)
        credentials = flow.run_local_server(
            host="localhost", port=0, open_browser=True,
            authorization_prompt_message="Approve Gmail read and send access for VOSI in your browser.",
            success_message="Gmail is connected to VOSI. You can close this browser tab.",
            access_type="offline", prompt="consent"
        )
        GMAIL_TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
        gmail_auth_state.update({"status": "connected", "error": None})
    except Exception as exc:
        gmail_auth_state.update({"status": "error", "error": str(exc)})
    finally:
        gmail_auth_lock.release()


@app.post("/gmail/connect")
def connect_gmail():
    if not gmail_auth_lock.acquire(blocking=False):
        return {"success": True, **gmail_auth_state, "message": "Gmail authorization is already running."}
    gmail_auth_state.update({"status": "connecting", "error": None})
    threading.Thread(target=_run_gmail_oauth, daemon=True).start()
    return {"success": True, "status": "connecting", "message": "A Google sign-in window should open. Approve Gmail read and send access."}


@app.get("/gmail/status")
def gmail_status():
    if gmail_auth_state["status"] == "connecting":
        return {"success": True, **gmail_auth_state}
    try:
        credentials = _gmail_credentials()
        if credentials and credentials.has_scopes([GMAIL_SEND_SCOPE]):
            gmail_auth_state.update({"status": "connected", "error": None})
        elif credentials:
            gmail_auth_state.update({"status": "reconnect_required", "error": "Reconnect Gmail and approve the send permission."})
        elif gmail_auth_state["status"] != "error":
            gmail_auth_state.update({"status": "disconnected", "error": None})
    except Exception as exc:
        gmail_auth_state.update({"status": "error", "error": str(exc)})
    return {"success": True, **gmail_auth_state}



class GmailSearchRequest(BaseModel):
    query: str
    count: int = 5

class GmailSendRequest(BaseModel):
    recipient: str
    subject: str = "Message from VOSI"
    body: str
    confirmed: bool = False


@app.post("/gmail/send")
def send_gmail_message(req: GmailSendRequest):
    recipient = (req.recipient or "").strip()
    subject = (req.subject or "Message from VOSI").strip()
    body = (req.body or "").strip()
    if not req.confirmed:
        return {"success": False, "error": "Email sending requires your confirmation in VOSI."}
    if not re.fullmatch(r"[^\\s@]+@[^\\s@]+\\.[^\\s@]+", recipient):
        return {"success": False, "error": "Enter a valid recipient email address."}
    if not body:
        return {"success": False, "error": "The email message cannot be empty."}
    if len(recipient) > 254 or len(subject) > 250 or len(body) > 20000:
        return {"success": False, "error": "The email is too long. Shorten the recipient, subject, or message."}
    try:
        credentials = _gmail_credentials()
        if not credentials:
            return {"success": False, "connected": False, "error": "Gmail is not connected. Connect Gmail from VOSI Connectors first."}
        if not credentials.has_scopes([GMAIL_SEND_SCOPE]):
            return {"success": False, "connected": True, "reconnect_required": True, "error": "Reconnect Gmail and approve the new send permission before sending."}
        message = MIMEText(body, _charset="utf-8")
        message["to"] = recipient
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"success": True, "message_id": sent.get("id"), "recipient": recipient, "subject": subject, "message": "Email sent successfully."}
    except Exception as exc:
        return {"success": False, "error": f"Could not send the email: {exc}"}



def _gmail_clean_value(value: str) -> str:
    value = re.sub(r"[^\w@.+\-\s]", " ", value or "", flags=re.UNICODE)
    value = re.sub(r"\b(?:OR|AND|NOT)\b", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value)[:120].strip()




def _gmail_has_attachment(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("filename"):
        return True
    return any(_gmail_has_attachment(part) for part in payload.get("parts", []) if isinstance(part, dict))


def _gmail_query_from_ai_intent(intent: dict):
    """Validate model-produced fields and build Gmail syntax from an allow-list."""
    if not isinstance(intent, dict):
        return None
    parts = []
    filters = {}
    def value(key):
        item = intent.get(key)
        return _gmail_clean_value(str(item)) if isinstance(item, str) else ""
    for key, operator in (("sender", "from"), ("recipient", "to")):
        item = value(key)
        if item:
            parts.append(f"{operator}:({item})")
            filters[key] = item
    for key in ("subject", "keywords", "filename"):
        item = value(key)
        if item:
            parts.append(f'{key}:("{item}")' if key in {"subject", "filename"} else item)
            filters[key] = item
    for key in ("after", "before"):
        item = value(key)
        if item and re.fullmatch(r"\d{4}/\d{2}/\d{2}", item):
            parts.append(f"{key}:{item}")
            filters[key] = item
    for age_key in ("newer_than", "older_than"):
        age = value(age_key)
        if age and re.fullmatch(r"\d{1,4}[dmy]", age.lower()):
            parts.append(f"{age_key}:{age.lower()}")
            filters[age_key] = age.lower()
    label = value("label")
    if label:
        parts.append(f"label:{label}")
        filters["label"] = label
    read_status = value("read_status").lower()
    if read_status in {"read", "unread"}:
        parts.append(f"is:{read_status}")
        filters["read_status"] = read_status
    for key, operator in (("has_attachment", "has:attachment"), ("starred", "is:starred"), ("important", "is:important")):
        if intent.get(key) is True:
            parts.append(operator)
            filters[key] = True
    category = value("category").lower()
    if category in {"primary", "social", "promotions", "updates", "forums"}:
        parts.append(f"category:{category}")
        filters["category"] = category
    folder = value("folder").lower()
    if folder in {"inbox", "sent", "drafts", "spam", "trash", "anywhere"}:
        parts.append(f"in:{folder}")
        filters["folder"] = folder
    if not parts:
        return None
    return {"gmail_query": " ".join(parts), "filters": filters}



def _gmail_parse_advanced_syntax(text: str):
    """Accept a limited, validated subset of Gmail's native search operators."""
    matches = re.findall(r"\b(from|to|subject|after|before|newer_than|older_than|is|has|filename|label|category|in):(\"[^\"]+\"|[^\s]+)", text, re.I)
    if not matches:
        return None
    parts = []
    filters = {}
    for operator, raw in matches:
        key = operator.lower()
        value = raw.strip('"')
        if key in {"from", "to", "subject", "filename"}:
            safe = _gmail_clean_value(value)
            if not safe:
                continue
            parts.append(f'{key}:("{safe}")' if key in {"subject", "filename"} else f"{key}:({safe})")
            filters[key] = safe
        elif key in {"after", "before"}:
            normalized = value.replace("-", "/")
            if re.fullmatch(r"\d{4}/\d{2}/\d{2}", normalized):
                parts.append(f"{key}:{normalized}")
                filters[key] = normalized
        elif key in {"newer_than", "older_than"}:
            if re.fullmatch(r"\d{1,4}[dmy]", value.lower()):
                parts.append(f"{key}:{value.lower()}")
                filters[key] = value.lower()
        elif key == "is" and value.lower() in {"read", "unread", "starred", "important"}:
            parts.append(f"is:{value.lower()}")
            filters[key] = value.lower()
        elif key == "has" and value.lower() in {"attachment", "userlabels", "nouserlabels"}:
            parts.append(f"has:{value.lower()}")
            filters[key] = value.lower()
        elif key == "label":
            safe = _gmail_clean_value(value)
            if safe:
                parts.append(f'label:"{safe}"')
                filters[key] = safe
        elif key == "category" and value.lower() in {"primary", "social", "promotions", "updates", "forums"}:
            parts.append(f"category:{value.lower()}")
            filters[key] = value.lower()
        elif key == "in" and value.lower() in {"inbox", "sent", "drafts", "spam", "trash", "anywhere"}:
            parts.append(f"in:{value.lower()}")
            filters[key] = value.lower()
    if not parts:
        return None
    return {"gmail_query": " ".join(parts), "count": 5, "filters": filters}


def _gmail_natural_query(text: str):
    """Translate common natural-language Gmail requests into safe Gmail operators."""
    original = (text or "").strip()
    lower = original.lower()
    advanced = _gmail_parse_advanced_syntax(original)
    if advanced:
        return advanced
    count_match = re.search(r"\b(?:last|latest|show|find|get)\s+(\d{1,2})(?=\s*(?:emails?|messages?)?\s*(?:$|[?.!,;]))|\b(\d{1,2})\s*(?:emails?|messages?)\b", lower)
    count_value = next((group for group in count_match.groups() if group), None) if count_match else None
    count = max(1, min(int(count_value), 50)) if count_value else (50 if re.search(r"\ball\b", lower) else 5)
    terms = []
    filters = {}

    def add(key, value):
        if value:
            filters[key] = value

    # Sender and recipient can be expressed in different word orders.
    sender_match = re.search(r"\b(?:from|by|sent\s+by)\s+(.+?)(?=\s+(?:and|about|regarding|subject|with|before|after|since|until|on|today|yesterday|this\s+week|last\s+week|last\s+month|(?:last|past)\s+\d+\s+days?|unread|read|with\s+attachment|has\s+attachment|having\s+attachment|to:)|[?.!,;]|$)", original, re.I)
    if not sender_match:
        sender_match = re.search(r"\b(?:did|has|have)\s+(.+?)\s+(?:send|sent|email|emailed|mail|mailed)\s+me\b", original, re.I)
    if sender_match:
        sender = _gmail_clean_value(sender_match.group(1))
        sender = re.sub(r"^(?:the\s+)?", "", sender, flags=re.I)
        if sender and sender.lower() not in {"someone", "anyone", "anybody"}:
            add("sender", sender)
            terms.append(("from", sender))

    recipient_match = re.search(r"\bto\s+(.+?)(?=\s+(?:from|about|regarding|subject|before|after|since|until|today|yesterday|unread|read|has\s+attachment)|[?.!,;]|$)", original, re.I)
    if recipient_match:
        recipient = _gmail_clean_value(recipient_match.group(1))
        add("recipient", recipient)
        terms.append(("to", recipient))

    subject_match = re.search(r"\bsubject\s*(?:is|:)?\s*[\"']?(.+?)[\"']?(?=\s+(?:from|to|before|after|since|until|unread|read|has\s+attachment)|[?.!,;]|$)", original, re.I)
    if subject_match:
        subject = _gmail_clean_value(subject_match.group(1))
        add("subject", subject)
        terms.append(("subject", subject))

    # Relative dates.
    today = datetime.now().date()
    date_terms = []
    if re.search(r"\btoday\b", lower):
        date_terms = [f"after:{today.strftime('%Y/%m/%d')}", f"before:{(today.fromordinal(today.toordinal()+1)).strftime('%Y/%m/%d')}"]
        add("date", "today")
    elif re.search(r"\byesterday\b", lower):
        day = today.fromordinal(today.toordinal()-1)
        date_terms = [f"after:{day.strftime('%Y/%m/%d')}", f"before:{today.strftime('%Y/%m/%d')}"]
        add("date", "yesterday")
    elif re.search(r"\b(last|past)\s+(\d+)\s+days?\b", lower):
        days = min(3650, int(re.search(r"\b(?:last|past)\s+(\d+)\s+days?\b", lower).group(1)))
        date_terms = [f"newer_than:{days}d"]
        add("date", f"last {days} days")
    elif re.search(r"\b(this|current)\s+week\b", lower):
        monday = today.fromordinal(today.toordinal() - today.weekday())
        date_terms = [f"after:{monday.strftime('%Y/%m/%d')}"]
        add("date", "this week")
    elif re.search(r"\blast\s+week\b", lower):
        monday = today.fromordinal(today.toordinal() - today.weekday())
        previous = monday.fromordinal(monday.toordinal()-7)
        date_terms = [f"after:{previous.strftime('%Y/%m/%d')}", f"before:{monday.strftime('%Y/%m/%d')}"]
        add("date", "last week")
    elif re.search(r"\blast\s+month\b", lower):
        first_this = today.replace(day=1)
        last_month_end = first_this.fromordinal(first_this.toordinal()-1)
        first_last = last_month_end.replace(day=1)
        date_terms = [f"after:{first_last.strftime('%Y/%m/%d')}", f"before:{first_this.strftime('%Y/%m/%d')}"]
        add("date", "last month")

    if re.search(r"\bunread\b", lower):
        date_terms.append("is:unread"); add("read_status", "unread")
    elif re.search(r"\bread\b", lower):
        date_terms.append("is:read"); add("read_status", "read")
    if re.search(r"\b(?:has|with|having)\s+(?:an?\s+)?attachments?\b|\battachments?\b", lower):
        date_terms.append("has:attachment"); add("attachment", True)
    if re.search(r"\bstarred\b|\bstarred\s+emails?\b", lower):
        date_terms.append("is:starred"); add("starred", True)
    if re.search(r"\bimportant\b|\bpriority\s+emails?\b", lower):
        date_terms.append("is:important"); add("important", True)
    if re.search(r"\bsent\s+(?:emails?|messages?)\b|\bin\s+my\s+sent\b", lower):
        date_terms.append("in:sent"); add("folder", "sent")
    if re.search(r"\bin\s+spam\b|\bspam\s+emails?\b", lower):
        date_terms.append("in:spam"); add("folder", "spam")
    if re.search(r"\bin\s+trash\b|\bdeleted\s+emails?\b", lower):
        date_terms.append("in:trash"); add("folder", "trash")
    if re.search(r"\b(?:anywhere|all\s+mail)\b", lower):
        date_terms.append("in:anywhere"); add("folder", "anywhere")

    category_match = re.search(r"\b(?:in\s+)?(primary|social|promotions|updates|forums)\s+(?:tab|category|emails?|messages?)?\b", lower)
    if category_match:
        category = category_match.group(1)
        date_terms.append(f"category:{category}")
        add("category", category)

    # Remove intent/control words and extracted values to leave topic/body keywords.
    cleaned = original
    for pattern in [
        r"\b(?:from|by|sent\s+by)\s+.+?(?=\s+(?:and|about|regarding|subject|with|before|after|since|until|on|today|yesterday|this\s+week|last\s+week|last\s+month|(?:last|past)\s+\d+\s+days?|unread|read|with\s+attachment|has\s+attachment)|[?.!,;]|$)",
        r"\b(?:did|has|have)\s+.+?\s+(?:send|sent|email|emailed|mail|mailed)\s+me\b",
        r"\bto\s+.+?(?=\s+(?:from|about|regarding|subject|before|after|since|until|today|yesterday|unread|read|has\s+attachment)|[?.!,;]|$)",
        r"\bsubject\s*(?:is|:)?\s*[\"']?.+?[\"']?(?=\s+(?:from|to|before|after|since|until|unread|read)|[?.!,;]|$)",
    ]:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:please|can|could|would|you|vosi|gmail|emails?|e-mail|mail|messages?|message|inbox|check|search|find|look|show|read|list|tell|me|my|i|the|a|an|is|are|was|were|did|do|does|have|has|had|got|get|any|all|latest|recent|newest|last|first|whether|if|there|something|anything|for|about|regarding|with|without|past|day|days|month|months|year|years|attachment|attachments|unread|read|starred|important|today|yesterday|this|week|month|sent|received|from|by|to|on|before|after|since|until|in|tab|category)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\d{1,2}\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9@._+\-\"'\s]", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" '\"")
    if cleaned and len(cleaned) > 1:
        add("keywords", cleaned)
        # Quoted phrase is more predictable for multi-word natural-language topics.
        terms.append(("text", cleaned))

    query_parts = []
    for kind, value in terms:
        safe = _gmail_clean_value(value).replace('"', "")
        if not safe:
            continue
        if kind == "from":
            query_parts.append(f"from:({safe})")
        elif kind == "to":
            query_parts.append(f"to:({safe})")
        elif kind == "subject":
            query_parts.append(f'subject:("{safe}")')
        else:
            query_parts.append(safe)
    query_parts.extend(date_terms)
    return {"gmail_query": " ".join(query_parts), "count": count, "filters": filters}


@app.post("/gmail/search")
def search_gmail_natural(req: GmailSearchRequest):
    original = (req.query or "").strip()
    if not original or len(original) > 500:
        return {"success": False, "error": "Enter a Gmail search under 500 characters."}
    parsed = None
    try:
        ai_intent = interpret_gmail_search(original)
        parsed = _gmail_query_from_ai_intent(ai_intent) if ai_intent else None
    except Exception:
        parsed = None
    if parsed is None:
        parsed = _gmail_natural_query(original)
    try:
        credentials = _gmail_credentials()
        if not credentials:
            return {"success": False, "connected": False, "error": "Gmail is not connected. Use the VOSI Connectors menu and choose Connect Gmail first."}
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        safe_count = max(1, min(int(req.count or parsed["count"]), 50))
        response = service.users().messages().list(
            userId="me", maxResults=safe_count, q=parsed["gmail_query"] or None
        ).execute()
        messages = []
        for item in response.get("messages", []):
            message = service.users().messages().get(
                userId="me", id=item["id"], format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"]
            ).execute()
            headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
            messages.append({
                "id": message.get("id"),
                "sender": headers.get("from", "Unknown sender"),
                "recipient": headers.get("to", ""),
                "subject": headers.get("subject", "(No subject)"),
                "date": headers.get("date", ""),
                "snippet": message.get("snippet", ""),
                "unread": "UNREAD" in message.get("labelIds", []),
                "starred": "STARRED" in message.get("labelIds", []),
                "important": "IMPORTANT" in message.get("labelIds", []),
                "has_attachment": _gmail_has_attachment(message.get("payload", {}))
            })
        return {
            "success": True, "connected": True, "count": len(messages),
            "search_text": original, "gmail_query": parsed["gmail_query"],
            "filters": parsed["filters"], "messages": messages
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.get("/gmail/messages")
def latest_gmail_messages(count: int = 5, q: str = ""):
    """Read latest Gmail messages, or search using Gmail's native query syntax."""
    safe_count = max(1, min(count, 10))
    search_query = (q or "").strip()[:200]
    try:
        credentials = _gmail_credentials()
        if not credentials:
            return {"success": False, "connected": False, "error": "Gmail is not connected. Use the VOSI Connectors menu and choose Connect Gmail first."}
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        list_args = {"userId": "me", "maxResults": safe_count}
        if search_query:
            list_args["q"] = search_query
        response = service.users().messages().list(**list_args).execute()
        messages = []
        for item in response.get("messages", []):
            message = service.users().messages().get(
                userId="me", id=item["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {header["name"].lower(): header["value"] for header in message.get("payload", {}).get("headers", [])}
            messages.append({
                "id": message.get("id"),
                "sender": headers.get("from", "Unknown sender"),
                "subject": headers.get("subject", "(No subject)"),
                "date": headers.get("date", ""),
                "snippet": message.get("snippet", "")
            })
        return {"success": True, "connected": True, "count": len(messages), "query": search_query, "messages": messages}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


from pipeline import ScreenPipeline
from brain import analyze_screen_question, draft_letter, interpret_gmail_search
from database import save_interaction, get_recent_interactions, get_recent_tasks, get_recent_observations, save_task_state

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
