"""All agent tools as plain Python functions + their JSON schema definitions."""

from __future__ import annotations

import base64
import json
import math
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .db import save_to_db
from .visualizer import generate_charts
import requests

from . import config
from .extractor import extract_frames as _v2_extract_frames, FrameMeta
from .pipeline import run_pipeline as _v2_run_pipeline

# ═══════════════════════════════════════════════════════════════════════════════
# Tool implementations
# ═══════════════════════════════════════════════════════════════════════════════

def extract_frames(video_path: str, fps: int = config.FPS) -> dict:
    """Extract frames from a video using the v2 extractor (400x225, 1fps).

    The v2 extractor saves frames to {video_dir}/{video_stem}/frames/ and
    writes frames_meta.json for the pipeline.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return {"error": f"Video not found: {video_path}"}

    metas = _v2_extract_frames(video_path, sample_fps=fps)
    work_dir = video_path.parent / video_path.stem

    cap = cv2.VideoCapture(str(video_path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_src / src_fps if src_fps > 0 else 0
    cap.release()

    return {
        "video": str(video_path),
        "duration_sec": round(duration_sec, 1),
        "total_frames": len(metas),
        "fps_used": fps,
        "frames_dir": str(work_dir),
    }


def load_training_plan(video_path: str,
                       user_id: str | None = None,
                       workout_date: str | None = None) -> dict:
    """Load the training plan from a local JSON file next to the video.

    Looks for *training_plan*.json or *plan*.json in the same directory.
    Returns found=False if no file exists or the file cannot be parsed.
    """
    video_dir  = Path(video_path).parent
    candidates = (list(video_dir.glob("*training_plan*.json"))
                  + list(video_dir.glob("*plan*.json")))
    if not candidates:
        return {"found": False}
    plan_path = candidates[0]
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["found"]   = True
        plan["_source"] = "file"
        plan["_path"]   = str(plan_path)
        return plan
    except Exception as e:
        return {"found": False, "error": str(e)}


def analyze_frame_batch(
    frames_dir: str,
    video_duration_sec: float,
    training_plan: dict | None = None,
    video_key: str = "",
) -> dict:
    """Two-phase pipeline: optical flow + Phase 1 coarse segmentation + Phase 2 fine recognition.

    Uses the v2 algorithm (src_v2_guize_last) which provides:
      - Optical flow analysis for motion detection
      - Phase 1: stitch grids + coarse interval detection (EXERCISE/REST/TRANSITION)
      - Phase 2: per-EXERCISE fine-grained recognition with entrance frames
    """
    from . import progress as _prog

    work_dir = Path(frames_dir)
    meta_path = work_dir / "frames_meta.json"
    if not meta_path.exists():
        return {"error": f"frames_meta.json not found in {work_dir}. Run extract_frames first.",
                "segments": [], "video_duration_sec": video_duration_sec}

    if video_key:
        _prog.update(video_key, 3, "启动 v2 两阶段识别流水线…")

    output_dir = config.RESULTS_DIR / work_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)

    _v2_run_pipeline(
        work_dir=work_dir,
        prompts_dir=Path(__file__).parent / "prompts",
        overwrite=False,
        output_dir=output_dir,
    )

    segments = _convert_v2_results(output_dir, video_duration_sec)

    if video_key:
        _prog.update(video_key, 3, f"识别出 {len(segments)} 个时间段")

    return {"segments": segments, "video_duration_sec": video_duration_sec}


def _convert_v2_results(output_dir: Path, video_duration_sec: float) -> list[dict]:
    """Convert v2 pipeline output (period_result_adjusted.json + exercise_result.json)
    into the gym_analyzer segment format expected by compute_dashboard."""

    exercise_path = output_dir / "exercise_result.json"
    period_path = output_dir / "period_result_adjusted.json"
    if not period_path.exists():
        period_path = output_dir / "period_result.json"

    segments: list[dict] = []

    # Load period segments
    period_data = {}
    if period_path.exists():
        period_data = json.loads(period_path.read_text(encoding="utf-8"))

    # Load exercise results for detailed info
    exercise_map: dict[str, dict] = {}
    if exercise_path.exists():
        ex_data = json.loads(exercise_path.read_text(encoding="utf-8"))
        for r in ex_data.get("results", []):
            exercise_map[r.get("segmentId", "")] = r

    for seg in period_data.get("segments", []):
        state = seg.get("state", "").upper()
        start_sec = seg.get("start_sec", 0.0)
        end_sec = seg.get("end_sec", 0.0)
        seg_type = "exercise" if state == "EXERCISE" else ("rest" if state == "REST" else "transition")

        out: dict[str, Any] = {
            "start_sec": round(start_sec, 1),
            "end_sec": round(end_sec, 1),
            "type": seg_type,
        }

        if seg_type == "exercise":
            seg_id = seg.get("segmentId", "")
            ex_result = exercise_map.get(seg_id, {}).get("result", {})

            exercise_name = ex_result.get("exercise", "") or ""
            equipment = ex_result.get("equipment", "") or ""

            # Map sets from v2 format
            sets_list = ex_result.get("sets", [])
            sets_count = len(sets_list) if sets_list else 1
            reps_estimate = 0
            if sets_list:
                reps_vals = [s.get("reps", 0) for s in sets_list if isinstance(s, dict)]
                reps_estimate = round(sum(reps_vals) / len(reps_vals)) if reps_vals else 0

            from .db import get_exercise_muscles
            muscles = get_exercise_muscles(exercise_name)

            out.update({
                "exercise_name": exercise_name or equipment,
                "equipment": equipment,
                "exercise_id": ex_result.get("exercise_id", ""),
                "sets_count": sets_count,
                "reps_estimate": reps_estimate,
                "primary_muscles": muscles.get("primary", []),
                "secondary_muscles": muscles.get("secondary", []),
                "confidence": float(ex_result.get("confidence", 0.0) or 0.0),
                "note": seg.get("reason", "")[:120],
            })

        segments.append(out)

    return segments


def compute_dashboard(
    segments_result: dict,
    weight_kg: float = 65.0,
    gender: str = "female",
    age: int = 25,
    date_str: str | None = None,
) -> dict:
    """Convert raw segments into the 4 dashboard API payloads."""
    segments     = segments_result.get("segments", [])
    duration_sec = segments_result.get("video_duration_sec", 0)
    avg_hr       = segments_result.get("avg_hr")
    exercise_segs = [s for s in segments if s.get("type") == "exercise"]
    is_female     = gender.lower() in ("female", "f", "女")
    today         = date_str or date.today().isoformat()

    duration_min = round(duration_sec / 60, 1)

    total_calories = 0.0
    if avg_hr and avg_hr > 0:
        hr = float(avg_hr)
        if is_female:
            kcal_per_min = (-20.4022 + 0.4472 * hr - 0.1263 * weight_kg + 0.0740 * age) / 4.184
        else:
            kcal_per_min = (-55.0969 + 0.6309 * hr + 0.1988 * weight_kg + 0.2017 * age) / 4.184
        total_calories = max(0.0, kcal_per_min) * duration_min
    else:
        gender_factor = 0.9 if is_female else 1.0
        from .db import get_exercise_met_batch
        ex_names = [seg.get("exercise_name", "") for seg in exercise_segs]
        met_map = get_exercise_met_batch(ex_names)
        for seg in exercise_segs:
            dur_min = (seg.get("end_sec", 0) - seg.get("start_sec", 0)) / 60
            name = seg.get("exercise_name", "")
            met = met_map.get(name, 4.0)
            total_calories += met * weight_kg * (dur_min / 60) * gender_factor

    svg_volume: dict[str, float] = defaultdict(float)
    for seg in exercise_segs:
        dur = seg.get("end_sec", 0) - seg.get("start_sec", 0)
        for m in seg.get("primary_muscles", []):
            svg_volume[m] += dur * 1.0
        for m in seg.get("secondary_muscles", []):
            svg_volume[m] += dur * 0.5

    group_volume: dict[str, float] = defaultdict(float)
    for svg_id, vol in svg_volume.items():
        group = config.MUSCLE_GROUP_DISPLAY.get(svg_id)
        if group:
            group_volume[group] = max(group_volume[group], vol)

    max_vol = max(group_volume.values(), default=1)
    muscle_distribution = {g: round(v / max_vol * 100) for g, v in group_volume.items() if v > 0}

    max_svg = max(svg_volume.values(), default=1)
    muscles_api: dict[str, str] = {}
    for svg_id, vol in svg_volume.items():
        ratio = vol / max_svg
        muscles_api[svg_id] = "high" if ratio >= 0.6 else ("medium" if ratio >= 0.3 else "low")

    total_sets = sum(s.get("sets_count", 1) for s in exercise_segs)
    completion_rate = min(100, round(len(exercise_segs) / max(1, len(exercise_segs) + 1) * 100 + 20))

    year, month = int(today[:4]), int(today[5:7])

    daily = {
        "duration_min": duration_min,
        "calories": round(total_calories),
        "avg_hr": None,
        "completion_rate": completion_rate,
        "muscle_distribution": muscle_distribution,
    }
    weekly = {
        "total_sets": total_sets,
        "sets_trend_pct": 0,
        "total_calories": round(total_calories),
        "calories_trend_pct": 0,
        "daily_sets": [0, 0, 0, 0, 0, 0, total_sets],
        "day_labels": [
            f"{(date.today() - timedelta(days=6 - i)).month}/{(date.today() - timedelta(days=6 - i)).day}"
            for i in range(7)
        ],
    }
    calendar = {
        "year": year,
        "month": month,
        "days": {today: "full" if completion_rate >= 80 else "partial"},
    }
    return {
        "date": today,
        "daily": daily,
        "muscles": muscles_api,
        "weekly": weekly,
        "calendar": calendar,
        "raw_segments": segments,
    }


def save_result(date_str: str, dashboard: dict,
                hr_csv_path: str | None = None,
                user_id: str | None = None) -> dict:
    """保存 JSON 备份，同时写入数据库（保证分析结果持久化）。"""
    path = config.RESULTS_DIR / f"{date_str}.json"
    # 确保 dashboard 里的日期与文件名一致
    if dashboard.get("date") != date_str:
        dashboard = dict(dashboard)
        dashboard["date"] = date_str
    path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    # 写库——无论 agent 有没有单独调用 save_to_db，这里都保证落库
    from .db import save_to_db as _save_to_db
    db = _save_to_db(dashboard, user_id=user_id, hr_csv_path=hr_csv_path)

    return {
        "saved":          str(path),
        "date":           date_str,
        "db_status":      db.get("status"),
        "db_session_id":  db.get("session_id"),
        "db_exercises":   db.get("exercises_written"),
        "db_hr_points":   db.get("hr_points"),
        "db_error":       db.get("error"),
    }


def load_results(date_str: str | None = None) -> dict:
    """Load stored results. If date_str is None, load all results."""
    if date_str:
        path = config.RESULTS_DIR / f"{date_str}.json"
        if not path.exists():
            return {"error": f"No result for {date_str}"}
        return json.loads(path.read_text(encoding="utf-8"))

    all_results = {}
    for f in sorted(config.RESULTS_DIR.glob("*.json")):
        try:
            all_results[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return all_results


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════════════════
# Tool schemas (OpenAI function-call format)
# ═══════════════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "extract_frames",
            "description": "Extract frames from a workout video at 1fps. Must be called first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_path": {"type": "string", "description": "Absolute path to the video file"},
                    "fps": {"type": "integer", "description": "Frames per second to extract (default 1)", "default": 1},
                },
                "required": ["video_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_training_plan",
            "description": (
                "Load the training plan from a local JSON file (*training_plan*.json or *plan*.json) "
                "in the same directory as the video. Returns found=false if no file exists. "
                "Call this before analyze_frame_batch to give Gemini the planned exercises as context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_path":   {"type": "string", "description": "Path to the video file"},
                    "user_id":      {"type": "string", "description": "User UUID — used to query the workout_plan table"},
                    "workout_date": {"type": "string", "description": "YYYY-MM-DD workout date; finds the latest plan on or before this date"},
                },
                "required": ["video_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_frame_batch",
            "description": (
                "Analyze extracted frames using the two-phase v2 pipeline: "
                "Phase 1 (optical flow + coarse segmentation) → Phase 2 (per-exercise fine recognition). "
                "Pass frames_dir from extract_frames result and duration_sec."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "frames_dir": {
                        "type": "string",
                        "description": "frames_dir value from extract_frames result",
                    },
                    "video_duration_sec": {
                        "type": "number",
                        "description": "duration_sec value from extract_frames result",
                    },
                    "training_plan": {
                        "type": "object",
                        "description": "Optional plan dict from load_training_plan.",
                    },
                },
                "required": ["frames_dir", "video_duration_sec"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_dashboard",
            "description": "Convert raw segments into the 4 frontend API payloads (daily/muscles/weekly/calendar).",
            "parameters": {
                "type": "object",
                "properties": {
                    "segments_result": {
                        "type": "object",
                        "description": "Result dict from analyze_frame_batch",
                    },
                    "weight_kg": {"type": "number",  "description": "User body weight in kg", "default": 65.0},
                    "gender":    {"type": "string",  "description": "'male' or 'female'", "default": "female"},
                    "age":       {"type": "integer", "description": "User age in years", "default": 25},
                    "date_str":  {"type": "string",  "description": "Workout date YYYY-MM-DD (use the workout_date from agent params)"},
                },
                "required": ["segments_result"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_result",
            "description": "Save dashboard JSON to disk AND write all data to PostgreSQL. Always call this as the final step.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str":     {"type": "string", "description": "Workout date YYYY-MM-DD"},
                    "dashboard":    {"type": "object", "description": "Dashboard dict from compute_dashboard"},
                    "hr_csv_path":  {"type": "string", "description": "Optional HR CSV path (from agent run params)"},
                    "user_id":      {"type": "string", "description": "User UUID (leave blank to use default)"},
                },
                "required": ["date_str", "dashboard"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_results",
            "description": "Load previously saved workout results from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "Specific date YYYY-MM-DD, or omit for all results"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_db",
            "description": (
                "Save the computed dashboard to PostgreSQL (workout_session + exercise_execution tables). "
                "Optionally loads a heart rate CSV and writes it to biometric_stream. "
                "Must be called after compute_dashboard so the dashboard data is in the fitness DB "
                "and visible on the frontend at http://localhost:8000."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dashboard": {
                        "type": "object",
                        "description": "Dashboard dict from compute_dashboard",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "UUID of the user this session belongs to",
                    },
                    "hr_csv_path": {
                        "type": "string",
                        "description": "Optional path to a heart rate CSV file",
                    },
                },
                "required": ["dashboard", "user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_charts",
            "description": (
                "Generate timeline and summary PNG charts from Gemini segments. "
                "Call after compute_dashboard. Saves files to gym_analyzer/results/."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "segments_result": {
                        "type": "object",
                        "description": "Result dict from analyze_frame_batch",
                    },
                    "dashboard": {
                        "type": "object",
                        "description": "Dashboard dict from compute_dashboard",
                    },
                    "date_str": {
                        "type": "string",
                        "description": "Date string YYYY-MM-DD for output filename",
                    },
                },
                "required": ["segments_result", "dashboard"],
            },
        },
    },
]

# Dispatch map
TOOL_REGISTRY: dict[str, Any] = {
    "extract_frames":      extract_frames,
    "load_training_plan":  load_training_plan,
    "analyze_frame_batch": analyze_frame_batch,
    "compute_dashboard":   compute_dashboard,
    "generate_charts":     generate_charts,
    "save_result":         save_result,
    "load_results":        load_results,
    "save_to_db":          save_to_db,
}
