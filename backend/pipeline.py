from pathlib import Path
from observation import observe_image
from brain import analyze_context
from context import ContextEngine
from task import TaskEngine
from database import initialize_database, save_observation, get_recent_observations


MAX_RECENT_SCREEN_FRAMES = 4


class ScreenPipeline:
    def __init__(self):
        self.context = ContextEngine()
        self.task = TaskEngine()
        self.latest_screen_path = None
        self.recent_screen_frames = []
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
        self.latest_screen_path = str(path)
        context_record = self.context.add_observation(observation)
        save_observation(observation)

        self.recent_screen_frames.append({
            "timestamp": observation.get("timestamp"),
            "filename": path.name,
            "path": str(path),
        })

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
            "recent_screens": [
                {"timestamp": frame["timestamp"], "filename": frame["filename"]}
                for frame in self.recent_screen_frames
            ],
        })
        return {
            "success": True,
            "observation": observation,
            "context_record": context_record,
            "recent_context": recent_context,
            "recent_screens": [
                {"timestamp": frame["timestamp"], "filename": frame["filename"]}
                for frame in self.recent_screen_frames
            ],
            "stored_history": stored_history,
            "task_state": self.task.get_task_state(),
            "brain": brain_result,
        }

    def get_recent_screen_frames(self):
        """Return the bounded frame window for internal AI analysis."""
        return [dict(frame) for frame in self.recent_screen_frames]

    def get_state(self):
        return {
            "task": self.task.get_task_state(),
            "recent_context": self.context.get_recent_observations(),
            "recent_screens": [
                {"timestamp": frame["timestamp"], "filename": frame["filename"]}
                for frame in self.recent_screen_frames
            ],
            "stored_history": get_recent_observations(),
            "latest_screen_available": bool(self.latest_screen_path),
        }
