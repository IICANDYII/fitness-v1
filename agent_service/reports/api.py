from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, date
from collections import defaultdict

app = FastAPI(title="Fitness Dashboard API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"]
)

DB = dict(host="localhost", port=5432, dbname="fitness", user="postgres", password="666666")
USER_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

# 练习（中文名）→ 肌群权重映射（权重 1=辅助, 2=主要）
EXERCISE_MUSCLES: dict[str, dict[str, int]] = {
    "平板卧推":     {"chest": 2, "front-shoulders": 1, "b-triceps": 1},
    "上斜哑铃推":   {"chest": 2, "front-shoulders": 1},
    "站姿推举":     {"front-shoulders": 2, "b-triceps": 1},
    "侧平举":       {"front-shoulders": 2},
    "绳索下压":     {"b-triceps": 2},
    "硬拉":         {"b-lats": 2, "b-lowerback": 2, "b-glutes": 1, "b-hamstrings": 1},
    "杠铃划船":     {"b-lats": 2, "traps": 1, "biceps": 1},
    "引体向上":     {"b-lats": 2, "biceps": 1, "traps": 1},
    "面拉":         {"b-rear-shoulders": 2, "b-traps-middle": 2},
    "杠铃弯举":     {"biceps": 2},
    "深蹲":         {"quads": 2, "b-glutes": 2},
    "腿举":         {"quads": 2, "b-glutes": 1},
    "罗马尼亚硬拉": {"b-hamstrings": 2, "b-glutes": 2, "b-lowerback": 1},
    "腿弯举":       {"b-hamstrings": 2},
    "提踵":         {"calves": 2, "b-calves": 1},
}

# 大肌群聚合：仪表板 Card 1 "训练部位分布"
MAJOR_GROUPS = {
    "胸": ["chest"],
    "背": ["b-lats", "traps", "b-traps-middle", "b-lowerback"],
    "腿": ["quads", "calves", "b-calves", "b-hamstrings"],
    "臀": ["b-glutes"],
}

def get_conn():
    return psycopg2.connect(**DB, cursor_factory=psycopg2.extras.RealDictCursor)

def muscle_intensity_label(score: float, max_score: float) -> str:
    if max_score == 0:
        return "none"
    ratio = score / max_score
    if ratio >= 0.6:
        return "high"
    elif ratio >= 0.25:
        return "medium"
    elif ratio > 0:
        return "low"
    return "none"


@app.get("/api/daily")
def daily():
    """最近一次训练的当日分析：时长/热量/心率/完成率/肌群分布"""
    conn = get_conn()
    cur = conn.cursor()

    # 最近一次 session
    cur.execute("""
        SELECT session_id,
               start_time, end_time, calories, completion_rate,
               ROUND(EXTRACT(EPOCH FROM (end_time - start_time)) / 60) AS duration_min
        FROM workout_session
        WHERE user_id = %s
        ORDER BY start_time DESC
        LIMIT 1
    """, (USER_ID,))
    session = cur.fetchone()
    if not session:
        conn.close()
        return {}

    sid = session["session_id"]

    # 平均心率（session 时段内的 biometric 数据）
    cur.execute("""
        SELECT ROUND(AVG(heart_rate)) AS avg_hr
        FROM biometric_stream
        WHERE user_id = %s
          AND timestamp BETWEEN %s AND %s
    """, (USER_ID, session["start_time"], session["end_time"]))
    hr_row = cur.fetchone()
    avg_hr = int(hr_row["avg_hr"]) if hr_row and hr_row["avg_hr"] else 0

    # 本次 session 的动作执行记录
    cur.execute("""
        SELECT exercise_name, sets FROM exercise_execution
        WHERE session_id = %s
    """, (sid,))
    executions = cur.fetchall()
    conn.close()

    # 计算各大肌群加权组数
    muscle_scores: dict[str, float] = defaultdict(float)
    for row in executions:
        name = row["exercise_name"]
        sets = row["sets"] or 0
        for muscle, weight in EXERCISE_MUSCLES.get(name, {}).items():
            muscle_scores[muscle] += sets * weight

    # 聚合到 4 个大肌群
    group_scores: dict[str, float] = {}
    for label, muscles in MAJOR_GROUPS.items():
        group_scores[label] = sum(muscle_scores.get(m, 0) for m in muscles)

    max_score = max(group_scores.values()) if group_scores else 1
    muscle_distribution = {
        k: round(v / max_score * 100) if max_score else 0
        for k, v in group_scores.items()
    }

    return {
        "date": session["start_time"].date().isoformat(),
        "duration_min": int(session["duration_min"]),
        "calories": int(session["calories"]),
        "avg_hr": avg_hr,
        "completion_rate": round(float(session["completion_rate"]) * 100),
        "muscle_distribution": muscle_distribution,
    }


