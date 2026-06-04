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

# ═══════════════════════════════════════════════════════════════════════════════
# Tool implementations
# ═══════════════════════════════════════════════════════════════════════════════

def extract_frames(video_path: str, fps: int = config.FPS) -> dict:
    """Extract frames from a video at the given fps, save to gym_analyzer/frames/.

    Returns a COMPACT summary only — frame list is saved to disk, not returned.
    Downstream tools load frames from frames_dir themselves to avoid passing
    large data through the LLM context.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return {"error": f"Video not found: {video_path}"}

    out_dir = config.FRAMES_DIR / video_path.stem
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    cap = cv2.VideoCapture(str(video_path))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_src / src_fps
    step = max(1, round(src_fps / fps))

    index: list[dict] = []   # saved to disk only
    frame_idx = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            ts = frame_idx / src_fps
            h, w = frame.shape[:2]
            scale = min(config.CELL_W / w, config.CELL_H / h)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)),
                                   interpolation=cv2.INTER_AREA)
            out_path = out_dir / f"f{saved_count:05d}_{int(ts):05d}s.jpg"
            cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, config.FRAME_QUALITY])
            index.append({"idx": saved_count, "timestamp": round(ts, 1),
                          "path": str(out_path)})
            saved_count += 1
        frame_idx += 1

    cap.release()

    index_path = out_dir / "_index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")

    return {
        "video": str(video_path),
        "duration_sec": round(duration_sec, 1),
        "total_frames": saved_count,
        "fps_used": fps,
        "frames_dir": str(out_dir),
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
    """全量上下文策略：所有帧合成一张大网格图，一次 Gemini 调用完成划分和识别。

    与旧版（60 帧/批）的区别：
      旧版：分批调用，跨批无上下文，容易误判切换点
      新版：全量一张图，AI 看到完整时间线再分段，切换点识别更准
    """
    from . import progress as _prog

    index_path = Path(frames_dir) / "_index.json"
    if not index_path.exists():
        return {"error": f"Frame index not found: {index_path}",
                "segments": [], "video_duration_sec": video_duration_sec}
    frames = json.loads(index_path.read_text(encoding="utf-8"))

    if not frames:
        return {"segments": [], "video_duration_sec": video_duration_sec}

    n = len(frames)
    fps = config.FPS

    if video_key:
        _prog.update(video_key, 3, f"合成 {n} 帧全量网格图…")

    grid = _make_full_grid(frames)

    if video_key:
        _prog.update(video_key, 3,
            f"提交 {n} 帧（{grid['cols']}×{grid['rows']} 网格）给 Gemini…")

    system_prompt = _build_full_context_prompt(n, fps, video_duration_sec, training_plan)
    intro = (
        f"以下是整段训练视频的全部 {n} 张关键帧（{fps}fps），已合成为一张大网格图。\n"
        f"网格布局：{grid['cols']} 列 × {grid['rows']} 行\n"
        f"每个 cell 左上角绿底白字数字是 frame index（0-based，从左到右、从上到下）。\n"
        f"frame index × {1.0/fps:.1f} = 该帧在视频中的秒数。\n\n"
        "请按系统提示输出严格 JSON，不含 markdown 代码块。"
    )
    content: list[dict] = [
        {"type": "text", "text": intro},
        {"type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{grid['b64']}",
        }},
    ]

    url = f"{config.GATEWAY_URL}/chat/completions"
    payload = {
        "model": config.VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": content},
        ],
        "max_tokens": 8192,
    }
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {config.GATEWAY_KEY}",
                 "Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"]

    segments = _parse_full_context_segs(raw, n, frames, fps)

    if video_key:
        _prog.update(video_key, 3, f"识别出 {len(segments)} 个时间段")

    return {"segments": segments, "video_duration_sec": video_duration_sec}


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
        for seg in exercise_segs:
            dur_min = (seg.get("end_sec", 0) - seg.get("start_sec", 0)) / 60
            name = seg.get("exercise_name", "")
            met  = next((v for k, v in config.EXERCISE_MET.items() if k in name),
                        config.EXERCISE_MET["default"])
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
# Internal helpers — full-context grid + prompt
# ═══════════════════════════════════════════════════════════════════════════════

# 器械 → 动作候选（用于 prompt，与 video_analysis EQUIPMENT_LIBRARY 对齐）
_EQUIPMENT: dict[str, list[str]] = {
    "跑步":     ["跑步", "快走"],
    "椭圆机":   ["椭圆机"],
    "动感单车": ["动感单车"],
    "划船机":   ["划船机"],
    "杠铃":     ["平板卧推", "上斜卧推", "下斜卧推", "深蹲", "硬拉", "划船", "推举", "弯举"],
    "史密斯架": ["史密斯卧推", "史密斯深蹲", "史密斯推举"],
    "哑铃":     ["哑铃卧推", "哑铃飞鸟", "哑铃弯举", "哑铃侧平举", "哑铃划船", "哑铃推举"],
    "龙门架":   ["绳索夹胸", "绳索下拉", "绳索划船", "绳索三头下压", "绳索弯举"],
    "高位下拉": ["高位下拉"],
    "坐姿划船": ["坐姿划船"],
    "蝴蝶机":   ["夹胸", "反向夹胸"],
    "腿举机":   ["腿举"],
    "推肩机":   ["推肩"],
    "引体向上": ["引体向上", "悬垂举腿"],
    "自重训练": ["俯卧撑", "平板支撑", "卷腹", "箭步蹲"],
}


def _make_full_grid(frames: list[dict]) -> dict:
    """合成全量网格大图，cell 固定 220×123，canvas 按需放大。

    返回 {"b64": str, "cols": int, "rows": int}。
    """
    cell_w, cell_h = config.CELL_W, config.CELL_H
    n = len(frames)
    ratio = (16 / 9) * (16 / 9) / 2  # ≈ 1.58
    cols = max(1, round(math.sqrt(n * ratio)))
    rows = math.ceil(n / cols)

    canvas = np.full((rows * cell_h, cols * cell_w, 3), 230, dtype=np.uint8)
    for i, fm in enumerate(frames):
        img = cv2.imread(fm["path"])
        if img is None:
            continue
        h, w = img.shape[:2]
        scale = min(cell_w / w, cell_h / h)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        r, c = divmod(i, cols)
        y0, x0 = r * cell_h, c * cell_w
        canvas[y0:y0 + img.shape[0], x0:x0 + img.shape[1]] = img
        # 绿底白字 frame index
        label = str(i)
        lbl_w = max(22, 8 * len(label) + 6)
        cv2.rectangle(canvas, (x0, y0), (x0 + lbl_w, y0 + 14), (40, 180, 40), -1)
        cv2.putText(canvas, label, (x0 + 3, y0 + 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

    _, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return {
        "b64": base64.b64encode(buf.tobytes()).decode(),
        "cols": cols,
        "rows": rows,
    }


def _build_full_context_prompt(
    n_frames: int,
    fps: int,
    duration_s: float,
    training_plan: dict | None = None,
) -> str:
    interval_s = 1.0 / fps
    eq_names = "、".join(f'"{k}"' for k in _EQUIPMENT)
    n_equipment = len(_EQUIPMENT)
    movements_block = "\n".join(
        f"  - {eq}: {' / '.join(mvs)}" for eq, mvs in _EQUIPMENT.items() if mvs
    )
    long_rest_frames = max(5, int(round(60.0 / interval_s)))

    # 格式化训练计划
    plan_text = "（本次训练未提供训练计划）"
    n_planned = 0
    if training_plan and training_plan.get("found"):
        lines: list[str] = []
        name = training_plan.get("name") or training_plan.get("planName") or "未命名"
        lines.append(f"计划名称：{name}")
        phases = training_plan.get("phases", [])
        if phases:
            for phase in phases:
                phase_name = phase.get("phaseName", "")
                for ex in phase.get("exercises", []):
                    n_planned += 1
                    ex_name = ex.get("exerciseName") or ex.get("movementName") or "未命名"
                    eq = ex.get("equipmentId") or ex.get("equipmentName") or ""
                    tail = f"（{eq}）" if eq else ""
                    lines.append(f"  动作 {n_planned}. {ex_name}{tail}")
        else:
            for ex in training_plan.get("plannedExercises", []):
                n_planned += 1
                ex_name = ex.get("movementName") or ex.get("exerciseName") or "未命名"
                lines.append(f"  动作 {n_planned}. {ex_name}")
        plan_text = "\n".join(lines)

    min_expected = max(3, n_planned + 2) if n_planned else 3
    max_expected = max(8, n_planned * 4 + 2) if n_planned else 20

    return f"""你是一名专业的健身视频时间线标注员，同时负责估算每个动作的组数和次数。你的任务是分析一组按时间顺序排列的关键帧截图，将它们划分成多个连续的时间段，并对每个运动段估算组数（sets_count）和单组次数（reps_estimate）。

