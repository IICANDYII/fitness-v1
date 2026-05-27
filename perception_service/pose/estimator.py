from typing import List, Dict, Any


class PoseEstimator:
    """MediaPipe / ViTPose human pose estimator."""

    def __init__(self, backend: str = "mediapipe"):
        self.backend = backend

    def estimate(self, frame: Any) -> Dict:
        """Extract body keypoints from a video frame.

        Returns {type: "pose", keypoints: [{name, x, y}], confidence}
        """
        pass

    def classify_action(self, keypoint_sequence: List[Dict]) -> Dict:
        """Classify exercise from a sequence of keypoint frames.

        Returns {exercise, rep_count, phase, tempo, rom}
        """
        pass
