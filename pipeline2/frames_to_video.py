"""
frames_to_video.py — 新 pipeline 第一步(下半):把抽出的帧拼回一个预览视频

- 读取 frames_meta.json（保证顺序与时间戳一致），回退为目录内排序
- 用 cv2.VideoWriter 按指定播放帧率拼成 mp4（不依赖 ffmpeg）
- 每帧左上角烧录 时间戳/帧号，方便对着 ground_truth 核对

用法:
    python frames_to_video.py <帧目录> [--fps 10] [--out preview.mp4]
    # 帧目录 = extract_frames.py 的 --out（含 frames/ 与 frames_meta.json）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np


def _imread_unicode(path: Path) -> np.ndarray | None:
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _load_order(work_dir: Path) -> list[tuple[Path, float, int]]:
    """返回 [(帧路径, 时间戳, 帧号)]，优先用 frames_meta.json。"""
    meta_path = work_dir / "frames_meta.json"
    if meta_path.exists():
        metas = json.loads(meta_path.read_text(encoding="utf-8"))
        out = []
        for m in metas:
            out.append((work_dir / m["path"], float(m["timestamp"]), int(m["index"])))
        return out
    # 回退:直接扫 frames/ 目录
    frames_dir = work_dir / "frames"
    files = sorted(frames_dir.glob("frame_*.jpg"))
    return [(p, float(i), i) for i, p in enumerate(files)]


def frames_to_video(work_dir: Path, out_path: Path, play_fps: float = 10.0) -> None:
    items = _load_order(work_dir)
    if not items:
        raise RuntimeError(f"没有找到帧: {work_dir}")

    first = _imread_unicode(items[0][0])
    if first is None:
        raise RuntimeError(f"无法读取首帧: {items[0][0]}")
    h, w = first.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, play_fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError("VideoWriter 打开失败（编码器不可用）")

    print(f"[stitch] {len(items)}帧 → {w}x{h} @ {play_fps}fps")
    speedup = play_fps / 1.0  # 抽帧为 1fps 时的加速倍数（仅用于打印提示）
    written = 0
    for path, ts, idx in items:
        img = _imread_unicode(path)
        if img is None:
            print(f"[stitch] 跳过损坏帧: {path}", file=sys.stderr)
            continue
        if img.shape[:2] != (h, w):
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        # 烧录时间戳 / 帧号
        mm, ss = divmod(int(ts), 60)
        label = f"{mm:02d}:{ss:02d}  #{idx}"
        cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0), 1, cv2.LINE_AA)
        writer.write(img)
        written += 1
    writer.release()

    out_dur = written / play_fps
    print(f"[stitch] 完成: {written}帧 → {out_path}")
    print(f"[stitch] 预览时长 {out_dur:.1f}s（约 {speedup:.0f}x 加速）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("work_dir", help="含 frames/ 和 frames_meta.json 的目录")
    ap.add_argument("--fps", type=float, default=10.0, help="预览播放帧率")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    work_dir = Path(args.work_dir).expanduser()
    out_path = (Path(args.out).expanduser() if args.out
                else work_dir / f"preview_{int(args.fps)}fps.mp4")
    frames_to_video(work_dir, out_path, args.fps)


if __name__ == "__main__":
    main()