## 输入说明

你收到的是一段健身房训练视频的 {n_frames} 张关键帧，按时间顺序排列；每张图左上角绿色数字就是它的 frame index（0-based）。
相邻两帧间隔 {interval_s} 秒。视频总时长约 {duration_s:.1f} 秒。
视频为训练者**第一人称视角**（可穿戴相机），画面中**通常看不到训练者本人**，主要看到器械、健身房环境、显示屏等。

## ⚠️ 核心要求：根据训练计划对照视频，识别每个动作段

你会同时收到一份**本次训练计划**（见下方）。计划告诉你用户今天打算做哪些动作、用什么器械、做几组。
你的任务是在关键帧中找到每个计划动作对应的视频片段，并识别出动作之间的休息和移动。

### 本次训练计划

{plan_text}

### 你应该怎么用这份计划

- 计划是**参考**，不是硬约束。用户可能跳过某个动作、调换顺序、或临时加了计划外的动作。
- 计划告诉你「大概会出现哪些器械和动作」→ 帮你缩小识别范围，而不是直接抄答案。
- 你必须**用画面证据判断**，不能因为计划里写了某个动作就把不相关的帧也标成它。
- 如果视频中出现了计划里没有的器械/动作 → 正常标注，在 note 中注明「计划外」。
- 如果计划里的某个动作在视频中完全找不到 → 不要硬凑，该动作可能被跳过了。

