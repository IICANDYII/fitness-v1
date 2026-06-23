"""
Batch run: all videos in gym_analyzer/input, output to result/v14/
v14 说明：
  - Phase 1 使用 phase1_period_recognize_v6.yaml
    · 全时间线器材识别（每个 segment 都标注 equipment）
    · 维护 equipment_timeline（器材切换事件列表）
    · IMU 综合摘要（acc_std 运动强度、欧拉角姿态分类、加速度峰值计数）
  - Phase 2 使用 phase2_exercise_recognize_v9.yaml
    · Step1 器械识别优先：入场帧 + Phase 1 equipment 交叉验证
    · Step2 光流 & IMU 交叉验证（姿态缩小候选、rep_count_hint）
    · Step3 动作识别总流程 + 易混动作硬判别规则（A~F）+ 一致性检查
    · Step4 次数统计（光流周期 + IMU 峰值交叉验证）
    · Step4.5 组间休息细分（rest_periods）
    · Step5 Phase 1 区间修正建议

流程：
  1. 加载帧元数据 + IMU 数据（如有），统计周期信息、峰值信息、运动强度、用户姿态
  2. 计算/加载光流
  3. Phase 1（v6）：区间划分 + 全时间线器材识别 + IMU 综合摘要
  4. Phase 2（v9）：逐 EXERCISE 精细识别
     - 综合 IMU 摘要（子窗口细分、加速度峰值、组间休息检测、运动周期估计）
     - 光流摘要（方向、强度、周期性）
     - Phase 1 器材时间线
     → 识别动作 + 组数 + 次数
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gym_analyzer.pipeline import run_pipeline

INPUT_DIR   = Path(r"D:\WorkPath\fitness_new\gym_analyzer\input")
OUTPUT_BASE = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result\v14")
PROMPTS_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\prompts")

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
    print(f"版本：v14 (phase1=v6 器材识别+IMU综合, phase2=v9 易混动作硬判别+一致性检查)\n")

    total = len(VIDEOS)
    success = 0
    failed = []

    for i, name in enumerate(VIDEOS, 1):
        work_dir   = INPUT_DIR / name
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
