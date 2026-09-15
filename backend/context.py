from datetime import datetime


class ContextEngine:
    def __init__(self):
        self.observations = []

    def add_observation(self, observation):
        record = {
            "timestamp": datetime.now().isoformat(),
            "observation": observation
        }

        self.observations.append(record)

        return record

    def get_recent_observations(self, limit=5):
        return self.observations[-limit:]

    def clear(self):
        self.observations.clear()