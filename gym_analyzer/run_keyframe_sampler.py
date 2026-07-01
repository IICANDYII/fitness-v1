"""
run_keyframe_sampler.py - 批量运行 Ego-Interaction Keyframe Sampler

对 gym_analyzer/input/ 下的所有视频执行关键帧重新采样。

用法：
  # 处理所有视频
  python -m gym_analyzer.run_keyframe_sampler

  # 处理单个视频
  python -m gym_analyzer.run_keyframe_sampler --video input/8.mp4

  # 不使用 Roboflow API（仅本地模型）
  python -m gym_analyzer.run_keyframe_sampler --no-roboflow

  # 指定单个 segment
  python -m gym_analyzer.run_keyframe_sampler --video input/8.mp4 --start 30 --end 90
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .ego_keyframe_sampler import (
    extract_keyframes,
    process_video_segments,
    load_config,
)
from .config import VIDEO_EXTS


INPUT_DIR = Path(__file__).parent / "input"
V10_RESULT_DIR = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "v10"


def _find_videos(input_dir: Path) -> list[Path]:
    """查找目录下所有视频文件。"""
    videos = []
    for f in sorted(input_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in VIDEO_EXTS:
            videos.append(f)
    return videos


def _load_period_result(video_path: Path) -> list[dict] | None:
    """加载视频对应的 Phase1 period_result.json。"""
    work_dir = video_path.parent / video_path.stem
    v10_dir = V10_RESULT_DIR / video_path.stem

    candidates = [
        work_dir / "period_result_adjusted.json",
        work_dir / "period_result.json",
        v10_dir / "period_result.json",
    ]
    for p in candidates:
        if p.exists():
            print(f"[Batch] 使用 period_result: {p}")
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            segments = data.get("segments", data) if isinstance(data, dict) else data
            if isinstance(segments, list):
                return segments
    return None


def run_single_video(
    video_path: Path,
    config: dict,
    use_roboflow: bool = True,
    start_sec: float | None = None,
    end_sec: float | None = None,
    overwrite: bool = False,
) -> list[dict]:
    """对单个视频运行关键帧采样。"""
    work_dir = video_path.parent / video_path.stem
    output_dir = work_dir / "keyframes"

    if not overwrite and output_dir.exists():
        existing = list(output_dir.glob("*cv_summary.json"))
        if existing:
            print(f"[Batch] 跳过 {video_path.name}（已有 {len(existing)} 个结果）")
            return []

    if start_sec is not None and end_sec is not None:
        segment = {"start": start_sec, "end": end_sec}
        result = extract_keyframes(
            video_path=video_path,
            segment=segment,
            output_dir=output_dir,
            config=config,
            use_roboflow=use_roboflow,
            seg_id="manual_001",
        )
        return [result]

    segments = _load_period_result(video_path)
    if segments is None:
        print(f"[Batch] 警告: {video_path.name} 没有 period_result.json，跳过")
        print(f"  请先运行 pipeline 获取 Phase1 结果")
        return []

    exercise_segs = [s for s in segments if s.get("state", "").upper() == "EXERCISE"]
    if not exercise_segs:
        print(f"[Batch] 警告: {video_path.name} 没有 EXERCISE 区间，跳过")
        return []

    return process_video_segments(
        video_path=video_path,
        segments=segments,
        output_dir=output_dir,
        config=config,
        use_roboflow=use_roboflow,
    )


def main():
    parser = argparse.ArgumentParser(
        description="批量运行 Ego-Interaction Keyframe Sampler")
    parser.add_argument(
        "--video", default=None,
        help="指定单个视频路径（默认处理 input/ 下所有视频）")
    parser.add_argument(
        "--start", type=float, default=None,
        help="手动指定 Exercise 起始时间（秒），需配合 --end")
    parser.add_argument(
        "--end", type=float, default=None,
        help="手动指定 Exercise 结束时间（秒），需配合 --start")
    parser.add_argument(
        "--no-roboflow", action="store_true",
        help="不使用 Roboflow API，用本地模型检测手部")
    parser.add_argument(
        "--config", default=None,
        help="配置文件路径")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="覆盖已有结果")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    use_roboflow = not args.no_roboflow

    t0 = time.time()

    if args.video:
        video_path = Path(args.video)
        if not video_path.is_absolute():
            video_path = INPUT_DIR.parent / video_path
        if not video_path.exists():
            video_path = INPUT_DIR / args.video
        if not video_path.exists():
            print(f"视频不存在: {args.video}")
            return

        results = run_single_video(
            video_path, config, use_roboflow,
            start_sec=args.start, end_sec=args.end,
            overwrite=args.overwrite,
        )
    else:
        videos = _find_videos(INPUT_DIR)
        if not videos:
            print(f"input/ 下没有视频文件")
            return

        print(f"找到 {len(videos)} 个视频:")
        for v in videos:
            print(f"  {v.name}")
        print()

        all_results = []
        for video_path in videos:
            results = run_single_video(
                video_path, config, use_roboflow,
                overwrite=args.overwrite,
            )
            all_results.extend(results)

        results = all_results

    elapsed = time.time() - t0
    total_segments = len(results)
    print(f"\n{'=' * 60}")
    print(f"批量处理完成！")
    print(f"  处理了 {total_segments} 个 Exercise 区间")
    print(f"  总耗时: {elapsed:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
