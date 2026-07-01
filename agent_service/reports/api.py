from __future__ import annotations
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any
import psycopg2
import psycopg2.extras
import json
import threading
import uuid as _uuid
from datetime import datetime, timedelta, date
from collections import defaultdict
from pathlib import Path
import os

app = FastAPI(title="Fitness Dashboard API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"]
)

DB = dict(
    host=os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost")),
    port=int(os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432"))),
    dbname=os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "fitness")),
    user=os.getenv("DB_USER", os.getenv("POSTGRES_USER", "postgres")),
    password=os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "666666")),
    connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "3")),
)
USER_ID     = "00000000-0000-0000-0000-000000025803"
RESULTS_DIR = Path(__file__).parent.parent.parent / "gym_analyzer" / "results"

# exercise_execution.exercise_name (short/AI-variant) → exercises.name_cn (canonical)
EXERCISE_ALIAS: dict[str, str] = {
    "平板卧推":       "杠铃平卧推",
    "上斜哑铃推":     "哑铃上斜卧推",
    "侧平举":         "哑铃侧平举",
    "深蹲":           "杠铃深蹲",
    "硬拉":           "杠铃硬拉",
    "站姿推举":       "杠铃过顶推举",
    "提踵":           "站姿提踵",
    "杠铃划船":       "杠铃俯身划船",
    "罗马尼亚硬拉":   "杠铃罗马尼亚硬拉",
    "腿举":           "器械腿举",
    "腿弯举":         "器械腘绳肌弯举",
    "面拉":           "绳索面拉",
    "绳索下压":       "绳索下压",
    "引体向上":       "引体向上",
    "杠铃弯举":       "杠铃弯举",
    # AI 识别的变体名 → exercises.name_cn 精确值
    "史密斯深蹲":     "史密斯机深蹲",
    "跑步":           "跑步机慢跑",
    "器械下拉":       "器械下拉",
    "绳索反握下压":   "绳索下压",
    "悬垂举腿":       "悬垂举腿",
    "臀桥":           "臀桥",
}

# exercise_name → exercise category for the time-bar widget
# date → video file mapping (per user)
_DATE_VIDEO_MAP: dict[str, dict[str, str]] = {
    "00000000-0000-0000-0000-000000025803": {
        "2026-05-27": "1.mp4",
        "2026-05-29": "2.mp4",
        "2026-05-31": "3.mp4",
        "2026-06-02": "4.mp4",
        "2026-06-03": "8.mp4",
        "2026-06-05": "9.mp4",
        "2026-06-06": "张靖义-2026.06.11.mp4",
        "2026-06-08": "手臂-胸-杨博宇.mp4",
        "2026-06-10": "肩-秦紫渝.mp4",
        "2026-06-11": "肩-背-秦紫渝.mp4",
        "2026-06-13": "肩背-叶翔.mp4",
        "2026-06-15": "腿-张开.mp4",
    },
}

EXERCISE_CATEGORY: dict[str, str] = {
    # 有氧
    "跑步": "有氧", "慢跑": "有氧", "快走": "有氧", "健步走": "有氧",
    "游泳": "有氧", "骑车": "有氧", "单车": "有氧", "动感单车": "有氧",
    "椭圆机": "有氧", "跳绳": "有氧", "爬楼梯": "有氧", "划船机": "有氧",
    "有氧操": "有氧", "跑步机": "有氧", "室外跑": "有氧", "功率车": "有氧",
    "HIIT": "有氧", "踏步机": "有氧",
    # 核心
    "卷腹": "核心", "仰卧起坐": "核心", "平板支撑": "核心",
    "悬垂举腿": "核心", "俄罗斯转体": "核心", "腹轮": "核心",
    "侧卷腹": "核心", "反向卷腹": "核心", "死虫": "核心",
    "臀桥": "核心", "超人式": "核心", "腹肌撕裂者": "核心",
    "直腿抬高": "核心", "剪刀腿": "核心",
    # 热身/拉伸
    "热身": "热身/拉伸", "拉伸": "热身/拉伸", "动态拉伸": "热身/拉伸",
    "泡沫轴": "热身/拉伸", "瑜伽": "热身/拉伸", "静态拉伸": "热身/拉伸",
    "颈部拉伸": "热身/拉伸", "腿部拉伸": "热身/拉伸", "放松": "热身/拉伸",
}
# Anything not in the dict defaults to 力量 (strength/anaerobic)


def _read_raw_segments(date_str: str) -> tuple[list[dict], float]:
    """Read per-exercise segments from the gym_analyzer results JSON for a given date."""
    p = RESULTS_DIR / f"{date_str}.json"
    if not p.exists():
        return [], 0.0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        all_segs = data.get("raw_segments", [])
        exercise_segs = []
        for s in all_segs:
            if s.get("type") != "exercise":
                continue
            name      = s.get("exercise_name", "")
            canonical = EXERCISE_ALIAS.get(name, name)
            cat       = EXERCISE_CATEGORY.get(canonical) or EXERCISE_CATEGORY.get(name) or "力量"
            exercise_segs.append({
                "exercise_name":   name,
                "category":        cat,
                "start_sec":       round(float(s.get("start_sec", 0)), 1),
                "end_sec":         round(float(s.get("end_sec",   0)), 1),
                "sets_count":      int(s.get("sets_count", 1) or 1),
                "reps_estimate":   int(s.get("reps_estimate", 0) or 0),
                "primary_muscles": s.get("primary_muscles") or [],
                "secondary_muscles": s.get("secondary_muscles") or [],
                "exercise_reason": s.get("exercise_reason", ""),
                "action_disambiguation": s.get("action_disambiguation"),
                "reps_per_set":    s.get("reps_per_set") or [],
            })
        total_sec = max((s["end_sec"] for s in all_segs if "end_sec" in s), default=0.0)
        return exercise_segs, float(total_sec)
    except Exception:
        return [], 0.0


def _read_all_segments(date_str: str) -> list[dict]:
    """Read ALL segments (exercise + transition + rest) for the timeline visualization."""
    p = RESULTS_DIR / f"{date_str}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        all_segs = data.get("raw_segments", [])
        result = []
        for s in all_segs:
            seg = {
                "type":      s.get("type", "transition"),
                "start_sec": round(float(s.get("start_sec", 0)), 1),
                "end_sec":   round(float(s.get("end_sec",   0)), 1),
            }
            if s.get("type") == "exercise":
                seg["exercise_name"]  = s.get("exercise_name", "")
                seg["equipment"]      = s.get("equipment", "")
                seg["sets_count"]     = int(s.get("sets_count", 1) or 1)
                seg["reps_estimate"]  = int(s.get("reps_estimate", 0) or 0)
                seg["confidence"]     = float(s.get("confidence", 0) or 0)
                seg["exercise_reason"] = s.get("exercise_reason", "")
                seg["action_disambiguation"] = s.get("action_disambiguation")
                seg["reps_per_set"]  = s.get("reps_per_set") or []
            result.append(seg)
        return result
    except Exception:
        return []


# Major groups for Card 1 bar chart.
# Values are SVG muscle IDs (without b- prefix); both front and back maps are checked.
MAJOR_GROUPS: dict[str, list[str]] = {
    "胸":   ["chest"],
    "肩":   ["shoulders", "front-shoulders", "rear-shoulders"],
    "臂":   ["triceps", "biceps"],
    "背":   ["lats", "traps", "lowerback", "scapula"],
    "腿":   ["quads", "hamstrings", "calves"],
    "臀":   ["glutes", "hips"],
    "腹":   ["abdominals", "obliques"],
}

MUSCLE_CN: dict[str, str] = {
    "chest": "胸部", "front-shoulders": "肩前束", "rear-shoulders": "肩后束",
    "shoulders": "肩部", "triceps": "肱三头肌", "biceps": "肱二头肌",
    "lats": "背阔肌", "traps": "斜方肌", "lowerback": "下背", "scapula": "肩胛",
    "quads": "股四头肌", "hamstrings": "腘绳肌", "calves": "小腿",
    "glutes": "臀大肌", "hips": "髋部", "abdominals": "腹直肌", "obliques": "腹斜肌",
    "forearms": "前臂",
}


def compute_muscle_summary(raw_scores: dict[str, float]) -> dict:
    group_scores = {
        g: sum(raw_scores.get(m, 0) for m in ms)
        for g, ms in MAJOR_GROUPS.items()
    }
    trained = [(g, s) for g, s in group_scores.items() if s > 0]
    trained.sort(key=lambda x: x[1], reverse=True)
    missing = [g for g, s in group_scores.items() if s == 0]
    if not trained:
        return {"primary": [], "secondary": [], "missing": []}
    top = trained[0][1]
    primary = [g for g, s in trained if s >= top * 0.5]
    secondary = [g for g, s in trained if s < top * 0.5]
    return {"primary": primary, "secondary": secondary, "missing": missing}


BALANCE_MUSCLE_TO_GROUP: dict[str, str] = {}
for _bg, _bms in MAJOR_GROUPS.items():
    for _bm in _bms:
        BALANCE_MUSCLE_TO_GROUP[_bm] = _bg

_DEFAULT_TARGET: dict[str, float] = {
    "腿": 0.16, "臀": 0.14, "背": 0.16, "腹": 0.14,
    "胸": 0.14, "肩": 0.14, "臂": 0.12,
}


