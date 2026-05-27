from typing import Dict, Any


class QueueDetector:
    """Detect equipment queue length and occupancy from video."""

    def detect(self, frame: Any, equipment_id: str) -> Dict:
        """Detect queue status for a piece of equipment.

        Returns {equipment_id, occupied, queue_count}
        """
        pass
