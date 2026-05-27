from typing import Dict

from .base import Skill


class WorkoutAnalyzer(Skill):
    """Analyze completed workout session metrics (post-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {executions: [...], session}
        Output: {total_volume, avg_quality, muscle_groups_hit, highlights}
        """
        pass
