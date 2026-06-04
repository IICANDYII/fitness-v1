"""CLI entry point.

Usage:
  python -m gym_analyzer.run <video_path> [--date 2026-06-01] [--weight 65]
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from .agent import GymAnalyzerAgent
from .config import DEFAULT_USER_ID


def main():
    parser = argparse.ArgumentParser(description="Gym Analyzer — analyze a workout video")
    parser.add_argument("video",     help="Path to the workout video file")
    parser.add_argument("--date",    default=date.today().isoformat(), help="Date of workout (YYYY-MM-DD)")
    parser.add_argument("--weight",  type=float, default=65.0,   help="User weight in kg")
    parser.add_argument("--gender",  default="female",            help="Gender: male / female")
    parser.add_argument("--age",     type=int,   default=25,      help="Age in years")
    parser.add_argument("--hr",      default=None,                help="Heart rate CSV path (auto-detected if omitted)")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID,     help="User UUID for DB write")
    args = parser.parse_args()

    hr_csv = args.hr

    print(f"Analyzing {args.video} ...")
    agent = GymAnalyzerAgent()
    result = agent.run(
        args.video,
        workout_date=args.date,
        weight_kg=args.weight,
        gender=args.gender,
        age=args.age,
        hr_csv_path=hr_csv,
        user_id=args.user_id,
    )

    if result:
        print("\n✓ Analysis complete")
        daily = result.get("daily", {})
        print(f"  Duration    : {daily.get('duration_min')} min")
        print(f"  Calories    : {daily.get('calories')} kcal")
        print(f"  Completion  : {daily.get('completion_rate')}%")
        print(f"  Saved to    : gym_analyzer/results/{args.date}.json")
    else:
        print("Analysis returned empty result — check API credentials and video path.")


if __name__ == "__main__":
    main()