### 期望的分段结构

根据计划，本次训练有 {n_planned} 个动作。加上每个动作之间的休息和移动，你的分段结果**大约**在 {min_expected} 到 {max_expected} 段之间。
这只是参考范围，实际多一些少一些都正常——关键是你的分段要有画面证据支撑。

## 你的工作流程（必须严格按此执行）

### 第一步：逐帧扫描，写出每一帧的状态标签

从第 0 帧开始，逐帧检查，为每一帧写出一个临时标签。你必须关注：
- 画面中主体是什么？（器械？走廊？地面？天花板？手机屏幕？水杯？）
- 画面是否在运动中？（模糊程度、前后帧的场景变化）
- 和前一帧相比，场景是否发生了变化？（器械换了？位置变了？视角突变？）

标签只有三种：
- **E**（exercise）：画面中可见用户**正在操作**某台器械（不是仅仅路过看到器械）
- **T**（transition）：画面在移动中——场景在变化、在走动、在换位置
- **R**（rest）：画面静止或接近静止——用户在坐着/站着/看手机/喝水/等待

### 第二步：重点检查——找出所有「状态切换点」

回顾你第一步写的标签序列，找出所有相邻帧标签不同的位置——这些就是切换点。

特别注意以下容易遗漏的切换信号：
- **器械变了**：前几帧是一台器械的特写，后几帧变成另一台器械 → 中间一定经过了 transition
- **视角突变**：前一帧看着器械，下一帧突然看到走廊/天花板/地面 → 状态切换了
- **画面从动到静**：前几帧画面有运动模糊，后几帧变清晰静止 → 从 exercise 进入 rest
- **画面从静到动**：反过来 → 从 rest 进入 exercise 或 transition

### 第三步：合并连续相同标签，生成分段

将连续的相同标签合并为一个段。合并规则：
- 连续的 E 帧且器械相同 → 合并为一个 exercise 段
- 连续的 E 帧但器械不同 → 必须拆成不同的 exercise 段（中间插入 transition）
- 连续的 T 帧 → 合并为一个 transition 段
- 连续的 R 帧 → 合并为一个 rest 段

**去噪规则**：如果某个段只有 1 帧（仅 {interval_s} 秒），且前后段类型相同 → 将这 1 帧归入前一段（视为噪声）。

### 第四步：对每个 exercise 段识别器械、动作，并估算组数和次数

**sets_count（组数）**：数一数该 exercise 段内出现了几次"动到停"的周期，每个周期对应一组。
- 若该段内有明显的"运动 → 短暂停止 → 运动"节奏重复 N 次 → sets_count = N
- 若看不清节奏但段持续时间 > 60 秒 → sets_count = round(duration / 40)（每组约 40 秒）
- 若段持续时间 ≤ 60 秒 → sets_count = 1

