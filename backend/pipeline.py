from observation import observe_image
from brain import analyze_context
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
        # Step 1: Observe the screen image
        observation_result = observe_image(file_path)

        if not observation_result["success"]:
            return observation_result

        observation = observation_result["observation"]

        # Step 2: Add observation to current session context
        context_record = self.context.add_observation(
            observation
        )

        # Step 3: Save observation permanently
        save_observation(observation)

        # Step 4: Get persistent history
        stored_history = get_recent_observations()

        # Step 5: Ask the mock AI brain to analyze
        # the current screen and context
        brain_result = analyze_context({
            "observation": observation,
            "context": self.context.get_recent_observations(),
            "task": self.task.get_task_state(),
            "history": stored_history
        })

        # Step 6: Return the complete Screen AI pipeline result
        return {
            "success": True,
            "observation": observation,
            "context_record": context_record,
            "recent_context": self.context.get_recent_observations(),
            "stored_history": stored_history,
            "task_state": self.task.get_task_state(),
            "brain": brain_result
        }

    def get_state(self):
        return {
            "task": self.task.get_task_state(),
            "recent_context": self.context.get_recent_observations(),
            "stored_history": get_recent_observations()
        }
