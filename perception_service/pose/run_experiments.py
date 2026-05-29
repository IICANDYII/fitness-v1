"""
run_experiments.py
------------------
并行运行 3 采样率 × 3 模型 = 9 组实验，评估不同条件下健身视频的识别效果。

实验矩阵
  采样率 : 2fps (step=1, 582帧) / 1fps (step=2, 291帧) / 0.33fps (step=6, 97帧)
  模型   : flash  → gemini-2.5-flash-preview-05-20
            lite   → gemini-2.0-flash-lite
            g3flash → gemini-3-flash-preview

流程（每组实验）
  Step 1  period_recognize — 视频阶段切分 (exercise / transition / rest)
  Step 2  pose_recognize   — exercise 段精细识别 + 计划匹配

输出目录
  perception_service/pose/output/
    30K_2fps_flash/
      period_result.json
      pose_result.json
      run.log
    30K_2fps_lite/
      ...
    ... (共 9 个子目录)
    experiment_summary.json
"""

import base64
import io
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

# ── gemini_client 常量（模型 ID）────────────────────────────────────────
_POSE_DIR = Path(__file__).parent
sys.path.insert(0, str(_POSE_DIR))
from gemini_client import MODEL_FLASH, MODEL_FLASH_LITE  # noqa: E402

# ── 环境变量（.env 在项目根 D:\WorkPath\fitness\.env）──────────────────
load_dotenv(_POSE_DIR.parent.parent / ".env")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://nextrouter.cc/v1")
ZCHAT_API_KEY   = os.getenv("ZCHAT_API_KEY")
ZCHAT_BASE_URL  = os.getenv("ZCHAT_BASE_URL", "https://api.zchat.tech/v1")

# ══════════════════════════════════════════════════════════════════════════
# 实验矩阵配置
# ══════════════════════════════════════════════════════════════════════════

FRAMES_DIR  = Path(r"D:\WorkPath\fitness\video\frames\短视频")
OUTPUT_BASE = Path(r"D:\WorkPath\fitness\perception_service\pose\output")

ORIG_INTERVAL = 0.5   # 原始帧间隔（秒），源视频以 2fps 抽帧

FPS_CONFIGS = [
    {"label": "2fps",    "step": 1, "interval": 0.5},   # 582 帧
    {"label": "1fps",    "step": 2, "interval": 1.0},   # 291 帧
    {"label": "0.33fps", "step": 6, "interval": 3.0},   #  97 帧
]

MODEL_CONFIGS = [
    # nextrouter.cc  ──  Gemini 系列
    {"name": "flash",   "model_id": MODEL_FLASH,
     "base_url": GEMINI_BASE_URL, "api_key_var": "GEMINI_API_KEY"},
    {"name": "lite",    "model_id": MODEL_FLASH_LITE,
     "base_url": GEMINI_BASE_URL, "api_key_var": "GEMINI_API_KEY"},
    {"name": "g3flash", "model_id": "gemini-3-flash-preview",
     "base_url": GEMINI_BASE_URL, "api_key_var": "GEMINI_API_KEY"},
    # zchat.tech  ──  Claude Sonnet 4.5 multimodal
    {"name": "claude",  "model_id": "claude-sonnet-4-5",
     "base_url": ZCHAT_BASE_URL,  "api_key_var": "ZCHAT_API_KEY"},
]

# True → 跳过 period_result.json 中已有有效 segments 的实验（重跑时避免重复调用）
SKIP_EXISTING = True

# pose 段内额外降采样（原始帧 → 取 1/N）
POSE_SAMPLE_STEP = 2

# ══════════════════════════════════════════════════════════════════════════
# 训练计划（注入 pose 识别 prompt）
# ══════════════════════════════════════════════════════════════════════════

TRAINING_PLAN = {
    "planId": "plan_demo_001",
    "userId": "user_test_001",
    "date":   "2026-05-27",
    "name":   "全身基础训练",
    "phases": [
        {
            "phaseName": "warmup",
            "order": 1,
            "exercises": [
                {"order": 1, "equipmentId": "equip_treadmill_01",    "exerciseName": "跑步机慢跑"},
            ],
        },
        {
            "phaseName": "strength",
            "order": 2,
            "exercises": [
                {"order": 2, "equipmentId": "equip_smith_machine_01","exerciseName": "史密斯机深蹲"},
            ],
        },
        {
            "phaseName": "core",
            "order": 3,
            "exercises": [
                {"order": 3, "equipmentId": "equip_pull_up_bar_01",  "exerciseName": "悬垂举腿"},
            ],
        },
    ],
}