def compute_fitness_balance(cur, uid: str, ref_date) -> dict:
    """Rolling 7-day Fitness Balance v3 = 0.15*G + 0.40*S + 0.20*E + 0.25*C."""
    from gym_analyzer.db import get_exercise_muscles
    window_start = ref_date - timedelta(days=6)
    cur.execute("""
        SELECT DATE(ws.start_time) AS day, ee.exercise_name AS name,
               COALESCE(SUM(ee.sets), 0) AS sets,
               COALESCE(MAX(ee.confidence), 0.85) AS confidence
        FROM workout_session ws
        JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
        GROUP BY DATE(ws.start_time), ee.exercise_name
    """, (uid, window_start, ref_date))
    rows = cur.fetchall()

    strength_days: set = set()
    covered_groups: set = set()
    muscle_exposure: dict[str, float] = {g: 0.0 for g in MAJOR_GROUPS}
    exercises_data: list = []
    total_exercise_units: float = 0.0

    for r in rows:
        raw_sets = int(r["sets"] or 0)
        if raw_sets == 0:
            continue
        exercise_unit = min(raw_sets, 4)
        confidence = float(r["confidence"] or 0.85)
        strength_days.add(r["day"])
        total_exercise_units += exercise_unit
        mdata = get_exercise_muscles(r["name"])
        for mid in mdata.get("primary", []):
            bare = mid.lstrip("b-") if mid.startswith("b-") else mid
            grp = BALANCE_MUSCLE_TO_GROUP.get(bare)
            if grp:
                covered_groups.add(grp)
                muscle_exposure[grp] += exercise_unit * 1.0 * confidence
        for mid in mdata.get("secondary", []):
            bare = mid.lstrip("b-") if mid.startswith("b-") else mid
            grp = BALANCE_MUSCLE_TO_GROUP.get(bare)
            if grp:
                covered_groups.add(grp)
                muscle_exposure[grp] += exercise_unit * 0.5 * confidence
        unit_suf = min(exercise_unit / 2, 1)
        evidence_i = 0.35 * confidence + 0.25 * 0.7 + 0.25 * unit_suf + 0.15 * 0
        exercises_data.append({"unit": exercise_unit, "evidence": evidence_i})

    strength_days_7d = len(strength_days)
    covered_count = len(covered_groups)
    missing = [g for g in MAJOR_GROUPS if g not in covered_groups]

    if strength_days_7d == 0:
        return {"score": 0, "status": "insufficient_data",
                "G": 0, "S": 0, "E": 0, "C": 0,
                "strength_days": 0, "covered_count": 0,
                "missing_groups": missing}

    # --- G: Guideline Reference Score (15%) ---
    freq_ratio = min(strength_days_7d / 2, 1)
    cov_ratio = covered_count / 7
    G = 100 * min(freq_ratio, cov_ratio)

    # --- S: Preference-Adjusted Structure Score (40%) ---
    total_exposure = sum(muscle_exposure.values())
    if total_exposure > 0:
        actual_share = {g: muscle_exposure[g] / total_exposure for g in MAJOR_GROUPS}
        target = dict(_DEFAULT_TARGET)
        deviation = sum(abs(actual_share[g] - target[g]) for g in MAJOR_GROUPS)
        S = 100 * max(1 - 0.5 * deviation, 0)
    else:
        S = 0

    # --- E: Effective Training Evidence Score (20%) ---
    total_units = sum(e["unit"] for e in exercises_data)
    if total_units > 0:
        E = 100 * sum(e["evidence"] * e["unit"] for e in exercises_data) / total_units
    else:
        E = 0

    # --- C: Strength Consistency & Dose Score (25%) ---
    day_consistency = min(strength_days_7d / 4, 1)
    unit_dose = min(total_exercise_units / 8, 1)
    C = 100 * (0.6 * day_consistency + 0.4 * unit_dose)

    score = round(0.15 * G + 0.40 * S + 0.20 * E + 0.25 * C)
    status = "active" if score > 0 else "insufficient_data"
    return {
        "score": min(score, 100), "status": status,
        "G": round(G), "S": round(S), "E": round(E), "C": round(C),
        "strength_days": strength_days_7d,
        "covered_count": covered_count,
        "missing_groups": missing,
    }


def group_peak(muscles: list[str], svg_scores: dict[str, float]) -> float:
    """
    Peak individual-muscle score for a group.
    Checks both the front SVG key (e.g. 'lats') and the back SVG key ('b-lats')
    so the result is comparable to Card 2's per-muscle scores.
    """
    peak = 0.0
    for m in muscles:
        peak = max(peak,
                   svg_scores.get(m, 0),
                   svg_scores.get("b-" + m, 0))
    return peak


def group_total(muscles: list[str], raw_scores: dict[str, float]) -> float:
    """Total score of all muscles in a major group, using unprefixed muscle IDs."""
    return sum(raw_scores.get(m, 0) for m in muscles)


def compute_share_distribution(raw_scores: dict[str, float]) -> dict[str, int]:
    """Return major-group share_percent values for Card 1 bars."""
    group_scores = {
        label: group_total(muscles, raw_scores)
        for label, muscles in MAJOR_GROUPS.items()
    }
    total = sum(v for v in group_scores.values() if v > 0)
    if total <= 0:
        return {}
    return {
        label: round(score / total * 100)
        for label, score in group_scores.items()
        if score > 0
    }


def compute_relative_heatmap(svg_scores: dict[str, float]) -> dict[str, int]:
    """Return per-SVG-muscle relative_percent values for Card 2 heatmap."""
    if not svg_scores:
        return {}
    max_overall = max(svg_scores.values()) or 1
    heatmap = {
        muscle: round(score / max_overall * 100)
        for muscle, score in svg_scores.items()
        if score > 0
    }
    for group_muscles in MAJOR_GROUPS.values():
        for m in group_muscles:
            heatmap.setdefault(m, 0)
            heatmap.setdefault("b-" + m, 0)
    return heatmap


def compute_distribution(cur, session_id) -> dict[str, int]:
    """Return muscle_distribution (label→0-100) for a given session_id."""
    cur.execute(
        "SELECT exercise_name, sets, reps FROM exercise_execution WHERE session_id = %s",
        (session_id,),
    )
    rows = cur.fetchall()
    _, raw_scores = compute_muscles(cur, rows)
    return compute_share_distribution(raw_scores)


def get_conn():
    return psycopg2.connect(**DB, cursor_factory=psycopg2.extras.RealDictCursor)


def muscle_intensity_label(score: float, max_score: float) -> str:
    if max_score == 0:
        return "none"
    r = score / max_score
    if r >= 0.6:
        return "high"
    if r >= 0.25:
        return "medium"
    if r > 0:
        return "low"
    return "none"


def compute_muscles(cur, rows: list) -> tuple[dict[str, float], dict[str, float]]:
    """
    Compute per-muscle scores from exercise execution rows.

    rows: list of dicts with 'exercise_name' and 'sets' (or 'total_sets').

    Returns:
      svg_scores  – back muscles prefixed 'b-'  (used by Card 2 SVG heatmap)
      raw_scores  – no prefix on any muscle       (used by Card 1 MAJOR_GROUPS)

    Weighting: primary (text-mw-red) × 2, secondary (text-mw-gray) × 1.
    Data source: exercises.source_data->'muscles'->'frontBodyMap'/'backBodyMap'
    """
    canonical_names = list({EXERCISE_ALIAS.get(r["exercise_name"], r["exercise_name"]) for r in rows})
    ex_map: dict[str, dict] = {}
    if canonical_names:
        cur.execute(
            "SELECT name_cn, source_data->'muscles' AS m FROM exercises WHERE name_cn = ANY(%s)",
            (canonical_names,),
        )
        ex_map = {r["name_cn"]: (r["m"] or {}) for r in cur.fetchall()}
        # Fuzzy fallback for names not found by exact match
        _PREFIX = re.compile(r'^(史密斯机?|杠铃|哑铃|自重|器械|绳索|弹力带|壶铃|TRX)')
        for cn in canonical_names:
            if cn in ex_map:
                continue
            core = _PREFIX.sub('', cn).strip()
            if len(core) < 2:
                continue
            cur.execute(
                "SELECT name_cn, source_data->'muscles' AS m "
                "FROM exercises WHERE name_cn LIKE %s ORDER BY LENGTH(name_cn) LIMIT 1",
                (f'%{core}%',),
            )
            row = cur.fetchone()
            if row and row["m"]:
                ex_map[cn] = row["m"]

    svg_scores: defaultdict[str, float] = defaultdict(float)
    raw_scores: defaultdict[str, float] = defaultdict(float)

    for row in rows:
        name      = row["exercise_name"]
        canonical = EXERCISE_ALIAS.get(name, name)
        sets      = float(row.get("sets") or row.get("total_sets") or 0)
        m         = ex_map.get(canonical, {})
        fm        = m.get("frontBodyMap", {})
        bm        = m.get("backBodyMap",  {})

        for muscle in fm.get("text-mw-red", []):
            svg_scores[muscle]        += sets * 2
            raw_scores[muscle]        += sets * 2
        for muscle in bm.get("text-mw-red", []):
            svg_scores["b-" + muscle] += sets * 2
            raw_scores[muscle]        += sets * 2
        for muscle in fm.get("text-mw-gray", []):
            svg_scores[muscle]        += sets
            raw_scores[muscle]        += sets
        for muscle in bm.get("text-mw-gray", []):
            svg_scores["b-" + muscle] += sets
            raw_scores[muscle]        += sets

    return dict(svg_scores), dict(raw_scores)


# SVG muscle IDs that live on the back body map
_BACK_MUSCLES = {"lats", "lowerback", "hamstrings", "glutes",
                 "rear-shoulders", "triceps", "traps", "scapula"}


