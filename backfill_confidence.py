"""
Backfill the `confidence` column in exercise_execution from video analysis JSON files.

For each exercise_name found across all exercise_result.json files, takes the max
confidence seen and updates matching rows in the database.
"""

import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

RESULTS_DIR = r"E:\fitness_code\gym_analyzer\results"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "fitness",
    "user": "postgres",
    "password": "666666",
}


def collect_confidence_from_jsons(results_dir: str) -> dict[str, float]:
    """Walk all exercise_result.json files and return {exercise_name: max_confidence}."""
    confidence_map: dict[str, float] = {}

    for root, _dirs, files in os.walk(results_dir):
        if "exercise_result.json" not in files:
            continue
        filepath = os.path.join(root, "exercise_result.json")
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[WARN] Skipping {filepath}: {exc}")
            continue

        for entry in data.get("results", []):
            result = entry.get("result", {})
            exercise_name = result.get("exercise")
            confidence = result.get("confidence")
            if exercise_name and confidence is not None:
                existing = confidence_map.get(exercise_name, 0.0)
                if confidence > existing:
                    confidence_map[exercise_name] = confidence
                    print(f"  Found: {exercise_name} confidence={confidence} (from {filepath})")

    return confidence_map


def update_database(confidence_map: dict[str, float]) -> None:
    """Update exercise_execution rows with the collected confidence values."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for exercise_name, confidence in sorted(confidence_map.items()):
                cur.execute(
                    """
                    UPDATE exercise_execution
                       SET confidence = %s
                     WHERE exercise_name = %s
                       AND (confidence IS NULL OR confidence = 0.85)
                    RETURNING execution_id, exercise_name, confidence
                    """,
                    (confidence, exercise_name),
                )
                updated = cur.fetchall()
                if updated:
                    print(f"[UPDATE] {exercise_name} -> {confidence} ({len(updated)} rows)")
                    for row in updated:
                        print(f"         execution_id={row['execution_id']}")
                else:
                    print(f"[SKIP]   {exercise_name} -> {confidence} (no matching rows to update)")

        conn.commit()
        print("\nDone. All updates committed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    print("=== Collecting confidence values from JSON files ===\n")
    confidence_map = collect_confidence_from_jsons(RESULTS_DIR)

    if not confidence_map:
        print("\nNo confidence values found. Nothing to update.")
        return

    print(f"\n=== Updating database ({len(confidence_map)} exercises) ===\n")
    update_database(confidence_map)


if __name__ == "__main__":
    main()
