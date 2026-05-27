from typing import Dict, List

from .base import Skill


class GymScanner(Skill):
    """Scan gym environment for equipment availability (pre-workout)."""

    def run(self, input: Dict) -> Dict:
        """
        Input:  {equipment_states: [{equipment_id, occupied, queue_count}]}
        Output: {available_equipment: [...], congested_equipment: [...]}
        """
        equipment_states: List[Dict] = input.get("equipment_states", [])

        available = [e for e in equipment_states if not e.get("occupied")]
        congested = [e for e in equipment_states if e.get("queue_count", 0) > 2]

        return {"available_equipment": available, "congested_equipment": congested}
