"""关键帧抽取：每1秒两帧，缩放到 ≤640 像素，编码为 JPEG。

输入：视频路径 + 输出目录
输出：frames/ 子目录下的 keyframe_{index:04d}.jpg + 内存中的元数据列表
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

from . import config


def _imread_unicode(path: Path, flag: int = cv2.IMREAD_COLOR):
    """cv2.imread 的 Unicode 路径兼容版。

    Windows 上 cv2.imread 用 ANSI 编码处理路径，遇到中文文件夹名（如"5月26日"）
    会读不到文件且不报错。改用 np.fromfile + cv2.imdecode 绕开 cv2 自己的路径处理。
    """
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
        if buf.size == 0:
            return None
        return cv2.imdecode(buf, flag)
    except (OSError, ValueError):
        return None


@dataclass
class FrameMeta:
    """单个抽帧的元数据。"""
    frameIndex: int                      # 0-based
    timestamp: float                     # 秒，相对视频开头
    filename: str                        # 相对 frames_dir 的文件名


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    durationSeconds: float
    totalFrames: int

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def probe_video(video_path: Path) -> VideoInfo:
    """读取视频基本信息（不抽帧）。"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    duration = total / fps if fps > 0 else 0.0
    return VideoInfo(
        width=w, height=h, fps=round(fps, 2),
        durationSeconds=round(duration, 2), totalFrames=total,
    )


def _scaled_size(w: int, h: int, max_dim: int) -> tuple[int, int]:
    """按最大边长等比缩放。"""
    if max(w, h) <= max_dim:
        return w, h
    if w >= h:
        new_w = max_dim
        new_h = int(round(h * max_dim / w))
    else:
        new_h = max_dim
        new_w = int(round(w * max_dim / h))
    return new_w, new_h


def extract_keyframes(video_path: Path, frames_dir: Path) -> tuple[VideoInfo, list[FrameMeta]]:
    """按 SAMPLING_INTERVAL_S 抽帧并写入 frames_dir。

    返回 (视频信息, 抽帧元数据列表)。已抽过的帧（同文件名存在）会被跳过，
    便于断点续跑节省时间。
    """
    frames_dir.mkdir(parents=True, exist_ok=True)

    info = probe_video(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video_path}")

    out_w, out_h = _scaled_size(info.width, info.height, config.KEYFRAME_MAX_DIM)

    frames: list[FrameMeta] = []
    interval = config.SAMPLING_INTERVAL_S
    t = 0.0
    idx = 0

    while t < info.durationSeconds:
        target_frame = int(t * info.fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        if not ret:
            break

        if (out_w, out_h) != (info.width, info.height):
            frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)

        filename = f"keyframe_{idx:04d}.jpg"
        out_path = frames_dir / filename

        if not out_path.exists():
            ok, buf = cv2.imencode(
                ".jpg", frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), config.KEYFRAME_JPEG_QUALITY],
            )
            if ok:
                out_path.write_bytes(buf.tobytes())

        frames.append(FrameMeta(frameIndex=idx, timestamp=round(t, 2), filename=filename))
        idx += 1
        t += interval

    cap.release()
    return info, frames


def compute_motion_scores(frames: list[FrameMeta], frames_dir: Path) -> list[float]:
    """计算相邻帧灰度 absdiff 均值（缩到 160x90），用于辅助 AI 判断"画面是否在动"。

    返回与 frames 等长的列表，第 0 帧 motion = 0.0。
    用 _imread_unicode 兼容中文路径（cv2.imread 在 Windows + 中文路径下会静默失败）。
    """
    scores: list[float] = []
    prev_small = None
    for f in frames:
        img = _imread_unicode(frames_dir / f.filename, cv2.IMREAD_GRAYSCALE)
        if img is None:
            scores.append(0.0)
            prev_small = None
            continue
        small = cv2.resize(img, (160, 90), interpolation=cv2.INTER_AREA)
        if prev_small is None:
            scores.append(0.0)
        else:
            diff = cv2.absdiff(small, prev_small)
            scores.append(round(float(diff.mean()), 2))
        prev_small = small
    return scores
