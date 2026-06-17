"""
recognize_video.py
------------------
两阶段 LLM 识别（光流增强版）：
  Phase 1: period_recognize → 粗粒度阶段划分（EXERCISE / REST / TRANSITION）
  Phase 2: exercise_recognize → exercise 段精细识别（器械→动作→组次）

用法:
  python recognize_video.py [--phase1 YAML] [--phase2 YAML] [--folder NAME]

  --phase1  阶段1 Prompt YAML 文件名（默认 phase1_period_recognize_v3.yaml）
  --phase2  阶段2 Prompt YAML 文件名（默认 phase2_exercise_recognize_v4.yaml）
  --folder  只处理 frames 目录下指定的子文件夹，不指定则处理全部子文件夹
"""

import argparse
import base64
import io
import json
import math
import os
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import requests
import yaml
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ── 路径 ───────────────────────────────────────────────────────
FRAMES_ROOT = Path(os.getenv("FRAMES_ROOT", r"D:\WorkPath\fitness\video\frames"))
OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", r"D:\WorkPath\fitness\video\result"))
MID_RESULT_DIR = Path(os.getenv("MID_RESULT_DIR", r"D:\WorkPath\fitness\video\result\mid_result"))
PROMPT_DIR = Path(os.getenv("PROMPT_DIR", r"D:\WorkPath\fitness\video\coreCode\prompt"))

# ── 采样 ───────────────────────────────────────────────────────
SOURCE_FPS = 2
TARGET_FPS = 1
INTERVAL = 1.0 / TARGET_FPS

# ── 光流 ───────────────────────────────────────────────────────
FLOW_RESIZE_W = 320
FLOW_RESIZE_H = 240

# ── Phase 1 ────────────────────────────────────────────────────
PERIOD_SAMPLE_STEP = 1
PERIOD_GRID_COLS = 10
PERIOD_WINDOW_SEC = 60

# ── Phase 2 ────────────────────────────────────────────────────
EXERCISE_SAMPLE_STEP = 1
EXERCISE_BOUNDARY_PAD = 15

# ── 图片 ───────────────────────────────────────────────────────
GRID_JPEG_QUALITY = 75
GRID_MAX_CELL_W = 480
GRID_MAX_CELL_H = 270

# ── LLM ────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://nextrouter.cc/v1")
MODEL = "gemini-3-flash-preview"

# ── 并发 ──────────────────────────────────────────────────────
MAX_FOLDER_WORKERS = int(os.getenv("MAX_FOLDER_WORKERS", "3"))
MAX_EXERCISE_WORKERS = int(os.getenv("MAX_EXERCISE_WORKERS", "4"))

_print_lock = threading.Lock()


def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

# ── 训练计划 ───────────────────────────────────────────────────
TRAINING_PLAN = {
    "planId": "plan_demo_001",
    "userId": "user_test_001",
    "date": "2026-05-27",
    "name": "全身基础训练",
    "phases": [
        {
            "phaseName": "warmup",
            "order": 1,
            "exercises": [
                {"order": 1, "equipmentId": "equip_treadmill_01", "exerciseName": "跑步机慢跑"}
            ],
        },
        {
            "phaseName": "strength",
            "order": 2,
            "exercises": [
                {"order": 2, "equipmentId": "equip_smith_machine_01", "exerciseName": "史密斯机深蹲"}
            ],
        },
        {
            "phaseName": "core",
            "order": 3,
            "exercises": [
                {"order": 3, "equipmentId": "equip_pull_up_bar_01", "exerciseName": "悬垂举腿"}
            ],
        },
    ],
}


# ═══════════════════════════════════════════════════════════════
# YAML Prompt 加载
# ═══════════════════════════════════════════════════════════════

def load_yaml_prompt(name: str) -> dict:
    path = PROMPT_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ═══════════════════════════════════════════════════════════════
# 帧解析 & 降采样
# ═══════════════════════════════════════════════════════════════

_STATE_RE = re.compile(r"state(\d+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.jpg")
_FRAME_RE = re.compile(r"frame_(\d+)\.jpg")


def parse_frames(frames_dir: Path) -> list[dict]:
    frames = []
    for f in frames_dir.iterdir():
        m = _STATE_RE.match(f.name)
        if m:
            idx = int(m.group(1))
            ts = datetime.strptime(m.group(2), "%Y-%m-%d_%H-%M-%S")
            frames.append({"index": idx, "timestamp": ts, "path": f})
            continue
        m = _FRAME_RE.match(f.name)
        if m:
            idx = int(m.group(1))
            ts = datetime(2000, 1, 1) + timedelta(seconds=idx / SOURCE_FPS)
            frames.append({"index": idx, "timestamp": ts, "path": f})

    seen_indices = set()
    deduped = []
    for fr in sorted(frames, key=lambda x: x["index"]):
        if fr["index"] not in seen_indices:
            seen_indices.add(fr["index"])
            deduped.append(fr)
    return deduped


def downsample_to_1fps(all_frames: list[dict]) -> list[dict]:
    step = SOURCE_FPS // TARGET_FPS
    return all_frames[::step]


