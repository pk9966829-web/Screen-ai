from datetime import datetime


class TaskEngine:
    def __init__(self):
        self.task = None
        self.current_step = None
        self.completed_steps = []
        self.next_step = None
        self.created_at = None

    def start_task(self, task_name):
        self.task = task_name
        self.current_step = None
        self.completed_steps = []
        self.next_step = None
        self.created_at = datetime.now().isoformat()
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
        if isinstance(task_name, str) and task_name.strip():
            if not self.task or task_name.strip().lower() != self.task.strip().lower():
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
            'task': self.task,
            'current_step': self.current_step,
            'completed_steps': self.completed_steps,
            'next_step': self.next_step,
            'created_at': self.created_at,
        }