**reps_estimate（单组次数）**：从段内单次运动幅度 / 画面节奏估算单组次数，典型范围 6-15 次。
- 看不清次数时可根据动作类型填典型值：卧推/深蹲 = 8，弯举 = 12，有氧 = 0

**对每个 exercise 段识别器械和动作**

**equipmentName** 从以下 {n_equipment} 个标签中选一个：
{eq_names}

**movementName** 从对应器械的候选动作中选一个：
{movements_block}

## 器械判断规则

### 🔴 核心原则：看到器械 ≠ 正在用器械

第一人称视角下，用户走过任何器械都会拍到它。你必须看到**操作证据**才能标记为 exercise：

| 器械 | 必须看到的操作证据 |
|------|------------------|
| 跑步 | 履带在转动 + 控制面板亮着 + 画面有节奏性上下晃动 |
| 椭圆机 | 踏板在做椭圆运动 + 长动臂在前后摆 |
| 动感单车 | 腿部蹬踏动作 + 飞轮在转 |
| 划船机 | 滑座在前后滑动 + 拉绳/拉柄被拉动 |
| 杠铃 | 杠铃杆在移动（上下推/拉）或在用户身上（肩/胸前） |
| 史密斯架 | 双立柱内的杠铃在上下移动 + 卡扣可见 |
| 哑铃 | 用户手持哑铃在做动作（非仅放在架上） |
| 龙门架 | 绳索被拉紧 + 配重在升降（**双立柱**结构） |
| 高位下拉 | 用户坐在座椅上 + 从头顶拉下拉杆（**单立柱** + 大腿挡板） |
| 坐姿划船 | 坐在座垫上 + 横向拉杆被拉动 |
| 蝴蝶机 | 坐着 + 两侧扇形挡板在合拢/张开 |
| 腿举机 | 45°斜板 + 脚蹬踏板在推动 |
| 推肩机 | 坐着 + 双手握把向上推 |
| 自重训练 | 镜头低角度看地面/墙面 + 无器械被操作 |
| 引体向上 | 用户身体悬挂 + 脚离地 + 向上拉 |

### 🔴 易混淆场景

- **引体向上 vs 高位下拉**：脚离地悬挂 → 引体向上；坐在椅子上 → 高位下拉
- **龙门架 vs 高位下拉**：龙门架是**双立柱**独立结构；高位下拉是**单立柱** + 座椅 + 大腿挡板
- **路过器械 vs 使用器械**：画面快速扫过器械（1-2帧）→ transition；画面持续停留在同一器械（3帧以上）+ 有操作动作 → exercise
- **看手机/喝水**：即使坐在器械上，只要没在做动作 → rest（不是 exercise）

### 动作识别要点

- 杠铃：躺着向上推 → 卧推；站着从地面拉起 → 硬拉；杠铃在肩上蹲下 → 深蹲；屈臂向上 → 弯举
- 哑铃：双臂水平展开合拢 → 飞鸟；屈肘上举 → 弯举；过头推 → 推举
- 龙门架：高位双手向中合 → 绳索夹胸；屈肘下压 → 三头下压；低位水平拉 → 绳索划船
- 自重：躺地上抬头脚 → 卷腹；撑地推身体 → 俯卧撑；身体平直撑住不动 → 平板支撑

如果看不清具体动作，movementName 直接填 equipmentName（兜底）。

## 输出格式

严格输出 JSON，不要输出任何其他文字：

{{
  "frame_labels": "EEEEERRRTTTEEEEEERRREEEE...",
  "segments": [
    {{
      "startFrameIndex": 0,
      "endFrameIndex": 5,
      "status": "exercise",
      "equipmentName": "杠铃",
      "movementName": "平板卧推",
      "confidence": 0.85,
      "sets_count": 3,
      "reps_estimate": 8,
      "plannedOrder": 1,
      "note": "可见杠铃杆在上下推动，3次运动-停止节奏 → 3组，每组约8次"
    }},
    {{
      "startFrameIndex": 6,
      "endFrameIndex": 8,
      "status": "rest",
      "note": "画面静止，坐在卧推凳上调息"
    }},
    {{
      "startFrameIndex": 9,
      "endFrameIndex": 11,
      "status": "transition",
      "note": "画面在移动，从卧推区走向龙门架"
    }}
  ]
}}

### 输出规则