@app.get("/api/weekly")
def weekly():
    """近 7 日训练量、热量汇总及每日组数明细（用于折线图）"""
    conn = get_conn()
    cur = conn.cursor()

    # 以最近一次 session 的日期为基准，向前取 7 天
    cur.execute("""
        SELECT DATE(start_time) AS day
        FROM workout_session WHERE user_id = %s
        ORDER BY start_time DESC LIMIT 1
    """, (USER_ID,))
    latest = cur.fetchone()
    if not latest:
        conn.close()
        return {}
    end_date: date = latest["day"]
    start_date: date = end_date - timedelta(days=6)

    # 每日总组数
    cur.execute("""
        SELECT DATE(ws.start_time) AS day,
               COALESCE(SUM(ee.sets), 0) AS total_sets
        FROM workout_session ws
        LEFT JOIN exercise_execution ee ON ee.session_id = ws.session_id
        WHERE ws.user_id = %s
          AND DATE(ws.start_time) BETWEEN %s AND %s
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

    # 上一个 7 天（用于趋势对比）
    prev_start = start_date - timedelta(days=7)
    prev_end = start_date - timedelta(days=1)
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

    # 填满 7 天数组
    days_list = [start_date + timedelta(days=i) for i in range(7)]
    daily_sets = [daily_rows.get(d, 0) for d in days_list]
    day_labels = ["周" + "一二三四五六日"[d.weekday()] for d in days_list]

    total_sets = sum(daily_sets)
    total_kcal = sum(daily_kcal.values())

    def trend_pct(cur_val: float, prev_val: float) -> float:
        if prev_val == 0:
            return 0.0
        return round((cur_val - prev_val) / prev_val * 100, 1)

    return {
        "total_sets": total_sets,
        "total_calories": round(total_kcal),
        "sets_trend_pct": trend_pct(total_sets, prev_sets),
        "calories_trend_pct": trend_pct(total_kcal, prev_kcal),
        "daily_sets": daily_sets,
        "day_labels": day_labels,
    }


@app.get("/api/muscles")
def muscles():
    """近 7 日肌群热力图：每个肌群 SVG ID 对应的强度 high/medium/low/none"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT DATE(ws.start_time) AS day
        FROM workout_session ws WHERE ws.user_id = %s
        ORDER BY ws.start_time DESC LIMIT 1
    """, (USER_ID,))
    latest = cur.fetchone()
    if not latest:
        conn.close()
        return {}
    end_date = latest["day"]
    start_date = end_date - timedelta(days=6)

    cur.execute("""
        SELECT ee.exercise_name, SUM(ee.sets) AS total_sets
        FROM exercise_execution ee
        JOIN workout_session ws ON ws.session_id = ee.session_id
        WHERE ws.user_id = %s AND DATE(ws.start_time) BETWEEN %s AND %s
        GROUP BY ee.exercise_name
    """, (USER_ID, start_date, end_date))
    rows = cur.fetchall()
    conn.close()

    muscle_scores: dict[str, float] = defaultdict(float)
    for row in rows:
        name = row["exercise_name"]
        sets = float(row["total_sets"] or 0)
        for muscle, weight in EXERCISE_MUSCLES.get(name, {}).items():
            muscle_scores[muscle] += sets * weight

    max_score = max(muscle_scores.values()) if muscle_scores else 1
    return {
        muscle: muscle_intensity_label(score, max_score)
        for muscle, score in muscle_scores.items()
    }


@app.get("/api/calendar")
def calendar():
    """当月每日训练状态：full(完整)/partial(部分)/rest(休息)"""
    conn = get_conn()
    cur = conn.cursor()

    today = date.today()
    month_start = today.replace(day=1)
    # 取当月所有 session
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
        rate = float(row["completion_rate"] or 0)
        result[day_str] = "full" if rate >= 0.95 else "partial"
    return {
        "year": today.year,
        "month": today.month,
        "days": result
    }
