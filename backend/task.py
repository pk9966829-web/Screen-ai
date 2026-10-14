from datetime import datetime
from uuid import uuid4


class TaskEngine:
    def __init__(self):
        self.task = None
        self.current_step = None
        self.completed_steps = []
        self.next_step = None
        self.created_at = None
        self.task_key = None

    def start_task(self, task_name):
        self.task_key = uuid4().hex
        self.task = task_name
        self.current_step = None
        self.completed_steps = []
        self.next_step = None
        self.created_at = datetime.now().isoformat()
        return self.get_task_state()

    def restore_task_state(self, state):
        """Restore the last persisted active task after a backend restart."""
        if not isinstance(state, dict) or not state.get("task"):
            return self.get_task_state()
        self.task_key = state.get("task_key")
        self.task = state.get("task")
        self.current_step = state.get("current_step")
        self.completed_steps = list(state.get("completed_steps") or [])[-30:]
        self.next_step = state.get("next_step")
        self.created_at = state.get("created_at")
        return self.get_task_state()

    def set_current_step(self, step):
        self.current_step = step
        return self.get_task_state()

    def complete_step(self, step):
        if step not in self.completed_steps:
            self.completed_steps.append(step)
        return self.get_task_state()

    def set_next_step(self, step):
        self.next_step = step
        return self.get_task_state()

    def apply_workflow_update(self, update):
        # Apply conservative workflow suggestions without erasing prior progress.
        if not isinstance(update, dict):
            return self.get_task_state()
        task_name = update.get('task_name')
        # AI inference may suggest a task label, but must never silently replace
        # an active user-created task. Only initialize an empty tracker.
        if not self.task and isinstance(task_name, str) and task_name.strip():
            self.start_task(task_name.strip()[:200])
        current = update.get('current_step')
        if isinstance(current, str) and current.strip():
            self.current_step = current.strip()[:300]
        completed = update.get('confirmed_completed_steps', [])
        if isinstance(completed, list):
            for step in completed:
                if isinstance(step, str) and step.strip() and step.strip() not in self.completed_steps:
                    self.completed_steps.append(step.strip()[:300])
            self.completed_steps = self.completed_steps[-30:]
        next_step = update.get('next_step')
        if isinstance(next_step, str) and next_step.strip():
            self.next_step = next_step.strip()[:300]
        return self.get_task_state()

    def get_task_state(self):
        return {
            'task_key': self.task_key,
            'task': self.task,
            'current_step': self.current_step,
            'completed_steps': self.completed_steps,
            'next_step': self.next_step,
            'created_at': self.created_at,
        }
