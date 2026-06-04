"""PostgreSQL integration for gym_analyzer.

All write functions accept an explicit user_id so video analysis data can be
linked to any user in user_profile_long_term.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

_DB_DEFAULTS = dict(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "fitness"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "666666"),
)


def get_conn():
    return psycopg2.connect(**_DB_DEFAULTS, cursor_factory=psycopg2.extras.RealDictCursor)


# ── 动作名标准化：对齐到 exercises 库 ─────────────────────────────────────────

def _edit_distance(a: str, b: str) -> int:
    """Levenshtein 距离。"""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0: return lb
    if lb == 0: return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[lb]


def _match_name(name: str, db_names: list[str]) -> str:
    """把 AI 识别的动作名对齐到 exercises.name_cn 中最接近的条目。

    优先级：
      1. 精确匹配
      2. 互为子串且长度差 ≤ 3（处理「深蹲」/「杠铃深蹲」等前后缀差异）
      3. 编辑距离 ≤ 2（处理「史密斯深蹲」/「史密斯机深蹲」等一两字差异）
    未匹配到时返回原名（调用方可决定是否新建条目）。
    """
    if not name or not db_names:
        return name
    if name in db_names:
        return name
    # 子串匹配
    for db in db_names:
        if db and (name in db or db in name) and abs(len(name) - len(db)) <= 3:
            return db
    # 编辑距离
    best, best_d = None, 3
    for db in db_names:
        if not db:
            continue
        d = _edit_distance(name, db)
        if d < best_d:
            best_d, best = d, db
    return best if best else name


def _load_db_names(cur) -> list[str]:
    """从 exercises 表读取所有 name_cn（去除空值）。"""
    cur.execute("SELECT name_cn FROM exercises WHERE name_cn IS NOT NULL AND name_cn != ''")
    return [r["name_cn"] for r in cur.fetchall()]


def normalize_segment_names(segments: list[dict], db_names: list[str]) -> tuple[list[dict], dict[str, str]]:
    """把 segments 里每个 exercise_name 对齐到库中标准名。

    返回 (normalized_segments, mapping)，mapping 记录被替换的名称对供日志使用。
    """
    mapping: dict[str, str] = {}
    result = []
    for seg in segments:
        if seg.get("type") == "exercise" and seg.get("exercise_name"):
            orig = seg["exercise_name"]
            norm = _match_name(orig, db_names)
            if norm != orig:
                mapping[orig] = norm
                seg = dict(seg)
                seg["exercise_name"] = norm
        result.append(seg)
    return result, mapping


# ── exercise_execution ────────────────────────────────────────────────────────

def write_exercises(session_id: str, segments: list[dict],
                    date_str: str, user_id: str, cur) -> None:
    """Insert exercise_execution rows (aggregated by exercise name).

    同名动作的多个段（多组）聚合为一行：
      sets  = 各段 sets_count 之和
      reps  = 各段 reps_estimate 的最大值（单组次数）
      timestamp / end_time = 首次出现 / 最后出现的时间戳
    """
    base_dt = datetime.fromisoformat(date_str)
    from collections import OrderedDict

    # 按首次出现顺序聚合
    agg: OrderedDict[str, dict] = OrderedDict()
    for seg in segments:
        if seg.get("type") != "exercise":
            continue
        name      = seg.get("exercise_name") or "未知动作"
        sets      = max(1, int(seg.get("sets_count") or 1))
        reps      = max(0, int(seg.get("reps_estimate") or 0))
        start_sec = float(seg.get("start_sec", 0))
        end_sec   = float(seg.get("end_sec", start_sec))
        seg_dur   = max(0.0, end_sec - start_sec)
        if name not in agg:
            agg[name] = {"sets": sets, "reps": reps,
                         "start_sec": start_sec, "end_sec": end_sec,
                         "total_duration": seg_dur}
        else:
            agg[name]["sets"]           += sets
            agg[name]["reps"]            = max(agg[name]["reps"], reps)
            agg[name]["end_sec"]         = max(agg[name]["end_sec"], end_sec)
            agg[name]["total_duration"] += seg_dur   # 累加各组实际时长，排除组间休息

    for name, a in agg.items():
        ts_start     = base_dt + timedelta(seconds=a["start_sec"])
        ts_end       = base_dt + timedelta(seconds=a["end_sec"])
        duration_sec = a["total_duration"]            # 实际运动秒数之和
        cur.execute("""
            INSERT INTO exercise_execution
                (user_id, session_id, exercise_name,
                 timestamp, end_time, duration_sec,
                 sets, reps, tempo, rom)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, session_id, name,
              ts_start, ts_end, duration_sec,
              a["sets"], a["reps"], None, None))