def compute_muscles_from_segs(cur, segs: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    """Compute muscle scores from raw_segments (JSON source).

    Uses primary_muscles/secondary_muscles fields from the JSON directly.
    Falls back to the exercises DB table for segments with empty muscle lists.
    """
    # Collect exercises that have no JSON muscle data — need DB lookup
    no_muscle = list({
        EXERCISE_ALIAS.get(s["exercise_name"], s["exercise_name"])
        for s in segs
        if not s.get("primary_muscles") and not s.get("secondary_muscles")
    })
    db_map: dict[str, dict] = {}
    if no_muscle:
        # 1. Exact match
        cur.execute(
            "SELECT name_cn, source_data->'muscles' AS m FROM exercises WHERE name_cn = ANY(%s)",
            (no_muscle,),
        )
        db_map = {r["name_cn"]: (r["m"] or {}) for r in cur.fetchall()}

        # 2. Fuzzy fallback: strip equipment prefix and search by core movement name
        _PREFIX = re.compile(r'^(史密斯机?|杠铃|哑铃|自重|器械|绳索|弹力带|壶铃|TRX)')
        for name in no_muscle:
            if name in db_map:
                continue
            core = _PREFIX.sub('', name).strip()
            if len(core) < 2:
                continue
            cur.execute(
                "SELECT name_cn, source_data->'muscles' AS m "
                "FROM exercises WHERE name_cn LIKE %s ORDER BY LENGTH(name_cn) LIMIT 1",
                (f'%{core}%',),
            )
            row = cur.fetchone()
            if row and row["m"]:
                db_map[name] = row["m"]

    svg_scores: defaultdict[str, float] = defaultdict(float)
    raw_scores: defaultdict[str, float] = defaultdict(float)

    for seg in segs:
        name      = seg["exercise_name"]
        sets      = float(seg.get("sets_count") or 1)
        primary   = seg.get("primary_muscles") or []
        secondary = seg.get("secondary_muscles") or []

        # Fall back to DB when JSON has no muscle data
        if not primary:
            canonical = EXERCISE_ALIAS.get(name, name)
            m  = db_map.get(canonical, {})
            fm = m.get("frontBodyMap", {})
            bm = m.get("backBodyMap",  {})
            primary   = fm.get("text-mw-red", []) + [("b-" + x) for x in bm.get("text-mw-red", [])]
            secondary = fm.get("text-mw-gray", []) + [("b-" + x) for x in bm.get("text-mw-gray", [])]

        for muscle in primary:
            back = muscle.startswith("b-") or muscle in _BACK_MUSCLES
            key  = muscle if muscle.startswith("b-") else ("b-" + muscle if back else muscle)
            svg_scores[key]                                                += sets * 2
            raw_scores[muscle[2:] if muscle.startswith("b-") else muscle] += sets * 2

        for muscle in secondary:
            back = muscle.startswith("b-") or muscle in _BACK_MUSCLES
            key  = muscle if muscle.startswith("b-") else ("b-" + muscle if back else muscle)
            svg_scores[key]                                                += sets
            raw_scores[muscle[2:] if muscle.startswith("b-") else muscle] += sets

    return dict(svg_scores), dict(raw_scores)


# ── MET-based calorie helpers ─────────────────────────────────────────────────

def _get_user_profile(cur, uid: str) -> dict:
    """返回 user_profile_long_term 中的体重/性别/年龄。"""
    cur.execute("""
        SELECT weight, gender, age
        FROM user_profile_long_term WHERE user_id = %s
    """, (uid,))
    row = cur.fetchone()
    return dict(row) if row else {}


def _calc_met_calories(cur, session_id: str,
                       weight_kg: float, gender: str, age: int) -> float:
    """MET × 体重 × 时长 × 性别系数 × 年龄系数。

    来源：Ainsworth et al. 2011 Compendium of Physical Activities
    性别系数：女性取 0.90，男性取 1.00
    年龄系数：20 岁后每年下降 0.5%，下限 0.75
    """
    cur.execute("""
        SELECT exercise_name,
               COALESCE(duration_sec,
                        EXTRACT(EPOCH FROM (end_time - timestamp))) AS duration_sec
        FROM exercise_execution
        WHERE session_id = %s
          AND (duration_sec > 0
               OR (end_time IS NOT NULL AND end_time > timestamp))
    """, (session_id,))
    rows = cur.fetchall()
    if not rows:
        return 0.0

    names = list({EXERCISE_ALIAS.get(r["exercise_name"], r["exercise_name"]) for r in rows})
    cur.execute("""
        SELECT DISTINCT ON (name_cn) name_cn, estimated_mets
        FROM exercises
        WHERE name_cn = ANY(%s) AND estimated_mets IS NOT NULL
        ORDER BY name_cn,
                 CASE WHEN exercise_id LIKE 'ex_%%' THEN 0 ELSE 1 END,
                 exercise_id
    """, (names,))
    met_map = {r["name_cn"]: float(r["estimated_mets"]) for r in cur.fetchall()}

    is_female     = gender.lower() in ("female", "f", "女")
    gender_factor = 0.90 if is_female else 1.00

    age_factor = max(0.75, 1.0 - max(0, age - 20) * 0.005)

    total = 0.0
    for row in rows:
        name      = row["exercise_name"]
        canonical = EXERCISE_ALIAS.get(name, name)
        met       = met_map.get(canonical) or met_map.get(name) or 4.0
        dur_h     = float(row["duration_sec"] or 0) / 3600
        total    += met * weight_kg * dur_h * gender_factor * age_factor

    return round(total, 1)


@app.get("/api/users")
def users_list():
    """列出所有用户画像，供前端选择。"""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.gender, u.age, u.height, u.weight, u.fitness_goal,
               u.experience_level,
               COUNT(ws.session_id) AS session_count,
               MAX(DATE(ws.start_time)) AS last_workout,
               MIN(u.created_at) AS created_at
        FROM user_profile_long_term u
        LEFT JOIN workout_session ws ON ws.user_id = u.user_id
        GROUP BY u.user_id, u.gender, u.age, u.height, u.weight,
                 u.fitness_goal, u.experience_level
        ORDER BY last_workout DESC NULLS LAST, created_at
    """)
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        g = (r["gender"] or "").lower()
        gender_cn = "女" if g in ("female", "f", "女") else "男"
        label = f"{gender_cn} {r['age'] or '?'}岁 {r['height'] or '?'}cm/{r['weight'] or '?'}kg {r['fitness_goal'] or ''}"
        result.append({
            "user_id": str(r["user_id"]),
            "label": label.strip(),
            "gender": r["gender"],
            "age": r["age"],
            "height": r["height"],
            "weight": r["weight"],
            "fitness_goal": r["fitness_goal"],
            "session_count": r["session_count"],
            "last_workout": str(r["last_workout"]) if r["last_workout"] else None,
        })
    return result


@app.get("/api/user")
def user(user_id: str | None = None):
    """返回当前用户基本信息（性别等），供前端切换人体图性别。"""
    uid  = user_id or USER_ID
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT gender FROM user_profile_long_term WHERE user_id = %s",
        (uid,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"gender": "male"}
    g = (row["gender"] or "male").lower()
    return {"gender": "female" if g in ("female", "f", "女") else "male"}


@app.get("/api/daily")
def daily(date: str | None = None, user_id: str | None = None):
    """指定日期（默认最近一次）的当日分析：时长/热量/完成率/肌群分布"""
    uid  = user_id or USER_ID
    conn = get_conn()
    cur  = conn.cursor()

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            conn.close()
            return JSONResponse(status_code=400, content={"error": "invalid date"})
        cur.execute("""
            SELECT session_id, start_time, end_time, calories, completion_rate, total_volume,
                   ROUND(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) AS duration_min
            FROM workout_session
            WHERE user_id = %s AND DATE(start_time) = %s
            ORDER BY start_time LIMIT 1
        """, (uid, target_date))
    else:
        cur.execute("""
            SELECT session_id, start_time, end_time, calories, completion_rate, total_volume,
                   ROUND(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) AS duration_min
            FROM workout_session
            WHERE user_id = %s
            ORDER BY start_time DESC LIMIT 1
        """, (uid,))

    session = cur.fetchone()
    if not session:
        bal_date = target_date if date else __import__('datetime').date.today()
        fitness_balance = compute_fitness_balance(cur, uid, bal_date)
        conn.close()
        date_str = bal_date.isoformat() if hasattr(bal_date, 'isoformat') else str(bal_date)
        video_file = _DATE_VIDEO_MAP.get(uid, {}).get(date_str)
        resp = {"fitness_balance": fitness_balance}
        if video_file:
            resp["video_file"] = video_file
            resp["total_sec"] = 0
        return resp

    sid = session["session_id"]

    # 用户画像（体重/性别/年龄）→ MET 卡路里
    profile    = _get_user_profile(cur, uid)
    weight_kg  = float(profile.get("weight") or 65.0)
    gender_str = str(profile.get("gender") or "female")
    age        = int(profile.get("age") or 25)
    calories   = _calc_met_calories(cur, sid, weight_kg, gender_str, age)

    # 把计算结果写回 workout_session，保持 weekly 一致
    if calories > 0:
        cur.execute("UPDATE workout_session SET calories = %s WHERE session_id = %s",
                    (calories, sid))
        conn.commit()

    # Read JSON segments first — used as the primary source for exercises + muscles
    date_str = session["start_time"].date().isoformat()
    raw_segs, total_sec = _read_raw_segments(date_str)
    all_segments = _read_all_segments(date_str)
    if total_sec == 0:
        total_sec = float(session["duration_min"]) * 60

    # 动作执行记录：优先从 JSON（和视频分析一致），无 JSON 则查数据库
    if raw_segs:
        # Aggregate by exercise name: same format compute_muscles expects
        from collections import OrderedDict as _OD
        _agg: _OD = _OD()
        for seg in raw_segs:
            n = seg["exercise_name"]
            if n not in _agg:
                _agg[n] = {"exercise_name": n, "sets": seg["sets_count"],
                           "reps": seg["reps_estimate"]}
            else:
                _agg[n]["sets"] += seg["sets_count"]
                _agg[n]["reps"]  = max(_agg[n]["reps"], seg["reps_estimate"])
        executions = list(_agg.values())
    else:
        cur.execute(
            "SELECT exercise_name, sets, reps FROM exercise_execution WHERE session_id = %s ORDER BY timestamp",
            (sid,),
        )
        executions = cur.fetchall()

    svg_scores, raw_scores = (compute_muscles_from_segs(cur, raw_segs)
                              if raw_segs else compute_muscles(cur, executions))

    # Card 1 bars use share_percent across major groups.
    muscle_distribution = compute_share_distribution(raw_scores)
    muscle_heatmap = compute_relative_heatmap(svg_scores)

    # category_duration: computed later from raw_segments (accurate per-segment durations)
    # — avoids the DB aggregation which spans first→last occurrence including rest gaps
    category_duration: dict[str, int] = {"有氧": 0, "力量": 0, "核心": 0, "热身/拉伸": 0}

    # Previous training session muscle distribution (for trend arrows)
    cur.execute("""
        SELECT session_id FROM workout_session
        WHERE user_id = %s AND DATE(start_time) < %s
        ORDER BY start_time DESC LIMIT 1
    """, (uid, session["start_time"].date()))
    prev_row = cur.fetchone()
    prev_distribution: dict[str, int] = {}
    if prev_row:
        prev_distribution = compute_distribution(cur, prev_row["session_id"])

    conn.close()

    # trend: "up" / "down" / "flat" per group
    muscle_trend: dict[str, str] = {}
    all_labels = set(muscle_distribution) | set(prev_distribution)
    for label in all_labels:
        cur_val  = muscle_distribution.get(label, 0)
        prev_val = prev_distribution.get(label, 0)
        if cur_val > prev_val:
            muscle_trend[label] = "up"
        elif cur_val < prev_val:
            muscle_trend[label] = "down"
        else:
            muscle_trend[label] = "flat"

    # Build CN→EN name lookup
    cn_names = list({r["exercise_name"] for r in executions})
    _en_conn = get_conn()
    _en_cur = _en_conn.cursor()
    _en_cur.execute("SELECT name_cn, name FROM exercises WHERE name_cn = ANY(%s)", (cn_names,))
    _cn_to_en = {r["name_cn"]: r["name"] for r in _en_cur.fetchall()}
    _en_conn.close()

    exercises_list = [
        {"name": r["exercise_name"],
         "name_en": _cn_to_en.get(r["exercise_name"], r["exercise_name"]),
         "sets": int(r["sets"] or 0), "reps": int(r["reps"] or 0)}
        for r in executions
    ]

    # Fill category_duration from raw_segments — each entry has exact start/end secs
    for seg in raw_segs:
        cat = seg.get("category", "力量")
        if cat in category_duration:
            category_duration[cat] += int(round(seg["end_sec"] - seg["start_sec"]))

    balance_conn = get_conn()
    balance_cur = balance_conn.cursor()
    fitness_balance = compute_fitness_balance(balance_cur, uid, session["start_time"].date())
    balance_conn.close()

    return {
        "date":              date_str,
        "duration_min":      int(session["duration_min"]),
        "calories":          int(calories),
        "completion_rate":   round(float(session["completion_rate"]) * 100),
        "total_volume":      int(session["total_volume"] or 0),
        "muscle_distribution": muscle_distribution,
        "muscle_trend":        muscle_trend,
        "muscle_heatmap":      muscle_heatmap,
        "muscle_summary":      compute_muscle_summary(raw_scores),
        "fitness_balance":     fitness_balance,
        "exercises":           exercises_list,
        "category_duration":   {k: v for k, v in category_duration.items() if v > 0},
        "raw_segments":        raw_segs,
        "all_segments":        all_segments,
        "total_sec":           total_sec,
        "video_file":          _DATE_VIDEO_MAP.get(uid, {}).get(date_str),
    }


@app.get("/api/weekly")
def weekly(user_id: str | None = None):
    """近 7 日训练量、热量汇总及每日组数明细（用于折线图）"""
    uid  = user_id or USER_ID
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        SELECT DATE(start_time) AS day
        FROM workout_session WHERE user_id = %s
        ORDER BY start_time DESC LIMIT 1
    """, (uid,))
    latest = cur.fetchone()
    if not latest:
        conn.close()
        return {}
    ref_date:   date = latest["day"]
    # Week runs Sunday(0) to Saturday(6); find the Sunday of the current week
    sun_offset = (ref_date.weekday() + 1) % 7
    start_date: date = ref_date - timedelta(days=sun_offset)
    end_date:   date = start_date + timedelta(days=6)

    # 每日总组数
    cur.execute("""
        SELECT DATE(ws.start_time) AS day,
               COALESCE(SUM(ee.sets), 0) AS total_sets
        FROM workout_session ws
        LEFT JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
        GROUP BY DATE(ws.start_time)
        ORDER BY day
    """, (uid, start_date, end_date))
    daily_rows = {row["day"]: int(row["total_sets"]) for row in cur.fetchall()}

    # 每日热量
    cur.execute("""
        SELECT DATE(start_time) AS day, SUM(calories) AS kcal
        FROM workout_session
        WHERE user_id = %s AND DATE(start_time) BETWEEN %s AND %s
        GROUP BY DATE(start_time)
    """, (uid, start_date, end_date))
    daily_kcal = {row["day"]: float(row["kcal"]) for row in cur.fetchall()}

    # 上一个 7 天（趋势对比）
    prev_start = start_date - timedelta(days=7)
    prev_end   = start_date - timedelta(days=1)
    cur.execute("""
        SELECT COALESCE(SUM(ee.sets), 0) AS sets, COALESCE(SUM(ws.calories), 0) AS kcal
        FROM workout_session ws
        LEFT JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
    """, (uid, prev_start, prev_end))
    prev = cur.fetchone()
    conn.close()

    prev_sets = float(prev["sets"]) if prev else 0
    prev_kcal = float(prev["kcal"]) if prev else 0

    days_list  = [start_date + timedelta(days=i) for i in range(7)]
    daily_sets = [daily_rows.get(d, 0) for d in days_list]
    day_labels = ["周" + "日一二三四五六"[(d.weekday() + 1) % 7] for d in days_list]

    total_sets = sum(daily_sets)
    total_kcal = sum(daily_kcal.values())

    # 本周训练频率 / 每日时长(分钟) / 每日推拉腿覆盖
    _c2 = get_conn(); _cur2 = _c2.cursor()
    _cur2.execute("""
        SELECT DATE(start_time) AS day,
               COALESCE(SUM(ROUND(EXTRACT(EPOCH FROM (end_time - start_time)) / 60)), 0) AS dur
        FROM workout_session
        WHERE user_id = %s AND DATE(start_time) BETWEEN %s AND %s
        GROUP BY DATE(start_time)
    """, (uid, start_date, end_date))
    _dur_rows = {r["day"]: int(r["dur"] or 0) for r in _cur2.fetchall()}
    daily_duration = [_dur_rows.get(d, 0) for d in days_list]
    total_duration = sum(daily_duration)
    # 按有 workout_session 记录的天数算频率（不依赖 exercise_execution）
    training_frequency = sum(1 for v in daily_duration if v > 0)

    _cur2.execute("""
        SELECT DATE(ws.start_time) AS day, ee.exercise_name AS name,
               COALESCE(SUM(ee.sets), 0) AS sets
        FROM workout_session ws
        JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
        GROUP BY DATE(ws.start_time), ee.exercise_name
    """, (uid, start_date, end_date))
    from gym_analyzer.db import get_exercise_muscles
    _muscle_group_totals: dict[str, float] = {g: 0 for g in MAJOR_GROUPS}
    _muscle_to_group = {}
    for g, ms in MAJOR_GROUPS.items():
        for m in ms:
            _muscle_to_group[m] = g
    for r in _cur2.fetchall():
        sets = int(r["sets"] or 0)
        mdata = get_exercise_muscles(r["name"])
        for mid in mdata.get("primary", []):
            bare = mid.lstrip("b-") if mid.startswith("b-") else mid
            grp = _muscle_to_group.get(bare)
            if grp:
                _muscle_group_totals[grp] += sets * 2
        for mid in mdata.get("secondary", []):
            bare = mid.lstrip("b-") if mid.startswith("b-") else mid
            grp = _muscle_to_group.get(bare)
            if grp:
                _muscle_group_totals[grp] += sets * 1
    _mg_total = sum(_muscle_group_totals.values())
    muscle_coverage = []
    if _mg_total > 0:
        for g in MAJOR_GROUPS:
            pct = round(_muscle_group_totals[g] / _mg_total * 100)
            if pct > 0:
                muscle_coverage.append({"group": g, "pct": pct})
    _c2.close()

    def trend_pct(cur_val: float, prev_val: float) -> float:
        if prev_val == 0:
            return 0.0
        return round((cur_val - prev_val) / prev_val * 100, 1)

    return {
        "total_sets":        total_sets,
        "total_calories":    round(total_kcal),
        "sets_trend_pct":    trend_pct(total_sets, prev_sets),
        "calories_trend_pct": trend_pct(total_kcal, prev_kcal),
        "daily_sets":        daily_sets,
        "day_labels":        day_labels,
        "training_frequency": training_frequency,
        "total_duration":    total_duration,
        "daily_duration":    daily_duration,
        "muscle_coverage":   muscle_coverage,
    }


