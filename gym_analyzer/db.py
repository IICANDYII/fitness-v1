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
        confidence = float(seg.get("confidence", 0.85) or 0.85)
        if name not in agg:
            agg[name] = {"sets": sets, "reps": reps,
                         "start_sec": start_sec, "end_sec": end_sec,
                         "total_duration": seg_dur, "confidence": confidence}
        else:
            agg[name]["sets"]           += sets
            agg[name]["reps"]            = max(agg[name]["reps"], reps)
            agg[name]["end_sec"]         = max(agg[name]["end_sec"], end_sec)
            agg[name]["total_duration"] += seg_dur
            agg[name]["confidence"]      = max(agg[name]["confidence"], confidence)

    for name, a in agg.items():
        ts_start     = base_dt + timedelta(seconds=a["start_sec"])
        ts_end       = base_dt + timedelta(seconds=a["end_sec"])
        duration_sec = a["total_duration"]            # 实际运动秒数之和
        cur.execute("""
            INSERT INTO exercise_execution
                (user_id, session_id, exercise_name,
                 timestamp, end_time, duration_sec,
                 sets, reps, tempo, rom, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, session_id, name,
              ts_start, ts_end, duration_sec,
              a["sets"], a["reps"], None, None, a.get("confidence", 0.85)))


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
          "rear-shoulders", "triceps", "traps"}


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


def get_exercise_muscles(name_cn: str, cur=None) -> dict[str, list[str]]:
    """Query primary/secondary SVG muscle IDs from exercises table by Chinese name.

    Returns {"primary": [...], "secondary": [...]} or empty lists if not found.
    Tries exact match first, then substring match.
    """
    close = False
    if cur is None:
        conn = get_conn()
        cur = conn.cursor()
        close = True
    try:
        cur.execute(
            "SELECT source_data->'muscles' AS m FROM exercises WHERE name_cn = %s "
            "ORDER BY CASE WHEN exercise_id NOT LIKE '%%\\_001' THEN 0 ELSE 1 END LIMIT 1",
            (name_cn,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                "SELECT source_data->'muscles' AS m FROM exercises "
                "WHERE name_cn LIKE %s "
                "ORDER BY CASE WHEN exercise_id NOT LIKE '%%\\_001' THEN 0 ELSE 1 END, LENGTH(name_cn) LIMIT 1",
                (f'%{name_cn}%',),
            )
            row = cur.fetchone()
        if not row or not row["m"]:
            return {"primary": [], "secondary": []}
        m = row["m"] if isinstance(row["m"], dict) else json.loads(row["m"])
        fm = m.get("frontBodyMap", {})
        bm = m.get("backBodyMap", {})
        primary = list(dict.fromkeys(fm.get("text-mw-red", []) + bm.get("text-mw-red", [])))
        secondary = list(dict.fromkeys(fm.get("text-mw-gray", []) + bm.get("text-mw-gray", [])))
        return {"primary": primary, "secondary": secondary}
    finally:
        if close:
            conn.close()


def get_exercise_met(name_cn: str, cur=None) -> float:
    """Query estimated MET value from exercises table by Chinese name.

    Returns the MET value or 4.0 as default (moderate resistance training).
    """
    close = False
    if cur is None:
        conn = get_conn()
        cur = conn.cursor()
        close = True
    try:
        cur.execute(
            "SELECT estimated_mets FROM exercises WHERE name_cn = %s "
            "AND estimated_mets IS NOT NULL "
            "ORDER BY CASE WHEN exercise_id NOT LIKE '%%\\_001' THEN 0 ELSE 1 END LIMIT 1",
            (name_cn,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                "SELECT estimated_mets FROM exercises "
                "WHERE name_cn LIKE %s AND estimated_mets IS NOT NULL "
                "ORDER BY CASE WHEN exercise_id NOT LIKE '%%\\_001' THEN 0 ELSE 1 END, LENGTH(name_cn) LIMIT 1",
                (f'%{name_cn}%',),
            )
            row = cur.fetchone()
        return float(row["estimated_mets"]) if row and row["estimated_mets"] else 4.0
    finally:
        if close:
            conn.close()


def get_exercise_met_batch(names: list[str]) -> dict[str, float]:
    """Batch query MET values for multiple exercise names. Returns {name_cn: met}."""
    if not names:
        return {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT DISTINCT ON (name_cn) name_cn, estimated_mets
            FROM exercises
            WHERE name_cn = ANY(%s) AND estimated_mets IS NOT NULL
            ORDER BY name_cn,
                     CASE WHEN exercise_id NOT LIKE '%%\\_001' THEN 0 ELSE 1 END,
                     exercise_id
        """, (list(set(names)),))
        result = {r["name_cn"]: float(r["estimated_mets"]) for r in cur.fetchall()}
        missing = [n for n in names if n not in result]
        for name in missing:
            cur.execute(
                "SELECT estimated_mets FROM exercises "
                "WHERE name_cn LIKE %s AND estimated_mets IS NOT NULL "
                "ORDER BY CASE WHEN exercise_id NOT LIKE '%%\\_001' THEN 0 ELSE 1 END, LENGTH(name_cn) LIMIT 1",
                (f'%{name}%',),
            )
            row = cur.fetchone()
            if row and row["estimated_mets"]:
                result[name] = float(row["estimated_mets"])
        return result
    finally:
        conn.close()


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


