from typing import List, Dict, Any


class YOLODetector:
    """YOLOv11-based gym equipment detection."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None

    def load(self):
        pass

    def detect(self, frame: Any) -> List[Dict]:
        """Detect gym equipment in a video frame.

        Returns list of {equipment, confidence, occupied, bbox}
        """
        pass
