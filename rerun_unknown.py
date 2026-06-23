"""
Re-run Phase 2 for UNKNOWN_ACTION / empty exercise segments across ALL versions.
Reads existing exercise_result.json, re-identifies UNKNOWN segments, updates in place.
"""
import sys
import json
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from gym_analyzer.extractor import FrameMeta
from gym_analyzer.optical_flow import load_flow
from gym_analyzer.yaml_loader import load_prompts
from gym_analyzer.recognizer import _recognize_one_exercise

INPUT_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\input")
RESULT_BASE = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result")
PROMPTS_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\prompts")
SHARED_DIR = RESULT_BASE / "shared"

# Load env
for p in [Path(__file__).parent / ".env", Path(__file__).parent / "gym_analyzer" / ".env"]:
    if p.exists():
        load_dotenv(p)
        break

_, phase2_prompt = load_prompts(PROMPTS_DIR)

# Cache: video_name -> (frame_metas, frames_dir, flow_data)
_video_cache: dict = {}

def _load_video_data(name: str):
    if name in _video_cache:
        return _video_cache[name]

    frames_base = INPUT_DIR / name
    meta_path = frames_base / "frames_meta.json"
    if not meta_path.exists():
        _video_cache[name] = None
        return None

    frame_metas = [FrameMeta(**m) for m in json.load(open(meta_path, encoding="utf-8"))]
    frames_dir = frames_base / "frames"

    shared_flow = SHARED_DIR / name / "optical_flow.json"
    flow_path = frames_base / "optical_flow.json"
    cached = load_flow(shared_flow) if shared_flow.exists() else load_flow(flow_path)
    if not cached:
        _video_cache[name] = None
        return None

    flow_data, _ = cached
    _video_cache[name] = (frame_metas, frames_dir, flow_data)
    return _video_cache[name]


total_fixed = 0
total_unknown = 0

for ver_dir in sorted(RESULT_BASE.iterdir()):
    if not ver_dir.name.startswith("v") or not ver_dir.is_dir():
        continue
    if not ver_dir.name[1:].isdigit():
        continue

    for video_dir in sorted(ver_dir.iterdir()):
        if not video_dir.is_dir():
            continue
        ex_path = video_dir / "exercise_result.json"
        if not ex_path.exists():
            continue

        data = json.load(open(ex_path, encoding="utf-8"))
        results = data if isinstance(data, list) else data.get("results", [])

        unknowns = []
        for i, r in enumerate(results):
            res = r.get("result", r)
            ex = (res.get("exercise", "") or "").strip()
            eq = (res.get("equipment", "") or "").strip()
            if not ex or "UNKNOWN" in ex.upper() or not eq or "UNKNOWN" in eq.upper():
                unknowns.append((i, r))

        if not unknowns:
            continue

        name = video_dir.name
        ver = ver_dir.name
        total_unknown += len(unknowns)

        print(f"\n{'='*60}")
        print(f"{ver}/{name}: {len(unknowns)} UNKNOWN segments")
        print(f"{'='*60}")

        vdata = _load_video_data(name)
        if vdata is None:
            print(f"  [SKIP] No frame data or optical flow for {name}")
            continue
        frame_metas, frames_dir, flow_data = vdata

        updated = 0
        for idx, r in unknowns:
            seg_id = r.get("segmentId", "?")
            st_str = r.get("startTimeStr", "?")
            et_str = r.get("endTimeStr", "?")
            print(f"\n  Re-identifying {seg_id}: {st_str}~{et_str}")

            seg = {
                "segmentId": seg_id,
                "start_sec": r.get("startTime", r.get("start_sec", 0)),
                "end_sec": r.get("endTime", r.get("end_sec", 0)),
                "reason": r.get("reason", ""),
            }

            try:
                new_result = _recognize_one_exercise(
                    seg=seg,
                    frame_metas=frame_metas,
                    frames_dir=frames_dir,
                    output_dir=video_dir,
                    flow_data=flow_data,
                    system_prompt=phase2_prompt.system,
                )
                if new_result is None:
                    continue

                new_res = new_result.get("result", new_result)
                new_ex = (new_res.get("exercise", "") or "").strip()
                new_eq = (new_res.get("equipment", "") or "").strip()
                still_bad = (not new_ex or "UNKNOWN" in new_ex.upper()
                             or not new_eq or "UNKNOWN" in new_eq.upper())

                if not still_bad:
                    results[idx] = {**r, "result": new_res}
                    old_ex = (r.get("result", r).get("exercise", "") or "(empty)")
                    print(f"  [OK] {seg_id}: {old_ex} -> {new_ex} ({new_eq})")
                    updated += 1
                else:
                    print(f"  [FAIL] {seg_id}: still unknown eq=[{new_eq}] ex=[{new_ex}]")
            except Exception as e:
                print(f"  [ERROR] {seg_id}: {e}")
                traceback.print_exc()

        if updated > 0:
            if isinstance(data, dict):
                data["results"] = results
            else:
                data = results
            with open(ex_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n  Saved {updated}/{len(unknowns)} fixes -> {ex_path}")
            total_fixed += updated
        else:
            print(f"\n  No fixes for {ver}/{name}")

print(f"\n{'='*60}")
print(f"Done. Fixed {total_fixed}/{total_unknown} UNKNOWN segments across all versions.")
print(f"{'='*60}")
