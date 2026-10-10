from pathlib import Path
from PIL import Image, ImageChops, ImageStat
from threading import Lock, Thread
import time
from observation import observe_image
from brain import analyze_context, analyze_screen_transition
from context import ContextEngine
from task import TaskEngine
from database import initialize_database, save_observation, get_recent_observations


MAX_RECENT_SCREEN_FRAMES = 4
MAX_SCREEN_CHANGE_EVENTS = 20
SCREEN_CHANGE_THRESHOLD = 10.0


def _screen_change_score(previous_path: str, current_path: str):
    """Compare small grayscale thumbnails; return a 0-255 mean pixel difference."""
    try:
        with Image.open(previous_path) as previous, Image.open(current_path) as current:
            previous = previous.convert("L").resize((64, 36))
            current = current.convert("L").resize((64, 36))
            difference = ImageChops.difference(previous, current)
            return round(ImageStat.Stat(difference).mean[0], 2)
    except (OSError, ValueError):
        # A comparison failure should never block screen capture or AI questions.
        return None


class ScreenPipeline:
    def __init__(self):
        self.context = ContextEngine()
        self.task = TaskEngine()
        self.latest_screen_path = None
        self.recent_screen_frames = []
        self.screen_change_history = []
        self._transition_lock = Lock()
        self._transition_worker_active = False
        self._last_transition_analysis_at = 0.0
        initialize_database()

    def start_task(self, task_name): return self.task.start_task(task_name)
    def set_current_step(self, step): return self.task.set_current_step(step)
    def complete_step(self, step): return self.task.complete_step(step)
    def set_next_step(self, step): return self.task.set_next_step(step)

    def process_image(self, file_path: str):
        observation_result = observe_image(file_path)
        if not observation_result["success"]:
            return observation_result

        observation = observation_result["observation"]
        path = Path(file_path)
        previous_path = self.latest_screen_path
        change_score = _screen_change_score(previous_path, str(path)) if previous_path else None
        changed = change_score is not None and change_score >= SCREEN_CHANGE_THRESHOLD
        observation["change_score"] = change_score
        observation["screen_changed"] = changed
        observation["change_status"] = (
            "changed" if changed else ("stable" if change_score is not None else "baseline")
        )

        self.latest_screen_path = str(path)
        context_record = self.context.add_observation(observation)
        save_observation(observation)

        frame = {
            "timestamp": observation.get("timestamp"),
            "filename": path.name,
            "path": str(path),
            "change_score": change_score,
            "screen_changed": changed,
            "change_status": observation["change_status"],
        }
        self.recent_screen_frames.append(frame)

        if changed:
            self.screen_change_history.append({
                "timestamp": observation.get("timestamp"),
                "filename": path.name,
                "change_score": change_score,
                "status": "visual_change_detected",
                "note": "Visual difference detected; this alone does not confirm a task step is complete.",
            })
            self.screen_change_history = self.screen_change_history[-MAX_SCREEN_CHANGE_EVENTS:]
            self._maybe_schedule_transition_analysis(previous_path, str(path))

        # Keep only a small rolling window so screen awareness does not
        # accumulate screenshots indefinitely.
        while len(self.recent_screen_frames) > MAX_RECENT_SCREEN_FRAMES:
            expired = self.recent_screen_frames.pop(0)
            expired_path = Path(expired["path"])
            if str(expired_path) != self.latest_screen_path:
                try:
                    expired_path.unlink(missing_ok=True)
                except OSError:
                    pass

        stored_history = get_recent_observations()
        recent_context = self.context.get_recent_observations()
        brain_result = analyze_context({
            "observation": observation,
            "context": recent_context,
            "task": self.task.get_task_state(),
            "history": stored_history,
            "recent_screens": self.get_recent_screen_frames(),
            "screen_changes": self.get_recent_screen_changes(),
        })
        return {
            "success": True,
            "observation": observation,
            "context_record": context_record,
            "recent_context": recent_context,
            "recent_screens": self._public_recent_screens(),
            "screen_changes": self.get_recent_screen_changes(),
            "stored_history": stored_history,
            "task_state": self.task.get_task_state(),
            "brain": brain_result,
        }

    def _maybe_schedule_transition_analysis(self, previous_path, current_path):
        # Only run vision inference for an active task, at most once every 15 seconds.
        if not self.task.task or not previous_path or not Path(previous_path).is_file():
            return
        now = time.monotonic()
        with self._transition_lock:
            if self._transition_worker_active or now - self._last_transition_analysis_at < 15:
                return
            self._transition_worker_active = True
            self._last_transition_analysis_at = now
        task_snapshot = self.task.get_task_state()
        Thread(
            target=self._run_transition_analysis,
            args=(previous_path, current_path, task_snapshot),
            daemon=True,
            name="vosi-screen-transition",
        ).start()

    def _run_transition_analysis(self, previous_path, current_path, task_snapshot):
        try:
            result = analyze_screen_transition(previous_path, current_path, task_snapshot)
            if not result.get("success"):
                return
            update = result.get("workflow_update") or {}
            # Do not apply a late result to a different task or a task that was stopped.
            if self.task.task != task_snapshot.get("task"):
                return
            if update:
                self.task.apply_workflow_update(update)
            event = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "filename": Path(current_path).name,
                "change_score": None,
                "status": "transition_interpreted",
                "confidence": result.get("confidence", 0),
                "evidence": result.get("evidence", ""),
                "current_step": update.get("current_step"),
                "next_step": update.get("next_step"),
                "note": "AI interpretation of visible screen evidence; verify if uncertain.",
            }
            self.screen_change_history.append(event)
            self.screen_change_history = self.screen_change_history[-MAX_SCREEN_CHANGE_EVENTS:]
        except Exception:
            # Background inference must never interrupt screen capture.
            pass
        finally:
            with self._transition_lock:
                self._transition_worker_active = False

    def _public_recent_screens(self):
        return [
            {
                "timestamp": frame["timestamp"],
                "filename": frame["filename"],
                "change_score": frame.get("change_score"),
                "screen_changed": frame.get("screen_changed", False),
                "change_status": frame.get("change_status", "baseline"),
            }
            for frame in self.recent_screen_frames
        ]

    def get_recent_screen_frames(self):
        """Return the bounded frame window for internal AI analysis."""
        return [dict(frame) for frame in self.recent_screen_frames]

    def get_recent_screen_changes(self, limit=10):
        """Return recent detected visual transitions, newest last."""
        return [dict(event) for event in self.screen_change_history[-max(0, limit):]]

    def get_state(self):
        return {
            "task": self.task.get_task_state(),
            "recent_context": self.context.get_recent_observations(),
            "recent_screens": self._public_recent_screens(),
            "screen_changes": self.get_recent_screen_changes(),
            "stored_history": get_recent_observations(),
            "latest_screen_available": bool(self.latest_screen_path),
        }
