"""FastAPI server — serves the 4 dashboard endpoints + video analysis trigger.

Endpoints:
  GET  /api/daily            → 当日分析
  GET  /api/muscles          → 肌群热力图
  GET  /api/weekly           → 每周分析
  GET  /api/calendar         → 月历视图
  GET  /api/files            → 列出 input/ 目录中的视频和心率文件
  POST /api/analyze          → 触发视频分析
  GET  /api/analyze/progress → 分析进度
  GET  /api/status           → 已分析日期列表
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import shutil
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config, progress as prog
from .agent import GymAnalyzerAgent
from .db import get_conn
from .tools import load_results

app = FastAPI(title="Gym Analyzer API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _latest_result() -> dict:
    """Return the most recent saved result, or raise 404."""
    results = load_results()
    if not results:
        raise HTTPException(404, "No analysis results found. POST /api/analyze first.")
    latest_date = sorted(results.keys())[-1]
    return results[latest_date]


def _merge_weekly(results: dict) -> dict:
    """Build /api/weekly from stored results (Sunday–Saturday week)."""
    from datetime import timedelta
    today = date.today()
    # Find the Sunday that starts the current week
    sun_offset = (today.weekday() + 1) % 7   # Mon=0…Sun=6 → offset 1…0
    week_start = today - timedelta(days=sun_offset)

    day_labels, daily_sets = [], []
    total_sets = 0
    total_calories = 0
    training_frequency = 0

    for i in range(7):
        d = week_start + timedelta(days=i)
        label = f"{d.month}/{d.day}"
        day_labels.append(label)
        r = results.get(d.isoformat(), {})
        kcal = r.get("daily", {}).get("calories", 0) if r else 0
        dur  = r.get("daily", {}).get("duration_min", 0) if r else 0
        sets = r.get("daily", {}).get("completion_rate", 0) // 10 if r else 0
        daily_sets.append(sets)
        total_sets += sets
        total_calories += kcal
        if dur and dur > 0:
            training_frequency += 1

    return {
        "total_sets": total_sets,
        "sets_trend_pct": 0,
        "total_calories": total_calories,
        "calories_trend_pct": 0,
        "daily_sets": daily_sets,
        "day_labels": day_labels,
        "training_frequency": training_frequency,
    }


def _merge_calendar(results: dict) -> dict:
    today = date.today()
    days = {}
    for date_str, r in results.items():
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d.year == today.year and d.month == today.month:
            rate = r.get("daily", {}).get("completion_rate", 0)
            days[date_str] = "full" if rate >= 80 else "partial"
    return {"year": today.year, "month": today.month, "days": days}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/daily")
def daily():
    return _latest_result().get("daily", {})


@app.get("/api/muscles")
def muscles():
    return _latest_result().get("muscles", {})


@app.get("/api/weekly")
def weekly():
    return _merge_weekly(load_results())


@app.get("/api/calendar")
def calendar():
    return _merge_calendar(load_results())


@app.get("/")
@app.get("/analyzer")
def analyzer_page():
    """Serve the video analyzer frontend page."""
    html = Path(__file__).parent / "analyzer.html"
    return FileResponse(str(html), media_type="text/html")


class UserCreate(BaseModel):
    gender: str = "male"
    age: int = 25
    height: int = 170
    weight: int = 65
    fitness_goal: str = ""
    experience_level: str = "intermediate"


@app.get("/api/users")
def list_users():
    """List all users from user_profile_long_term."""
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT user_id, gender, age, height, weight,
                   fitness_goal, experience_level
            FROM user_profile_long_term
            ORDER BY id
        """)
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "user_id":          str(r["user_id"]),
            "gender":           r["gender"],
            "age":              r["age"],
            "height":           r["height"],
            "weight":           r["weight"],
            "fitness_goal":     r["fitness_goal"] or "",
            "experience_level": r["experience_level"] or "",
            "label": (
                f"{r['gender']}  {r['age']}岁  "
                f"{r['height']}cm / {r['weight']}kg  "
                f"{r['fitness_goal'] or ''}"
            ).strip(),
        }
        for r in rows
    ]


