"""
video_stitcher.py - 低帧率运动区间视频拼接模块

根据 period_result.json 中的 EXERCISE 区间，从已抽帧的帧序列中
将运动区间前后扩充 15 秒，按 1fps/2fps 采样率拼接成低帧率视频（.mp4）。

用法：
  python -m gym_analyzer.video_stitcher <work_dir> <period_result_json> [--fps 1] [--output-dir <dir>]
  python -m gym_analyzer.video_stitcher gym_analyzer/input/1 recognize/visualize/result/v10/1/period_result.json
  python -m gym_analyzer.video_stitcher gym_analyzer/input/2 recognize/visualize/result/v10/2/period_result.json --fps 2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


EXERCISE_PAD_SEC = 15
DEFAULT_FPS = 1
VIDEO_CODEC = "mp4v"
JPEG_SOURCE_FPS = 1


def _imread_unicode(path: str) -> np.ndarray | None:
    buf = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def sec_to_hhmmss(sec: float) -> str:
    s = int(sec)
    h, rem = divmod(s, 3600)
    m, sec_part = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec_part:02d}"


def load_period_result(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    segments = data.get("segments", [])
    return [s for s in segments if s.get("state", "").upper() == "EXERCISE"]


def load_frames_meta(work_dir: Path) -> list[dict]:
    meta_path = work_dir / "frames_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"找不到 frames_meta.json: {meta_path}")
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_frame_path(fm: dict, frames_dir: Path) -> Path:
    name = Path(fm["path"]).name
    p = frames_dir / name
    if p.exists():
        return p
    clean = fm["path"].replace("frames/", "").replace("frames\\", "")
    p = frames_dir / clean
    if p.exists():
        return p
    return frames_dir / name


def stitch_exercise_video(
    frame_metas: list[dict],
    frames_dir: Path,
    start_sec: float,
    end_sec: float,
    output_path: Path,
    target_fps: int = DEFAULT_FPS,
) -> dict | None:
    """
    将指定时间范围内的帧拼接为低帧率视频。

    Args:
        frame_metas:  帧元数据列表 (index, timestamp, path)
        frames_dir:   帧文件目录
        start_sec:    视频起始秒数（已含 pad）
        end_sec:      视频结束秒数（已含 pad）
        output_path:  输出视频路径
        target_fps:   目标帧率（1 或 2）

    Returns:
        dict with video metadata, or None if no frames found
    """
    window_metas = [
        fm for fm in frame_metas
        if start_sec - 0.5 <= fm["timestamp"] <= end_sec + 0.5
    ]
    if not window_metas:
        print(f"  [video_stitcher] 警告：{sec_to_hhmmss(start_sec)}~{sec_to_hhmmss(end_sec)} 无帧")
        return None

    if target_fps == 2 and JPEG_SOURCE_FPS == 1:
        pass

    first_img = _imread_unicode(str(_resolve_frame_path(window_metas[0], frames_dir)))
    if first_img is None:
        print(f"  [video_stitcher] 警告：首帧读取失败")
        return None

    h, w = first_img.shape[:2]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*VIDEO_CODEC)
    writer = cv2.VideoWriter(str(output_path), fourcc, target_fps, (w, h))

    if not writer.isOpened():
        print(f"  [video_stitcher] 错误：无法创建视频文件 {output_path}")
        return None

    written = 0
    skipped = 0

    for fm in window_metas:
        img_path = _resolve_frame_path(fm, frames_dir)
        img = _imread_unicode(str(img_path))

        if img is None:
            skipped += 1
            continue

        if img.shape[:2] != (h, w):
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)

        ts_text = sec_to_hhmmss(fm["timestamp"])
        cv2.putText(img, ts_text, (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, ts_text, (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)

        if target_fps == 2 and JPEG_SOURCE_FPS == 1:
            writer.write(img)
            writer.write(img)
            written += 2
        else:
            writer.write(img)
            written += 1

    writer.release()

    duration_sec = (end_sec - start_sec)
    file_size = output_path.stat().st_size if output_path.exists() else 0

    meta = {
        "path": str(output_path),
        "start_sec": start_sec,
        "end_sec": end_sec,
        "start_time": sec_to_hhmmss(start_sec),
        "end_time": sec_to_hhmmss(end_sec),
        "duration_sec": round(duration_sec, 1),
        "source_frames": len(window_metas),
        "written_frames": written,
        "skipped_frames": skipped,
        "target_fps": target_fps,
        "resolution": f"{w}x{h}",
        "file_size_kb": round(file_size / 1024, 1),
    }

    print(f"  [video_stitcher] 视频已生成: {output_path.name}  "
          f"{len(window_metas)} 帧 → {written} 写入帧  "
          f"{target_fps}fps  {w}x{h}  {file_size / 1024:.0f}KB  "
          f"{sec_to_hhmmss(start_sec)}~{sec_to_hhmmss(end_sec)}")

    return meta


def stitch_all_exercises(
    work_dir: str | Path,
    period_result_path: str | Path,
    target_fps: int = DEFAULT_FPS,
    output_dir: str | Path | None = None,
    pad_sec: float = EXERCISE_PAD_SEC,
) -> list[dict]:
    """
    批量处理：读取 period_result.json，为每个 EXERCISE 区间生成低帧率视频。

    Args:
        work_dir:             帧数据目录（包含 frames_meta.json 和 frames/）
        period_result_path:   period_result.json 路径
        target_fps:           目标帧率（1 或 2）
        output_dir:           视频输出目录（默认 work_dir/exercise_videos/）
        pad_sec:              EXERCISE 区间前后扩充秒数（默认 15）

    Returns:
        list[dict]，每个 dict 包含视频元数据
    """
    work_dir = Path(work_dir)
    period_result_path = Path(period_result_path)

    if output_dir is None:
        output_dir = work_dir / "exercise_videos"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_metas = load_frames_meta(work_dir)
    total_dur = frame_metas[-1]["timestamp"] if frame_metas else 0
    exercises = load_period_result(period_result_path)

    print(f"\n{'=' * 60}")
    print(f"视频拼接：低帧率运动区间视频")
    print(f"帧目录：{work_dir}")
    print(f"区间文件：{period_result_path}")
    print(f"总帧数：{len(frame_metas)}  时长：{sec_to_hhmmss(total_dur)}")
    print(f"EXERCISE 区间数：{len(exercises)}")
    print(f"目标帧率：{target_fps}fps  前后扩充：{pad_sec}s")
    print(f"输出目录：{output_dir}")
    print(f"{'=' * 60}\n")

    results = []
    for idx, seg in enumerate(exercises):
        t_start = seg.get("start_sec", 0.0)
        t_end = seg.get("end_sec", 0.0)
        seg_id = f"exercise_{idx + 1:03d}"

        pad_start = max(0.0, t_start - pad_sec)
        pad_end = min(total_dur, t_end + pad_sec)

        print(f"  [{seg_id}] 原区间: {sec_to_hhmmss(t_start)}~{sec_to_hhmmss(t_end)}  "
              f"扩充后: {sec_to_hhmmss(pad_start)}~{sec_to_hhmmss(pad_end)}")

        video_path = output_dir / f"{seg_id}_{target_fps}fps.mp4"
        frames_dir = work_dir / "frames"

        meta = stitch_exercise_video(
            frame_metas=frame_metas,
            frames_dir=frames_dir,
            start_sec=pad_start,
            end_sec=pad_end,
            output_path=video_path,
            target_fps=target_fps,
        )

        if meta:
            meta["segment_id"] = seg_id
            meta["original_start_sec"] = t_start
            meta["original_end_sec"] = t_end
            meta["original_start_time"] = sec_to_hhmmss(t_start)
            meta["original_end_time"] = sec_to_hhmmss(t_end)
            meta["pad_sec"] = pad_sec
            meta["segment_reason"] = seg.get("reason", "")
            results.append(meta)

    manifest_path = output_dir / "video_manifest.json"
    manifest = {
        "source_work_dir": str(work_dir),
        "period_result": str(period_result_path),
        "target_fps": target_fps,
        "pad_sec": pad_sec,
        "total_exercises": len(exercises),
        "videos_generated": len(results),
        "videos": results,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"完成！生成 {len(results)}/{len(exercises)} 个视频")
    print(f"清单文件：{manifest_path}")
    print(f"{'=' * 60}\n")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="将 EXERCISE 区间拼接为低帧率视频")
    parser.add_argument(
        "work_dir",
        help="帧数据目录（包含 frames_meta.json 和 frames/）")
    parser.add_argument(
        "period_result",
        help="period_result.json 路径")
    parser.add_argument(
        "--fps", type=int, default=DEFAULT_FPS, choices=[1, 2],
        help=f"目标帧率（默认 {DEFAULT_FPS}）")
    parser.add_argument(
        "--output-dir", "-o", default=None,
        help="视频输出目录（默认 <work_dir>/exercise_videos/）")
    parser.add_argument(
        "--pad", type=float, default=EXERCISE_PAD_SEC,
        help=f"EXERCISE 区间前后扩充秒数（默认 {EXERCISE_PAD_SEC}）")

    args = parser.parse_args()

    stitch_all_exercises(
        work_dir=args.work_dir,
        period_result_path=args.period_result,
        target_fps=args.fps,
        output_dir=args.output_dir,
        pad_sec=args.pad,
    )


if __name__ == "__main__":
    main()