_PLAN_STR = json.dumps(TRAINING_PLAN, ensure_ascii=False, indent=2)

# ══════════════════════════════════════════════════════════════════════════
# System prompts
# ══════════════════════════════════════════════════════════════════════════

PERIOD_SYSTEM = """\
你是一个专业的第一人称健身视频分析 AI。

你将收到：
- 一张由多个视频关键帧按时间顺序拼接而成的网格图
- 读取顺序：从左到右、从上到下，即第 1 帧在左上角

你的任务：
将视频切分为 exercise / transition / rest 三类时间段。
不需要识别具体动作名称或器材，只需判断用户当前处于哪个阶段。

时间计算：
- 第 N 帧（从 1 开始）: startTime = (N-1) × frame_interval
- endTime = endFrame × frame_interval
- duration = endTime - startTime

阶段定义：
exercise   — 重复性动作，固定在器材附近，规律视角节奏变化
transition — 行走、大范围视角变化、接近/离开器材、调整设备参数
rest       — 长时间静止、坐下、玩手机、喝水

第一人称视频特点：
- 存在头部抖动、转头、手部遮挡、短暂模糊
- 重点看整体行为模式，不要因单帧异常误判阶段切换

输出规范（严格遵守）：
- 直接输出 JSON 数组，禁止 Markdown 包裹（```）、注释、解释性文字
- 每个元素必须含字段：status（值为 exercise / transition / rest）、startTime、endTime、duration
- 禁止使用 "phase" 等其他字段名代替 "status"

输出示例：
[
  {"status": "transition", "startTime": 0.0,  "endTime": 60.0,  "duration": 60.0},
  {"status": "exercise",   "startTime": 60.0, "endTime": 150.0, "duration": 90.0},
  {"status": "rest",       "startTime": 150.0,"endTime": 180.0, "duration": 30.0}
]\
"""

POSE_SYSTEM = f"""\
你是一个专业的第一人称健身动作识别与评估 AI。

【用户当日训练计划】（前置信息，所有动作识别与匹配须参照此计划）
{_PLAN_STR}

你将收到：
- 某一段 exercise 时间段的关键帧网格图（单张图片）
- 本段的起止时间与总时长

任务：
1. 识别使用器材与动作名称
2. 估算本段组数与每组次数
3. 将识别结果与上方训练计划匹配，说明偏差

置信度 0~1：0.9+ 非常确定；0.7+ 较确定；< 0.5 不可靠则填 unknown

计划匹配状态：
matched   — 器材 + 动作与计划完全吻合
partial   — 器材一致但动作不同（需说明差异）
unplanned — 计划中没有该动作
unknown   — 无法判断器材

输出：严格输出 JSON 对象，不允许 Markdown 包裹、注释、解释性文字。\
"""

# ══════════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════════

def _log(exp_id: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][{exp_id}] {msg}", flush=True)


def parse_frames(frames_dir: Path) -> list[dict]:
    """扫描帧目录，按帧序号排序返回帧信息列表。"""
    pat = re.compile(r"state(\d+)_[\d_-]+\.jpg")
    frames = []
    for f in frames_dir.iterdir():
        m = pat.match(f.name)
        if m:
            frames.append({"index": int(m.group(1)), "path": f})
    return sorted(frames, key=lambda x: x["index"])


def _grid_cols(n: int) -> int:
    """根据帧数自适应确定网格列数，保持宽高比接近 4:3。"""
    if n <= 100:
        return 10
    if n <= 300:
        return 15
    return 20


MAX_GRID_BYTES = 12 * 1024 * 1024   # 12 MB → base64 后约 16 MB，在 API 限额内



