"""
Batch run: all videos in gym_analyzer/input, output to result/v16/
v16 说明：
  - Phase 1 使用 phase1_period_recognize_v7.yaml
    · 静态参照物姿态验证（天花板/地面交叉验证 supine vs hanging）
    · 器材视觉特征清单（equipment_features，供 Phase 2 验证）
    · 绳索挂点高度识别（cable_anchor: high/mid/low）
    · 全局 vs 局部光流区分（global_motion: true/false）
    · 器材/姿态推理 reason（equipment_reason, posture_reason）
  - Phase 2 使用 phase2_exercise_recognize_v11.yaml
    · Step2.1-H 绳索动作细分（7种绳索动作按挂点+手轨迹+上臂位置判断）
    · Step3.1-I 双杠臂屈伸硬约束（必须 global_motion=true + 无座椅）
    · Step3.1-B 弯举/侧平举强化（无 LEFT/RIGHT 光流→默认弯举）
    · Step3.1-D 蝴蝶机细分（夹胸 vs 反向飞鸟）
    · equipment_features 验证回路（Phase 1→2 器材验证）
    · exercise_reason 动作判断依据
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gym_analyzer.pipeline import run_pipeline

INPUT_DIR   = Path(r"D:\WorkPath\fitness_new\gym_analyzer\input")
OUTPUT_BASE = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result\v16")
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
    print(f"版本：v16 (phase1=v7 静态参照物+器材特征+绳索挂点+全局光流, phase2=v11 绳索细分+双杠硬约束+弯举侧举强化)\n")

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
                version="v16",
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