1. **frame_labels**：长度恰好 {n_frames} 个字符，每个字符是 E / T / R
2. **segments** 按时间顺序排列，首段 startFrameIndex=0，末段 endFrameIndex={n_frames - 1}
3. 相邻段连续：segments[i+1].startFrameIndex == segments[i].endFrameIndex + 1
4. exercise 段必须填 equipmentName / movementName / confidence / sets_count / reps_estimate / plannedOrder
5. plannedOrder：对应训练计划第 N 个动作则填 N，计划外填 null
6. transition / rest 段只填 status 和 note
7. 每个段的 note 用一句话描述你看到了什么（exercise 段必须说明组数估算依据）

### 自检清单（输出前必须检查）

- [ ] frame_labels 长度是否等于 {n_frames}？
- [ ] segments 是否连续覆盖 0 到 {n_frames - 1}？
- [ ] 对照训练计划，每个计划中的动作是否都尝试在视频中找到了对应段？
- [ ] 每个 exercise 段的 note 里是否描述了你看到的操作证据？
- [ ] 是否有 exercise 段超过 {long_rest_frames * 2} 帧？如果有，检查中间是否包含了组间休息
- [ ] 两个不同器械的 exercise 段之间，是否有 transition 或 rest 段隔开？
"""


def _parse_full_context_segs(
    raw: str,
    n_frames: int,
    frames: list[dict],
    fps: int,
) -> list[dict]:
    """AI 输出（frame_classifier_full_context 格式）→ gym_analyzer segments 格式。

    转换：startFrameIndex/endFrameIndex → start_sec/end_sec
          status → type
          equipmentName + movementName → exercise_name
          movementName → primary_muscles/secondary_muscles（从 config.EXERCISE_MUSCLES 查）
    """
    s = raw.strip()
    # 剥 markdown 代码围栏
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    # 定位 JSON 对象
    if not s.startswith("{"):
        i = s.find("{")
        j = s.rfind("}")
        if i >= 0 and j > i:
            s = s[i:j + 1]

    segs_raw: list[dict] = []
    try:
        obj = json.loads(s, strict=False)
        if isinstance(obj, dict):
            segs_raw = obj.get("segments", [])
    except (json.JSONDecodeError, ValueError):
        return []

    if not segs_raw:
        return []

    interval_s = 1.0 / fps
    result: list[dict] = []

    for seg in segs_raw:
        try:
            start_fi = int(seg.get("startFrameIndex", 0))
            end_fi   = int(seg.get("endFrameIndex", start_fi))
        except (TypeError, ValueError):
            continue

        start_fi = max(0, start_fi)
        end_fi   = min(n_frames - 1, max(start_fi, end_fi))

        # 用 frames 里的实际 timestamp（若可用）
        ts_start = frames[start_fi]["timestamp"] if start_fi < len(frames) else start_fi * interval_s
        ts_end   = (frames[end_fi]["timestamp"] + interval_s) if end_fi < len(frames) else (end_fi + 1) * interval_s

        status = seg.get("status", "rest")
        seg_type = "exercise" if status == "exercise" else ("rest" if status == "rest" else "transition")

        out: dict[str, Any] = {
            "start_sec": round(ts_start, 1),
            "end_sec":   round(ts_end, 1),
            "type":      seg_type,
        }

        if seg_type == "exercise":
            mv_name = seg.get("movementName") or ""
            eq_name = seg.get("equipmentName") or ""
            exercise_name = mv_name or eq_name
            muscles = config.EXERCISE_MUSCLES.get(exercise_name, {})
            # 优先使用 AI 估算的组数；无法解析时默认 1
            raw_sets = seg.get("sets_count")
            try:
                sets_count = max(1, int(raw_sets)) if raw_sets is not None else 1
            except (TypeError, ValueError):
                sets_count = 1
            raw_reps = seg.get("reps_estimate")
            try:
                reps_estimate = max(0, int(raw_reps)) if raw_reps is not None else 0
            except (TypeError, ValueError):
                reps_estimate = 0
            out.update({
                "exercise_name":    exercise_name,
                "sets_count":       sets_count,
                "reps_estimate":    reps_estimate,
                "primary_muscles":  muscles.get("primary", []),
                "secondary_muscles": muscles.get("secondary", []),
                "confidence":       float(seg.get("confidence", 0.0) or 0.0),
                "note":             str(seg.get("note", ""))[:120],
            })

        result.append(out)

    return result


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
                "Analyze ALL extracted frames in one shot using Gemini full-context vision. "
                "Synthesizes all frames into a single large grid image, enabling the model to "
                "see the complete workout timeline before segmenting. "
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
