from typing import Dict
from uuid import UUID


class WorkoutPlanner:
    """Generate and dynamically adjust workout plans based on user state and goals."""

    def generate_plan(self, user_id: UUID, goal: str, state: Dict) -> Dict:
        """Generate a full workout plan.

        Returns plan_json with phases and exercises.
        """
        pass

    def adjust_plan(self, plan: Dict, state: Dict) -> Dict:
        """Adjust an in-progress plan based on real-time fatigue / equipment state."""
        pass
