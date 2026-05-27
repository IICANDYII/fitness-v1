from typing import Dict

from .base import Skill


class PoseTracker(Skill):
    """Track rep count and form quality from pose data (in-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {exercise, keypoints, confidence}
        Output: {rep_count, phase, tempo, rom, quality_score}
        """
        pass