@app.post("/api/users")
def create_user(body: UserCreate):
    """Create a new user in user_profile_long_term. Returns the new user_id."""
    import uuid
    new_id = str(uuid.uuid4())
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_profile_long_term
                (user_id, gender, age, height, weight,
                 fitness_goal, experience_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (new_id, body.gender, body.age, body.height,
              body.weight, body.fitness_goal, body.experience_level))
        # workout_session FK references user_profile, so sync there too
        cur.execute("""
            INSERT INTO user_profile (user_id, height, weight, age, gender, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO NOTHING
        """, (new_id, body.height, body.weight, body.age, body.gender))
        conn.commit()
    finally:
        conn.close()
    return {
        "user_id": new_id,
        "gender":  body.gender,
        "age":     body.age,
        "height":  body.height,
        "weight":  body.weight,
        "fitness_goal": body.fitness_goal,
        "label": f"{body.gender}  {body.age}岁  {body.height}cm / {body.weight}kg  {body.fitness_goal}".strip(),
    }


@app.get("/api/files")
def list_files():
    """Recursively list video, HR, and JSON files under gym_analyzer/input/.

    Returns:
      videos:   [{name, label, path, size_mb}]
      hr_files: [{name, label, path, size_mb}]
    """
    videos, hr_files = [], []
    for f in sorted(config.INPUT_DIR.rglob("*")):
        if not f.is_file():
            continue
        # label shows subfolder context: "5.25 / 5.25.mp4"
        rel   = f.relative_to(config.INPUT_DIR)
        label = str(rel).replace("\\", " / ")
        size_mb = round(f.stat().st_size / 1024 / 1024, 1)
        entry = {"name": f.name, "label": label, "path": str(f), "size_mb": size_mb}
        if f.suffix.lower() in config.VIDEO_EXTS:
            videos.append(entry)
        elif f.suffix.lower() in config.HR_EXTS:
            hr_files.append(entry)
    return {
        "input_dir": str(config.INPUT_DIR),
        "videos": videos,
        "hr_files": hr_files,
    }


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """接收本地视频文件上传，保存到 gym_analyzer/input/ 目录。"""
    if Path(file.filename).suffix.lower() not in config.VIDEO_EXTS:
        raise HTTPException(400, f"不支持的文件类型：{file.filename}")
    dest = config.INPUT_DIR / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {
        "path":    str(dest),
        "name":    file.filename,
        "size_mb": round(dest.stat().st_size / 1024 / 1024, 1),
    }


@app.post("/api/upload/plan")
async def upload_plan(file: UploadFile = File(...)):
    """接收训练计划 JSON 文件，保存到 gym_analyzer/input/training_plan.json。"""
    if Path(file.filename).suffix.lower() != ".json":
        raise HTTPException(400, f"需要 JSON 文件，收到：{file.filename}")
    dest = config.INPUT_DIR / "training_plan.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        json.loads(dest.read_text(encoding="utf-8"))
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "无效的 JSON 文件，无法解析")
    return {"path": str(dest), "filename": file.filename}


@app.get("/api/status")
def status():
    results = load_results()
    return {"analyzed_dates": sorted(results.keys()), "total": len(results)}


class AnalyzeRequest(BaseModel):
    video_path: str
    user_id: str | None = None
    date: str | None = None
    weight_kg: float = 65.0
    gender: str = "female"
    age: int = 25


def _run_analysis(video_path: str, user_id: str, workout_date: str,
                  weight_kg: float, gender: str, age: int):
    try:
        agent = GymAnalyzerAgent()
        agent.run(video_path, workout_date, weight_kg,
                  gender=gender, age=age, user_id=user_id)
    except Exception as e:
        prog.mark_error(video_path, str(e))


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Trigger video analysis in the background."""
    if not Path(req.video_path).exists():
        raise HTTPException(400, f"Video not found: {req.video_path}")
    workout_date = req.date or date.today().isoformat()
    uid = req.user_id or config.DEFAULT_USER_ID
    background_tasks.add_task(
        _run_analysis, req.video_path, uid, workout_date,
        req.weight_kg, req.gender, req.age
    )
    prog.update(req.video_path, 0, "排队等待分析")
    return {"status": "queued", "date": workout_date, "video": req.video_path}


@app.get("/api/analyze/progress")
def get_progress():
    """Return real-time progress for all running/completed analyses."""
    return prog.get_all()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("gym_analyzer.api:app", host="0.0.0.0", port=config.API_PORT, reload=True)