# ── 批量导入 exercise_mapping_v1.json + SVG 肌群映射 ────────────────────────

_EXERCISE_MUSCLES_SVG: dict[str, dict[str, list[str]]] = {
    "跑步机":           {"primary": ["quads", "hamstrings", "calves"], "secondary": ["glutes"]},
    "椭圆机":           {"primary": ["quads", "hamstrings"], "secondary": ["glutes", "calves"]},
    "登阶机/爬楼机":    {"primary": ["quads", "glutes", "calves"], "secondary": ["hamstrings"]},
    "健身车/动感单车":   {"primary": ["quads", "hamstrings"], "secondary": ["calves", "glutes"]},
    "交叉训练车":       {"primary": ["quads", "hamstrings"], "secondary": ["glutes", "calves"]},
    "高位下拉":         {"primary": ["lats"], "secondary": ["biceps", "rear-shoulders"]},
    "坐姿绳索划船":     {"primary": ["lats", "traps"], "secondary": ["biceps", "rear-shoulders"]},
    "绳索下压":         {"primary": ["triceps"], "secondary": []},
    "绳索夹胸":         {"primary": ["chest"], "secondary": []},
    "绳索侧平举":       {"primary": ["front-shoulders"], "secondary": ["rear-shoulders"]},
    "绳索过顶臂屈伸":   {"primary": ["triceps"], "secondary": []},
    "绳索弯举":         {"primary": ["biceps"], "secondary": ["forearms"]},
    "固定器械推胸":     {"primary": ["chest"], "secondary": ["front-shoulders", "triceps"]},
    "蝴蝶机夹胸":       {"primary": ["chest"], "secondary": []},
    "固定器械推肩":     {"primary": ["front-shoulders"], "secondary": ["triceps", "traps"]},
    "固定器械侧平举":   {"primary": ["front-shoulders"], "secondary": ["rear-shoulders"]},
    "坐姿腿屈伸":       {"primary": ["quads"], "secondary": []},
    "坐姿腿弯举":       {"primary": ["hamstrings"], "secondary": []},
    "腿举":             {"primary": ["quads", "glutes"], "secondary": ["hamstrings"]},
    "固定器械提踵":     {"primary": ["calves"], "secondary": []},
    "辅助引体向上":     {"primary": ["lats"], "secondary": ["biceps", "rear-shoulders"]},
    "辅助双杠臂屈伸":   {"primary": ["chest", "triceps"], "secondary": ["front-shoulders"]},
    "固定器械坐姿划船": {"primary": ["lats", "traps"], "secondary": ["biceps", "rear-shoulders"]},
    "史密斯深蹲":       {"primary": ["quads", "glutes"], "secondary": ["hamstrings", "lowerback"]},
    "史密斯硬拉":       {"primary": ["hamstrings", "lowerback"], "secondary": ["glutes", "traps", "lats"]},
    "史密斯推肩":       {"primary": ["front-shoulders"], "secondary": ["triceps", "traps"]},
    "史密斯卧推":       {"primary": ["chest"], "secondary": ["front-shoulders", "triceps"]},
    "史密斯上斜卧推":   {"primary": ["chest"], "secondary": ["front-shoulders", "triceps"]},
    "杠铃硬拉":         {"primary": ["hamstrings", "lowerback"], "secondary": ["glutes", "traps", "lats"]},
    "杠铃深蹲":         {"primary": ["quads", "glutes"], "secondary": ["hamstrings", "lowerback"]},
    "杠铃俯身划船":     {"primary": ["lats", "traps"], "secondary": ["biceps", "lowerback"]},
    "杠铃弯举":         {"primary": ["biceps"], "secondary": ["forearms"]},
    "杠铃卧推":         {"primary": ["chest"], "secondary": ["front-shoulders", "triceps"]},
    "杠铃上斜卧推":     {"primary": ["chest"], "secondary": ["front-shoulders", "triceps"]},
    "杠铃推举":         {"primary": ["front-shoulders"], "secondary": ["triceps", "traps"]},
    "哑铃弯举":         {"primary": ["biceps"], "secondary": ["forearms"]},
    "哑铃侧平举":       {"primary": ["front-shoulders"], "secondary": ["rear-shoulders"]},
    "哑铃推肩":         {"primary": ["front-shoulders"], "secondary": ["triceps", "traps"]},
    "哑铃深蹲":         {"primary": ["quads", "glutes"], "secondary": ["hamstrings"]},
    "哑铃硬拉":         {"primary": ["hamstrings", "lowerback"], "secondary": ["glutes", "traps"]},
    "哑铃罗马尼亚硬拉": {"primary": ["hamstrings", "glutes"], "secondary": ["lowerback"]},
    "哑铃上台阶":       {"primary": ["quads", "glutes"], "secondary": ["hamstrings"]},
    "哑铃提踵":         {"primary": ["calves"], "secondary": []},
    "哑铃卧推":         {"primary": ["chest"], "secondary": ["front-shoulders", "triceps"]},
    "引体向上":         {"primary": ["lats"], "secondary": ["biceps", "rear-shoulders"]},
    "俯卧撑":           {"primary": ["chest", "triceps"], "secondary": ["front-shoulders"]},
    "箭步蹲":           {"primary": ["quads", "glutes"], "secondary": ["hamstrings"]},
    "自重深蹲":         {"primary": ["quads", "glutes"], "secondary": ["hamstrings"]},
    "双杠臂屈伸":       {"primary": ["chest", "triceps"], "secondary": ["front-shoulders"]},
}


