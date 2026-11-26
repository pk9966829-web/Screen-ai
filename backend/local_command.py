"""API-free, allowlisted local command router for CHERRY AI (Windows desktop)."""
from __future__ import annotations

import ast
import base64
import ctypes
import os
import platform
import re
import subprocess
import threading
import urllib.parse
import uuid
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

APP_ALIASES = {
    "chrome": ("chrome", "chrome.exe"),
    "google chrome": ("chrome", "chrome.exe"),
    "edge": ("msedge", "msedge.exe"),
    "microsoft edge": ("msedge", "msedge.exe"),
    "vscode": ("code", "Code.exe"),
    "visual studio code": ("code", "Code.exe"),
    "notepad": ("notepad", "notepad.exe"),
    "calculator": ("calc", "Calculator.exe"),
    "file explorer": ("explorer", "explorer.exe"),
    "explorer": ("explorer", "explorer.exe"),
    "settings": ("ms-settings:", None),
    "task manager": ("taskmgr", "Taskmgr.exe"),
    "command prompt": ("cmd", "cmd.exe"),
    "cmd": ("cmd", "cmd.exe"),
    "powershell": ("powershell", "powershell.exe"),
    "downloads": (str(Path.home() / "Downloads"), None),
    "desktop": (str(Path.home() / "Desktop"), None),
    "documents": (str(Path.home() / "Documents"), None),
    "pictures": (str(Path.home() / "Pictures"), None),
}
SITE_URLS = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "flipkart": "https://www.flipkart.com",
    "amazon": "https://www.amazon.in",
    "chatgpt": "https://chatgpt.com",
    "github": "https://github.com",
}
SEARCH_PATTERNS = [
    (re.compile(r"^(?:search\s+(?:youtube|on youtube)\s+for|youtube\s+search\s+for)\s+(.+)$", re.I), "youtube"),
    (re.compile(r"^(?:search\s+(?:google|web)\s+for|google\s+search\s+for|search\s+for)\s+(.+)$", re.I), "google"),
    (re.compile(r"^(?:search\s+(?:flipkart|on flipkart)\s+for)\s+(.+)$", re.I), "flipkart"),
    (re.compile(r"^(?:search\s+(?:amazon|on amazon)\s+for)\s+(.+)$", re.I), "amazon"),
]

def _open_target(target: str) -> bool:
    if platform.system() == "Windows":
        if target.startswith("ms-settings:"):
            os.startfile(target)  # type: ignore[attr-defined]
        elif Path(target).exists():
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
        return True
    return webbrowser.open(target) if target.startswith(("http://", "https://")) else False

def _calc(expression: str) -> float | int:
    """Evaluate a tiny arithmetic grammar without eval or arbitrary code."""
    tree = ast.parse(expression, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Load)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError("Only basic arithmetic is supported.")
    if any(isinstance(n, ast.Constant) and (not isinstance(n.value, (int, float)) or abs(n.value) > 1e12) for n in ast.walk(tree)):
        raise ValueError("Numeric values must be ordinary numbers.")
    if any(isinstance(n, ast.Pow) for n in ast.walk(tree)) and any(isinstance(n, ast.Constant) and abs(n.value) > 10 for n in ast.walk(tree)):
        raise ValueError("Exponent is too large.")
    result = _safe_eval(tree.body)
    if abs(result) > 1e15:
        raise ValueError("Result is too large.")
    return result

def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.UnaryOp): return -_safe_eval(node.operand) if isinstance(node.op, ast.USub) else _safe_eval(node.operand)
    if isinstance(node, ast.BinOp):
        a, b = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Add): return a+b
        if isinstance(node.op, ast.Sub): return a-b
        if isinstance(node.op, ast.Mult): return a*b
        if isinstance(node.op, ast.Div): return a/b
        if isinstance(node.op, ast.FloorDiv): return a//b
        if isinstance(node.op, ast.Mod): return a%b
        if isinstance(node.op, ast.Pow): return a**b
    raise ValueError("Unsupported expression.")

def _show_alarm(label: str) -> None:
    """Show an interactive Windows alarm with short audible alert pulses."""
    if platform.system() != "Windows":
        return
    try:
        for _ in range(5):
            ctypes.windll.kernel32.Beep(1000, 500)
            threading.Event().wait(0.25)
        ctypes.windll.user32.MessageBoxW(0, label, "CHERRY AI", 0x00000040)
    except Exception:
        # The task still ran; do not leak or crash the backend on notification failure.
        pass


