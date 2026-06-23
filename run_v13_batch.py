"""
Batch run: all videos in gym_analyzer/input, output to result/v13/
v13 说明：
  - Phase 1 使用 phase1_period_recognize_v6.yaml
    · 全时间线器材识别（每个 segment 都标注 equipment）
    · 维护 equipment_timeline（器材切换事件列表）
    · IMU 综合摘要（acc_std 运动强度、欧拉角姿态分类、加速度峰值计数）
  - Phase 2 使用 phase2_exercise_recognize_v8.yaml
    · 接收 Phase 1 器材预识别 + 姿态 + 器材切换时间线
    · IMU 综合摘要（子窗口细分、rep 峰值计数交叉验证、组间休息检测）
    · 输出 rest_periods（组间休息段）和 imu_rep_hint（IMU 峰值计数）

流程：
  1. 加载帧元数据 + IMU 数据（如有）
  2. 计算/加载光流
  3. Phase 1：区间划分 + 全时间线器材识别 + IMU 综合摘要
  4. Phase 2：逐 EXERCISE 精细识别（器材验证 + IMU 交叉验证 + 组间休息细分）
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gym_analyzer.pipeline import run_pipeline

INPUT_DIR  = Path(r"D:\WorkPath\fitness_new\gym_analyzer\input")
OUTPUT_BASE = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result\v13")
PROMPTS_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\prompts")

# 自动扫描 input 目录下所有子目录（每个子目录对应一段已抽帧的视频）
VIDEOS = sorted(
    d.name for d in INPUT_DIR.iterdir()
    if d.is_dir() and (d / "frames_meta.json").exists()
)


def main():
    if not VIDEOS:
        print(f"[ERROR] 在 {INPUT_DIR} 下未找到任何已抽帧目录（需要包含 frames_meta.json）")
        sys.exit(1)

    print(f"找到 {len(VIDEOS)} 个视频目录：{VIDEOS}")
    print(f"输出基目录：{OUTPUT_BASE}")
    print(f"Prompt 目录：{PROMPTS_DIR}")
    print(f"版本：v13 (phase1=v6 器材识别+IMU综合, phase2=v8 交叉验证+组间休息)\n")

    total = len(VIDEOS)
    success = 0
    failed = []

    for i, name in enumerate(VIDEOS, 1):
        work_dir  = INPUT_DIR / name
        output_dir = OUTPUT_BASE / name
        print(f"\n{'#' * 70}")
        print(f"# [{i}/{total}] {name}")
        print(f"#   work_dir:   {work_dir}")
        print(f"#   output_dir: {output_dir}")
        print(f"{'#' * 70}")

        try:
            run_pipeline(
                work_dir=str(work_dir),
                prompts_dir=str(PROMPTS_DIR),
                overwrite=True,
                exercise_workers=4,
                output_dir=str(output_dir),
            )
            success += 1
        except Exception as e:
            print(f"\n[ERROR] {name}: {e}")
            traceback.print_exc()
            failed.append(name)

    print(f"\n{'=' * 70}")
    print(f"Batch 完成: {success}/{total} 成功")
    if failed:
        print(f"失败: {failed}")
    print(f"输出目录: {OUTPUT_BASE}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