# ── biometric_stream ──────────────────────────────────────────────────────────

def write_heart_rate(hr_rows: list[dict], user_id: str, cur) -> None:
    """Insert biometric_stream rows (uses caller's cursor/transaction)."""
    for row in hr_rows:
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        cur.execute("""
            INSERT INTO biometric_stream
                (user_id, timestamp, heart_rate, hrv, fatigue_score, steps)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, ts, int(row["heart_rate"]),
              float(row.get("hrv", 0) or 0),
              float(row.get("fatigue_score", 0) or 0),
              int(row.get("steps", 0) or 0)))


def load_hr_csv(csv_path: str, session_date: str) -> list[dict]:
    """Load a heart rate CSV into rows for write_heart_rate()."""
    rows: list[dict] = []
    base_dt = datetime.fromisoformat(session_date)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return rows
        headers = [h.lower().strip() for h in reader.fieldnames]
        ts_col  = next((h for h in headers if "time" in h or h == "ts"), None)
        hr_col  = next((h for h in headers if "bpm" in h or "heart" in h or h == "hr"), None)
        if not ts_col or not hr_col:
            return rows
        orig_ts = reader.fieldnames[headers.index(ts_col)]
        orig_hr = reader.fieldnames[headers.index(hr_col)]
        for raw in reader:
            try:
                ts_raw = raw[orig_ts].strip()
                hr_val = int(float(raw[orig_hr].strip()))
                try:
                    ts = datetime.fromisoformat(ts_raw)
                except ValueError:
                    ts = base_dt + timedelta(seconds=float(ts_raw))
                rows.append({"timestamp": ts, "heart_rate": hr_val})
            except Exception:
                continue
    return rows


# ── exercises table — muscle mapping ─────────────────────────────────────────

_FRONT = {"chest", "abdominals", "obliques", "front-shoulders",
          "biceps", "forearms", "quads", "calves", "traps"}
_BACK  = {"lats", "lowerback", "hamstrings", "glutes",
          "rear-shoulders", "triceps", "traps-middle"}


def _build_source_data(primary: list[str], secondary: list[str]) -> dict:
    return {
        "muscles": {
            "frontBodyMap": {
                "text-mw-red":  [m for m in primary   if m in _FRONT],
                "text-mw-gray": [m for m in secondary if m in _FRONT],
            },
            "backBodyMap": {
                "text-mw-red":  [m for m in primary   if m in _BACK],
                "text-mw-gray": [m for m in secondary if m in _BACK],
            },
        }
    }


def upsert_exercises(exercise_names: list[str]) -> int:
    """Upsert exercises with muscle data so api.py compute_muscles() works."""
    from .config import EXERCISE_MUSCLES

    conn = get_conn()
    cur  = conn.cursor()
    inserted = 0
    try:
        for name_cn in set(exercise_names):
            mapping = EXERCISE_MUSCLES.get(name_cn)
            if mapping is None:
                for key, val in EXERCISE_MUSCLES.items():
                    if key in name_cn or name_cn in key:
                        mapping = val
                        break
            source_data = (
                _build_source_data(mapping["primary"], mapping.get("secondary", []))
                if mapping else
                {"muscles": {
                    "frontBodyMap": {"text-mw-red": [], "text-mw-gray": []},
                    "backBodyMap":  {"text-mw-red": [], "text-mw-gray": []},
                }}
            )
            exercise_id = "ex_" + name_cn.replace(" ", "_")
            cur.execute("""
                INSERT INTO exercises (exercise_id, name, name_cn, source_data)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (exercise_id) DO UPDATE
                    SET source_data = EXCLUDED.source_data,
                        name_cn     = EXCLUDED.name_cn
            """, (exercise_id, name_cn, name_cn,
                  json.dumps(source_data, ensure_ascii=False)))
            inserted += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return inserted


# ── Main tool function ────────────────────────────────────────────────────────

def save_to_db(dashboard: dict, user_id: str | None = None,
               hr_csv_path: str | None = None) -> dict:
    """用单个事务把当天同一用户的所有数据全部覆盖写入。

    清理范围（同 user_id + 同日期）：
      workout_session + exercise_execution（级联）+ biometric_stream

    写入顺序（全部在同一个连接 / 事务内）：
      1. upsert exercises（参考表，不做清理）
      2. 删除旧 workout_session + exercise_execution + biometric_stream
      3. 插入新 workout_session
      4. 插入新 exercise_execution（同名动作已聚合）
      5. 插入新 biometric_stream（仅当 hr_csv_path 有效时）
      6. COMMIT
    """
    try:
        from .config import DEFAULT_USER_ID
        user_id  = user_id or DEFAULT_USER_ID
        segments = dashboard.get("raw_segments", [])
        date_str = dashboard.get("date", datetime.now().date().isoformat())
        daily    = dashboard.get("daily", {})

        # 1. 加载库中所有 name_cn，把 segments 的动作名对齐到库中标准名
        _norm_conn = get_conn()
        _norm_cur  = _norm_conn.cursor()
        db_names   = _load_db_names(_norm_cur)
        _norm_conn.close()

        segments, name_map = normalize_segment_names(segments, db_names)
        if name_map:
            print(f"  [name-norm] 动作名对齐: {name_map}")

        # 2. 仅对库中不存在的动作新建条目（避免重复写入）
        known = set(db_names)
        new_names = [
            s["exercise_name"] for s in segments
            if s.get("type") == "exercise"
            and s.get("exercise_name")
            and s["exercise_name"] not in known
        ]
        if new_names:
            upsert_exercises(new_names)
            print(f"  [upsert] 新动作写入 exercises: {new_names}")

        # 2-6. 单连接 / 单事务写全部行记录
        hr_rows: list[dict] = []
        if hr_csv_path and Path(hr_csv_path).exists():
            hr_rows = load_hr_csv(hr_csv_path, date_str)

        duration   = float(daily.get("duration_min", 0))
        calories   = float(daily.get("calories", 0))
        completion = daily.get("completion_rate", 0) / 100.0
        start_dt   = datetime.fromisoformat(date_str)
        end_dt     = start_dt + timedelta(minutes=duration)

        conn = get_conn()
        cur  = conn.cursor()
        try:
            # 删除当天旧数据
            cur.execute("""
                SELECT session_id FROM workout_session
                WHERE user_id = %s AND DATE(start_time) = %s
            """, (user_id, date_str))
            old_ids = [r["session_id"] for r in cur.fetchall()]
            if old_ids:
                cur.execute("DELETE FROM exercise_execution WHERE session_id = ANY(%s)", (old_ids,))
                cur.execute("DELETE FROM workout_session    WHERE session_id = ANY(%s)", (old_ids,))

            cur.execute("""
                DELETE FROM biometric_stream
                WHERE user_id = %s AND DATE(timestamp) = %s
            """, (user_id, date_str))

            # 插入 workout_session
            cur.execute("""
                INSERT INTO workout_session
                    (user_id, start_time, end_time, calories, completion_rate, total_volume)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING session_id
            """, (user_id, start_dt, end_dt, calories, completion, 0.0))
            session_id = str(cur.fetchone()["session_id"])

            # 插入 exercise_execution（同名动作聚合）
            write_exercises(session_id, segments, date_str, user_id, cur)

            # 插入 biometric_stream（有 HR CSV 才写）
            if hr_rows:
                write_heart_rate(hr_rows, user_id, cur)

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return {
            "session_id":        session_id,
            "user_id":           user_id,
            "exercises_written": len([s for s in segments if s.get("type") == "exercise"]),
            "hr_points":         len(hr_rows),
            "status":            "ok",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
