"""
extract_frames.py — 新 pipeline 第一步：视频抽帧

- 1fps 均匀抽帧（上游约束）
- 缩放到 400×225
- 支持中文路径（np.fromfile / buf.tofile）
- 输出 frames/ + frames_meta.json

用法:
    python extract_frames.py <视频路径> [--fps 1] [--w 400] [--h 225] [--out DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class FrameMeta:
    index: int        # 输出帧序号（0-based）
    timestamp: float  # 视频内时间戳（秒）
    path: str         # 相对 out_dir 的路径


def _imwrite_unicode(path: Path, img: np.ndarray, quality: int = 85) -> None:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError(f"编码失败: {path}")
    buf.tofile(str(path))


def extract_frames(
    video_path: Path,
    out_dir: Path,
    sample_fps: float = 1.0,
    frame_w: int = 400,
    frame_h: int = 225,
) -> list[FrameMeta]:
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dur = total / src_fps if src_fps else 0.0
    interval = max(1, round(src_fps / sample_fps))  # 每隔多少原始帧取一帧

    print(f"[extract] {video_path.name}")
    print(f"[extract] 源 {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
          f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {src_fps:.2f}fps  "
          f"{total}帧  {dur:.1f}s")
    print(f"[extract] 抽 {sample_fps}fps (每{interval}帧取1) → {frame_w}x{frame_h}")

    metas: list[FrameMeta] = []
    src_idx = 0
    out_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if src_idx % interval == 0:
            ts = src_idx / src_fps if src_fps else float(out_idx)
            resized = cv2.resize(frame, (frame_w, frame_h), interpolation=cv2.INTER_AREA)
            fname = f"frame_{out_idx:05d}.jpg"
            _imwrite_unicode(frames_dir / fname, resized)
            metas.append(FrameMeta(out_idx, round(ts, 3), f"frames/{fname}"))
            out_idx += 1
            if out_idx % 60 == 0:
                pct = ts / dur * 100 if dur else 0
                print(f"[extract]   {out_idx}帧 / {ts:.0f}s ({pct:.0f}%)")
        src_idx += 1
    cap.release()

    meta_path = out_dir / "frames_meta.json"
    meta_path.write_text(
        json.dumps([asdict(m) for m in metas], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[extract] 完成: {len(metas)}帧 → {frames_dir}")
    print(f"[extract] 元数据 → {meta_path}")
    return metas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--w", type=int, default=400)
    ap.add_argument("--h", type=int, default=225)
    ap.add_argument("--out", default=None, help="输出目录，默认 视频同目录/视频名")
    args = ap.parse_args()

    video = Path(args.video).expanduser()
    if not video.exists():
        print(f"视频不存在: {video}", file=sys.stderr)
        sys.exit(1)
    out_dir = Path(args.out).expanduser() if args.out else video.parent / video.stem
    extract_frames(video, out_dir, args.fps, args.w, args.h)


if __name__ == "__main__":
    main()
