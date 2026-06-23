#!/usr/bin/env python3
"""
Insert user profile + 12 training sessions for:
  男 30岁 177cm / 70kg  目标: 增肌+减脂
  user_id: 00000000-0000-0000-0000-000000025803  (DEFAULT_UID in api.py)

日期与 api.py _DATE_VIDEO_MAP 完全对齐，确保视频回放可用。
"""

import sys
import uuid as _uuid
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta

# Make psycopg2 handle UUID columns as Python uuid.UUID objects (not plain strings)
psycopg2.extras.register_uuid()

DB = dict(
    host="localhost", port=5432, dbname="fitness",
    user="postgres", password="666666", connect_timeout=5,
)

USER_ID = "00000000-0000-0000-0000-000000025803"

# ── 12 training sessions ──────────────────────────────────────────────────────
# Exercise names match EXERCISE_ALIAS keys in api.py → canonical lookup works.
# dur_sec = total actual exercise time (no rest), used for MET calorie calc.

SESSIONS = [
    {
        "date": "2026-05-27", "start_hour": 18, "duration_min": 62,
        "completion_rate": 0.95, "total_volume": 13200,
        "exercises": [
            {"name": "平板卧推",    "sets": 4, "reps": 10, "dur_sec": 600, "conf": 0.90},
            {"name": "上斜哑铃推",  "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.85},
            {"name": "侧平举",      "sets": 3, "reps": 15, "dur_sec": 420, "conf": 0.88},
            {"name": "绳索下压",    "sets": 3, "reps": 12, "dur_sec": 420, "conf": 0.87},
        ],
    },
    {
        "date": "2026-05-29", "start_hour": 19, "duration_min": 65,
        "completion_rate": 1.0, "total_volume": 10800,
        "exercises": [
            {"name": "杠铃划船",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.88},
            {"name": "引体向上",    "sets": 3, "reps":  8, "dur_sec": 540, "conf": 0.82},
            {"name": "器械下拉",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.90},
            {"name": "杠铃弯举",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.89},
        ],
    },
    {
        "date": "2026-05-31", "start_hour": 10, "duration_min": 70,
        "completion_rate": 0.92, "total_volume": 18400,
        "exercises": [
            {"name": "深蹲",        "sets": 4, "reps": 10, "dur_sec": 720, "conf": 0.85},
            {"name": "腿举",        "sets": 3, "reps": 12, "dur_sec": 540, "conf": 0.90},
            {"name": "罗马尼亚硬拉","sets": 3, "reps": 10, "dur_sec": 540, "conf": 0.86},
            {"name": "腿弯举",      "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.88},
            {"name": "提踵",        "sets": 3, "reps": 20, "dur_sec": 360, "conf": 0.92},
        ],
    },
    {
        "date": "2026-06-02", "start_hour": 18, "duration_min": 60,
        "completion_rate": 1.0, "total_volume": 13000,
        "exercises": [
            {"name": "平板卧推",    "sets": 4, "reps":  8, "dur_sec": 660, "conf": 0.92},
            {"name": "上斜哑铃推",  "sets": 3, "reps": 10, "dur_sec": 480, "conf": 0.87},
            {"name": "站姿推举",    "sets": 3, "reps": 10, "dur_sec": 480, "conf": 0.83},
            {"name": "绳索下压",    "sets": 3, "reps": 12, "dur_sec": 420, "conf": 0.88},
        ],
    },
    {
        "date": "2026-06-03", "start_hour": 19, "duration_min": 63,
        "completion_rate": 0.95, "total_volume": 10400,
        "exercises": [
            {"name": "杠铃划船",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.90},
            {"name": "引体向上",    "sets": 3, "reps":  6, "dur_sec": 540, "conf": 0.80},
            {"name": "杠铃弯举",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.88},
            {"name": "悬垂举腿",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.85},
        ],
    },
    {
        "date": "2026-06-05", "start_hour": 18, "duration_min": 68,
        "completion_rate": 0.95, "total_volume": 21600,
        "exercises": [
            {"name": "深蹲",        "sets": 5, "reps":  8, "dur_sec": 900, "conf": 0.88},
            {"name": "腿举",        "sets": 4, "reps": 12, "dur_sec": 660, "conf": 0.91},
            {"name": "罗马尼亚硬拉","sets": 3, "reps": 10, "dur_sec": 540, "conf": 0.86},
            {"name": "提踵",        "sets": 4, "reps": 20, "dur_sec": 480, "conf": 0.93},
        ],
    },
    {
        "date": "2026-06-06", "start_hour": 18, "duration_min": 72,
        "completion_rate": 1.0, "total_volume": 15200,
        "exercises": [
            {"name": "平板卧推",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.91},
            {"name": "上斜哑铃推",  "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.88},
            {"name": "杠铃划船",    "sets": 3, "reps": 10, "dur_sec": 540, "conf": 0.89},
            {"name": "绳索下压",    "sets": 4, "reps": 12, "dur_sec": 540, "conf": 0.89},
        ],
    },
    {
        "date": "2026-06-08", "start_hour": 19, "duration_min": 60,
        "completion_rate": 1.0, "total_volume": 11200,
        "exercises": [
            {"name": "平板卧推",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.91},
            {"name": "杠铃弯举",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.88},
            {"name": "绳索下压",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.87},
            {"name": "侧平举",      "sets": 3, "reps": 15, "dur_sec": 420, "conf": 0.86},
        ],
    },
    {
        "date": "2026-06-10", "start_hour": 19, "duration_min": 65,
        "completion_rate": 1.0, "total_volume": 10600,
        "exercises": [
            {"name": "站姿推举",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.85},
            {"name": "侧平举",      "sets": 4, "reps": 15, "dur_sec": 600, "conf": 0.89},
            {"name": "器械下拉",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.92},
            {"name": "面拉",        "sets": 3, "reps": 15, "dur_sec": 480, "conf": 0.87},
        ],
    },
    {
        "date": "2026-06-11", "start_hour": 18, "duration_min": 70,
        "completion_rate": 0.95, "total_volume": 11800,
        "exercises": [
            {"name": "站姿推举",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.86},
            {"name": "侧平举",      "sets": 4, "reps": 15, "dur_sec": 600, "conf": 0.88},
            {"name": "杠铃划船",    "sets": 3, "reps": 10, "dur_sec": 540, "conf": 0.89},
            {"name": "引体向上",    "sets": 3, "reps":  6, "dur_sec": 540, "conf": 0.80},
            {"name": "面拉",        "sets": 3, "reps": 15, "dur_sec": 480, "conf": 0.87},
        ],
    },
    {
        "date": "2026-06-13", "start_hour": 19, "duration_min": 63,
        "completion_rate": 1.0, "total_volume": 11400,
        "exercises": [
            {"name": "站姿推举",    "sets": 4, "reps": 10, "dur_sec": 660, "conf": 0.86},
            {"name": "侧平举",      "sets": 4, "reps": 15, "dur_sec": 600, "conf": 0.88},
            {"name": "杠铃划船",    "sets": 3, "reps": 10, "dur_sec": 540, "conf": 0.90},
            {"name": "器械下拉",    "sets": 3, "reps": 12, "dur_sec": 480, "conf": 0.92},
        ],
    },
    {
        "date": "2026-06-15", "start_hour": 10, "duration_min": 72,
        "completion_rate": 1.0, "total_volume": 20000,
        "exercises": [
            {"name": "深蹲",        "sets": 4, "reps": 10, "dur_sec": 720, "conf": 0.87},
            {"name": "腿举",        "sets": 3, "reps": 12, "dur_sec": 540, "conf": 0.91},
            {"name": "罗马尼亚硬拉","sets": 3, "reps": 10, "dur_sec": 540, "conf": 0.86},
            {"name": "提踵",        "sets": 3, "reps": 20, "dur_sec": 360, "conf": 0.93},
            {"name": "臀桥",        "sets": 3, "reps": 15, "dur_sec": 420, "conf": 0.88},
        ],
    },
]


def upsert_user(cur):
    """Ensure user exists in user_profile_long_term with full profile."""
    cur.execute("""
        INSERT INTO user_profile_long_term
            (user_id, gender, age, height, weight, fitness_goal,
             experience_level, sleep_hours)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
            SET gender           = EXCLUDED.gender,
                age              = EXCLUDED.age,
                height           = EXCLUDED.height,
                weight           = EXCLUDED.weight,
                fitness_goal     = EXCLUDED.fitness_goal,
                experience_level = EXCLUDED.experience_level,
                updated_at       = NOW()
    """, (USER_ID, "male", 30, 177, 70, "增肌+减脂", "intermediate", 7.5))
    print(f"  [user]  user_profile_long_term upserted: {USER_ID}")


def insert_session(session: dict, cur) -> str:
    """Delete existing session for this date, insert fresh, return session_id."""
    date_str = session["date"]

    # Remove any existing session for this user + date
    cur.execute("""
        SELECT session_id FROM workout_session
        WHERE user_id = %s AND DATE(start_time) = %s
    """, (USER_ID, date_str))
    old_ids = [r["session_id"] for r in cur.fetchall()]
    if old_ids:
        cur.execute("DELETE FROM exercise_execution WHERE session_id = ANY(%s)", (old_ids,))
        cur.execute("DELETE FROM workout_session    WHERE session_id = ANY(%s)", (old_ids,))
        print(f"  [del]   removed {len(old_ids)} old session(s) for {date_str}")

    start_dt = datetime.fromisoformat(date_str).replace(
        hour=session["start_hour"], minute=0, second=0
    )
    end_dt   = start_dt + timedelta(minutes=session["duration_min"])

    cur.execute("""
        INSERT INTO workout_session
            (user_id, start_time, end_time, calories, completion_rate, total_volume)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """, (USER_ID, start_dt, end_dt,
          0.0,                            # calories — api.py recomputes via MET on first /api/daily call
          session["completion_rate"],
          session["total_volume"]))

    return str(cur.fetchone()["session_id"])


def insert_exercises(session_id: str, session: dict, cur):
    """Insert exercise_execution rows with sequential timestamps."""
    start_dt   = datetime.fromisoformat(session["date"]).replace(
        hour=session["start_hour"], minute=5, second=0   # first exercise starts 5 min in (warm-up)
    )
    cursor_dt  = start_dt

    for ex in session["exercises"]:
        dur     = ex["dur_sec"]
        ts_start = cursor_dt
        ts_end   = ts_start + timedelta(seconds=dur)
        cur.execute("""
            INSERT INTO exercise_execution
                (user_id, session_id, exercise_name,
                 timestamp, end_time, duration_sec,
                 sets, reps, tempo, rom, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (USER_ID, session_id, ex["name"],
              ts_start, ts_end, dur,
              ex["sets"], ex["reps"],
              "2-0-2", 0.85,
              ex["conf"]))
        # advance cursor: exercise time + ~2 min rest per set
        rest_sec = ex["sets"] * 120
        cursor_dt = ts_end + timedelta(seconds=rest_sec)


def main():
    print(f"Connecting to PostgreSQL @ {DB['host']}:{DB['port']}/{DB['dbname']} …")
    try:
        conn = psycopg2.connect(**DB, cursor_factory=psycopg2.extras.RealDictCursor)
    except Exception as e:
        print(f"ERROR: cannot connect to DB — {e}")
        print("Make sure the Docker container is running: docker start postgres-pgvector")
        sys.exit(1)

    cur = conn.cursor()
    ok  = 0

    try:
        # 1. Upsert user profile
        upsert_user(cur)

        # 2. Insert 12 sessions
        for s in SESSIONS:
            try:
                sid = insert_session(s, cur)
                insert_exercises(sid, s, cur)
                n_ex = len(s["exercises"])
                print(f"  [ok]    {s['date']}  {s['duration_min']} min  "
                      f"{n_ex} exercises  session={sid[:12]}…")
                ok += 1
            except Exception as e:
                print(f"  [FAIL]  {s['date']}  {e}")
                conn.rollback()
                # Re-open transaction for remaining sessions
                conn = psycopg2.connect(**DB, cursor_factory=psycopg2.extras.RealDictCursor)
                cur  = conn.cursor()
                continue

        conn.commit()
        print(f"\n[OK] Done: {ok}/{len(SESSIONS)} sessions inserted for user {USER_ID}")
        print("  Open http://localhost:8000 to view the dashboard.")

    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Fatal error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
