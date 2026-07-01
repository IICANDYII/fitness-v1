"""Retry failed exercise_001 for dataset 1."""
import json
import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv(".env")
from gym_analyzer.run_video_phase2 import _recognize_one_exercise_video
from gym_analyzer.optical_flow import load_flow
from gym_analyzer.yaml_loader import load_prompt
from pathlib import Path

prompt = load_prompt("gym_analyzer/prompts/phase2_exercise_recognize_v4_video.yaml")

with open("gym_analyzer/input/1/frames_meta.json", "r", encoding="utf-8") as f:
    frame_metas = json.load(f)

flow_data, _ = load_flow(Path("recognize/visualize/result/shared/1/optical_flow.json"))

with open("recognize/visualize/result/v10/1/period_result.json", "r", encoding="utf-8") as f:
    pd = json.load(f)
segs = [s for s in pd["segments"] if s["state"].upper() == "EXERCISE"]
for i, s in enumerate(segs, 1):
    s.setdefault("segmentId", f"exercise_{i:03d}")

seg = segs[0]
out_dir = Path("recognize/visualize/result/v10-1fps/1")
video_cache = out_dir / "exercise_videos"

result = _recognize_one_exercise_video(
    seg, frame_metas, Path("gym_analyzer/input/1/frames"), out_dir,
    flow_data, prompt.system, 1,
    user_prompt_template=prompt.user,
    video_cache_dir=video_cache,
)

if result:
    with open(out_dir / "exercise_result.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    # Remove any existing exercise_001 result
    data["results"] = [r for r in data["results"] if r["segmentId"] != "exercise_001"]
    data["results"].insert(0, result)
    data["results"].sort(key=lambda r: r["startTime"])
    with open(out_dir / "exercise_result.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    res = result["result"]
    print(f"OK: {res.get('exercise', '?')} conf={res.get('confidence', '?')}")
else:
    print("FAILED")