def _schedule_windows_alarm(target: datetime, label: str) -> tuple[bool, str]:
    """Schedule an interactive alarm with Task Scheduler, or a short in-memory timer."""
    if platform.system() != "Windows":
        return False, "Alarms and timers are supported on Windows desktop only."
    now = datetime.now().astimezone()
    delay = max(0, int((target - now).total_seconds()))
    trigger_at = target.replace(second=0, microsecond=0)
    if trigger_at <= now:
        timer = threading.Timer(delay, _show_alarm, args=(label,))
        timer.daemon = True
        timer.start()
        return True, "A short timer was started in this backend process."

    sleep_seconds = max(0, int((target - trigger_at).total_seconds()))
    script = (
        f"Start-Sleep -Seconds {sleep_seconds}; "
        "for ($i = 0; $i -lt 5; $i++) { "
        "[System.Media.SystemSounds]::Exclamation.Play(); "
        "Start-Sleep -Milliseconds 250 }; "
        "Add-Type -AssemblyName PresentationFramework; "
        "[System.Windows.MessageBox]::Show('Your CHERRY AI alarm is due.', "
        "'CHERRY AI', 'OK', 'Information') | Out-Null"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    task_name = "CHERRY AI " + label + " " + uuid.uuid4().hex[:8]
    task_command = "powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand " + encoded
    try:
        result = subprocess.run(
            [
                "schtasks", "/Create", "/TN", task_name, "/TR", task_command,
                "/SC", "ONCE", "/ST", trigger_at.strftime("%H:%M"),
                "/SD", trigger_at.strftime("%x"), "/F", "/IT",
            ],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, "Windows Task Scheduler could not create the alarm."
    if result.returncode != 0:
        return False, "Windows Task Scheduler rejected the alarm. Check Windows task permissions."
    return True, "Scheduled with Windows Task Scheduler."


def route_local_command(message: str) -> dict[str, Any] | None:
    """Return a response for recognized API-free commands, otherwise None."""
    text = (message or "").strip()
    if not text: return None
    low = re.sub(r"\s+", " ", text.lower()).strip()

    # Compound browser command: "open YouTube and search for <query>".
    compound_youtube = re.match(r"^(?:open|launch|start)\s+(?:youtube|you tube)\s+(?:and\s+)?(?:search|look up|find)\s+(?:for\s+)?(.+)$", low, re.I)
    if compound_youtube:
        query = compound_youtube.group(1).strip()
        if not query:
            return {"success": False, "local_command": True, "understanding": "Please tell me what to search for on YouTube."}
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        opened = _open_target(url)
        return {"success": opened, "local_command": True, "understanding": f"Opened YouTube search for “{query}” in your browser." if opened else "Could not open the browser."}

    # Public web/video/product searches: open browser directly, no model/API.
    for pattern, site in SEARCH_PATTERNS:
        match = pattern.match(low)
        if match:
            query = match.group(1).strip()
            if not query: return {"success": False, "local_command": True, "understanding": "Please tell me what to search for."}
            if site == "youtube": url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
            elif site == "google": url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
            else: url = SITE_URLS[site] + "/search?q=" + urllib.parse.quote_plus(query)
            opened = _open_target(url)
            return {"success": opened, "local_command": True, "understanding": f"Opened {site.title()} search for “{query}” in your browser." if opened else "Could not open the browser."}

    open_match = re.match(r"^(?:open|launch|start)\s+(.+)$", low)
    if open_match:
        target = open_match.group(1).strip().rstrip(".")
        if target in SITE_URLS:
            ok = _open_target(SITE_URLS[target])
            return {"success": ok, "local_command": True, "understanding": f"Opened {target.title()}." if ok else "Unable to open website."}
        if target in APP_ALIASES:
            app_target, _ = APP_ALIASES[target]
            ok = _open_target(app_target)
            return {"success": ok, "local_command": True, "understanding": f"Opened {target.title()}." if ok else f"Could not open {target.title()}."}
        if re.match(r"^(https?://)?[\w.-]+\.[a-z]{2,}(?:/.*)?$", target):
            url = target if target.startswith(("http://", "https://")) else "https://" + target
            ok = _open_target(url)
            return {"success": ok, "local_command": True, "understanding": f"Opened {url}." if ok else "Unable to open website."}

    # Calculations, no external model.
    calc_match = re.match(r"^(?:calculate|what is|what's)\s+([0-9.() +\-*/%]+)\??$", low)
    if calc_match:
        try:
            answer = _calc(calc_match.group(1))
            return {"success": True, "local_command": True, "understanding": f"Result: {answer}"}
        except Exception as exc:
            return {"success": False, "local_command": True, "understanding": f"Calculator: {exc}"}

    if low in {"what time is it", "current time", "tell me the time"}:
        return {"success": True, "local_command": True, "understanding": "Local time: " + datetime.now().astimezone().strftime("%I:%M %p")}

    if low in {"lock my pc", "lock pc", "lock computer", "lock my computer"}:
        if platform.system() == "Windows":
            ctypes.windll.user32.LockWorkStation()
            return {"success": True, "local_command": True, "understanding": "Locked your Windows computer."}
        return {"success": False, "local_command": True, "understanding": "PC lock is supported on Windows only."}

    if low in {"shutdown", "shut down my pc", "shutdown my pc", "restart my pc", "restart computer"}:
        action = "restart" if "restart" in low else "shutdown"
        return {"success": True, "local_command": True, "requires_confirmation": True, "understanding": f"I can {action} your PC, but this action requires a separate confirmation step. No system change was made."}

    if low in {"take screenshot", "screenshot", "capture screen"}:
        if platform.system() == "Windows":
            try:
                from PIL import ImageGrab
                folder = Path.home() / "Pictures" / "CHERRY AI Screenshots"
                folder.mkdir(parents=True, exist_ok=True)
                file = folder / "screenshot.png"
                ImageGrab.grab().save(file)
                return {"success": True, "local_command": True, "understanding": f"Screenshot saved at {file}."}
            except Exception as exc:
                return {"success": False, "local_command": True, "understanding": f"Screenshot failed: {exc}"}
        return {"success": False, "local_command": True, "understanding": "Screenshot is supported on Windows desktop only."}

    if low in {"wifi settings", "open wifi settings", "bluetooth settings", "open bluetooth settings"}:
        settings_uri = "ms-settings:network-wifi" if "wifi" in low else "ms-settings:bluetooth"
        ok = _open_target(settings_uri) if platform.system() == "Windows" else False
        return {"success": ok, "local_command": True, "understanding": "Opened Windows settings. Use the settings page to change the radio state." if ok else "Windows settings shortcut is supported on Windows only."}

    volume_match = re.match(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?$", low)
    if volume_match:
        pct = int(volume_match.group(1))
        if not 0 <= pct <= 100: return {"success": False, "local_command": True, "understanding": "Volume must be between 0 and 100%."}
        if platform.system() == "Windows":
            try:
                # Windows multimedia master volume API; no shell or AI/API.
                level = round(65535 * pct / 100)
                ctypes.windll.winmm.waveOutSetVolume(0, level | (level << 16))
                return {"success": True, "local_command": True, "understanding": f"Set Windows master volume to {pct}%."}
            except Exception as exc:
                return {"success": False, "local_command": True, "understanding": f"Could not set volume: {exc}"}
        return {"success": False, "local_command": True, "understanding": "Volume control is supported on Windows desktop only."}

    if low in {"mute", "mute volume", "unmute", "unmute volume", "volume up", "volume down", "increase volume", "decrease volume"}:
        if platform.system() == "Windows":
            key = {"mute":"0xAD","mute volume":"0xAD","unmute":"0xAD","unmute volume":"0xAD","volume up":"0xAF","increase volume":"0xAF","volume down":"0xAE","decrease volume":"0xAE"}[low]
            # Windows key event; mute/unmute toggles, so cannot guarantee state.
            ctypes.windll.user32.keybd_event(int(key, 16), 0, 0, 0)
            ctypes.windll.user32.keybd_event(int(key, 16), 0, 2, 0)
            return {"success": True, "local_command": True, "understanding": "Sent the Windows audio key command. Mute is a toggle, so the current state may change."}
        return {"success": False, "local_command": True, "understanding": "Audio controls are supported on Windows desktop only."}

    alarm_match = re.match(r"^(?:set\s+)?alarm\s+(?:(?:for|at)\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", low)
    if alarm_match:
        hour, minute, meridiem = int(alarm_match.group(1)), int(alarm_match.group(2) or 0), alarm_match.group(3)
        if minute > 59 or hour > 23 or (meridiem and not 1 <= hour <= 12):
            return {"success": False, "local_command": True, "understanding": "That alarm time is invalid. Try a time such as 5:30 PM."}
        if meridiem:
            hour = (hour % 12) + (12 if meridiem == "pm" else 0)
        elif 1 <= hour <= 12:
            return {"success": False, "local_command": True, "understanding": "Please specify AM or PM, for example set alarm for 5 PM."}
        now = datetime.now().astimezone()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        ok, detail = _schedule_windows_alarm(target, "Alarm")
        return {"success": ok, "local_command": True, "understanding": f"Alarm scheduled for {target.strftime('%I:%M %p')}." if ok else detail}

    timer_match = re.match(r"^(?:set\s+)?timer\s+(?:for\s+)?(\d+)\s*(seconds?|minutes?|hours?)$", low)
    if timer_match:
        n, unit = int(timer_match.group(1)), timer_match.group(2)
        seconds = n * (60 if unit.startswith("minute") else 3600 if unit.startswith("hour") else 1)
        if not 1 <= seconds <= 86400:
            return {"success": False, "local_command": True, "understanding": "Timer length must be between 1 second and 24 hours."}
        if platform.system() != "Windows":
            return {"success": False, "local_command": True, "understanding": "Timer shortcut is Windows-only."}
        target = datetime.now().astimezone() + timedelta(seconds=seconds)
        ok, detail = _schedule_windows_alarm(target, "Timer")
        return {"success": ok, "local_command": True, "understanding": f"Timer set for {n} {unit}." if ok else detail}

    return None
