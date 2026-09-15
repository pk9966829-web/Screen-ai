from observation import observe_image
from context import ContextEngine
from task import TaskEngine
from database import (
    initialize_database,
    save_observation,
    get_recent_observations
)


class ScreenPipeline:
    def __init__(self):
        self.context = ContextEngine()
        self.task = TaskEngine()

        initialize_database()

    def start_task(self, task_name):
        return self.task.start_task(task_name)

    def set_current_step(self, step):
        return self.task.set_current_step(step)

    def complete_step(self, step):
        return self.task.complete_step(step)

    def set_next_step(self, step):
        return self.task.set_next_step(step)

    def process_image(self, file_path: str):
        observation_result = observe_image(file_path)

        if not observation_result["success"]:
            return observation_result

        observation = observation_result["observation"]

        # Add observation to current session context
        context_record = self.context.add_observation(
            observation
        )

        # Save observation permanently
        save_observation(observation)

        # Get persistent history
        stored_history = get_recent_observations()

        return {
            "success": True,
            "observation": observation,
            "context_record": context_record,
            "recent_context": self.context.get_recent_observations(),
            "stored_history": stored_history,
            "task_state": self.task.get_task_state()
        }

    def get_state(self):
        return {
            "task": self.task.get_task_state(),
            "recent_context": self.context.get_recent_observations(),
            "stored_history": get_recent_observations()
        }