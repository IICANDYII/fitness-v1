from typing import Dict

from .base import Skill


class CalorieEstimator(Skill):
    """Estimate calories burned during a workout session (post-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {exercises: [{name, sets, reps, weight}], user_weight_kg, duration_min}
        Output: {calories_burned}
        """
        pass
