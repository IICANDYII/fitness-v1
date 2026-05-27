from typing import Dict

from .base import Skill


class RecoveryAnalysis(Skill):
    """Assess user recovery status from biometric signals (pre-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {hrv, sleep_score, fatigue}
        Output: {status, adjustment}
        """
        hrv = input.get("hrv", 0)
        fatigue = input.get("fatigue", 0)

        if fatigue > 7 or hrv < 35:
            return {"status": "low_recovery", "adjustment": "-30%"}
        if fatigue > 5 or hrv < 50:
            return {"status": "moderate_recovery", "adjustment": "-10%"}
        return {"status": "ready", "adjustment": "0%"}