def build_grid(frames: list[dict]) -> tuple[bytes, int, int]:
    """
    将帧列表拼成网格图，子图保持原始像素尺寸（无缩放）。
    自动降低 JPEG 质量直到文件 ≤ MAX_GRID_BYTES。
    返回 (jpeg_bytes, cols, rows)。
    """
    if not frames:
        raise ValueError("frames 为空")

    n    = len(frames)
    cols = _grid_cols(n)

    # 初始质量：帧数越多起始越低
    if n <= 100:
        quality = 88
    elif n <= 200:
        quality = 82
    elif n <= 400:
        quality = 74
    else:
        quality = 65

    # 取第一帧确定单帧尺寸
    probe = Image.open(frames[0]["path"])
    fw, fh = probe.size
    probe.close()

    rows = math.ceil(n / cols)
    canvas = Image.new("RGB", (cols * fw, rows * fh), color=(30, 30, 30))
    for i, frame in enumerate(frames):
        img = Image.open(frame["path"])
        canvas.paste(img, ((i % cols) * fw, (i // cols) * fh))
        img.close()

    # 自适应质量：超出大小限制时逐步降低
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=quality)
    while len(buf.getvalue()) > MAX_GRID_BYTES and quality > 40:
        quality -= 8
        buf = io.BytesIO()
        canvas.save(buf, format="JPEG", quality=quality)

    jpeg = buf.getvalue()
    return jpeg, cols, rows


def to_data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


def call_llm(system: str, user_parts: list[dict], model_id: str, exp_id: str,
             base_url: str | None = None, api_key: str | None = None) -> str:
    """OpenAI-compatible 接口调用，支持 per-model base_url / api_key，含重试。"""
    _base = base_url or GEMINI_BASE_URL
    _key  = api_key  or GEMINI_API_KEY
    url   = f"{_base}/chat/completions"
    payload = {
        "model":       model_id,
        "messages":    [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_parts},
        ],
        "temperature": 0.1,
        "max_tokens":  8192,
    }
    headers = {
        "Authorization": f"Bearer {_key}",
        "Content-Type":  "application/json",
    }
    for attempt in range(1, 5):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=600)
        except requests.exceptions.RequestException as exc:
            if attempt < 4:
                wait = 30 * attempt
                _log(exp_id, f"  网络错误: {exc}，{wait}s 后重试 ({attempt}/3)")
                time.sleep(wait)
                continue
            raise
        if resp.status_code == 429:
            wait = 60 * attempt
            _log(exp_id, f"  [429] 限流，{wait}s 后重试 ({attempt}/3)")
            time.sleep(wait)
            continue
        if not resp.ok:
            _log(exp_id, f"  [HTTP {resp.status_code}] {resp.text[:200]}")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    raise RuntimeError(f"[{exp_id}] 超过最大重试次数")


def parse_json(text: str):
    """去除 Markdown 包裹后解析 JSON。"""
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def is_exercise(seg: dict) -> bool:
    """兼容模型返回 status / phase / event / state / type 等不同字段名。"""
    return any(seg.get(k) == "exercise" for k in ("status", "phase", "event", "state", "type"))


