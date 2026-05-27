import asyncio
from typing import Callable, Optional


class VideoStreamServer:
    """WebRTC / RTSP video stream receiver."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self._frame_callback: Optional[Callable] = None

    def on_frame(self, callback: Callable):
        self._frame_callback = callback

    async def start(self):
        pass
