"""Batch import: convert existing analysis results into DB records for all users."""

import sys
import json
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from gym_analyzer.tools import _convert_v2_results, compute_dashboard
from gym_analyzer.db import save_to_db

RESULTS_DIR = Path(__file__).parent / "gym_analyzer" / "results"

# 8 results folders
RESULT_FOLDERS = sorted(
    [d for d in RESULTS_DIR.iterdir() if d.is_dir() and (d / "exercise_result.json").exists()],
    key=lambda d: d.name,
)

# 12 users without data (skip the first user who already has 3 sessions)
USERS = [
    {"user_id": "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12", "gender": "female", "weight": 60, "age": 24},
    {"user_id": "00000000-0000-0000-0000-000000033814", "gender": "female", "weight": 55, "age": 24},
    {"user_id": "00000000-0000-0000-0000-000000067318", "gender": "male",   "weight": 58, "age": 24},
    {"user_id": "00000000-0000-0000-0000-000000068454", "gender": "male",   "weight": 78, "age": 23},
    {"user_id": "00000000-0000-0000-0000-000000016458", "gender": "female", "weight": 65, "age": 22},
    {"user_id": "00000000-0000-0000-0000-000000077544", "gender": "male",   "weight": 85, "age": 29},
    {"user_id": "00000000-0000-0000-0000-000000074683", "gender": "female", "weight": 60, "age": 24},
    {"user_id": "00000000-0000-0000-0000-000000025803", "gender": "male",   "weight": 70, "age": 30},
    {"user_id": "00000000-0000-0000-0000-000000082274", "gender": "male",   "weight": 133, "age": 30},
    {"user_id": "00000000-0000-0000-0000-000000032488", "gender": "female", "weight": 47, "age": 23},
    {"user_id": "00000000-0000-0000-0000-000000087478", "gender": "male",   "weight": 70, "age": 29},
    {"user_id": "00000000-0000-0000-0000-000000088265", "gender": "male",   "weight": 85, "age": 24},
]

def get_video_duration(result_dir: Path) -> float:
    pr = result_dir / "period_result.json"
    if pr.exists():
        data = json.loads(pr.read_text(encoding="utf-8"))
        return float(data.get("total_1fps_frames", 0))
    return 0.0


def import_result(result_dir: Path, user: dict, workout_date: str):
    uid = user["user_id"]
    print(f"\n{'='*60}")
    print(f"Importing: {result_dir.name} -> user {uid[:12]}... date={workout_date}")
    print(f"  gender={user['gender']} weight={user['weight']}kg age={user['age']}")

    duration_sec = get_video_duration(result_dir)
    segments = _convert_v2_results(result_dir, duration_sec)
    exercise_segs = [s for s in segments if s.get("type") == "exercise"]
    print(f"  Segments: {len(segments)} total, {len(exercise_segs)} exercises, duration={duration_sec:.0f}s")

    if not exercise_segs:
        print("  SKIP: no exercise segments")
        return False

    segments_result = {"segments": segments, "video_duration_sec": duration_sec}
    dashboard = compute_dashboard(
        segments_result,
        weight_kg=user["weight"],
        gender=user["gender"],
        age=user["age"],
        date_str=workout_date,
    )

    result = save_to_db(dashboard, user_id=uid)
    print(f"  DB result: {result.get('status', 'unknown')} "
          f"exercises={result.get('exercises_written', 0)} "
          f"session={str(result.get('session_id', ''))[:12]}")
    return result.get("status") == "ok"


def main():
    print(f"Found {len(RESULT_FOLDERS)} result folders: {[d.name for d in RESULT_FOLDERS]}")
    print(f"Found {len(USERS)} users to populate")

    today = date(2026, 6, 17)
    assignments = []

    # Round 1: assign 1 result to each of the first 8 users (different dates in last 2 weeks)
    for i, folder in enumerate(RESULT_FOLDERS):
        user = USERS[i % len(USERS)]
        d = today - timedelta(days=14 - i * 2)
        assignments.append((folder, user, d.isoformat()))

    # Round 2: give remaining 4 users data by reusing results with different dates
    for i in range(8, len(USERS)):
        folder = RESULT_FOLDERS[i - 8]
        user = USERS[i]
        d = today - timedelta(days=7 - (i - 8))
        assignments.append((folder, user, d.isoformat()))

    # Round 3: give some users a second session (different day) for richer dashboard
    extra_pairs = [
        (1, 0), (3, 2), (5, 4), (7, 6),  # reuse alternating results
    ]
    for result_idx, user_idx in extra_pairs:
        if result_idx < len(RESULT_FOLDERS) and user_idx < len(USERS):
            folder = RESULT_FOLDERS[result_idx]
            user = USERS[user_idx]
            d = today - timedelta(days=3 + user_idx)
            assignments.append((folder, user, d.isoformat()))

    ok = 0
    fail = 0
    for folder, user, date_str in assignments:
        try:
            if import_result(folder, user, date_str):
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            fail += 1

    print(f"\n{'='*60}")
    print(f"Done: {ok} imported, {fail} failed")


if __name__ == "__main__":
    main()
