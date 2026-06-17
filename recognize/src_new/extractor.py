"""
extractor.py - 视频抽帧模块

策略：
  - 按 1 fps 均匀抽帧
  - 每帧强制缩放至 400×225（16:9）
  - 支持中文路径（np.fromfile + cv2.imdecode）

输出：
  - {视频同目录}/{视频名}/frames/  目录下的 JPEG 文件，命名为 frame_XXXXX.jpg
  - 返回 list[FrameMeta]，包含每帧的 index、时间戳、路径
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

FRAME_W = 400
FRAME_H = 225
SAMPLE_FPS = 1          # 每秒取 1 帧
JPEG_QUALITY = 85       # JPEG 压缩质量


# ──────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────

@dataclass
class FrameMeta:
    index: int          # 帧序号（0-based）
    timestamp: float    # 时间戳（秒）
    path: str           # 保存路径（相对于 work_dir）


# ──────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────

def _imwrite_unicode(path: str, img: np.ndarray, quality: int = JPEG_QUALITY) -> bool:
    """cv2.imwrite 的中文路径兼容版本。"""
    ext = Path(path).suffix.lower()
    encode_param = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext in (".jpg", ".jpeg") else []
    ok, buf = cv2.imencode(ext, img, encode_param)
    if not ok:
        return False
    buf.tofile(path)
    return True


# ──────────────────────────────────────────────
# 核心函数
# ──────────────────────────────────────────────

def extract_frames(
    video_path: str | Path,
    output_dir: str | Path | None = None,
    sample_fps: int = SAMPLE_FPS,
    frame_w: int = FRAME_W,
    frame_h: int = FRAME_H,
    overwrite: bool = False,
) -> list[FrameMeta]:
    """
    从视频中按 sample_fps 抽帧，缩放至 frame_w × frame_h，保存为 JPEG。

    帧文件存放在视频同目录下的 {视频名}/frames/，避免重复抽帧。
    output_dir 已废弃（保留参数兼容旧调用，但不再使用）。

    Args:
        video_path:  输入视频路径（支持中文）
        output_dir:  已废弃，忽略
        sample_fps:  抽帧速率（帧/秒），默认 1
        frame_w:     输出帧宽度，默认 400
        frame_h:     输出帧高度，默认 225
        overwrite:   若元数据文件已存在，是否重新抽帧

    Returns:
        list[FrameMeta]，按时间顺序排列
    """
    video_path = Path(video_path)
    work_dir = video_path.parent / video_path.stem
    frames_dir = work_dir / "frames"
    meta_path = work_dir / "frames_meta.json"

    # ── 检查缓存 ──
    if not overwrite and meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        metas = [FrameMeta(**m) for m in raw]
        print(f"[extractor] 使用缓存：{len(metas)} 帧（{meta_path}）")
        return metas

    frames_dir.mkdir(parents=True, exist_ok=True)

    # ── 打开视频 ──
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video_path}")

    video_fps: float = cap.get(cv2.CAP_PROP_FPS)
    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s: float = total_frames / video_fps if video_fps > 0 else 0

    print(f"[extractor] 视频: {video_path.name}")
    print(f"[extractor] 原始 FPS={video_fps:.2f}  总帧数={total_frames}  时长={duration_s:.1f}s")
    print(f"[extractor] 抽帧: {sample_fps} fps → 输出尺寸 {frame_w}×{frame_h}")
    print(f"[extractor] 帧目录: {frames_dir}")

    # 每隔多少原始帧取 1 帧
    frame_interval = max(1, round(video_fps / sample_fps))

    metas: list[FrameMeta] = []
    frame_idx = 0      # 视频原始帧计数
    sample_idx = 0     # 输出帧序号

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            timestamp = frame_idx / video_fps

            # 缩放
            resized = cv2.resize(frame, (frame_w, frame_h), interpolation=cv2.INTER_AREA)

            # 保存
            fname = f"frame_{sample_idx:05d}.jpg"
            fpath = frames_dir / fname
            _imwrite_unicode(str(fpath), resized)

            metas.append(FrameMeta(
                index=sample_idx,
                timestamp=round(timestamp, 3),
                path=str(fpath.relative_to(work_dir)),
            ))

            sample_idx += 1

            # 进度
            if sample_idx % 60 == 0:
                pct = timestamp / duration_s * 100 if duration_s > 0 else 0
                print(f"[extractor]   {sample_idx} 帧 / {timestamp:.0f}s ({pct:.0f}%)")

        frame_idx += 1

    cap.release()

    # ── 保存元数据 ──
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump([asdict(m) for m in metas], f, ensure_ascii=False, indent=2)

    print(f"[extractor] 完成：共 {len(metas)} 帧，元数据 → {meta_path}")
    return metas


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python extractor.py <视频路径> [fps=1]")
        sys.exit(1)

    _video = sys.argv[1]
    _fps = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    results = extract_frames(_video, sample_fps=_fps)
    print(f"\n抽帧结果：{len(results)} 帧")
    for m in results[:5]:
        print(f"  [{m.index:05d}] t={m.timestamp:.1f}s  {m.path}")
    if len(results) > 5:
        print(f"  ... （共 {len(results)} 帧）")
