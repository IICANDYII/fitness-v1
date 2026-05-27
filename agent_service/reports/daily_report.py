from typing import Dict
from uuid import UUID
from datetime import date


class DailyReportGenerator:
    """Compile a post-workout daily summary report."""

    def generate(self, user_id: UUID, session_date: date) -> Dict:
        """
        Returns {summary, total_volume, calories, completion_rate, highlights}.
        """
        pass
