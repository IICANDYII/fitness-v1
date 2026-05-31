from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
from collections import defaultdict
from pathlib import Path

app = FastAPI(title="Fitness Dashboard API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"]
)

DB      = dict(host="localhost", port=5432, dbname="fitness", user="postgres", password="666666")
USER_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

# exercise_execution.exercise_name (short) → exercises.name_cn (canonical)
EXERCISE_ALIAS: dict[str, str] = {
    "平板卧推":      "杠铃平卧推",
    "上斜哑铃推":    "哑铃上斜卧推",
    "侧平举":        "哑铃侧平举",
    "深蹲":          "杠铃深蹲",
    "硬拉":          "杠铃硬拉",
    "站姿推举":      "杠铃过顶推举",
    "提踵":          "站姿提踵",
    "杠铃划船":      "杠铃俯身划船",
    "罗马尼亚硬拉":  "杠铃罗马尼亚硬拉",
    "腿举":          "器械腿举",
    "腿弯举":        "器械腘绳肌弯举",
    "面拉":          "绳索面拉",
    "绳索下压":      "绳索下压",
    "引体向上":      "引体向上",
    "杠铃弯举":      "杠铃弯举",
}

# Major groups for Card 1 bar chart.
# Values are SVG muscle IDs (without b- prefix); both front and back maps are checked.
MAJOR_GROUPS: dict[str, list[str]] = {
    "胸":   ["chest"],
    "肩":   ["shoulders", "front-shoulders", "rear-shoulders"],
    "臂":   ["triceps", "biceps"],
    "背":   ["lats", "traps", "traps-middle", "lowerback", "scapula"],
    "腿":   ["quads", "hamstrings", "calves"],
    "臀":   ["glutes", "hips"],
    "腹":   ["abdominals", "obliques"],
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


def compute_distribution(cur, session_id) -> dict[str, int]:
    """Return muscle_distribution (label→0-100) for a given session_id."""
    cur.execute(
        "SELECT exercise_name, sets, reps FROM exercise_execution WHERE session_id = %s",
        (session_id,),
    )
    rows = cur.fetchall()
    svg_scores, _ = compute_muscles(cur, rows)
    if not svg_scores:
        return {}
    max_overall = max(svg_scores.values())
    result = {}
    for label, muscles in MAJOR_GROUPS.items():
        peak = group_peak(muscles, svg_scores)
        if peak > 0:
            result[label] = round(peak / max_overall * 100)
    return result


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
    if canonical_names:
        cur.execute(
            "SELECT name_cn, source_data->'muscles' AS m FROM exercises WHERE name_cn = ANY(%s)",
            (canonical_names,),
        )
        ex_map: dict[str, dict] = {r["name_cn"]: (r["m"] or {}) for r in cur.fetchall()}
    else:
        ex_map = {}

    svg_scores: defaultdict[str, float] = defaultdict(float)
    raw_scores: defaultdict[str, float] = defaultdict(float)

    for row in rows:
        name      = row["exercise_name"]
        canonical = EXERCISE_ALIAS.get(name, name)
        sets      = float(row.get("sets") or row.get("total_sets") or 0)
        m         = ex_map.get(canonical, {})
        fm        = m.get("frontBodyMap", {})
        bm        = m.get("backBodyMap",  {})

        for muscle in fm.get("text-mw-red",  []):
            svg_scores[muscle]          += sets * 2
            raw_scores[muscle]          += sets * 2
        for muscle in fm.get("text-mw-gray", []):
            svg_scores[muscle]          += sets * 1
            raw_scores[muscle]          += sets * 1
        for muscle in bm.get("text-mw-red",  []):
            svg_scores["b-" + muscle]   += sets * 2
            raw_scores[muscle]          += sets * 2
        for muscle in bm.get("text-mw-gray", []):
            svg_scores["b-" + muscle]   += sets * 1
            raw_scores[muscle]          += sets * 1

    return dict(svg_scores), dict(raw_scores)


@app.get("/api/user")
def user():
    """返回当前用户基本信息（性别等），供前端切换人体图性别。"""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "SELECT gender FROM user_profile_long_term WHERE user_id = %s",
        (USER_ID,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"gender": "male"}
    g = (row["gender"] or "male").lower()
    return {"gender": "female" if g in ("female", "f", "女") else "male"}


@app.get("/api/daily")
def daily(date: str | None = None):
    """指定日期（默认最近一次）的当日分析：时长/热量/心率/完成率/肌群分布"""
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
        """, (USER_ID, target_date))
    else:
        cur.execute("""
            SELECT session_id, start_time, end_time, calories, completion_rate, total_volume,
                   ROUND(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) AS duration_min
            FROM workout_session
            WHERE user_id = %s
            ORDER BY start_time DESC LIMIT 1
        """, (USER_ID,))

    session = cur.fetchone()
    if not session:
        conn.close()
        return {}

    sid = session["session_id"]

    # 平均心率
    cur.execute("""
        SELECT ROUND(AVG(heart_rate)) AS avg_hr
        FROM biometric_stream
        WHERE user_id = %s AND timestamp BETWEEN %s AND %s
    """, (USER_ID, session["start_time"], session["end_time"]))
    hr_row = cur.fetchone()
    avg_hr = int(hr_row["avg_hr"]) if hr_row and hr_row["avg_hr"] else 0

    # 动作执行记录
    cur.execute(
        "SELECT exercise_name, sets, reps FROM exercise_execution WHERE session_id = %s ORDER BY timestamp",
        (sid,),
    )
    executions = cur.fetchall()

    svg_scores, _ = compute_muscles(cur, executions)

    # Card 1 bars: peak individual-muscle score per group,
    # normalised by the SAME global max as Card 2 — so bar % == heatmap intensity.
    max_overall = max(svg_scores.values()) if svg_scores else 1
    muscle_distribution = {}
    for label, muscles in MAJOR_GROUPS.items():
        peak = group_peak(muscles, svg_scores)
        if peak > 0:
            muscle_distribution[label] = round(peak / max_overall * 100)

    # Previous training session muscle distribution (for trend arrows)
    cur.execute("""
        SELECT session_id FROM workout_session
        WHERE user_id = %s AND DATE(start_time) < %s
        ORDER BY start_time DESC LIMIT 1
    """, (USER_ID, session["start_time"].date()))
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

    exercises_list = [
        {"name": r["exercise_name"], "sets": int(r["sets"] or 0), "reps": int(r["reps"] or 0)}
        for r in executions
    ]

    # Card 2 heatmap: each SVG muscle ID → its group's 0-100 pct from Card 1 bars.
    # All muscles in every group are included (0 for untrained groups) so the
    # frontend can reset inactive muscles to grey without a separate pass.
    muscle_heatmap: dict[str, int] = {}
    for label, group_muscles in MAJOR_GROUPS.items():
        pct = muscle_distribution.get(label, 0)
        for m in group_muscles:
            muscle_heatmap[m] = pct          # front SVG key
            muscle_heatmap["b-" + m] = pct   # back SVG key

    return {
        "date":              session["start_time"].date().isoformat(),
        "duration_min":      int(session["duration_min"]),
        "calories":          int(session["calories"]),
        "avg_hr":            avg_hr,
        "completion_rate":   round(float(session["completion_rate"]) * 100),
        "total_volume":      int(session["total_volume"] or 0),
        "muscle_distribution": muscle_distribution,
        "muscle_trend":        muscle_trend,
        "muscle_heatmap":      muscle_heatmap,
        "exercises":           exercises_list,
    }


@app.get("/api/weekly")
def weekly():
    """近 7 日训练量、热量汇总及每日组数明细（用于折线图）"""
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        SELECT DATE(start_time) AS day
        FROM workout_session WHERE user_id = %s
        ORDER BY start_time DESC LIMIT 1
    """, (USER_ID,))
    latest = cur.fetchone()
    if not latest:
        conn.close()
        return {}
    end_date:   date = latest["day"]
    start_date: date = end_date - timedelta(days=6)

    # 每日总组数
    cur.execute("""
        SELECT DATE(ws.start_time) AS day,
               COALESCE(SUM(ee.sets), 0) AS total_sets
        FROM workout_session ws
        LEFT JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
        GROUP BY DATE(ws.start_time)
        ORDER BY day
    """, (USER_ID, start_date, end_date))
    daily_rows = {row["day"]: int(row["total_sets"]) for row in cur.fetchall()}

    # 每日热量
    cur.execute("""
        SELECT DATE(start_time) AS day, SUM(calories) AS kcal
        FROM workout_session
        WHERE user_id = %s AND DATE(start_time) BETWEEN %s AND %s
        GROUP BY DATE(start_time)
    """, (USER_ID, start_date, end_date))
    daily_kcal = {row["day"]: float(row["kcal"]) for row in cur.fetchall()}

    # 上一个 7 天（趋势对比）
    prev_start = start_date - timedelta(days=7)
    prev_end   = start_date - timedelta(days=1)
    cur.execute("""
        SELECT COALESCE(SUM(ee.sets), 0) AS sets, COALESCE(SUM(ws.calories), 0) AS kcal
        FROM workout_session ws
        LEFT JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
    """, (USER_ID, prev_start, prev_end))
    prev = cur.fetchone()
    conn.close()

    prev_sets = float(prev["sets"]) if prev else 0
    prev_kcal = float(prev["kcal"]) if prev else 0

    days_list  = [start_date + timedelta(days=i) for i in range(7)]
    daily_sets = [daily_rows.get(d, 0) for d in days_list]
    day_labels = ["周" + "一二三四五六日"[d.weekday()] for d in days_list]

    total_sets = sum(daily_sets)
    total_kcal = sum(daily_kcal.values())

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
    }


