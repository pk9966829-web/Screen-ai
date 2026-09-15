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

    def get_task_state(self):
        return {
            "task": self.task,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "next_step": self.next_step,
            "created_at": self.created_at
        }