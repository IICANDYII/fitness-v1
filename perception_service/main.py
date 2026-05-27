import asyncio

from perception_service.websocket.server import VideoStreamServer
from perception_service.yolo.detector import YOLODetector
from perception_service.pose.estimator import PoseEstimator
from perception_service.state_stream.publisher import StatePublisher


async def main():
    server = VideoStreamServer()
    detector = YOLODetector(model_path="models/yolov11.pt")
    estimator = PoseEstimator()
    publisher = StatePublisher()

    detector.load()

    async def process_frame(frame, user_id: str):
        equipment = detector.detect(frame)
        pose = estimator.estimate(frame)
        publisher.publish_state(user_id, {"equipment": equipment, "pose": pose})

    server.on_frame(process_frame)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