_EXERCISE_METS: dict[str, float] = {
    "跑步机": 8.3, "椭圆机": 5.0, "登阶机/爬楼机": 7.0,
    "健身车/动感单车": 6.8, "交叉训练车": 5.0,
    "高位下拉": 4.5, "坐姿绳索划船": 4.5, "绳索下压": 3.5,
    "绳索夹胸": 3.5, "绳索侧平举": 3.0, "绳索过顶臂屈伸": 3.5,
    "绳索弯举": 3.0,
    "固定器械推胸": 5.0, "蝴蝶机夹胸": 3.5, "固定器械推肩": 4.5,
    "固定器械侧平举": 3.0, "坐姿腿屈伸": 3.5, "坐姿腿弯举": 3.5,
    "腿举": 5.0, "固定器械提踵": 3.0, "辅助引体向上": 5.0,
    "辅助双杠臂屈伸": 5.0, "固定器械坐姿划船": 4.5,
    "史密斯深蹲": 6.0, "史密斯硬拉": 6.0, "史密斯推肩": 4.5,
    "史密斯卧推": 5.5, "史密斯上斜卧推": 5.5,
    "杠铃硬拉": 6.0, "杠铃深蹲": 6.0, "杠铃俯身划船": 5.0,
    "杠铃弯举": 3.0, "杠铃卧推": 5.5, "杠铃上斜卧推": 5.5,
    "杠铃推举": 5.0,
    "哑铃弯举": 3.0, "哑铃侧平举": 3.0, "哑铃推肩": 4.5,
    "哑铃深蹲": 5.5, "哑铃硬拉": 5.5, "哑铃罗马尼亚硬拉": 5.5,
    "哑铃上台阶": 5.0, "哑铃提踵": 3.0, "哑铃卧推": 5.5,
    "引体向上": 8.0, "俯卧撑": 3.8, "箭步蹲": 5.0,
    "自重深蹲": 5.0, "双杠臂屈伸": 5.5,
}


def import_exercise_mapping(json_path: str | Path | None = None) -> int:
    """Import exercise_mapping_v1.json into the exercises table with SVG muscle data.

    Merges exercise metadata from the JSON with SVG muscle IDs from _EXERCISE_MUSCLES_SVG.
    Returns the number of rows upserted.
    """
    if json_path is None:
        json_path = Path(__file__).parent / "exercises_data" / "exercise_mapping_v1.json"
    json_path = Path(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    conn = get_conn()
    cur = conn.cursor()
    count = 0
    try:
        for exercise_id, info in mapping.items():
            name_cn = info.get("product_action_cn", "")
            equipment = info.get("standard_equipment", "")
            training_part = info.get("training_part_cn", "")
            action_pattern = info.get("action_pattern", "")
            level = info.get("first_person_level_min", "")

            muscles = _EXERCISE_MUSCLES_SVG.get(name_cn, {"primary": [], "secondary": []})
            source_data = _build_source_data(muscles["primary"], muscles.get("secondary", []))
            source_data["equipment"] = equipment
            source_data["training_part"] = training_part

            met_value = _EXERCISE_METS.get(name_cn)

            cur.execute("""
                INSERT INTO exercises (exercise_id, name, name_cn, source_data,
                                      movement_pattern, difficulty, estimated_mets)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (exercise_id) DO UPDATE
                    SET name_cn          = EXCLUDED.name_cn,
                        source_data      = EXCLUDED.source_data,
                        movement_pattern = EXCLUDED.movement_pattern,
                        difficulty       = EXCLUDED.difficulty,
                        estimated_mets   = COALESCE(EXCLUDED.estimated_mets, exercises.estimated_mets)
            """, (exercise_id, exercise_id.replace("_", " "), name_cn,
                  json.dumps(source_data, ensure_ascii=False),
                  action_pattern, level, met_value))
            count += cur.rowcount

        conn.commit()
        print(f"  [import] {count} exercises upserted into DB")
    finally:
        conn.close()
    return count


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
