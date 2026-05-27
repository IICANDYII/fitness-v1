from typing import Dict

from .base import Skill


class QueueDetector(Skill):
    """Detect equipment queue status and suggest alternatives (in-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {equipment_id, queue_count, available_alternatives: [...]}
        Output: {should_wait, suggested_alternative}
        """
        queue = input.get("queue_count", 0)
        alternatives = input.get("available_alternatives", [])

        if queue > 2 and alternatives:
            return {"should_wait": False, "suggested_alternative": alternatives[0]}
        return {"should_wait": True, "suggested_alternative": None}
