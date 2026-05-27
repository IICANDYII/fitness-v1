from typing import Dict

from .base import Skill


class ReportGenerator(Skill):
    """Generate a human-readable post-workout report (post-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {session, analysis, calories, user_profile}
        Output: {summary, highlights, next_session_suggestion}
        """
        pass
