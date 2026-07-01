"""批量运行视频版流水线，处理 gym_analyzer/input/ 下所有 .mp4 文件。"""
import sys
import traceback
from pathlib import Path

from gym_analyzer.pipeline_video import run_pipeline_video

input_dir = Path("gym_analyzer/input")
videos = sorted(input_dir.glob("*.mp4"), key=lambda p: p.stat().st_size)

completed = []
failed = []

for i, video in enumerate(videos, 1):
    # 跳过已有结果的
    out_dir = Path("recognize/visualize/result/v_video") / video.stem
    if (out_dir / "exercise_result.json").exists():
        print(f"\n[{i}/{len(videos)}] 跳过（已有结果）: {video.name}")
        completed.append(video.name)
        continue

    print(f"\n{'#' * 70}")
    print(f"# [{i}/{len(videos)}] 处理: {video.name} ({video.stat().st_size / 1024 / 1024:.0f} MB)")
    print(f"{'#' * 70}")

    try:
        run_pipeline_video(str(video))
        completed.append(video.name)
    except Exception as e:
        print(f"\n[错误] {video.name}: {e}")
        traceback.print_exc()
        failed.append((video.name, str(e)))

print(f"\n\n{'=' * 70}")
print(f"批量处理完成")
print(f"  成功: {len(completed)}")
print(f"  失败: {len(failed)}")
for name, err in failed:
    print(f"    {name}: {err}")
print(f"{'=' * 70}")
