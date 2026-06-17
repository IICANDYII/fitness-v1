"""
optical_flow.py - 光流计算与摘要

从已抽帧的图片序列计算稠密光流（Farneback），
提供运动强度、主方向、周期性分析，供 Phase1/Phase2 prompt 使用。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from .extractor import FrameMeta


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

FLOW_RESIZE_W = 320
FLOW_RESIZE_H = 240
INTERVAL = 1.0           # 帧间隔（秒），1fps


# ──────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────

def _imread_gray(path: Path) -> np.ndarray | None:
    buf = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def _classify_direction(angle_deg: float) -> str:
    a = angle_deg % 360
    if 315 <= a or a < 45:
        return "RIGHT"
    if 45 <= a < 135:
        return "DOWN"
    if 135 <= a < 225:
        return "LEFT"
    return "UP"


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


# ──────────────────────────────────────────────
# 光流计算
# ──────────────────────────────────────────────

def compute_optical_flow(
    frame_metas: list[FrameMeta],
    base_dir: Path,
) -> list[dict]:
    """
    计算相邻帧之间的稠密光流。

    Args:
        frame_metas:  FrameMeta 列表（已按时间排序）
        base_dir:     帧图片根目录（frame_metas[i].path 相对于此目录）

    Returns:
        list[dict]，每个 dict 包含：
          frame_pair, time_sec, avg_flow, max_flow,
          motion_energy, dominant_angle, dominant_direction
    """
    print(f"[optical_flow] 计算光流：{len(frame_metas)} 帧")
    flow_data: list[dict] = []

    for i in range(len(frame_metas) - 1):
        path1 = base_dir / frame_metas[i].path
        path2 = base_dir / frame_metas[i + 1].path

        img1 = _imread_gray(path1)
        img2 = _imread_gray(path2)
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

        t = frame_metas[i].timestamp
        flow_data.append({
            "frame_pair": [frame_metas[i].index, frame_metas[i + 1].index],
            "time_sec": round(t, 1),
            "avg_flow": round(avg_flow, 3),
            "max_flow": round(max_flow, 3),
            "motion_energy": round(motion_energy, 3),
            "dominant_angle": round(dominant_angle, 1),
            "dominant_direction": _classify_direction(dominant_angle),
        })

        if (i + 1) % 50 == 0:
            print(f"[optical_flow]   已处理 {i + 1}/{len(frame_metas) - 1} 帧对")

    print(f"[optical_flow]   完成，共 {len(flow_data)} 帧对")
    return flow_data


def analyze_periodicity(
    flow_data: list[dict],
    window_sec: int = 20,
) -> list[dict]:
    """自相关周期性分析。"""
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

        search = autocorr[min_lag: max_lag + 1]
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


# ──────────────────────────────────────────────
# 光流摘要格式化（给 LLM 看）
# ──────────────────────────────────────────────

def format_flow_for_period(
    flow_data: list[dict],
    periodicity: list[dict],
) -> str:
    """Phase 1 全局光流摘要。"""
    lines = [
        "=== 光流摘要（帧间运动趋势）===",
        f"总帧对数: {len(flow_data)}，帧间隔: {INTERVAL}s",
        "",
    ]
    chunk_sec = 10
    chunk_size = max(1, int(chunk_sec / INTERVAL))

    for i in range(0, len(flow_data), chunk_size):
        chunk = flow_data[i: i + chunk_size]
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


def summarize_window_flow(
    flow_data: list[dict],
    t_start: float,
    t_end: float,
) -> str:
    """Phase 1 单窗口光流摘要。"""
    seg = [d for d in flow_data if t_start - 0.5 <= d["time_sec"] <= t_end + 0.5]
    if not seg:
        return "  (无光流数据)"
    chunk_sec = 5
    chunk_size = max(1, int(chunk_sec / INTERVAL))
    lines: list[str] = []
    for i in range(0, len(seg), chunk_size):
        chunk = seg[i: i + chunk_size]
        ts = chunk[0]["time_sec"]
        te = chunk[-1]["time_sec"] + INTERVAL
        avg = float(np.mean([d["avg_flow"] for d in chunk]))
        main_dir = Counter(d["dominant_direction"] for d in chunk).most_common(1)[0][0]
        lines.append(f"  [{ts:.0f}s-{te:.0f}s] {_intensity_label(avg)}({avg:.1f}), {main_dir}")
    return "\n".join(lines)


def format_flow_for_exercise(
    flow_data: list[dict],
    start_sec: float,
    end_sec: float,
) -> str:
    """Phase 2 单 EXERCISE 区间光流摘要。"""
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
            chunk = seg[i: i + cs]
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

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 缓存读写
# ──────────────────────────────────────────────

def save_flow(
    flow_data: list[dict],
    periodicity: list[dict],
    total_keyframes: int,
    path: Path,
):
    from datetime import datetime
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "total_keyframes": total_keyframes,
            "interval_sec": INTERVAL,
            "created_at": datetime.now().isoformat(),
            "flow": flow_data,
            "periodicity": periodicity,
        }, f, ensure_ascii=False, indent=2)
    print(f"[optical_flow] 已保存 → {path}")


def load_flow(path: Path) -> tuple[list[dict], list[dict]] | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        flow_data = saved.get("flow", []) if isinstance(saved, dict) else []
        periodicity = saved.get("periodicity", []) if isinstance(saved, dict) else []
        if flow_data:
            print(f"[optical_flow] 使用缓存：{len(flow_data)} 帧对（{path}）")
            return flow_data, periodicity
    except (OSError, json.JSONDecodeError) as e:
        print(f"[optical_flow] 缓存读取失败，将重新计算：{e}")
    return None