def save_json(data: dict | list, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def compute_plan_completion(plan: dict, pose_items: list[dict]) -> dict:
    """
    将 Step 2 所有 exercise 段的识别结果与训练计划做完成度比对。
    返回结构化的计划完成报告。
    """
    # 展开计划中所有动作（保留顺序）
    plan_exercises: list[dict] = []
    for phase in plan.get("phases", []):
        for ex in phase.get("exercises", []):
            plan_exercises.append({
                "phase":        phase.get("phaseName"),
                "order":        ex.get("order"),
                "exerciseName": ex["exerciseName"],
                "equipmentId":  ex.get("equipmentId"),
            })

    matched_names: set[str] = set()
    buckets: dict[str, list] = {
        "matched":   [],
        "partial":   [],
        "unplanned": [],
        "unknown":   [],
    }

    for item in pose_items:
        pd     = item.get("pose_data", {})
        if "error" in pd:
            continue
        mv     = pd.get("movementName") or pd.get("exercise") or "未知"
        pm     = pd.get("planMatch", {})
        status = pm.get("status", "unknown")

        entry = {
            "segmentId":    item["segmentId"],
            "movementName": mv,
            "duration_sec": round(item["duration"], 1),
            "confidence":   pd.get("confidence"),
        }

        if status in ("matched", "partial"):
            matched_ex = pm.get("matchedPlanExercise") or {}
            if isinstance(matched_ex, dict):
                matched_names.add(matched_ex.get("exerciseName", ""))
            entry["matchedPlanExercise"] = matched_ex
        if status == "partial":
            entry["deviation"] = pm.get("deviation")
        if status == "unplanned":
            entry["note"] = pm.get("note")

        buckets.get(status, buckets["unknown"]).append(entry)

    missed = [ex for ex in plan_exercises if ex["exerciseName"] not in matched_names]
    n_matched = len(buckets["matched"])
    n_total   = len(plan_exercises)
    rate      = round(n_matched / n_total, 2) if n_total else 0.0
    total_ex_time = round(sum(i["duration"] for i in pose_items), 1)

    return {
        "completionRate":   rate,
        "summary": (
            f"计划共 {n_total} 项，完全匹配 {n_matched} 项（{rate*100:.0f}%）；"
            f"部分匹配 {len(buckets['partial'])} 项，"
            f"计划外 {len(buckets['unplanned'])} 项，"
            f"未完成 {len(missed)} 项"
        ),
        "matched":          buckets["matched"],
        "partial":          buckets["partial"],
        "unplanned":        buckets["unplanned"],
        "missed":           missed,
        "totalExerciseSec": total_ex_time,
    }


# ══════════════════════════════════════════════════════════════════════════
# 单次实验主体
# ══════════════════════════════════════════════════════════════════════════

def run_one(all_frames: list[dict], fps_cfg: dict, model_cfg: dict) -> dict:
    """执行一组 (fps, model) 实验，返回汇总 dict。"""

    fps_label  = fps_cfg["label"]
    step       = fps_cfg["step"]
    eff_ivl    = fps_cfg["interval"]
    model_id   = model_cfg["model_id"]
    model_name = model_cfg["name"]
    exp_id     = f"30K_{fps_label}_{model_name}"
    # per-model API 路由
    _base_url  = model_cfg.get("base_url", GEMINI_BASE_URL)
    _api_key   = os.getenv(model_cfg.get("api_key_var", "GEMINI_API_KEY")) or GEMINI_API_KEY

    out_dir    = OUTPUT_BASE / exp_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 跳过已成功的实验（period 有段 AND pose 有 > 0 条结果才算完成）──
    if SKIP_EXISTING:
        period_path = out_dir / "period_result.json"
        pose_path   = out_dir / "pose_result.json"
        if period_path.exists() and pose_path.exists():
            try:
                with open(period_path, encoding="utf-8") as _f:
                    _prev_per = json.load(_f)
                with open(pose_path, encoding="utf-8") as _f:
                    _prev_pos = json.load(_f)
                n_segs = len(_prev_per.get("segments", []))
                n_pose = len(_prev_pos.get("results", []))
                if n_segs > 0 and n_pose > 0:
                    _log(exp_id, f"跳过（period={n_segs}段，pose={n_pose}条，已完成）")
                    log_path = out_dir / "run.log"
                    if log_path.exists():
                        with open(log_path, encoding="utf-8") as _f:
                            return json.load(_f)
                    return {"exp_id": exp_id, "status": "skipped"}
                else:
                    _log(exp_id, f"重跑（period={n_segs}段，pose={n_pose}条，不完整）")
            except Exception:
                pass  # 解析失败则重跑

    start_ts   = datetime.now()
    errors: list[str] = []

    _log(exp_id, f"开始 | model={model_id} step={step} eff_interval={eff_ivl}s")

    # ── Step 1: Period Recognition ───────────────────────────────────────
    sampled = all_frames[::step]
    _log(exp_id, f"Step1 | 采样帧 {len(sampled)} 张")

    jpeg, g_cols, g_rows = build_grid(sampled)
    _log(exp_id, f"Step1 | 网格 {g_cols}×{g_rows}，{len(jpeg)//1024} KB")

    period_user = [
        {
            "type": "text",
            "text": (
                f"视频关键帧网格图：\n"
                f"- 列数：{g_cols}，行数：{g_rows}\n"
                f"- 有效帧数：{len(sampled)} 帧，帧间隔：{eff_ivl}s\n"
                f"- 读取顺序：从左到右、从上到下\n\n"
                "请将视频切分为 exercise / transition / rest 时间段，严格输出 JSON 数组。"
            ),
        },
        {"type": "image_url", "image_url": {"url": to_data_url(jpeg)}},
    ]

    segments: list[dict] = []
    try:
        raw = call_llm(PERIOD_SYSTEM, period_user, model_id, exp_id,
                       base_url=_base_url, api_key=_api_key)
        _log(exp_id, f"Step1 | 响应 {len(raw)} 字符")
        parsed = parse_json(raw)
        segments = parsed if isinstance(parsed, list) else parsed.get("segments", [])
    except Exception as exc:
        _log(exp_id, f"Step1 | [ERROR] {exc}")
        errors.append(f"period: {exc}")

    period_result = {
        "exp_id":          exp_id,
        "model":           model_id,
        "fps":             fps_label,
        "sample_step":     step,
        "total_frames":    len(all_frames),
        "sampled_frames":  len(sampled),
        "effective_interval_sec": eff_ivl,
        "grid":            {"cols": g_cols, "rows": g_rows},
        "created_at":      start_ts.isoformat(),
        "segments":        segments,
    }
    save_json(period_result, out_dir / "period_result.json")
    _log(exp_id, f"Step1 | 保存 period_result.json ({len(segments)} 段)")

    # ── Step 2: Pose Recognition ─────────────────────────────────────────
    exercise_segs = [s for s in segments if is_exercise(s)]
    _log(exp_id, f"Step2 | {len(exercise_segs)} 个 exercise 段")

    pose_items: list[dict] = []

    for idx, seg in enumerate(exercise_segs, 1):
        seg_id  = seg.get("segmentId") or f"exercise_{idx:03d}"
        t_start = float(seg.get("startTime", 0.0))
        t_end   = float(seg.get("endTime",   0.0))
        fi_s    = seg.get("startFrame")
        fi_e    = seg.get("endFrame")

        _log(exp_id, f"Step2 | [{idx}/{len(exercise_segs)}] {seg_id} {t_start:.1f}~{t_end:.1f}s")

        # 取该段帧（优先用 startFrame/endFrame 精确定位）
        base_idx = all_frames[0]["index"]
        if fi_s is not None and fi_e is not None:
            seg_frames = [f for f in all_frames if fi_s <= f["index"] <= fi_e]
        else:
            seg_frames = [
                f for f in all_frames
                if t_start - 0.1 <= (f["index"] - base_idx) * ORIG_INTERVAL <= t_end + 0.1
            ]

        seg_sampled = seg_frames[::POSE_SAMPLE_STEP] if seg_frames else []
        _log(exp_id, f"       段内帧 {len(seg_frames)} → 采样 {len(seg_sampled)}")

        if not seg_sampled:
            _log(exp_id, "       [警告] 无匹配帧，跳过")
            errors.append(f"pose {seg_id}: 无匹配帧")
            continue

        p_cols = max(1, round(math.sqrt(len(seg_sampled))))
        try:
            jpeg_p, pc, pr = build_grid(seg_sampled)
        except Exception as exc:
            _log(exp_id, f"       [ERROR] 网格构建: {exc}")
            errors.append(f"pose grid {seg_id}: {exc}")
            continue

        dur = t_end - t_start
        pose_user = [
            {
                "type": "text",
                "text": (
                    f"exercise 段 {seg_id} 的关键帧网格图：\n"
                    f"- 列数：{pc}，行数：{pr}\n"
                    f"- 有效帧数：{len(seg_sampled)} 帧\n"
                    f"- 本段时间：{t_start:.1f}s ~ {t_end:.1f}s（共 {dur:.1f}s）\n\n"
                    "（训练计划已在 system prompt 中提供，请直接参照匹配。）\n\n"
                    "请识别器材与动作、估算组次、说明与计划的匹配偏差。严格输出 JSON。"
                ),
            },
            {"type": "image_url", "image_url": {"url": to_data_url(jpeg_p)}},
        ]

        try:
            raw_p = call_llm(POSE_SYSTEM, pose_user, model_id, exp_id,
                             base_url=_base_url, api_key=_api_key)
            pose_data = parse_json(raw_p)
        except Exception as exc:
            _log(exp_id, f"       [ERROR] pose 识别: {exc}")
            errors.append(f"pose {seg_id}: {exc}")
            pose_data = {"error": str(exc)}

        pose_items.append({
            "segmentId":   seg_id,
            "startTime":   t_start,
            "endTime":     t_end,
            "duration":    dur,
            "frames_used": len(seg_sampled),
            "grid":        {"cols": pc, "rows": pr},
            "pose_data":   pose_data,
        })

    # ── 计划完成度分析（所有 exercise 段识别完成后汇总）───────────────────
    plan_completion = compute_plan_completion(TRAINING_PLAN, pose_items)
    _log(exp_id, f"Step2 | {plan_completion['summary']}")

    pose_result = {
        "exp_id":          exp_id,
        "model":           model_id,
        "fps":             fps_label,
        "created_at":      start_ts.isoformat(),
        "training_plan":   TRAINING_PLAN,
        "results":         pose_items,
        "plan_completion": plan_completion,
    }
    save_json(pose_result, out_dir / "pose_result.json")
    _log(exp_id, f"Step2 | 保存 pose_result.json ({len(pose_items)} 条)")

    # ── 写运行日志 ────────────────────────────────────────────────────────
    elapsed = round((datetime.now() - start_ts).total_seconds(), 1)
    summary = {
        "exp_id":          exp_id,
        "model":           model_id,
        "fps":             fps_label,
        "sample_step":     step,
        "sampled_frames":  len(sampled),
        "segments_total":  len(segments),
        "exercise_segs":   len(exercise_segs),
        "pose_results":    len(pose_items),
        "elapsed_sec":     elapsed,
        "errors":          errors,
        "status":          "ok" if not errors else "partial",
    }
    save_json(summary, out_dir / "run.log")
    _log(exp_id, f"完成 {elapsed}s | segments={len(segments)} pose={len(pose_items)} errors={len(errors)}")
    return summary


# ══════════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    # 前置检查
    if not GEMINI_API_KEY:
        print("[错误] GEMINI_API_KEY 未在 .env 中设置")
        sys.exit(1)

    if not FRAMES_DIR.is_dir():
        print(f"[错误] 帧目录不存在: {FRAMES_DIR}")
        sys.exit(1)

    # 一次性加载所有帧，实验间共享（只读）
    print(f"扫描帧目录: {FRAMES_DIR}")
    all_frames = parse_frames(FRAMES_DIR)
    if not all_frames:
        print("[错误] 未找到 state*.jpg 文件")
        sys.exit(1)
    print(f"共 {len(all_frames)} 帧，时长约 {(len(all_frames)-1)*ORIG_INTERVAL:.1f}s")

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    # 构建 9 组实验参数
    experiments = [
        (fps_cfg, model_cfg)
        for fps_cfg   in FPS_CONFIGS
        for model_cfg in MODEL_CONFIGS
    ]

    print(f"\n实验矩阵 ({len(experiments)} 组):")
    print(f"  {'实验 ID':<30}  {'帧数':>6}  {'模型'}")
    print(f"  {'-'*60}")
    for fps_cfg, model_cfg in experiments:
        n = math.ceil(len(all_frames) / fps_cfg["step"])
        eid = f"30K_{fps_cfg['label']}_{model_cfg['name']}"
        print(f"  {eid:<30}  {n:>6}  {model_cfg['model_id']}")

    print(f"\n输出目录: {OUTPUT_BASE}")
    print(f"并行 workers: {len(experiments)}（每组实验独立线程）\n")

    # 并行执行所有实验
    summaries: list[dict] = []
    with ThreadPoolExecutor(max_workers=len(experiments)) as pool:
        future_map = {
            pool.submit(run_one, all_frames, fps_cfg, model_cfg):
                f"30K_{fps_cfg['label']}_{model_cfg['name']}"
            for fps_cfg, model_cfg in experiments
        }
        for future in as_completed(future_map):
            exp_id = future_map[future]
            try:
                summaries.append(future.result())
            except Exception as exc:
                print(f"[FATAL][{exp_id}] {exc}")
                summaries.append({"exp_id": exp_id, "status": "failed", "error": str(exc)})

    # 全局汇总
    summaries.sort(key=lambda x: x.get("exp_id", ""))
    save_json(summaries, OUTPUT_BASE / "experiment_summary.json")

    # 打印结果表格
    print(f"\n{'='*70}")
    print(f"{'实验 ID':<30}  {'段数':>4}  {'pose':>4}  {'时长(s)':>8}  状态")
    print(f"{'-'*70}")
    for s in summaries:
        eid   = s.get("exp_id", "?")
        segs  = s.get("segments_total", "-")
        pose  = s.get("pose_results",   "-")
        t     = s.get("elapsed_sec",    "-")
        errs  = s.get("errors", [])
        state = "OK" if s.get("status") == "ok" else f"ERR({len(errs)})" if errs else s.get("status","?")
        print(f"{eid:<30}  {segs!s:>4}  {pose!s:>4}  {t!s:>8}  {state}")
    print(f"{'='*70}")
    print(f"汇总已保存: {OUTPUT_BASE / 'experiment_summary.json'}")


if __name__ == "__main__":
    main()
