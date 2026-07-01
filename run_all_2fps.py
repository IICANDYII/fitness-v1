"""Run video phase2 at 2fps for all remaining input directories."""
import json, sys, os, time as time_module
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv(".env")
from pathlib import Path
from datetime import datetime
import gym_analyzer.recognizer as recognizer
from gym_analyzer.run_video_phase2 import (
    _recognize_one_exercise_video, sec_to_hhmmss, tprint,
    apply_phase1_adjustments
)
from gym_analyzer.optical_flow import load_flow
from gym_analyzer.yaml_loader import load_prompt


def run_one_dataset(work_dir, period_result_path, output_dir, target_fps=2, pad_sec=15):
    work_dir = Path(work_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    recognizer.EXERCISE_BOUNDARY_PAD = pad_sec

    prompt = load_prompt("gym_analyzer/prompts/phase2_exercise_recognize_v4_video.yaml")

    with open(work_dir / "frames_meta.json", "r", encoding="utf-8") as f:
        frame_metas = json.load(f)

    flow_path = work_dir / "optical_flow.json"
    flow_data = []
    if flow_path.exists():
        try:
            flow_data, _ = load_flow(flow_path)
        except Exception as e:
            print(f"  [warn] optical_flow load failed: {e}")

    with open(period_result_path, "r", encoding="utf-8") as f:
        period_data = json.load(f)

    segments = period_data.get("segments", [])
    exercise_segs = [s for s in segments if s.get("state", "").upper() == "EXERCISE"]
    for i, s in enumerate(exercise_segs, 1):
        s.setdefault("segmentId", f"exercise_{i:03d}")

    if not exercise_segs:
        print("  No EXERCISE segments found, skipping")
        return

    # Copy period_result if not present
    import shutil
    dst_period = output_dir / "period_result.json"
    if not dst_period.exists():
        shutil.copy2(period_result_path, dst_period)

    # Load existing results (for resume)
    result_path = output_dir / "exercise_result.json"
    existing_results = []
    if result_path.exists():
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing_results = data.get("results", [])
    existing_ids = {r["segmentId"] for r in existing_results}

    missing_segs = [s for s in exercise_segs if s["segmentId"] not in existing_ids]
    if not missing_segs:
        print(f"  All {len(exercise_segs)} exercises already completed!")
        return

    print(f"  Total: {len(exercise_segs)}, Done: {len(existing_ids)}, Missing: {len(missing_segs)}")

    video_cache_dir = output_dir / "exercise_videos"
    new_results = []

    for seg in missing_segs:
        seg_id = seg["segmentId"]
        try:
            result = _recognize_one_exercise_video(
                seg, frame_metas, work_dir / "frames", output_dir,
                flow_data, prompt.system, target_fps,
                user_prompt_template=prompt.user,
                video_cache_dir=video_cache_dir,
            )
            if result:
                new_results.append(result)
                res = result["result"]
                print(f"  OK: {seg_id} -> {res.get('exercise','?')} conf={res.get('confidence','?')}")
            else:
                print(f"  SKIP: {seg_id} returned None")
        except Exception as e:
            print(f"  FAIL: {seg_id} -> {type(e).__name__}: {e}")

    # Merge and save
    all_results = existing_results + new_results
    all_results.sort(key=lambda r: r["startTime"])

    payload = {
        "version": f"v4-video-{target_fps}fps",
        "phase2_prompt": "phase2_exercise_recognize_v4_video.yaml",
        "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "target_fps": target_fps,
        "input_mode": "video",
        "results": all_results,
    }
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"  Saved {len(all_results)}/{len(exercise_segs)} results")

    # Generate adjusted period result
    total_dur = frame_metas[-1]["timestamp"] if frame_metas else 0
    adjusted_segments, applied = apply_phase1_adjustments(
        segments, all_results, total_dur)
    adj_payload = {
        "version": f"v4-video-{target_fps}fps",
        "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "segments": adjusted_segments,
        "adjustments_applied": applied,
    }
    adj_path = output_dir / "period_result_adjusted.json"
    with open(adj_path, "w", encoding="utf-8") as f:
        json.dump(adj_payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    input_base = Path("gym_analyzer/input")
    v10_base = Path("recognize/visualize/result/v10")
    output_base = Path("recognize/visualize/result/v10-2fps")

    done = {"1", "2"}
    skip = {"杨博宇-624"}  # no period_result

    dirs = sorted([d.name for d in input_base.iterdir() if d.is_dir()])

    for name in dirs:
        if name in done or name in skip:
            continue
        period_path = v10_base / name / "period_result.json"
        if not period_path.exists():
            print(f"\n[SKIP] {name}: no period_result.json in v10")
            continue

        work_dir = input_base / name
        output_dir = output_base / name

        # Count exercises
        with open(period_path, "r", encoding="utf-8") as f:
            pd = json.load(f)
        n_ex = sum(1 for s in pd.get("segments", []) if s.get("state", "").upper() == "EXERCISE")

        print(f"\n{'='*60}")
        print(f"[{name}] {n_ex} exercises, fps=2")
        print(f"{'='*60}")

        t0 = time_module.time()
        run_one_dataset(work_dir, period_path, output_dir, target_fps=2, pad_sec=15)
        elapsed = time_module.time() - t0
        print(f"  Time: {elapsed:.1f}s")

    print(f"\n{'='*60}")
    print("ALL DONE")
    print(f"{'='*60}")