def secs_to_mmss(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def mmss_to_secs(t: str) -> float:
    parts = t.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


# ═══════════════════════════════════════════════════════════════
# 光流计算
# ═══════════════════════════════════════════════════════════════

def _classify_direction(angle_deg: float) -> str:
    a = angle_deg % 360
    if 315 <= a or a < 45:
        return "RIGHT"
    if 45 <= a < 135:
        return "DOWN"
    if 135 <= a < 225:
        return "LEFT"
    return "UP"


def _imread_unicode(path: Path, flags=cv2.IMREAD_GRAYSCALE):
    buf = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(buf, flags)


def compute_optical_flow(keyframes: list[dict]) -> list[dict]:
    tprint("\n=== 计算光流 (Dense Optical Flow — Farneback) ===")
    flow_data: list[dict] = []

    for i in range(len(keyframes) - 1):
        img1 = _imread_unicode(keyframes[i]["path"])
        img2 = _imread_unicode(keyframes[i + 1]["path"])
        if img1 is None or img2 is None:
            continue

        h, w = img1.shape
        scale = min(FLOW_RESIZE_W / w, FLOW_RESIZE_H / h, 1.0)
        if scale < 1.0:
            img1 = cv2.resize(img1, None, fx=scale, fy=scale)
            img2 = cv2.resize(img2, None, fx=scale, fy=scale)

        flow = cv2.calcOpticalFlowFarneback(
            img1, img2, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
        )
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        avg_flow = float(np.mean(mag))
        max_flow = float(np.percentile(mag, 95))
        motion_energy = float(np.mean(mag ** 2))

        ang_deg = np.degrees(ang)
        weight_sum = float(np.sum(mag))
        if weight_sum > 1e-6:
            dominant_angle = float(np.average(ang_deg, weights=mag + 1e-8)) % 360
        else:
            dominant_angle = 0.0

        t = i * INTERVAL
        flow_data.append({
            "frame_pair": [keyframes[i]["index"], keyframes[i + 1]["index"]],
            "time_sec": round(t, 1),
            "avg_flow": round(avg_flow, 3),
            "max_flow": round(max_flow, 3),
            "motion_energy": round(motion_energy, 3),
            "dominant_angle": round(dominant_angle, 1),
            "dominant_direction": _classify_direction(dominant_angle),
        })

        if (i + 1) % 50 == 0:
            tprint(f"  已处理 {i + 1}/{len(keyframes) - 1} 帧对")

    tprint(f"  光流计算完成，共 {len(flow_data)} 帧对")
    return flow_data


def analyze_periodicity(flow_data: list[dict], window_sec: int = 20) -> list[dict]:
    if len(flow_data) < 10:
        return []

    signal = np.array([d["avg_flow"] for d in flow_data])
    step = max(1, window_sec // 2)
    results: list[dict] = []

    for start in range(0, len(signal) - window_sec, step):
        end = start + window_sec
        w = signal[start:end] - np.mean(signal[start:end])

        if np.std(w) < 0.1:
            results.append({
                "start_sec": round(start * INTERVAL, 1),
                "end_sec": round(end * INTERVAL, 1),
                "periodic": False,
                "period_sec": None,
                "strength": 0.0,
            })
            continue

        autocorr = np.correlate(w, w, mode="full")
        autocorr = autocorr[len(autocorr) // 2:]
        autocorr = autocorr / (autocorr[0] + 1e-8)

        min_lag = 2
        max_lag = min(window_sec // 2, len(autocorr) - 1)
        if max_lag <= min_lag:
            results.append({
                "start_sec": round(start * INTERVAL, 1),
                "end_sec": round(end * INTERVAL, 1),
                "periodic": False,
                "period_sec": None,
                "strength": 0.0,
            })
            continue

        search = autocorr[min_lag : max_lag + 1]
        peak_idx = int(np.argmax(search)) + min_lag
        peak_val = float(autocorr[peak_idx])

        is_periodic = peak_val > 0.3
        period = peak_idx * INTERVAL if is_periodic else None

        results.append({
            "start_sec": round(start * INTERVAL, 1),
            "end_sec": round(end * INTERVAL, 1),
            "periodic": is_periodic,
            "period_sec": round(period, 2) if period else None,
            "strength": round(peak_val, 3),
        })

    return results


# ═══════════════════════════════════════════════════════════════
# 光流摘要格式化
# ═══════════════════════════════════════════════════════════════

def _intensity_label(avg: float) -> str:
    if avg < 1.0:
        return "极低"
    if avg < 3.0:
        return "低"
    if avg < 6.0:
        return "中"
    if avg < 10.0:
        return "高"
    return "极高"


def detect_flow_transitions(flow_data: list[dict], window_sec: int = 3, threshold: float = 3.0) -> list[dict]:
    """Detect significant transitions (peaks/valleys) in optical flow avg_flow."""
    if len(flow_data) < 3:
        return []
    transitions = []
    flows = [d["avg_flow"] for d in flow_data]
    times = [d["time_sec"] for d in flow_data]

    for i in range(window_sec, len(flows) - 1):
        before_avg = float(np.mean(flows[max(0, i - window_sec):i]))
        after_avg = float(np.mean(flows[i:min(len(flows), i + window_sec)]))
        delta = after_avg - before_avg

        if abs(delta) >= threshold:
            transitions.append({
                "time_sec": times[i],
                "type": "rise" if delta > 0 else "drop",
                "before_avg": round(before_avg, 1),
                "after_avg": round(after_avg, 1),
                "delta": round(delta, 1),
            })

    merged = []
    for t in transitions:
        if merged and t["time_sec"] - merged[-1]["time_sec"] < 3 and t["type"] == merged[-1]["type"]:
            if abs(t["delta"]) > abs(merged[-1]["delta"]):
                merged[-1] = t
        else:
            merged.append(t)
    return merged


def format_flow_transitions(flow_data: list[dict], t_start: float = None, t_end: float = None) -> str:
    """Format detected flow transitions as text for LLM consumption."""
    if t_start is not None or t_end is not None:
        filtered = [d for d in flow_data
                     if (t_start is None or d["time_sec"] >= t_start - 0.5)
                     and (t_end is None or d["time_sec"] <= t_end + 0.5)]
    else:
        filtered = flow_data

    transitions = detect_flow_transitions(filtered)
    if not transitions:
        return "  (无显著光流强度突变)"

    lines = ["  ★ 光流强度突变点（活动边界候选）:"]
    for t in transitions:
        label = "↑骤升" if t["type"] == "rise" else "↓骤降"
        lines.append(
            f"    {t['time_sec']:.0f}s: avg_flow {t['before_avg']} → {t['after_avg']} ({label} Δ={t['delta']:+.1f})"
        )
    return "\n".join(lines)


def format_flow_for_period(flow_data: list[dict], periodicity: list[dict]) -> str:
    lines = [
        "=== 光流摘要（帧间运动趋势）===",
        f"总帧对数: {len(flow_data)}，帧间隔: {INTERVAL}s",
        "",
    ]
    chunk_sec = 10
    chunk_size = max(1, int(chunk_sec / INTERVAL))

    for i in range(0, len(flow_data), chunk_size):
        chunk = flow_data[i : i + chunk_size]
        if not chunk:
            continue
        t_s = chunk[0]["time_sec"]
        t_e = chunk[-1]["time_sec"] + INTERVAL
        avg = float(np.mean([d["avg_flow"] for d in chunk]))
        max_e = max(d["motion_energy"] for d in chunk)
        main_dir = Counter(d["dominant_direction"] for d in chunk).most_common(1)[0][0]
        lines.append(
            f"[{t_s:.0f}s-{t_e:.0f}s] "
            f"运动强度:{_intensity_label(avg)}(avg={avg:.1f}), "
            f"主方向:{main_dir}, 峰值能量:{max_e:.1f}"
        )

    if periodicity:
        lines += ["", "=== 运动周期性分析 ==="]
        for p in periodicity:
            if p["periodic"]:
                lines.append(
                    f"[{p['start_sec']:.0f}s-{p['end_sec']:.0f}s] "
                    f"周期性运动, 周期≈{p['period_sec']:.1f}s, 置信度:{p['strength']:.2f}"
                )
            else:
                lines.append(
                    f"[{p['start_sec']:.0f}s-{p['end_sec']:.0f}s] 无明显周期性"
                )

    return "\n".join(lines)


def format_flow_for_exercise(flow_data: list[dict], start_sec: float, end_sec: float) -> str:
    seg = [d for d in flow_data if start_sec - 0.5 <= d["time_sec"] <= end_sec + 0.5]
    if not seg:
        return "该区间无光流数据"

    lines = [f"=== 运动区间光流 [{start_sec:.0f}s-{end_sec:.0f}s] ==="]

    if len(seg) <= 40:
        for d in seg:
            lines.append(
                f"  t={d['time_sec']:.0f}s: flow={d['avg_flow']:.2f}, "
                f"方向={d['dominant_direction']}, 能量={d['motion_energy']:.2f}"
            )
    else:
        cs = 5
        for i in range(0, len(seg), cs):
            chunk = seg[i : i + cs]
            t_s = chunk[0]["time_sec"]
            t_e = chunk[-1]["time_sec"]
            avg = float(np.mean([d["avg_flow"] for d in chunk]))
            main_dir = Counter(d["dominant_direction"] for d in chunk).most_common(1)[0][0]
            lines.append(f"  [{t_s:.0f}s-{t_e:.0f}s]: avg_flow={avg:.2f}, 主方向={main_dir}")

    all_avg = float(np.mean([d["avg_flow"] for d in seg]))
    all_energy = float(np.mean([d["motion_energy"] for d in seg]))
    dir_dist = Counter(d["dominant_direction"] for d in seg)
    dir_str = ", ".join(f"{k}:{v}" for k, v in dir_dist.most_common())

    lines += [
        "",
        f"整体: avg_flow={all_avg:.2f}, avg_energy={all_energy:.2f}",
        f"方向分布: {dir_str}",
    ]

    dirs = [d["dominant_direction"] for d in seg]
    reversals = sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i - 1])
    if reversals > len(dirs) * 0.3:
        lines.append(f"运动模式: 频繁方向切换({reversals}次), 疑似往复运动")

    transition_text = format_flow_transitions(flow_data, start_sec, end_sec)
    lines.append("")
    lines.append(transition_text)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 网格图 & 编码
# ═══════════════════════════════════════════════════════════════

def build_grid_image(
    frames: list[dict], cols: int, jpeg_quality: int = GRID_JPEG_QUALITY
) -> tuple[bytes, int, int]:
    if not frames:
        raise ValueError("frames 为空")

    sample = Image.open(frames[0]["path"])
    fw, fh = sample.size
    sample.close()

    # 如果子帧超过上限尺寸，按比例缩放
    scale = min(GRID_MAX_CELL_W / fw, GRID_MAX_CELL_H / fh, 1.0)
    if scale < 1.0:
        fw = int(fw * scale)
        fh = int(fh * scale)

    rows = math.ceil(len(frames) / cols)
    tprint(
        f"    子图: {fw}×{fh}px (scale={scale:.2f}), 网格: {cols}×{rows}, 共 {len(frames)} 帧"
    )

    canvas = Image.new("RGB", (cols * fw, rows * fh), color=(30, 30, 30))
    for i, frame in enumerate(frames):
        img = Image.open(frame["path"])
        if scale < 1.0:
            img = img.resize((fw, fh), Image.LANCZOS)
        canvas.paste(img, ((i % cols) * fw, (i // cols) * fh))
        img.close()

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=jpeg_quality)
    jpeg_bytes = buf.getvalue()
    tprint(f"    网格图: {len(jpeg_bytes) / 1024:.0f} KB")
    return jpeg_bytes, cols, rows


def image_to_data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def gemini_generate(system_prompt: str, user_content: list[dict], max_retries: int = 5) -> str:
    url = f"{GEMINI_BASE_URL}/chat/completions"
    img_count = sum(1 for c in user_content if c.get("type") == "image_url")
    tprint(f"  → LLM 请求: {img_count} 张图片")

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 8192,
    }
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=600)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            elapsed = time.time() - t0
            wait = min(30 * attempt, 180)
            tprint(f"  [网络错误] {type(e).__name__} (耗时 {elapsed:.1f}s): {e}")
            if attempt < max_retries:
                tprint(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time.sleep(wait)
                continue
            raise

        elapsed = time.time() - t0
        if resp.status_code == 429:
            wait = 60 * attempt
            tprint(f"  [429] 耗时 {elapsed:.1f}s，等待 {wait}s 后重试（{attempt}/{max_retries}）...")
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            wait = min(30 * attempt, 180)
            tprint(f"  [HTTP {resp.status_code}] 耗时 {elapsed:.1f}s，等待 {wait}s 后重试（{attempt}/{max_retries}）...")
            if attempt < max_retries:
                time.sleep(wait)
                continue
        if not resp.ok:
            tprint(f"  [HTTP {resp.status_code}] {resp.text[:300]}")
        resp.raise_for_status()
        tprint(f"  ← LLM 响应: {elapsed:.1f}s")
        return resp.json()["choices"][0]["message"]["content"]

    raise RuntimeError("超过最大重试次数")


def extract_json(text: str):
    text = text.strip()
    # Strip <think>...</think> blocks (model chain-of-thought)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        text = "\n".join(inner).strip()
    # Try to find JSON object if there's surrounding text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    return json.loads(text)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tprint(f"  [OK] 已保存: {path}")


# ═══════════════════════════════════════════════════════════════
# Phase 1 — 阶段划分
# ═══════════════════════════════════════════════════════════════

def _summarize_window_flow(flow_data: list[dict], t_start: float, t_end: float) -> str:
    seg = [d for d in flow_data if t_start - 0.5 <= d["time_sec"] <= t_end + 0.5]
    if not seg:
        return "  (无光流数据)"
    chunk_sec = 5
    chunk_size = max(1, int(chunk_sec / INTERVAL))
    lines: list[str] = []
    for i in range(0, len(seg), chunk_size):
        chunk = seg[i : i + chunk_size]
        ts = chunk[0]["time_sec"]
        te = chunk[-1]["time_sec"] + INTERVAL
        avg = float(np.mean([d["avg_flow"] for d in chunk]))
        main_dir = Counter(d["dominant_direction"] for d in chunk).most_common(1)[0][0]
        lines.append(f"  [{ts:.0f}s-{te:.0f}s] {_intensity_label(avg)}({avg:.1f}), {main_dir}")

    transition_text = format_flow_transitions(flow_data, t_start, t_end)
    lines.append(transition_text)
    return "\n".join(lines)


def run_phase1_period(
    keyframes: list[dict],
    flow_data: list[dict],
    periodicity: list[dict],
    output_dir: Path,
    frames_dir: Path,
    phase1_yaml: str,
) -> list[dict]:
    tprint("\n" + "=" * 60)
    tprint(f"Phase 1: 阶段划分 ({phase1_yaml})")
    tprint("=" * 60)

    prompt_cfg = load_yaml_prompt(phase1_yaml)
    system_prompt = prompt_cfg["system"]

    sampled = keyframes[::PERIOD_SAMPLE_STEP]
    total_dur = (len(keyframes) - 1) * INTERVAL

    mid_result_dir = output_dir / "mid_result"
    mid_result_dir.mkdir(parents=True, exist_ok=True)

    win_size = PERIOD_WINDOW_SEC
    windows: list[dict] = []
    for si in range(0, len(sampled), win_size):
        ei = min(si + win_size, len(sampled))
        windows.append({
            "frames": sampled[si:ei],
            "start_sec": si * INTERVAL,
            "end_sec": (ei - 1) * INTERVAL,
        })

    tprint(f"  1fps 帧数: {len(sampled)}, 窗口: {len(windows)} 个 (每窗 {win_size}s)")

    intro = (
        f"以下是一段健身视频的关键帧（第一人称胸前相机），"
        f"共 {len(sampled)} 帧 (1fps)，总时长 {total_dur:.0f}s ({secs_to_mmss(total_dur)})。\n\n"
        f"按时间顺序分成 {len(windows)} 个窗口，每个窗口一张网格图 + 对应光流摘要。\n"
        f"网格读取顺序：从左到右、从上到下。\n\n"
        f"请综合所有窗口的关键帧画面与光流信息，将整段视频划分为 EXERCISE / TRANSITION。\n\n"
        f"关键规则：\n"
        f"- 第一人称胸前相机，用户本人不完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象\n"
        f"- 仅关注用户双手、正在接触的器械、视角运动变化\n"
        f"- 用户双手与器械持续交互 + 光流显示周期性运动 → EXERCISE\n"
        f"- 不同器械上的运动必须拆分为不同 EXERCISE 段（如跑步机 → 深蹲架 = 两段独立 EXERCISE，中间有 TRANSITION）\n"
        f"- 器械切换、行走、调整位置、休息、喝水、看手机 → TRANSITION\n"
    )
    user_content: list[dict] = [{"type": "text", "text": intro}]

    for i, win in enumerate(windows):
        jpeg, cols, rows = build_grid_image(win["frames"], cols=PERIOD_GRID_COLS)
        grid_path = mid_result_dir / f"phase1_window_{i + 1:03d}.jpg"
        grid_path.write_bytes(jpeg)
        tprint(f"    [网格图] 已保存: {grid_path}")
        flow_text = _summarize_window_flow(flow_data, win["start_sec"], win["end_sec"])

        win_header = (
            f"\n--- 窗口 {i + 1}/{len(windows)} "
            f"({secs_to_mmss(win['start_sec'])} ~ {secs_to_mmss(win['end_sec'])}, "
            f"{len(win['frames'])} 帧, {cols}×{rows}) ---\n"
            f"光流:\n{flow_text}"
        )
        user_content.append({"type": "text", "text": win_header})
        user_content.append({"type": "image_url", "image_url": {"url": image_to_data_url(jpeg)}})

    output_fmt = (
        f"\n\n请输出覆盖 00:00:00 ~ {secs_to_mmss(total_dur)} 的完整时间线，"
        f"严格按 JSON 格式，不要包含 Markdown 代码块或注释：\n"
        f'{{"segments": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", '
        f'"state": "EXERCISE|TRANSITION", "confidence": 0.0~1.0, '
        f'"reason": "判断依据"}}]}}'
    )
    user_content.append({"type": "text", "text": output_fmt})

    raw = gemini_generate(system_prompt, user_content)
    tprint(f"  响应长度: {len(raw)} 字符")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "period_raw_response.txt").write_text(raw, encoding="utf-8")

    try:
        result = extract_json(raw)
    except json.JSONDecodeError as e:
        tprint(f"  [警告] JSON 解析失败: {e}")
        result = {"raw_response": raw}

    segments = []
    if isinstance(result, dict):
        segments = result.get("segments", [])
    elif isinstance(result, list):
        segments = result

    for seg in segments:
        if "start_time" in seg and "start_sec" not in seg:
            seg["start_sec"] = mmss_to_secs(str(seg["start_time"]))
        if "end_time" in seg and "end_sec" not in seg:
            seg["end_sec"] = mmss_to_secs(str(seg["end_time"]))

    # 从 YAML 文件名提取版本号用于标记
    version_tag = phase1_yaml.replace("phase1_period_recognize_", "").replace(".yaml", "")

    meta = {
        "version": version_tag,
        "phase1_prompt": phase1_yaml,
        "source": str(frames_dir),
        "total_1fps_frames": len(keyframes),
        "sampled_frames": len(sampled),
        "sample_step": PERIOD_SAMPLE_STEP,
        "window_sec": PERIOD_WINDOW_SEC,
        "num_windows": len(windows),
        "model": MODEL,
        "created_at": datetime.now().isoformat(),
        "segments": segments,
    }
    save_json(meta, output_dir / "period_result.json")

    ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
    tprint(f"  Phase 1 完成: {len(segments)} 段, 其中 EXERCISE {ex_count} 段")
    return segments


# ═══════════════════════════════════════════════════════════════
# Phase 2 — 运动识别
# ═══════════════════════════════════════════════════════════════

def _coerce_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def apply_phase1_adjustments(
    segments: list[dict],
    exercise_results: list[dict],
    total_dur: float,
) -> tuple[list[dict], int]:
    adjusted = [dict(s) for s in segments]
    result_map = {r.get("segmentId"): r for r in exercise_results}

    applied = 0
    for i, seg in enumerate(adjusted):
        if seg.get("state", "").upper() != "EXERCISE":
            continue
        seg_id = seg.get("segmentId")
        res = result_map.get(seg_id, {}).get("result", {})
        adj = res.get("phase1_adjustment") or {}
        before = max(0.0, _coerce_float(adj.get("expand_before_sec")))
        after = max(0.0, _coerce_float(adj.get("expand_after_sec")))
        if before <= 0 and after <= 0:
            continue

        if before > 0 and i > 0:
            prev_seg = adjusted[i - 1]
            new_start = max(prev_seg.get("start_sec", 0.0), seg.get("start_sec", 0.0) - before)
            if new_start < seg.get("end_sec", 0.0):
                if new_start < seg.get("start_sec", 0.0):
                    seg["start_sec"] = new_start
                    seg["start_time"] = secs_to_mmss(new_start)
                    if new_start < prev_seg.get("end_sec", 0.0):
                        prev_seg["end_sec"] = new_start
                        prev_seg["end_time"] = secs_to_mmss(new_start)
                    applied += 1

        if after > 0 and i < len(adjusted) - 1:
            next_seg = adjusted[i + 1]
            new_end = min(next_seg.get("end_sec", total_dur), seg.get("end_sec", 0.0) + after)
            if new_end > seg.get("start_sec", 0.0):
                if new_end > seg.get("end_sec", 0.0):
                    seg["end_sec"] = new_end
                    seg["end_time"] = secs_to_mmss(new_end)
                    if new_end > next_seg.get("start_sec", 0.0):
                        next_seg["start_sec"] = new_end
                        next_seg["start_time"] = secs_to_mmss(new_end)
                    applied += 1

    if adjusted:
        adjusted[0]["start_sec"] = max(0.0, adjusted[0].get("start_sec", 0.0))
        adjusted[0]["start_time"] = secs_to_mmss(adjusted[0]["start_sec"])
        adjusted[-1]["end_sec"] = min(total_dur, adjusted[-1].get("end_sec", total_dur))
        adjusted[-1]["end_time"] = secs_to_mmss(adjusted[-1]["end_sec"])

    return adjusted, applied


def _recognize_one_exercise(
    seg: dict,
    keyframes: list[dict],
    flow_data: list[dict],
    system_prompt: str,
    output_dir: Path,
) -> dict | None:
    seg_id = seg.get("segmentId", "?")
    t_start = seg.get("start_sec", 0.0)
    t_end = seg.get("end_sec", 0.0)
    dur = t_end - t_start

    tprint(f"\n  ── {seg_id}: {secs_to_mmss(t_start)} ~ {secs_to_mmss(t_end)} ({dur:.0f}s)")

    pad_start = max(0.0, t_start - EXERCISE_BOUNDARY_PAD)
    pad_end = min((len(keyframes) - 1) * INTERVAL, t_end + EXERCISE_BOUNDARY_PAD)
    tprint(f"    [{seg_id}] 扩展取帧范围: {secs_to_mmss(pad_start)} ~ {secs_to_mmss(pad_end)}")

    seg_frames = [
        kf for j, kf in enumerate(keyframes)
        if pad_start - 0.5 <= j * INTERVAL <= pad_end + 0.5
    ]
    if not seg_frames:
        tprint(f"    [{seg_id}] [警告] 无匹配帧，跳过")
        return None

    sampled_seg = seg_frames[::EXERCISE_SAMPLE_STEP]
    tprint(f"    [{seg_id}] 段内帧数: {len(seg_frames)}, 采样: {len(sampled_seg)}")

    g_cols = max(1, round(math.sqrt(len(sampled_seg))))
    jpeg_bytes, g_cols, g_rows = build_grid_image(sampled_seg, cols=g_cols)

    flow_summary = format_flow_for_exercise(flow_data, t_start, t_end)

    user_text = (
        f"以下是 EXERCISE 段 [{seg_id}] 的关键帧网格图（第一人称胸前相机）：\n"
        f"- 网格列数: {g_cols}, 行数: {g_rows}\n"
        f"- 有效帧数: {len(sampled_seg)}, 帧间隔: {INTERVAL * EXERCISE_SAMPLE_STEP:.1f}s\n"
        f"- 时间范围: {secs_to_mmss(t_start)} ~ {secs_to_mmss(t_end)} (共 {dur:.0f}s)\n"
        f"- 读取顺序: 从左到右、从上到下\n\n"
        f"---\n\n"
        f"{flow_summary}\n\n"
        f"---\n\n"
        f"请按以下步骤分析：\n"
        f"Step 1 — 器械识别: 根据画面中用户双手接触的器械判断器械类型\n"
        f"Step 2 — 光流辅助: 结合光流方向（上下/前后/左右往复）推断运动类型\n"
        f"Step 3 — 动作判定: 综合器械+光流+画面判定具体动作\n"
        f"Step 4 — 组次统计: 利用光流周期统计组数和每组次数\n\n"
        f"关键约束：\n"
        f"- 第一人称胸前相机 → 用户自身不会完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象\n"
        f"- 必须看到用户双手或器械的运动证据才能判定动作\n"
        f"- 如果器械无法确定，equipment 填 \"UNKNOWN_EQUIPMENT\"\n"
        f"- 如果动作无法确定，exercise 填 \"UNKNOWN_ACTION\"\n\n"
        f"严格按以下 JSON 格式输出，不要包含 Markdown 代码块或注释：\n"
        f'{{"equipment": "器械名称", "exercise": "动作名称", "confidence": 0.0~1.0, '
        f'"sets": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", "reps": N}}]}}'
    )

    user_content = [
        {"type": "text", "text": user_text},
        {"type": "image_url", "image_url": {"url": image_to_data_url(jpeg_bytes)}},
    ]

    raw = gemini_generate(system_prompt, user_content)
    tprint(f"    [{seg_id}] 响应长度: {len(raw)} 字符")

    raw_path = output_dir / f"exercise_raw_{seg_id}.txt"
    raw_path.write_text(raw, encoding="utf-8")

    try:
        seg_result = extract_json(raw)
    except json.JSONDecodeError as e:
        tprint(f"    [{seg_id}] [警告] JSON 解析失败: {e}")
        seg_result = {"raw_response": raw}

    return {
        "segmentId": seg_id,
        "startTime": t_start,
        "endTime": t_end,
        "startTimeStr": secs_to_mmss(t_start),
        "endTimeStr": secs_to_mmss(t_end),
        "duration": dur,
        "frames_analyzed": len(sampled_seg),
        "grid": {"cols": g_cols, "rows": g_rows},
        "result": seg_result,
    }


def run_phase2_exercise(
    keyframes: list[dict],
    flow_data: list[dict],
    segments: list[dict],
    output_dir: Path,
    frames_dir: Path,
    phase2_yaml: str,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
) -> list[dict]:
    tprint("\n" + "=" * 60)
    tprint(f"Phase 2: 运动识别 ({phase2_yaml})")
    tprint("=" * 60)

    prompt_cfg = load_yaml_prompt(phase2_yaml)
    system_prompt = prompt_cfg["system"]

    version_tag = phase2_yaml.replace("phase2_exercise_recognize_", "").replace(".yaml", "")

    exercise_segs = [
        s for s in segments if s.get("state", "").upper() == "EXERCISE"
    ]
    for i, s in enumerate(exercise_segs, 1):
        s.setdefault("segmentId", f"exercise_{i:03d}")

    tprint(f"  共 {len(exercise_segs)} 个 EXERCISE 段待识别 (并发: {exercise_workers})")
    if not exercise_segs:
        save_json(
            {"version": version_tag, "message": "no exercise segments", "results": []},
            output_dir / "exercise_result.json",
        )
        return []

    all_results: list[dict] = []
    workers = min(exercise_workers, len(exercise_segs))

    if workers <= 1:
        for seg in exercise_segs:
            result = _recognize_one_exercise(seg, keyframes, flow_data, system_prompt, output_dir)
            if result:
                all_results.append(result)
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for seg in exercise_segs:
                fut = executor.submit(
                    _recognize_one_exercise, seg, keyframes, flow_data, system_prompt, output_dir
                )
                futures[fut] = seg.get("segmentId", "?")

            for fut in as_completed(futures):
                seg_id = futures[fut]
                try:
                    result = fut.result()
                    if result:
                        all_results.append(result)
                except Exception as e:
                    tprint(f"    [{seg_id}] [错误] 处理失败: {e}")

        all_results.sort(key=lambda r: r["startTime"])

    save_json(
        {
            "version": version_tag,
            "phase2_prompt": phase2_yaml,
            "source": str(frames_dir),
            "model": MODEL,
            "created_at": datetime.now().isoformat(),
            "training_plan": TRAINING_PLAN,
            "results": all_results,
        },
        output_dir / "exercise_result.json",
    )

    total_dur = (len(keyframes) - 1) * INTERVAL
    adjusted_segments, applied = apply_phase1_adjustments(segments, all_results, total_dur)
    save_json(
        {
            "version": version_tag,
            "source": str(frames_dir),
            "model": MODEL,
            "created_at": datetime.now().isoformat(),
            "adjustments_applied": applied,
            "segments": adjusted_segments,
        },
        output_dir / "period_result_adjusted.json",
    )
    return all_results


# ═══════════════════════════════════════════════════════════════
# 单个文件夹处理
# ═══════════════════════════════════════════════════════════════

def process_folder(
    folder_name: str,
    phase1_yaml: str,
    phase2_yaml: str,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
    version: str | None = None,
):
    frames_dir = FRAMES_ROOT / folder_name
    if version:
        output_dir = OUTPUT_ROOT / version / folder_name
    else:
        output_dir = OUTPUT_ROOT / folder_name
    shared_dir = OUTPUT_ROOT / "shared" / folder_name

    tprint(f"\n{'#' * 60}")
    tprint(f"# 处理文件夹: {folder_name}")
    tprint(f"#   帧目录: {frames_dir}")
    tprint(f"#   输出目录: {output_dir}")
    tprint(f"#   Phase 1: {phase1_yaml}")
    tprint(f"#   Phase 2: {phase2_yaml}")
    tprint(f"{'#' * 60}")

    all_frames = parse_frames(frames_dir)
    if not all_frames:
        tprint(f"[跳过] {folder_name}: 未找到关键帧")
        return

    tprint(f"原始帧数: {len(all_frames)} ({SOURCE_FPS}fps)")

    keyframes = downsample_to_1fps(all_frames)
    total_dur = (len(keyframes) - 1) * INTERVAL
    tprint(f"1fps 关键帧: {len(keyframes)}, 总时长约 {total_dur:.0f}s ({secs_to_mmss(total_dur)})")

    # ── 计算/读取光流（从 shared 目录缓存）──
    flow_data: list[dict] = []
    periodicity: list[dict] = []
    shared_dir.mkdir(parents=True, exist_ok=True)
    flow_path = shared_dir / "optical_flow.json"
    if flow_path.exists():
        try:
            with open(flow_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            flow_data = saved.get("flow", []) if isinstance(saved, dict) else []
            periodicity = saved.get("periodicity", []) if isinstance(saved, dict) else []
            tprint(f"已读取光流缓存: {flow_path}")
        except (OSError, json.JSONDecodeError) as e:
            tprint(f"[警告] 光流缓存读取失败，将重新计算: {e}")

    if not flow_data:
        flow_data = compute_optical_flow(keyframes)
        periodicity = analyze_periodicity(flow_data)
        save_json(
            {
                "total_keyframes": len(keyframes),
                "interval_sec": INTERVAL,
                "created_at": datetime.now().isoformat(),
                "flow": flow_data,
                "periodicity": periodicity,
            },
            flow_path,
        )

    # ── Phase 1 ──
    segments = run_phase1_period(
        keyframes, flow_data, periodicity, output_dir, frames_dir, phase1_yaml
    )

    # ── Phase 2 ──
    run_phase2_exercise(
        keyframes, flow_data, segments, output_dir, frames_dir, phase2_yaml,
        exercise_workers=exercise_workers,
    )

    tprint(f"\n[完成] {folder_name} → {output_dir}")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="两阶段 LLM 视频识别")
    parser.add_argument(
        "--phase1", default="phase1_period_recognize_v3.yaml",
        help="阶段1 Prompt YAML 文件名（默认 phase1_period_recognize_v3.yaml）",
    )
    parser.add_argument(
        "--phase2", default="phase2_exercise_recognize_v4.yaml",
        help="阶段2 Prompt YAML 文件名（默认 phase2_exercise_recognize_v4.yaml）",
    )
    parser.add_argument(
        "--folder", default=None,
        help="只处理指定子文件夹（默认处理 frames 目录下全部子文件夹）",
    )
    parser.add_argument(
        "--workers", type=int, default=MAX_FOLDER_WORKERS,
        help=f"视频文件夹并发数（默认 {MAX_FOLDER_WORKERS}）",
    )
    parser.add_argument(
        "--exercise-workers", type=int, default=MAX_EXERCISE_WORKERS,
        help=f"Phase2 运动段 LLM 并发数（默认 {MAX_EXERCISE_WORKERS}）",
    )
    parser.add_argument(
        "--version", default=None,
        help="结果版本标签（如 v1, v2），保存到 result/{version}/ 下",
    )
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        tprint("[错误] GEMINI_API_KEY 未设置")
        sys.exit(1)

    if args.folder:
        folders = [args.folder]
    else:
        if not FRAMES_ROOT.is_dir():
            tprint(f"[错误] 帧目录不存在: {FRAMES_ROOT}")
            sys.exit(1)
        folders = sorted([
            d.name for d in FRAMES_ROOT.iterdir() if d.is_dir()
        ])

    if not folders:
        tprint(f"[错误] {FRAMES_ROOT} 下无子文件夹")
        sys.exit(1)

    folder_workers = min(args.workers, len(folders))
    version = args.version
    tprint(f"待处理文件夹 ({len(folders)}): {folders}")
    tprint(f"Phase 1 YAML: {args.phase1}")
    tprint(f"Phase 2 YAML: {args.phase2}")
    if version:
        tprint(f"版本: {version} → {OUTPUT_ROOT / version}")
    tprint(f"并发: 文件夹={folder_workers}, Phase2段={args.exercise_workers}")

    t_total_start = time.time()

    if folder_workers <= 1:
        for folder_name in folders:
            process_folder(folder_name, args.phase1, args.phase2, args.exercise_workers, version)
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=folder_workers) as executor:
            for folder_name in folders:
                fut = executor.submit(
                    process_folder, folder_name, args.phase1, args.phase2, args.exercise_workers, version
                )
                futures[fut] = folder_name

            for fut in as_completed(futures):
                fname = futures[fut]
                try:
                    fut.result()
                except Exception as e:
                    tprint(f"[错误] {fname} 处理失败: {e}")

    t_total = time.time() - t_total_start
    tprint("\n" + "=" * 60)
    tprint(f"全部完成！总耗时: {t_total:.1f}s ({t_total / 60:.1f}min)")
    tprint("=" * 60)


if __name__ == "__main__":
    main()