@app.get("/api/muscles")
def muscles(date: str | None = None):
    """
    肌群热力图（high/medium/low/none）
    - ?date=YYYY-MM-DD → 仅该日数据
    - 无参数           → 最近 7 天
    """
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
        """, (USER_ID,))
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
    """, (USER_ID, start_date, end_date))
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
def hr_detail(date: str | None = None):
    """
    返回指定日期（默认最近一次训练日）的：
      - 生物特征流（每10分钟心率/HRV/疲劳）
      - 动作执行记录
      - session 信息
    """
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
            (USER_ID,),
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
    """, (USER_ID, target_date))
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
    """, (USER_ID, target_date))
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
    """, (USER_ID, target_date))
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
def calendar():
    """当月每日训练状态：full(完整)/partial(部分)/rest(休息)"""
    conn = get_conn()
    cur  = conn.cursor()

    today       = date.today()
    month_start = today.replace(day=1)
    cur.execute("""
        SELECT DATE(start_time) AS day, completion_rate
        FROM workout_session
        WHERE user_id = %s
          AND DATE(start_time) >= %s
          AND DATE(start_time) <= %s
        ORDER BY start_time
    """, (USER_ID, month_start, today))
    rows = cur.fetchall()
    conn.close()

    result: dict[str, str] = {}
    for row in rows:
        day_str = row["day"].isoformat()
        rate    = float(row["completion_rate"] or 0)
        result[day_str] = "full" if rate >= 0.95 else "partial"

    return {
        "year":  today.year,
        "month": today.month,
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


@app.get("/api/plan-viewer/latest-plan")
def plan_viewer_latest_plan():
    """Most recent workout_plan for the plan viewer user."""
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


# ── Serve plan_viewer.html at /plan-viewer ────────────────────────────────────
_REPORTS_DIR = Path(__file__).parent

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
