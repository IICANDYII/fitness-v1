"""
pipeline.py - 完整识别流水线

用法：
  # 先抽帧
  python -m src.extractor video/3.mp4 output/test_3

  # 再分析（从已抽好的帧文件夹）
  python -m src.pipeline output/test_3
  python -m src.pipeline output/test_3 --prompts .
  python -m src.pipeline output/test_3 --overwrite

流程：
  Step 1  加载已抽帧的元数据（frames_meta.json）
  Step 2  计算/加载光流
  Step 3  Phase 1 拼图 + 粗区间识别
  Step 4  Phase 2 逐 EXERCISE 区间精细识别（并发）
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from .extractor import FrameMeta
from .optical_flow import (
    compute_optical_flow,
    analyze_periodicity,
    save_flow,
    load_flow,
)
from .stitcher import stitch_phase1_grids, sec_to_hhmmss
from .yaml_loader import load_prompts, load_prompts_for_version
from .recognizer import run_phase1, run_phase2, load_imu_data, MAX_EXERCISE_WORKERS


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def run_pipeline(
    work_dir: str | Path,
    prompts_dir: str | Path | None = None,
    overwrite: bool = False,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
    output_dir: str | Path | None = None,
    version: str | None = None,
    version_info_path: str | Path | None = None,
    use_yolo: bool = False,
) -> None:
    """
    从已抽帧的文件夹执行完整分析。

    work_dir 可以是：
      - 视频文件路径（.mp4 等），自动推导为 video同目录/{视频名}/
      - 已有的工作目录（包含 frames_meta.json 和 frames/）

    Args:
        work_dir:     视频路径 或 工作目录（帧数据来源）
        prompts_dir:  yaml prompt 所在目录（默认 fitness_new 根目录）
        overwrite:    是否忽略缓存重新执行
        exercise_workers: Phase 2 并发数
        output_dir:   结果输出目录（默认与 work_dir 相同）
        version:      运行版本号（如 "v15"），指定后从 VERSION_INFO.md 查询对应 prompt
        version_info_path: VERSION_INFO.md 路径（默认 recognize/visualize/result/VERSION_INFO.md）
    """
    t0 = time.time()
    work_dir = Path(work_dir)
    if work_dir.is_file():
        work_dir = work_dir.parent / work_dir.stem

    video_dir = work_dir
    if output_dir is not None:
        out_dir = Path(output_dir)
    else:
        out_dir = video_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 加载环境变量 ──
    for env_candidate in [
        Path(__file__).parent.parent / ".env",   # fitness_code/.env
        Path(__file__).parent / ".env",           # gym_analyzer/.env
    ]:
        if env_candidate.exists():
            load_dotenv(env_candidate)
            break

    # ── 加载 prompts ──
    if prompts_dir is None:
        prompts_dir = Path(__file__).parent / "prompts"
    if version is not None:
        if version_info_path is None:
            version_info_path = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "VERSION_INFO.md"
        phase1_prompt, phase2_prompt = load_prompts_for_version(prompts_dir, version, version_info_path)
    else:
        phase1_prompt, phase2_prompt = load_prompts(prompts_dir)

    # ── Step 1：加载帧元数据 ──
    meta_path = video_dir / "frames_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"找不到 frames_meta.json，请先运行抽帧：\n"
            f"  python -m src_v2_guize.extractor <视频路径>\n"
            f"帧会自动存到 {video_dir}"
        )

    with open(meta_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    frame_metas = [FrameMeta(**m) for m in raw]

    frames_dir = video_dir / "frames"
    total_dur = frame_metas[-1].timestamp if frame_metas else 0

    print(f"\n{'=' * 60}")
    print(f"帧目录：{video_dir}")
    print(f"输出目录：{out_dir}")
    print(f"帧数：{len(frame_metas)}  时长：{sec_to_hhmmss(total_dur)}")
    print(f"Phase 2 并发数：{exercise_workers}")
    print(f"{'=' * 60}\n")

    # ── shared 目录（光流 + IMU 缓存）──
    _shared_base = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "shared"

    # ── Step 1.5：加载 IMU 数据（如有）──
    # 优先从 shared 目录加载 IMU.txt，其次从 video_dir 加载 IMU_data.txt
    _shared_imu = _shared_base / video_dir.name / "IMU.txt"
    imu_path = video_dir / "IMU_data.txt"
    imu_records = None
    if _shared_imu.exists():
        imu_records = load_imu_data(_shared_imu)
        if imu_records:
            print(f"[IMU] 已从 shared 加载 {len(imu_records)} 条记录，时长 {imu_records[-1][0]:.0f}s：{_shared_imu}")
    if not imu_records:
        imu_records = load_imu_data(imu_path)
        if imu_records:
            print(f"[IMU] 已加载 {len(imu_records)} 条记录，时长 {imu_records[-1][0]:.0f}s：{imu_path}")
    if not imu_records:
        print(f"[IMU] 未找到 IMU 数据，跳过传感器辅助")

    # ── Step 2：光流（各版本共享）──
    # 优先从 shared 目录加载预计算的光流，其次从 video_dir 加载
    _shared_flow = _shared_base / video_dir.name / "optical_flow.json"
    flow_path = video_dir / "optical_flow.json"

    cached = load_flow(_shared_flow) if _shared_flow.exists() else None
    if cached:
        print(f"[Step 2] 光流使用 shared 缓存：{_shared_flow}")
    else:
        cached = None if overwrite else load_flow(flow_path)

    if cached:
        flow_data, periodicity = cached
    else:
        print("[Step 2] 计算光流")
        flow_data = compute_optical_flow(frame_metas, video_dir)
        periodicity = analyze_periodicity(flow_data)
        save_flow(flow_data, periodicity, len(frame_metas), flow_path)

    # ── Step 3：Phase 1 ──
    period_result_path = out_dir / "period_result.json"

    equipment_timeline = []

    if not overwrite and period_result_path.exists():
        print(f"[Step 3] Phase 1 使用缓存：{period_result_path}")
        with open(period_result_path, "r", encoding="utf-8") as f:
            cached_result = json.load(f)
        segments = cached_result.get("segments", [])
        equipment_timeline = cached_result.get("equipment_timeline", [])
    else:
        print("[Step 3] Phase 1：拼图 + 粗区间识别")
        grids = stitch_phase1_grids(
            metas=frame_metas,
            output_dir=video_dir,
            frames_dir=frames_dir,
            overwrite=overwrite,
        )
        segments = run_phase1(
            frame_metas=frame_metas,
            grids=grids,
            flow_data=flow_data,
            prompt=phase1_prompt,
            output_dir=out_dir,
            imu_records=imu_records,
        )
        # 从保存的结果中提取 equipment_timeline
        if period_result_path.exists():
            with open(period_result_path, "r", encoding="utf-8") as f:
                equipment_timeline = json.load(f).get("equipment_timeline", [])

    ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
    print(f"  → {len(segments)} 个区间，其中 {ex_count} 个 EXERCISE")
    if equipment_timeline:
        print(f"  → 器材切换时间线: {len(equipment_timeline)} 个事件")

    # ── Phase 1 自检：未识别出任何动作则重试一次 ──
    if ex_count == 0 and len(frame_metas) > 10:
        print("  [WARN] Phase 1 未识别出任何 EXERCISE 区间，重新识别...")
        grids = stitch_phase1_grids(
            metas=frame_metas,
            output_dir=video_dir,
            frames_dir=frames_dir,
            overwrite=True,
        )
        segments = run_phase1(
            frame_metas=frame_metas,
            grids=grids,
            flow_data=flow_data,
            prompt=phase1_prompt,
            output_dir=out_dir,
            imu_records=imu_records,
        )
        if period_result_path.exists():
            with open(period_result_path, "r", encoding="utf-8") as f:
                equipment_timeline = json.load(f).get("equipment_timeline", [])
        ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
        print(f"  → 重试结果：{len(segments)} 个区间，其中 {ex_count} 个 EXERCISE")
        if ex_count == 0:
            print("  [WARN] 重试后仍无 EXERCISE，跳过 Phase 2")

    print()

    # ── Step 4：Phase 2 ──
    print("[Step 4] Phase 2：逐 EXERCISE 精细识别")
    exercise_results = run_phase2(
        frame_metas=frame_metas,
        frames_dir=frames_dir,
        flow_data=flow_data,
        segments=segments,
        prompt=phase2_prompt,
        output_dir=out_dir,
        exercise_workers=exercise_workers,
        imu_records=imu_records,
        equipment_timeline=equipment_timeline,
        use_yolo=use_yolo,
    )

    # ── 汇总 ──
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"完成！耗时 {elapsed:.1f}s")
    print(f"结果文件：")
    print(f"  {out_dir / 'period_result.json'}")
    print(f"  {out_dir / 'exercise_result.json'}")
    print(f"  {out_dir / 'period_result_adjusted.json'}")
    print(f"  {out_dir / 'period_raw_response.txt'}")
    print(f"共享缓存：")
    print(f"  {video_dir / 'optical_flow.json'}")
    print(f"  {video_dir / 'mid_result/'}")
    print(f"EXERCISE 识别结果：")
    for r in exercise_results:
        res = r.get("result", {})
        equip = res.get("equipment", "?")
        exer = res.get("exercise", "?")
        eid = res.get("exercise_id", "")
        conf = res.get("confidence", "?")
        sets = res.get("sets", [])
        eid_str = f"  [{eid}]" if eid else ""
        print(f"  {r['startTimeStr']}→{r['endTimeStr']}  "
              f"{equip} / {exer}{eid_str}  {len(sets)} 组  conf={conf}")
    print(f"{'=' * 60}\n")


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="健身视频运动区间识别（从已抽帧的文件夹分析）")
    parser.add_argument(
        "work_dir",
        help="视频文件路径（如 video/3.mp4）或工作目录（如 video/3）")
    parser.add_argument(
        "--prompts", "-p", default=None,
        help="yaml prompt 所在目录（默认：fitness_new 根目录）")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="忽略缓存，重新执行所有步骤")
    parser.add_argument(
        "--workers", "-w", type=int, default=MAX_EXERCISE_WORKERS,
        help=f"Phase 2 并发数（默认 {MAX_EXERCISE_WORKERS}）")
    parser.add_argument(
        "--output", "-o", default=None,
        help="结果输出目录（默认与 work_dir 相同）")
    parser.add_argument(
        "--version", "-v", default=None,
        help="运行版本号（如 v15），从 VERSION_INFO.md 查询对应 prompt")
    parser.add_argument(
        "--use-yolo", action="store_true",
        help="对比实验：对 Exercise 帧进行 YOLO 手部+器材标注后拼图")
    args = parser.parse_args()

    run_pipeline(
        work_dir=args.work_dir,
        prompts_dir=args.prompts,
        overwrite=args.overwrite,
        exercise_workers=args.workers,
        output_dir=args.output,
        version=args.version,
        use_yolo=args.use_yolo,
    )


if __name__ == "__main__":
    main()
