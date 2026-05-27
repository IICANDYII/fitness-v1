from typing import Dict

from .base import Skill


class SlackingDetector(Skill):
    """Detect when the user has stopped exercising (in-workout)."""

    MOTION_THRESHOLD = 0.2
    DURATION_THRESHOLD = 180  # seconds

    def run(self, input: Dict) -> Dict:
        """
        Input:  {motion_score, duration}
        Output: {slacking, alert}
        """
        motion = input.get("motion_score", 1.0)
        duration = input.get("duration", 0)

        slacking = motion < self.MOTION_THRESHOLD and duration > self.DURATION_THRESHOLD
        return {
            "slacking": slacking,
            "alert": "resume_training" if slacking else None,
        }
