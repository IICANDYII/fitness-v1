#!/usr/bin/env python3
"""
批量为 user_profile_long_term 中的所有用户生成训练计划，保存到 workout_plan 表。
每个用户每周训练天数取自 available_schedule.days_per_week（默认 3-5 天）。
支持多线程并发生成。

Usage:
  python generate_all_plans.py [--version v4] [--workers 4]
"""

import sys
import time
import json
import argparse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

from agent_service.planner.plan_generator import (
    DB_KWARGS,
    get_conn,
    fetch_user_profile,
    fetch_dynamic_state,
    fetch_history_plans,
    filter_exercises_by_rules,
    rank_by_vector,
    generate_plan_with_llm,
    generate_plan_v3,
    generate_plan_v4,
    save_workout_plan,
    save_plan_cache,
    _ensure_user_in_profile,
)

DEFAULT_DAYS = {
    "beginner":     3,
    "intermediate": 4,
    "advanced":     5,
}

_print_lock = threading.Lock()


def _log(msg: str):
    with _print_lock:
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            safe = msg.encode(sys.stdout.encoding or "gbk", errors="replace").decode(sys.stdout.encoding or "gbk", errors="replace")
            print(safe, flush=True)


def _patch_days(profile: dict) -> dict:
    """Ensure available_schedule has days_per_week (3-5) and daily_duration_min."""
    schedule = dict(profile.get("available_schedule") or {})
    if "days_per_week" not in schedule or not schedule["days_per_week"]:
        exp = profile.get("experience_level", "intermediate")
        schedule["days_per_week"] = DEFAULT_DAYS.get(exp, 4)
    schedule["days_per_week"] = max(3, min(5, int(schedule["days_per_week"])))
    if "daily_duration_min" not in schedule or not schedule["daily_duration_min"]:
        schedule["daily_duration_min"] = 60
    profile = dict(profile)
    profile["available_schedule"] = schedule
    return profile


def fetch_all_user_ids() -> list[str]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM user_profile_long_term ORDER BY id")
            return [str(r["user_id"]) for r in cur.fetchall()]


def generate_for_user(user_id: str, version: str = "v4") -> dict:
    """
    为单个用户生成训练计划。
    返回 {"user_id", "success", "plan_id", "elapsed", "error"}.
    """
    t0 = time.perf_counter()
    try:
        profile = fetch_user_profile(user_id)
        profile = _patch_days(profile)
        dynamic = fetch_dynamic_state(user_id)
        history = fetch_history_plans(user_id)

        sched = profile.get("available_schedule", {})
        _log(
            f"  [{user_id[:8]}] 开始生成  "
            f"目标={profile.get('fitness_goal')}  "
            f"水平={profile.get('experience_level')}  "
            f"每周{sched.get('days_per_week')}天"
        )

        filtered = filter_exercises_by_rules(profile)
        if not filtered:
            _log(f"  [{user_id[:8]}] [SKIP] 未筛出任何动作，跳过")
            return {"user_id": user_id, "success": False, "plan_id": None,
                    "elapsed": time.perf_counter() - t0, "error": "no_exercises_filtered"}

        ranked = rank_by_vector(filtered, profile, dynamic, history, top_k=40)

        if version == "v4":
            plan = generate_plan_v4(ranked, profile, dynamic)
        elif version == "v3":
            plan = generate_plan_v3(ranked, profile, dynamic)
        else:
            plan = generate_plan_with_llm(ranked, profile, dynamic)
            plan["_pipeline_version"] = "v2"

        _ensure_user_in_profile(user_id, profile)
        plan_id = save_workout_plan(user_id, profile.get("fitness_goal", ""), plan)
        save_plan_cache(user_id, version, plan)

        elapsed = time.perf_counter() - t0
        _log(f"  [{user_id[:8]}] [OK] 完成  plan_id={plan_id}  耗时={elapsed:.1f}s")
        return {"user_id": user_id, "success": True, "plan_id": plan_id,
                "elapsed": elapsed, "error": None}

    except Exception as e:
        elapsed = time.perf_counter() - t0
        err_msg = f"{type(e).__name__}: {str(e)[:200]}"
        _log(f"  [{user_id[:8]}] [FAIL] 失败  {err_msg}  耗时={elapsed:.1f}s")
        return {"user_id": user_id, "success": False, "plan_id": None,
                "elapsed": elapsed, "error": err_msg}


def main():
    parser = argparse.ArgumentParser(description="批量生成训练计划（多线程）")
    parser.add_argument("--version", default="v4", choices=["v2", "v3", "v4"],
                        help="pipeline 版本 (default: v4)")
    parser.add_argument("--workers", type=int, default=4,
                        help="并发线程数 (default: 4)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  批量训练计划生成  pipeline={args.version}  workers={args.workers}")
    print(f"{'='*60}")

    user_ids = fetch_all_user_ids()
    total = len(user_ids)
    print(f"\n共 {total} 个用户待处理\n")

    if not user_ids:
        print("无用户，退出。")
        return

    total_start = time.perf_counter()
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(generate_for_user, uid, args.version): uid
            for uid in user_ids
        }
        for future in as_completed(futures):
            results.append(future.result())

    total_elapsed = time.perf_counter() - total_start

    success = [r for r in results if r["success"]]
    failed  = [r for r in results if not r["success"]]

    print(f"\n{'='*60}")
    print(f"  完成: 成功={len(success)}  失败={len(failed)}  总耗时={total_elapsed:.1f}s")
    if failed:
        print(f"\n  失败明细:")
        for r in failed:
            print(f"    {r['user_id']}  →  {r['error']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
