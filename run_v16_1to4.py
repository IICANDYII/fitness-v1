"""Re-run videos 1-4 with v16 (fixed recognizer that uses YAML output format)."""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from gym_analyzer.pipeline import run_pipeline

INPUT_DIR   = Path(r"D:\WorkPath\fitness_new\gym_analyzer\input")
OUTPUT_BASE = Path(r"D:\WorkPath\fitness_new\recognize\visualize\result\v16")
PROMPTS_DIR = Path(r"D:\WorkPath\fitness_new\gym_analyzer\prompts")

VIDEOS = ["1", "2", "3", "4"]

def main():
    total = len(VIDEOS)
    success = 0
    failed = []

    for i, name in enumerate(VIDEOS, 1):
        work_dir   = INPUT_DIR / name
        output_dir = OUTPUT_BASE / name
        print(f"\n{'#' * 70}")
        print(f"# [{i}/{total}] {name}")
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
    print(f"Batch done: {success}/{total} succeeded")
    if failed:
        print(f"Failed: {failed}")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    main()