@app.get("/api/muscles")
def muscles(date: str | None = None, user_id: str | None = None):
    """
    肌群热力图（high/medium/low/none）
    - ?date=YYYY-MM-DD → 仅该日数据
    - 无参数           → 最近 7 天
    """
    uid  = user_id or USER_ID
    conn = get_conn()
    cur  = conn.cursor()

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            conn.close()
            return JSONResponse(status_code=400, content={"error": "invalid date"})
        start_date = end_date = target_date
    else:
        cur.execute("""
            SELECT DATE(start_time) AS day FROM workout_session
            WHERE user_id = %s ORDER BY start_time DESC LIMIT 1
        """, (uid,))
        latest = cur.fetchone()
        if not latest:
            conn.close()
            return {}
        end_date   = latest["day"]
        start_date = end_date - timedelta(days=6)

    cur.execute("""
        SELECT ee.exercise_name, SUM(ee.sets) AS total_sets
        FROM exercise_execution ee
        JOIN workout_session ws ON ws.session_id = ee.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
        GROUP BY ee.exercise_name
    """, (uid, start_date, end_date))
    rows = cur.fetchall()

    svg_scores, _ = compute_muscles(cur, rows)
    conn.close()

    if not svg_scores:
        return {}
    max_score = max(svg_scores.values())
    return {
        muscle: round(score / max_score * 100)
        for muscle, score in svg_scores.items()
    }


