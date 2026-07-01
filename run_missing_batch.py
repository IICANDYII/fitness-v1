"""
Batch run missing video/version combinations.
Missing:
  v9:  健身-高孟琦, 张靖义-2026.06.11
  v10: 健身-高孟琦
  v11: 健身-高孟琦
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gym_analyzer.pipeline import run_pipeline

INPUT_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\input")
OUTPUT_BASE = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result")
PROMPTS_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\prompts")

TASKS = [
    ("v9",  "健身-高孟琦"),
    ("v9",  "张靖义-2026.06.11"),
    ("v10", "健身-高孟琦"),
    ("v11", "健身-高孟琦"),
]


def main():
    total = len(TASKS)
    success = 0
    failed = []

    for i, (version, name) in enumerate(TASKS, 1):
        work_dir = INPUT_DIR / name
        output_dir = OUTPUT_BASE / version / name
        print(f"\n{'#' * 70}")
        print(f"# [{i}/{total}] {version} / {name}")
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
                version=version,
            )
            success += 1
        except Exception as e:
            print(f"\n[ERROR] {version}/{name}: {e}")
            traceback.print_exc()
            failed.append(f"{version}/{name}")

    print(f"\n{'=' * 70}")
    print(f"Batch done: {success}/{total} succeeded")
    if failed:
        print(f"Failed: {failed}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
