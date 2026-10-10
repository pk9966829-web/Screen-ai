from datetime import datetime


MAX_OBSERVATIONS = 12
MAX_INTERACTIONS = 20


class ContextEngine:
    def __init__(self):
        self.observations = []
        self.interactions = []

    def add_observation(self, observation):
        record = {
            "timestamp": datetime.now().isoformat(),
            "observation": observation,
        }
        self.observations.append(record)
        self.observations = self.observations[-MAX_OBSERVATIONS:]
        return record

    def get_recent_observations(self, limit=5):
        return self.observations[-max(0, limit):]

    def add_interaction(self, question, answer, screens_considered=0, task=None):
        record = {
            "timestamp": datetime.now().isoformat(),
            "question": str(question)[:1000],
            "answer": str(answer)[:2000],
            "screens_considered": int(screens_considered or 0),
            "task": task or {},
        }
        self.interactions.append(record)
        self.interactions = self.interactions[-MAX_INTERACTIONS:]
        return record

    def get_recent_interactions(self, limit=8):
        return self.interactions[-max(0, limit):]

    def clear(self):
        self.observations.clear()
        self.interactions.clear()