@app.get("/api/hr_detail")
def hr_detail(date: str | None = None, user_id: str | None = None):
    """
    返回指定日期（默认最近一次训练日）的：
      - 生物特征流（每10分钟心率/HRV/疲劳）
      - 动作执行记录
      - session 信息
    """
    uid  = user_id or USER_ID
    conn = get_conn()
    cur  = conn.cursor()

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            conn.close()
            return JSONResponse(status_code=400, content={"error": "invalid date format"})
    else:
        cur.execute(
            "SELECT DATE(start_time) AS day FROM workout_session "
            "WHERE user_id = %s ORDER BY start_time DESC LIMIT 1",
            (uid,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return {}
        target_date = row["day"]

    # biometric stream
    cur.execute("""
        SELECT timestamp, heart_rate, hrv, fatigue_score, steps
        FROM biometric_stream
        WHERE user_id = %s AND DATE(timestamp) = %s
        ORDER BY timestamp
    """, (uid, target_date))
    biometrics = [
        {
            "timestamp":     r["timestamp"].isoformat(),
            "heart_rate":    r["heart_rate"],
            "hrv":           float(r["hrv"] or 0),
            "fatigue_score": float(r["fatigue_score"] or 0),
            "steps":         r["steps"],
        }
        for r in cur.fetchall()
    ]

    # exercise executions
    cur.execute("""
        SELECT ee.exercise_name, ee.timestamp, ee.sets, ee.reps, ee.tempo, ee.rom
        FROM exercise_execution ee
        JOIN workout_session ws ON ws.session_id = ee.session_id
        WHERE ws.user_id = %s AND DATE(ee.timestamp) = %s
        ORDER BY ee.timestamp
    """, (uid, target_date))
    exercises = [
        {
            "exercise_name": r["exercise_name"],
            "timestamp":     r["timestamp"].isoformat(),
            "sets":          r["sets"],
            "reps":          r["reps"],
            "tempo":         r["tempo"],
            "rom":           float(r["rom"] or 0),
        }
        for r in cur.fetchall()
    ]

    # session meta
    cur.execute("""
        SELECT session_id, start_time, end_time, calories, completion_rate, total_volume,
               ROUND(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) AS duration_min
        FROM workout_session
        WHERE user_id = %s AND DATE(start_time) = %s
        ORDER BY start_time
    """, (uid, target_date))
    sessions = [
        {
            "session_id":      str(r["session_id"]),
            "start_time":      r["start_time"].isoformat(),
            "end_time":        r["end_time"].isoformat() if r["end_time"] else None,
            "calories":        float(r["calories"] or 0),
            "completion_rate": float(r["completion_rate"] or 0),
            "total_volume":    float(r["total_volume"] or 0),
            "duration_min":    int(r["duration_min"] or 0),
        }
        for r in cur.fetchall()
    ]

    conn.close()
    return {
        "date":       target_date.isoformat(),
        "biometrics": biometrics,
        "exercises":  exercises,
        "sessions":   sessions,
    }


@app.get("/api/calendar")
def calendar(year: int | None = None, month: int | None = None, user_id: str | None = None):
    """每日训练状态：full(完整)/partial(部分)。默认为最近一次训练所在月份。"""
    uid  = user_id or USER_ID
    conn = get_conn()
    cur  = conn.cursor()

    # 若未指定年月，取最近一次训练所在月份
    if year is None or month is None:
        cur.execute(
            "SELECT DATE(start_time) AS day FROM workout_session "
            "WHERE user_id = %s ORDER BY start_time DESC LIMIT 1",
            (uid,),
        )
        latest = cur.fetchone()
        ref = latest["day"] if latest else date.today()
        year  = year  or ref.year
        month = month or ref.month

    month_start = date(year, month, 1)
    # last day of month
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    cur.execute("""
        SELECT DATE(start_time) AS day, completion_rate
        FROM workout_session
        WHERE user_id = %s
          AND DATE(start_time) >= %s
          AND DATE(start_time) <= %s
        ORDER BY start_time
    """, (uid, month_start, month_end))
    rows = cur.fetchall()
    conn.close()

    result: dict[str, str] = {}
    for row in rows:
        day_str = row["day"].isoformat()
        rate    = float(row["completion_rate"] or 0)
        result[day_str] = "full" if rate >= 0.95 else "partial"

    video_map = _DATE_VIDEO_MAP.get(uid, {})
    for d_str in video_map:
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d.year == year and d.month == month and d_str not in result:
            result[d_str] = "video"

    return {
        "year":  year,
        "month": month,
        "days":  result,
    }


# ── Plan Viewer endpoints ─────────────────────────────────────────────────────
PLAN_VIEWER_USER = "b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12"

@app.get("/api/plan-viewer/profile")
def plan_viewer_profile():
    """Long-term user profile for the plan viewer page."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT * FROM user_profile_long_term WHERE user_id = %s",
        (PLAN_VIEWER_USER,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="用户画像不存在")
    data = dict(row)
    # serialise non-JSON-native types
    data["user_id"]    = str(data["user_id"])
    data["created_at"] = data["created_at"].isoformat() if data.get("created_at") else None
    data["updated_at"] = data["updated_at"].isoformat() if data.get("updated_at") else None
    return data


class ProfileUpdateRequest(BaseModel):
    gender: str | None = None
    age: int | None = None
    height: int | None = None
    weight: int | None = None
    sleep_hours: float | None = None
    fitness_goal: str | None = None
    experience_level: str | None = None
    preferred_training_style: list[str] | None = None
    available_equipment: list[str] | None = None
    available_schedule: dict[str, Any] | None = None


@app.put("/api/plan-viewer/profile")
def update_plan_viewer_profile(body: ProfileUpdateRequest):
    """Update editable fields of the plan-viewer user's long-term profile."""
    fields: list[str] = []
    values: list[Any] = []

    if body.gender is not None:
        fields.append("gender = %s"); values.append(body.gender)
    if body.age is not None:
        fields.append("age = %s"); values.append(body.age)
    if body.height is not None:
        fields.append("height = %s"); values.append(body.height)
    if body.weight is not None:
        fields.append("weight = %s"); values.append(body.weight)
    if body.sleep_hours is not None:
        fields.append("sleep_hours = %s"); values.append(body.sleep_hours)
    if body.fitness_goal is not None:
        fields.append("fitness_goal = %s"); values.append(body.fitness_goal)
    if body.experience_level is not None:
        fields.append("experience_level = %s"); values.append(body.experience_level)
    if body.preferred_training_style is not None:
        fields.append("preferred_training_style = %s"); values.append(body.preferred_training_style)
    if body.available_equipment is not None:
        fields.append("available_equipment = %s"); values.append(body.available_equipment)
    if body.available_schedule is not None:
        fields.append("available_schedule = %s"); values.append(json.dumps(body.available_schedule))

    if not fields:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    fields.append("updated_at = NOW()")
    values.append(PLAN_VIEWER_USER)

    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        f"UPDATE user_profile_long_term SET {', '.join(fields)} WHERE user_id = %s",
        values,
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/api/plan-viewer/latest-plan")
def plan_viewer_latest_plan(version: str | None = None):
    """
    返回指定版本（v2/v3）的最新计划。
    优先从文件缓存加载（毫秒级）；缓存不存在时回退到数据库最新记录。
    version 参数未传时使用当前服务器选定版本（_prompt_version）。
    """
    from agent_service.planner.plan_generator import load_plan_cache, plan_cache_meta

    ver = version or _prompt_version

    # 1. 尝试文件缓存
    cached = load_plan_cache(PLAN_VIEWER_USER, ver)
    if cached:
        plan = dict(cached)
        plan.setdefault("_source", "cache")
        meta = plan_cache_meta(PLAN_VIEWER_USER, ver) or {}
        plan["_cached_at"] = meta.get("generated_at")
        return plan

    # 2. 回退：数据库最新记录（不区分版本）
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT plan_id, date, goal, plan_json
        FROM workout_plan
        WHERE user_id = %s
        ORDER BY date DESC
        LIMIT 1
        """,
        (PLAN_VIEWER_USER,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"weekly_schedule": [], "plan_name": "暂无训练计划", "coaching_notes": [],
                "fitness_goal": None, "plan_id": None, "date": None, "_empty": True}
    plan = dict(row["plan_json"])
    plan["plan_id"] = str(row["plan_id"])
    plan["date"]    = row["date"].isoformat() if row.get("date") else None
    plan["_source"] = "db"
    return plan


# ── Exercise muscle map for plan viewer ───────────────────────────────────────
@app.get("/api/plan-viewer/muscles-map")
def plan_viewer_muscles_map():
    """Return {exercise_id: {primary, secondary}} for all exercises in the latest plan."""
    conn = get_conn()
    cur  = conn.cursor()

    # 1. Pull exercise_ids from latest plan
    cur.execute(
        """
        SELECT plan_json FROM workout_plan
        WHERE user_id = %s
        ORDER BY date DESC LIMIT 1
        """,
        (PLAN_VIEWER_USER,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="暂无训练计划")

    plan = row["plan_json"]
    ex_ids = [
        ex["exercise_id"]
        for day in plan.get("weekly_schedule", [])
        for ex in day.get("exercises", [])
        if ex.get("exercise_id")
    ]
    ex_ids = list(set(ex_ids))

    if not ex_ids:
        conn.close()
        return {}

    # 2. Query muscles from exercises table
    cur.execute(
        """
        SELECT exercise_id, primary_muscles, secondary_muscles
        FROM exercises
        WHERE exercise_id = ANY(%s)
        """,
        (ex_ids,)
    )
    result = {}
    for r in cur.fetchall():
        result[r["exercise_id"]] = {
            "primary":   r["primary_muscles"]   or [],
            "secondary": r["secondary_muscles"] or [],
        }
    conn.close()
    return result


# ── Prompt version management ─────────────────────────────────────────────────
_prompt_version: str = "v2"   # "v2" | "v3"

_PROMPT_FILES = {
    "v2": "workout_plan_generator_v2",
    "v3": "workout_plan_generator_v3",
}


@app.get("/api/plan-viewer/prompt-version")
def get_prompt_version():
    return {"version": _prompt_version}


class PromptVersionRequest(BaseModel):
    version: str


@app.post("/api/plan-viewer/prompt-version")
def set_prompt_version(body: PromptVersionRequest):
    global _prompt_version
    if body.version not in _PROMPT_FILES:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {body.version}")
    _prompt_version = body.version
    return {"version": _prompt_version}


@app.get("/api/plan-viewer/prompt-content/{version}")
def get_prompt_content(version: str):
    """返回指定版本的 prompt YAML 原始内容及元数据。"""
    import yaml as _yaml
    from pathlib import Path as _Path
    if version not in _PROMPT_FILES:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {version}")
    prompt_name = _PROMPT_FILES[version]
    # 找到 prompts/ 目录
    project_root = _Path(__file__).parents[2]
    candidates = list((project_root / "prompts").glob(f"{prompt_name}*.yaml"))
    if not candidates:
        raise HTTPException(status_code=404, detail="prompt 文件未找到")
    yaml_path = candidates[0]
    raw = yaml_path.read_text(encoding="utf-8")
    data = _yaml.safe_load(raw)
    return {
        "version":     data.get("version", "?"),
        "description": data.get("description", ""),
        "system":      data.get("system", ""),
        "user":        data.get("user", ""),
        "raw":         raw,
    }


# ── Plan regeneration ─────────────────────────────────────────────────────────
_regen_jobs: dict[str, dict] = {}


def _run_regen(job_id: str, user_id: str, version: str = "v2"):
    try:
        from agent_service.planner.plan_generator import (
            fetch_user_profile, fetch_dynamic_state, fetch_history_plans,
            filter_exercises_by_rules, rank_by_vector,
            generate_plan_with_llm, generate_plan_v3,
            save_workout_plan, save_plan_cache,
        )
        profile  = fetch_user_profile(user_id)
        dynamic  = fetch_dynamic_state(user_id)
        history  = fetch_history_plans(user_id)
        filtered = filter_exercises_by_rules(profile)
        if not filtered:
            _regen_jobs[job_id] = {"status": "error", "error": "未筛出任何动作"}
            return
        ranked = rank_by_vector(filtered, profile, dynamic, history, top_k=40)
        if version == "v3":
            plan = generate_plan_v3(ranked, profile, dynamic)
        else:
            plan = generate_plan_with_llm(ranked, profile, dynamic)
            plan["_pipeline_version"] = "v2"
        save_workout_plan(user_id, profile["fitness_goal"], plan)
        save_plan_cache(user_id, version, plan)          # 持久化到文件缓存
        _regen_jobs[job_id] = {"status": "done"}
    except Exception as exc:
        _regen_jobs[job_id] = {"status": "error", "error": str(exc)}


@app.post("/api/plan-viewer/regenerate-plan")
def regenerate_plan():
    """Start async plan regeneration using the current prompt version; returns a job_id to poll."""
    job_id = str(_uuid.uuid4())
    _regen_jobs[job_id] = {"status": "running"}
    threading.Thread(
        target=_run_regen,
        args=(job_id, PLAN_VIEWER_USER, _prompt_version),
        daemon=True,
    ).start()
    return {"job_id": job_id}


@app.get("/api/plan-viewer/regen-status/{job_id}")
def regen_status(job_id: str):
    job = _regen_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# ── Pregenerate both versions ─────────────────────────────────────────────────
_pregen_jobs: dict[str, dict] = {}   # "v2" / "v3" → job_id


@app.post("/api/plan-viewer/pregenerate-all")
def pregenerate_all():
    """
    同时启动 v2 + v3 两个后台生成任务。
    各自写入文件缓存；返回 {v2: job_id, v3: job_id}。
    """
    jid_v2 = str(_uuid.uuid4())
    jid_v3 = str(_uuid.uuid4())
    _regen_jobs[jid_v2] = {"status": "running", "version": "v2"}
    _regen_jobs[jid_v3] = {"status": "running", "version": "v3"}
    _pregen_jobs["v2"] = {"job_id": jid_v2, "status": "running"}
    _pregen_jobs["v3"] = {"job_id": jid_v3, "status": "running"}

    def _watch(jid: str, ver: str):
        _run_regen(jid, PLAN_VIEWER_USER, ver)
        _pregen_jobs[ver]["status"] = _regen_jobs[jid]["status"]

    threading.Thread(target=_watch, args=(jid_v2, "v2"), daemon=True).start()
    threading.Thread(target=_watch, args=(jid_v3, "v3"), daemon=True).start()
    return {"v2": jid_v2, "v3": jid_v3}


@app.get("/api/plan-viewer/cache-status")
def cache_status():
    """返回 v2/v3 文件缓存的生成时间（供 UI 展示预生成状态）。"""
    from agent_service.planner.plan_generator import plan_cache_meta
    return {
        "v2": plan_cache_meta(PLAN_VIEWER_USER, "v2"),
        "v3": plan_cache_meta(PLAN_VIEWER_USER, "v3"),
        "pregen_jobs": _pregen_jobs,
    }


# ── Video files serving ──────────────────────────────────────────────────────
_INPUT_DIR = Path(__file__).parent.parent.parent / "gym_analyzer" / "input"
_VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
_SHARED_DIR = Path(__file__).parent.parent.parent / "recognize" / "visualize" / "result" / "shared"
_RESULT_DIR = Path(__file__).parent.parent.parent / "recognize" / "visualize" / "result"


@app.get("/api/videos")
def list_videos():
    """List video files in gym_analyzer/input/."""
    if not _INPUT_DIR.is_dir():
        return []
    return sorted(
        f.name for f in _INPUT_DIR.iterdir()
        if f.suffix.lower() in _VIDEO_EXTS
    )


@app.get("/api/ground-truth")
def ground_truth_api(video: str | None = None, date: str | None = None, user_id: str | None = None):
    """Return ground_truth.json for a video (by name or date lookup)."""
    if not video and date:
        uid = user_id or USER_ID
        video = _DATE_VIDEO_MAP.get(uid, {}).get(date)
    if not video:
        return {"found": False}
    folder = Path(video).stem
    gt_path = (_SHARED_DIR / folder / "ground_truth.json").resolve()
    if not str(gt_path).startswith(str(_SHARED_DIR.resolve())):
        raise HTTPException(status_code=403)
    if not gt_path.is_file():
        return {"found": False}
    try:
        data = json.loads(gt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"found": False, "error": "invalid JSON"}
    exercises = [d for d in data if d.get("type") == "exercise"]
    return {"found": True, "data": data, "exercises": exercises, "folder": folder}


@app.get("/api/recognition-versions")
def recognition_versions(video: str | None = None, date: str | None = None, user_id: str | None = None):
    """List available recognition versions for a video."""
    if not video and date:
        uid = user_id or USER_ID
        video = _DATE_VIDEO_MAP.get(uid, {}).get(date)
    if not video:
        return []
    folder = Path(video).stem
    versions = []
    if _RESULT_DIR.is_dir():
        for d in _RESULT_DIR.iterdir():
            if d.name.startswith("v") and d.is_dir() and (d / folder).is_dir():
                versions.append(d.name)
    versions.sort(key=lambda v: int(v[1:]) if v[1:].isdigit() else 0)
    return versions


@app.get("/api/recognition-result")
def recognition_result(version: str, video: str | None = None, date: str | None = None, user_id: str | None = None):
    """Return recognition timeline + exercises for a video at a given version."""
    if not video and date:
        uid = user_id or USER_ID
        video = _DATE_VIDEO_MAP.get(uid, {}).get(date)
    if not video:
        return {"found": False}
    folder = Path(video).stem
    base = _RESULT_DIR / version / folder
    if not base.is_dir():
        return {"found": False}

    timeline = []
    adj = base / "period_result_adjusted.json"
    if not adj.is_file():
        adj = base / "period_result.json"
    if adj.is_file():
        try:
            adj_data = json.loads(adj.read_text(encoding="utf-8"))
            timeline = adj_data.get("segments", [])
            for i, seg in enumerate(timeline):
                if "segmentId" not in seg:
                    seg["segmentId"] = f"seg_{i}"
        except json.JSONDecodeError:
            pass

    exercises = []
    ex_data_full = {}
    ex_file = base / "exercise_result.json"
    if ex_file.is_file():
        try:
            raw_ex = json.loads(ex_file.read_text(encoding="utf-8"))
            if isinstance(raw_ex, dict):
                ex_data_full = raw_ex
                exercises = raw_ex.get("results", [])
            elif isinstance(raw_ex, list):
                ex_data_full = {"results": raw_ex}
                exercises = raw_ex
            for ex in exercises:
                if "segmentId" not in ex and "seg_idx" in ex:
                    ex["segmentId"] = f"seg_{ex['seg_idx']}"
                r = ex.get("result", ex)
                raw_sets = r.get("sets")
                if raw_sets is None or isinstance(raw_sets, (int, float)):
                    total_sets = int(raw_sets or 0)
                    total_reps = int(r.get("reps") or 0)
                    r["total_sets"] = total_sets
                    r["total_reps"] = total_reps
                    r["sets"] = [{"set_number": i + 1, "reps": total_reps // total_sets if total_sets else total_reps}
                                 for i in range(total_sets)] if total_sets else []
        except json.JSONDecodeError:
            pass

    ex_name_map = {ex.get("segmentId"): ex.get("result", {}).get("exercise", "") for ex in exercises if ex.get("segmentId")}
    for seg in timeline:
        sid = seg.get("segmentId")
        if sid and sid in ex_name_map:
            seg["exercise_name"] = ex_name_map[sid]

    # Load Phase 1 raw segments (with equipment/posture) and equipment_timeline
    phase1_segments = []
    equipment_timeline = []
    phase1_prompt = ""
    phase2_prompt = ""
    period_raw = base / "period_result.json"
    if period_raw.is_file():
        try:
            raw_data = json.loads(period_raw.read_text(encoding="utf-8"))
            phase1_segments = raw_data.get("segments", [])
            equipment_timeline = raw_data.get("equipment_timeline", [])
            phase1_prompt = raw_data.get("phase1_prompt", "")
        except json.JSONDecodeError:
            pass
    phase2_prompt = ex_data_full.get("phase2_prompt", "")

    return {
        "found": True, "timeline": timeline, "exercises": exercises,
        "folder": folder, "version": version,
        "phase1_segments": phase1_segments,
        "equipment_timeline": equipment_timeline,
        "phase1_prompt": phase1_prompt,
        "phase2_prompt": phase2_prompt,
    }


@app.get("/api/imu-summary")
def imu_summary(video: str | None = None, date: str | None = None, user_id: str | None = None,
                version: str | None = None):
    """Compute IMU statistical summary for dashboard visualization.

    Returns per-window Phase 1 stats and per-exercise-segment stats.
    """
    import sys, math
    if not video and date:
        uid = user_id or USER_ID
        video = _DATE_VIDEO_MAP.get(uid, {}).get(date)
    if not video:
        return {"found": False}
    folder = Path(video).stem

    # Load IMU data: check input dir first, then shared dir
    imu_path = _INPUT_DIR / folder / "IMU_data.txt"
    if not imu_path.is_file():
        imu_path = _SHARED_DIR / folder / "IMU.txt"
    if not imu_path.is_file():
        return {"found": False, "reason": "no_imu"}

    # Parse IMU_data.txt
    from datetime import datetime as _dt
    lines = imu_path.read_text(encoding="utf-8").splitlines()
    records = []
    t0 = None
    for line in lines[1:]:
        parts = line.strip().split("\t")
        if len(parts) < 9:
            continue
        try:
            dt = _dt.fromisoformat(parts[0])
            if t0 is None:
                t0 = dt
            t_rel = (dt - t0).total_seconds()
            acc_x, acc_y, acc_z = float(parts[2]), float(parts[3]), float(parts[4])
            acc_mag = (acc_x**2 + acc_y**2 + acc_z**2)**0.5
            gyro_x, gyro_y, gyro_z = float(parts[5]), float(parts[6]), float(parts[7])
            gyro_mag = (gyro_x**2 + gyro_y**2 + gyro_z**2)**0.5
            records.append({"t": t_rel, "acc_mag": acc_mag, "gyro_mag": gyro_mag,
                            "ax": acc_x, "ay": acc_y, "az": acc_z})
        except (ValueError, IndexError):
            continue

    if not records:
        return {"found": False, "reason": "no_records"}

    def acc_std_label(v):
        if v > 0.35: return "高"
        if v > 0.15: return "中高"
        if v > 0.05: return "低"
        return "静止"

    def posture_from_az(az):
        if az > -0.35: return "仰卧"
        if az > -0.78: return "俯身"
        if az > -0.88: return "坐姿"
        return "站姿"

    def count_peaks(vals, prom=0.15):
        if len(vals) < 5: return 0
        mean_v = sum(vals) / len(vals)
        thr = mean_v + prom
        p = 0
        for i in range(2, len(vals) - 2):
            if vals[i] > thr and vals[i] >= vals[i-1] and vals[i] >= vals[i+1] and vals[i] > vals[i-2] and vals[i] > vals[i+2]:
                p += 1
        return p

    total_dur = records[-1]["t"]
    window_sec = 30.0

    # Phase 1 windows
    phase1_windows = []
    wi = 0
    while True:
        t_s = wi * window_sec
        t_e = (wi + 1) * window_sec
        if t_s >= total_dur:
            break
        wi += 1
        w_recs = [r for r in records if t_s <= r["t"] < t_e]
        if not w_recs:
            phase1_windows.append({"start_sec": t_s, "end_sec": min(t_e, total_dur),
                                   "intensity": "无数据", "acc_std": 0, "posture": "",
                                   "peaks": 0, "hint": ""})
            continue
        acc_vals = [r["acc_mag"] for r in w_recs]
        az_vals = [r["az"] for r in w_recs]
        acc_mean = sum(acc_vals) / len(acc_vals)
        acc_std = (sum((a - acc_mean)**2 for a in acc_vals) / len(acc_vals))**0.5
        az_mean = sum(az_vals) / len(az_vals)
        posture = posture_from_az(az_mean)
        intensity = acc_std_label(acc_std)
        peaks = count_peaks(acc_vals)
        hint = ""
        if acc_std > 0.15 and peaks >= 3:
            hint = f"{posture}力量训练"
        elif acc_std > 0.05 and posture == "站姿":
            hint = "行走/调整"
        elif acc_std <= 0.05:
            hint = f"静止({posture})"
        phase1_windows.append({
            "start_sec": t_s, "end_sec": min(t_e, total_dur),
            "intensity": intensity, "acc_std": round(acc_std, 3),
            "posture": posture, "peaks": peaks, "hint": hint,
        })

    # Per-exercise segment stats
    exercise_imu = []
    if version:
        base = _RESULT_DIR / version / folder
        adj = base / "period_result_adjusted.json"
        if not adj.is_file():
            adj = base / "period_result.json"
        if adj.is_file():
            try:
                seg_data = json.loads(adj.read_text(encoding="utf-8"))
                segs = seg_data.get("segments", [])
            except json.JSONDecodeError:
                segs = []
            for seg in segs:
                if seg.get("state", "").upper() != "EXERCISE":
                    continue
                ts = seg.get("start_sec", 0)
                te = seg.get("end_sec", 0)
                pad = 5.0
                e_recs = [r for r in records if (ts - pad) <= r["t"] <= (te + pad)]
                if not e_recs:
                    exercise_imu.append({
                        "start_sec": ts, "end_sec": te,
                        "has_data": False,
                    })
                    continue
                acc_vals = [r["acc_mag"] for r in e_recs]
                az_vals = [r["az"] for r in e_recs]
                acc_mean = sum(acc_vals) / len(acc_vals)
                acc_std = (sum((a - acc_mean)**2 for a in acc_vals) / len(acc_vals))**0.5
                az_mean = sum(az_vals) / len(az_vals)
                posture = posture_from_az(az_mean)
                intensity = acc_std_label(acc_std)
                peaks = count_peaks(acc_vals)

                # Sub-windows (10s)
                sub_windows = []
                sub_sec = 10.0
                seg_recs = [r for r in records if ts <= r["t"] <= te]
                if len(seg_recs) > 20 and (te - ts) > sub_sec * 1.5:
                    t = ts
                    while t < te:
                        t2 = min(t + sub_sec, te)
                        sw = [r for r in seg_recs if t <= r["t"] < t2]
                        if len(sw) >= 3:
                            sa = [r["acc_mag"] for r in sw]
                            sa_m = sum(sa) / len(sa)
                            sa_std = (sum((a - sa_m)**2 for a in sa) / len(sa))**0.5
                            sa_az = sum(r["az"] for r in sw) / len(sw)
                            sub_windows.append({
                                "start_sec": t, "end_sec": t2,
                                "intensity": acc_std_label(sa_std),
                                "acc_std": round(sa_std, 3),
                                "posture": posture_from_az(sa_az),
                                "peaks": count_peaks(sa),
                            })
                        t += sub_sec

                # Rest period detection
                rest_periods = []
                rest_thr = 0.05
                min_rest = 10.0
                w_size = 3.0
                stride = 1.0
                rw = []
                t = ts
                while t + w_size <= te:
                    wr = [r for r in seg_recs if t <= r["t"] < t + w_size]
                    if len(wr) >= 3:
                        wa = [r["acc_mag"] for r in wr]
                        wm = sum(wa) / len(wa)
                        ws = (sum((a - wm)**2 for a in wa) / len(wa))**0.5
                        rw.append((t, t + w_size, ws))
                    t += stride
                cur_start = None
                cur_end = None
                for (ws, we, std) in rw:
                    if std < rest_thr:
                        if cur_start is None:
                            cur_start = ws
                        cur_end = we
                    else:
                        if cur_start is not None and cur_end - cur_start >= min_rest:
                            rest_periods.append({"start_sec": cur_start, "end_sec": cur_end,
                                                 "duration": round(cur_end - cur_start, 1)})
                        cur_start = None
                if cur_start is not None and cur_end and cur_end - cur_start >= min_rest:
                    rest_periods.append({"start_sec": cur_start, "end_sec": cur_end,
                                         "duration": round(cur_end - cur_start, 1)})

                exercise_imu.append({
                    "start_sec": ts, "end_sec": te,
                    "has_data": True,
                    "intensity": intensity, "acc_std": round(acc_std, 3),
                    "posture": posture, "peaks": peaks,
                    "sub_windows": sub_windows,
                    "rest_periods": rest_periods,
                })

    return {
        "found": True,
        "imu_duration": round(total_dur, 1),
        "record_count": len(records),
        "phase1_windows": phase1_windows,
        "exercise_imu": exercise_imu,
    }


@app.get("/api/clips-meta")
def clips_meta(version: str, video: str):
    """Return Phase1 clips and Phase2 exercise clips metadata."""
    folder = Path(video).stem
    base = _RESULT_DIR / version / folder

    phase1_clips = []
    p1_meta = base / "clips" / "clips_meta.json"
    if p1_meta.is_file():
        try:
            phase1_clips = json.loads(p1_meta.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    phase2_clips = []
    p2_dir = base / "phase2_clips"
    if p2_dir.is_dir():
        for f in sorted(p2_dir.glob("exercise_*.mp4")):
            seg_idx = int(f.stem.split("_")[1])
            phase2_clips.append({"seg_idx": seg_idx, "filename": f.name})

    return {"phase1_clips": phase1_clips, "phase2_clips": phase2_clips}


@app.get("/clip/{version}/{folder}/{phase}/{filename}", include_in_schema=False)
def serve_clip(version: str, folder: str, phase: str, filename: str, request: Request):
    """Serve a clip video file from result directories with Range support."""
    import urllib.parse
    folder = urllib.parse.unquote(folder)
    filename = urllib.parse.unquote(filename)
    if phase == "phase1":
        filepath = (_RESULT_DIR / version / folder / "clips" / filename).resolve()
    elif phase == "phase2":
        filepath = (_RESULT_DIR / version / folder / "phase2_clips" / filename).resolve()
    else:
        raise HTTPException(status_code=400, detail="phase must be phase1 or phase2")
    if not str(filepath).startswith(str(_RESULT_DIR.resolve())):
        raise HTTPException(status_code=403)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Clip not found: {filename}")

    file_size = filepath.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(filepath, media_type="video/mp4")
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        return FileResponse(filepath, media_type="video/mp4")
    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def iter_file():
        with open(filepath, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                data = f.read(min(remaining, 1024 * 1024))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_file(), status_code=206, media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
        },
    )


@app.get("/video/{filename}", include_in_schema=False)
def serve_video(filename: str, request: Request):
    """Serve a video file from gym_analyzer/input/ with HTTP Range support."""
    import urllib.parse
    filename = urllib.parse.unquote(filename)
    filepath = (_INPUT_DIR / filename).resolve()
    if not str(filepath).startswith(str(_INPUT_DIR.resolve())):
        raise HTTPException(status_code=403)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Video not found: {filename}")

    ext_map = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
               ".avi": "video/x-msvideo", ".mkv": "video/x-matroska"}
    media = ext_map.get(filepath.suffix.lower(), "video/mp4")
    file_size = filepath.stat().st_size

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(filepath, media_type=media)

    # Parse Range: bytes=start-end
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        return FileResponse(filepath, media_type=media)

    start = int(range_match.group(1))
    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def iter_file():
        with open(filepath, "rb") as f:
            f.seek(start)
            remaining = chunk_size
            while remaining > 0:
                read_size = min(remaining, 1024 * 1024)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iter_file(),
        status_code=206,
        media_type=media,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
        },
    )


# ── Prompt files viewer ─────────────────────────────────────────────────────
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "gym_analyzer" / "prompts"

@app.get("/api/prompt-versions")
def prompt_versions():
    """List available prompt files grouped by phase."""
    if not _PROMPTS_DIR.is_dir():
        return {"phase1": [], "phase2": []}
    phase1 = []
    phase2 = []
    for f in sorted(_PROMPTS_DIR.glob("phase1_period_recognize_v*.yaml")):
        v = f.stem.split("_v")[-1]
        phase1.append({"version": f"v{v}", "filename": f.name})
    for f in sorted(_PROMPTS_DIR.glob("phase2_exercise_recognize_v*.yaml")):
        v = f.stem.split("_v")[-1]
        phase2.append({"version": f"v{v}", "filename": f.name})
    phase1.sort(key=lambda x: int(x["version"][1:]) if x["version"][1:].isdigit() else 0)
    phase2.sort(key=lambda x: int(x["version"][1:]) if x["version"][1:].isdigit() else 0)
    return {"phase1": phase1, "phase2": phase2}


@app.get("/api/prompt-content")
def prompt_content(filename: str):
    """Return the content of a prompt YAML file."""
    filepath = (_PROMPTS_DIR / filename).resolve()
    if not str(filepath).startswith(str(_PROMPTS_DIR.resolve())):
        raise HTTPException(status_code=403)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail=f"Prompt not found: {filename}")
    content = filepath.read_text(encoding="utf-8")
    return {"filename": filename, "content": content}


# ── Serve plan_viewer.html at /plan-viewer ────────────────────────────────────
_REPORTS_DIR = Path(__file__).parent

@app.get("/api/evaluation-metrics")
def evaluation_metrics():
    """Compute v9-v15 recognition metrics across all ground-truth videos."""
    import sys
    eval_dir = str(Path(__file__).parent.parent.parent / "recognize" / "visualize")
    if eval_dir not in sys.path:
        sys.path.insert(0, eval_dir)
    from evaluate_versions import (
        get_all_video_ids, evaluate_version, f1,
    )
    video_ids = get_all_video_ids()
    versions = []
    for v in range(9, 16):
        vname = f"v{v}"
        vdir = _RESULT_DIR / vname
        if vdir.is_dir():
            versions.append(vname)

    rows = []
    per_video_all = {}
    details_all = {}
    for ver in versions:
        r = evaluate_version(ver, video_ids)
        m = r["micro"]
        t = r["totals"]
        gt_reps = t.get("gt_total_reps", 0)
        pred_reps = t.get("pred_total_reps", 0)
        gt_actions = t.get("gt_action_count", 0)
        pred_actions = t.get("pred_action_count", 0)
        rep_dev = round((pred_reps - gt_reps) / gt_reps * 100, 1) if gt_reps > 0 else 0
        action_dev = round((pred_actions - gt_actions) / gt_actions * 100, 1) if gt_actions > 0 else 0
        rows.append({
            "version": ver,
            "action_precision": round(m["action_precision"] * 100, 1),
            "action_recall": round(m["action_recall"] * 100, 1),
            "action_f1": round(m["action_f1"] * 100, 1),
            "set_acc": round(m["set_acc"] * 100, 1),
            "setrep_acc": round(m["setrep_acc"] * 100, 1),
            "joint_f1": round(m["joint_f1"] * 100, 1),
            "tp": t["action_tp"],
            "fp": t["action_fp"],
            "fn": t["action_fn"],
            "gt_count": t["gt_count"],
            "gt_total_reps": gt_reps,
            "pred_total_reps": pred_reps,
            "rep_deviation": rep_dev,
            "gt_action_count": gt_actions,
            "pred_action_count": pred_actions,
            "action_count_deviation": action_dev,
        })
        pv = {}
        for vid, vdata in r["per_video"].items():
            pv[vid] = {
                "action_f1": round(vdata["action_f1"] * 100, 1),
                "set_acc": round(vdata["set_acc"] * 100, 1),
                "setrep_acc": round(vdata["setrep_acc"] * 100, 1),
                "joint_f1": round(vdata["joint_f1"] * 100, 1),
            }
        per_video_all[ver] = pv
        details_all[ver] = r["details"]

    return {
        "versions": versions,
        "videos": video_ids,
        "rows": rows,
        "per_video": per_video_all,
        "details": details_all,
    }


@app.get("/evaluation", include_in_schema=False)
def evaluation_page():
    return FileResponse(_REPORTS_DIR / "evaluation.html")


@app.get("/", include_in_schema=False)
def dashboard_page():
    return FileResponse(_REPORTS_DIR / "training_dashboard.html")

@app.get("/report", include_in_schema=False)
def report_page():
    return FileResponse(_REPORTS_DIR / "training_dashboard.html")

@app.get("/plan-viewer", include_in_schema=False)
def serve_plan_viewer():
    return FileResponse(_REPORTS_DIR / "plan_viewer.html")

@app.get("/svg/{filename}", include_in_schema=False)
def serve_svg(filename: str):
    allowed = {"front_body.svg", "back_body.svg",
               "female_front_body.svg", "female_back_body.svg"}
    if filename not in allowed:
        raise HTTPException(status_code=404)
    return FileResponse(_REPORTS_DIR / filename, media_type="image/svg+xml")


# ── Server-side muscle highlight SVGs ────────────────────────────────────────
from fastapi.responses import Response as _Response

_svg_raw_cache: dict[str, str] = {}

def _load_svg_raw(name: str) -> str:
    if name not in _svg_raw_cache:
        _svg_raw_cache[name] = (_REPORTS_DIR / name).read_text(encoding="utf-8")
    return _svg_raw_cache[name]


@app.get("/api/plan-viewer/muscle-svg/{side}")
def muscle_svg(
    side: str,           # "front" or "back"
    primary: str = "",   # comma-separated svg group ids
    secondary: str = "", # comma-separated svg group ids
):
    """Return a highlighted SVG via injected <style> — no structural modification."""
    if side not in ("front", "back"):
        raise HTTPException(status_code=400)

    fname    = "front_body.svg" if side == "front" else "back_body.svg"
    raw      = _load_svg_raw(fname)

    prim_ids = [x for x in primary.split(",")  if x.strip()]
    sec_ids  = [x for x in secondary.split(",") if x.strip() and x not in prim_ids]

    # Build CSS selectors
    prim_sel = ", ".join(f"#{i}" for i in prim_ids) if prim_ids else ".__none__"
    sec_sel  = ", ".join(f"#{i}" for i in sec_ids)  if sec_ids  else ".__none__"

    style = f"""<style>
/* dim all muscle groups */
.bodymap {{ fill: #2a2f47 !important; color: #2a2f47 !important; }}
.bodymap path, .bodymap ellipse {{ fill: #2a2f47 !important; }}
/* hide joints, body outline, hover rings */
#body, #shoulders, #elbow, #wrist, #hips, #knees, #ankles,
[id^="hover"] {{ display: none !important; }}
/* primary muscles */
{prim_sel} {{ fill: #ff6584 !important; color: #ff6584 !important; }}
{prim_sel} path, {prim_sel} ellipse {{ fill: #ff6584 !important; }}
/* secondary muscles */
{sec_sel} {{ fill: #6c63ff !important; color: #6c63ff !important; }}
{sec_sel} path, {sec_sel} ellipse {{ fill: #6c63ff !important; }}
</style>"""

    # Inject <style> right after opening <svg> tag and fix dimensions
    svg = raw.replace("<svg ", '<svg width="34" height="62" ', 1)
    svg = svg.replace(">", ">" + style, 1)   # after the first >

    return _Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/fitness/body-svg/{side}", include_in_schema=False)
def fitness_body_svg(
    side: str,
    gender: str = "male",
    primary: str = "",
    secondary: str = "",
    tertiary: str = "",
):
    """Gender-aware highlighted body SVG for the Relty fitness screen.
    primary/secondary/tertiary: comma-separated SVG group IDs to color.
    Colors: primary=#4D9FFF (high), secondary=dimmer blue (med), tertiary=#E0B45A (low).
    """
    if side not in ("front", "back"):
        raise HTTPException(status_code=400)
    if gender not in ("male", "female"):
        gender = "male"

    if gender == "female":
        fname = "female_front_body.svg" if side == "front" else "female_back_body.svg"
    else:
        fname = "front_body.svg" if side == "front" else "back_body.svg"

    raw = _load_svg_raw(fname)

    prim_ids = [x.strip() for x in primary.split(",")  if x.strip()]
    sec_ids  = [x.strip() for x in secondary.split(",") if x.strip() and x.strip() not in prim_ids]
    tert_ids = [x.strip() for x in tertiary.split(",")  if x.strip() and x.strip() not in prim_ids and x.strip() not in sec_ids]

    def _sel(ids):
        return ", ".join(f"#{i}" for i in ids) if ids else ".__none__"

    style = (
        "<style>"
        ".bodymap { fill: rgba(255,255,255,0.07) !important; }"
        ".bodymap path, .bodymap ellipse, .bodymap circle { fill: rgba(255,255,255,0.07) !important; }"
        "#body, #b-body, #shoulders, #b-shoulders, #elbow, #b-elbow,"
        "#wrist, #b-wrist, #hips, #b-hips, #knees, #b-knees, #ankles, #b-ankles,"
        "[id^='hover'] { display: none !important; }"
        f"{_sel(prim_ids)} path, {_sel(prim_ids)} ellipse, {_sel(prim_ids)} circle"
        " { fill: #4D9FFF !important; }"
        f"{_sel(sec_ids)} path, {_sel(sec_ids)} ellipse, {_sel(sec_ids)} circle"
        " { fill: rgba(77,159,255,0.52) !important; }"
        f"{_sel(tert_ids)} path, {_sel(tert_ids)} ellipse, {_sel(tert_ids)} circle"
        " { fill: #E0B45A !important; }"
        "</style>"
    )

    # Inject <style> immediately after the opening <svg ...> tag
    svg = re.sub(r'(<svg[^>]*>)', r'\1' + style, raw, count=1)

    return _Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=60"},
    )


# ── Relty Wearable App (served via HTTP so JSX files load without CORS issues) ─
_RELTY_DIR = Path(__file__).parent.parent.parent / "Relty"
if _RELTY_DIR.is_dir():
    app.mount("/relty", StaticFiles(directory=str(_RELTY_DIR), html=True), name="relty")
