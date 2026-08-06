"""
recognizer.py - 两阶段 LLM 识别

Phase 1：粗区间识别（period_recognize）
  - 全部窗口拼图 + 光流摘要 → 一次调用
  - 输出：segments（EXERCISE / REST）

Phase 2：运动精细识别（exercise_recognize）
  - 每个 EXERCISE 区间独立调用（可并发）
  - 输出：equipment, exercise, sets, phase1_adjustment

模型：Gemini 3 Flash（通过 nextrouter）
"""

from __future__ import annotations

import base64
import json
import os
import re
import threading
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests

from .extractor import FrameMeta
from .optical_flow import (
    format_flow_for_exercise,
    summarize_window_flow,
)
from .stitcher import (
    resolve_frame_path,
    sec_to_hhmmss,
    sec_to_mmss,
    mmss_to_sec,
    stitch_exercise_grid,
)
from .yaml_loader import PromptConfig


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

EXERCISE_BOUNDARY_PAD = 15        # EXERCISE 区间前后扩展秒数
MAX_EXERCISE_WORKERS = 4          # Phase 2 并发数
INTERVAL = 1.0                    # 帧间隔（秒）

# ── 标准动作名称映射 ──
_EXERCISE_MAPPING_PATH = Path(__file__).parent / "exercises_data" / "exercise_mapping_v1.json"

def _load_exercise_mapping() -> dict:
    if not _EXERCISE_MAPPING_PATH.exists():
        return {}
    with open(_EXERCISE_MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

_EXERCISE_MAPPING: dict = _load_exercise_mapping()

def _build_standard_names_prompt() -> str:
    """构建标准动作名称列表，供 prompt 使用。"""
    if not _EXERCISE_MAPPING:
        return ""
    lines = ["### 标准动作名称列表（你的输出必须从中选择）\n"]
    lines.append("| exercise_id | exercise（动作名称） | equipment（器械名称） | 训练部位 |")
    lines.append("|------------|---------------------|---------------------|---------|")
    for eid, info in _EXERCISE_MAPPING.items():
        ex_name = info.get("product_action_cn", "")
        equip = info.get("standard_equipment", "")
        part = info.get("training_part_cn", "")
        lines.append(f"| {eid} | {ex_name} | {equip} | {part} |")
    lines.append("")
    lines.append("**重要约束：**")
    lines.append("- `exercise` 字段必须填写上表中 exercise（动作名称）列的值，不得自创名称")
    lines.append("- 如果表中名称含 `/`（如 `健身车/动感单车`），选择最匹配的一个即可")
    lines.append("- `exercise_id` 字段填写上表中对应的 exercise_id")
    lines.append("- `equipment` 字段用中文填写器械名称（如 跑步机、龙门架、杠铃、史密斯机、哑铃 等），不要填英文的 standard_equipment")
    lines.append("- 如果动作确实不在列表中，exercise 填 `UNKNOWN_ACTION`，exercise_id 填空字符串")
    lines.append("")
    return "\n".join(lines)

def _build_alias_map() -> dict[str, tuple[str, str]]:
    """构建别名 → (exercise_id, product_action_cn) 的映射，用于后处理标准化。"""
    alias_map: dict[str, tuple[str, str]] = {}
    for eid, info in _EXERCISE_MAPPING.items():
        cn = info.get("product_action_cn", "")
        for name in cn.split("/"):
            name = name.strip()
            if name:
                alias_map[name] = (eid, cn)
        alias_map[cn] = (eid, cn)
        alias_map[eid] = (eid, cn)
    return alias_map

_ALIAS_MAP: dict[str, tuple[str, str]] = _build_alias_map()

def _normalize_exercise_name(exercise: str) -> tuple[str, str | None]:
    """将 LLM 输出的动作名称标准化为映射表中的名称。
    Returns: (标准名称, exercise_id) 或 (原名称, None) 如果没匹配到。
    """
    if not exercise or not _ALIAS_MAP:
        return exercise, None
    ex = exercise.strip()
    if ex in _ALIAS_MAP:
        eid, cn = _ALIAS_MAP[ex]
        return cn, eid
    for alias, (eid, cn) in _ALIAS_MAP.items():
        if alias in ex or ex in alias:
            return cn, eid
    return ex, None

_print_lock = threading.Lock()


def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


# ──────────────────────────────────────────────
# IMU 数据处理
# ──────────────────────────────────────────────

IMU_WINDOW_SEC = 30  # Phase 1 摘要分段窗口大小（秒）

# IMU 记录类型别名：(t_rel, acc_mag, gyro_mag, ax, ay, az)
ImuRecord = tuple[float, float, float, float, float, float]


def load_imu_data(imu_path: Path) -> list[ImuRecord] | None:
    """
    解析 IMU_data.txt，返回 [(t_rel, acc_mag, gyro_mag, ax, ay, az), ...] 列表。
    t_rel 为相对于第一条记录的秒数。
    保留 ax/ay/az 轴向加速度用于姿态分类。
    文件不存在或解析失败则返回 None。
    """
    if not imu_path.exists():
        return None

    records: list[ImuRecord] = []
    t0 = None

    try:
        with open(imu_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return None

    if len(lines) < 2:
        return None

    from datetime import datetime as _dt

    for line in lines[1:]:  # 跳过表头
        parts = line.strip().split("\t")
        if len(parts) < 9:
            continue
        try:
            dt = _dt.fromisoformat(parts[0])
            if t0 is None:
                t0 = dt
            t_rel = (dt - t0).total_seconds()

            acc_x, acc_y, acc_z = float(parts[2]), float(parts[3]), float(parts[4])
            gyro_x, gyro_y, gyro_z = float(parts[5]), float(parts[6]), float(parts[7])

            acc_mag = (acc_x ** 2 + acc_y ** 2 + acc_z ** 2) ** 0.5
            gyro_mag = (gyro_x ** 2 + gyro_y ** 2 + gyro_z ** 2) ** 0.5

            records.append((t_rel, acc_mag, gyro_mag, acc_x, acc_y, acc_z))
        except (ValueError, IndexError):
            continue

    return records if records else None


def _gyro_label(gyro_mean: float) -> str:
    if gyro_mean > 30:
        return "高强度运动"
    if gyro_mean > 10:
        return "中等运动"
    if gyro_mean > 3:
        return "轻微运动"
    return "静止/休息"


def _acc_std_label(acc_std: float) -> str:
    if acc_std > 0.35:
        return "高"
    if acc_std > 0.15:
        return "中高"
    if acc_std > 0.05:
        return "低"
    return "静止"


def _posture_from_az(az_mean: float) -> str:
    """基于胸部佩戴 IMU 的 Z 轴加速度均值推断用户姿态。"""
    if az_mean > -0.35:
        return "仰卧"
    if az_mean > -0.78:
        return "俯身"
    if az_mean > -0.88:
        return "坐姿"
    return "站姿"


def _count_acc_peaks(acc_vals: list[float], min_prominence: float = 0.15) -> int:
    """简单峰值计数：检测加速度幅值中的局部极大值。"""
    if len(acc_vals) < 5:
        return 0
    mean_acc = sum(acc_vals) / len(acc_vals)
    threshold = mean_acc + min_prominence
    peaks = 0
    for i in range(2, len(acc_vals) - 2):
        if (acc_vals[i] > threshold
                and acc_vals[i] >= acc_vals[i - 1]
                and acc_vals[i] >= acc_vals[i + 1]
                and acc_vals[i] > acc_vals[i - 2]
                and acc_vals[i] > acc_vals[i + 2]):
            peaks += 1
    return peaks


def _detect_rest_periods(
    imu_records: list[ImuRecord],
    t_start: float,
    t_end: float,
    window_sec: float = 3.0,
    stride_sec: float = 1.0,
    rest_threshold: float = 0.05,
    min_rest_sec: float = 10.0,
) -> list[dict]:
    """在 EXERCISE 区间内检测组间休息段（acc_std 低谷段）。"""
    recs = [r for r in imu_records if t_start <= r[0] <= t_end]
    if len(recs) < 10:
        return []

    rest_windows = []
    t = t_start
    while t + window_sec <= t_end:
        w_recs = [r for r in recs if t <= r[0] < t + window_sec]
        if len(w_recs) >= 3:
            acc_vals = [r[1] for r in w_recs]
            mean_a = sum(acc_vals) / len(acc_vals)
            acc_std = (sum((a - mean_a) ** 2 for a in acc_vals) / len(acc_vals)) ** 0.5
            rest_windows.append((t, t + window_sec, acc_std))
        t += stride_sec

    # 合并连续低 acc_std 窗口为休息段
    periods = []
    cur_start = None
    for (ws, we, std) in rest_windows:
        if std < rest_threshold:
            if cur_start is None:
                cur_start = ws
            cur_end = we
        else:
            if cur_start is not None:
                if cur_end - cur_start >= min_rest_sec:
                    periods.append({
                        "start_sec": cur_start,
                        "end_sec": cur_end,
                        "start_time": sec_to_hhmmss(cur_start),
                        "end_time": sec_to_hhmmss(cur_end),
                        "duration_sec": round(cur_end - cur_start, 1),
                    })
                cur_start = None
    if cur_start is not None and cur_end - cur_start >= min_rest_sec:
        periods.append({
            "start_sec": cur_start,
            "end_sec": cur_end,
            "start_time": sec_to_hhmmss(cur_start),
            "end_time": sec_to_hhmmss(cur_end),
            "duration_sec": round(cur_end - cur_start, 1),
        })
    return periods


def format_imu_for_phase1(
    imu_records: list[ImuRecord],
    total_dur: float,
    window_sec: float = IMU_WINDOW_SEC,
) -> str:
    """生成整体 IMU 综合摘要（按时间窗口），供 Phase 1 辅助 EXERCISE/REST 区分。
    v6 增强：加入 acc_std 运动强度、欧拉角姿态分类、加速度峰值计数。
    """
    if not imu_records:
        return ""

    imu_dur = imu_records[-1][0]
    lines = [
        "[IMU传感器综合摘要]",
        f"IMU总时长: {imu_dur:.0f}s  视频时长: {total_dur:.0f}s  "
        f"(两者按录制起始时间对齐)",
        f"分段（每 {window_sec:.0f}s）— 含运动强度/姿态/峰值计数：",
    ]

    wi = 0
    while True:
        t_s = wi * window_sec
        t_e = (wi + 1) * window_sec
        if t_s >= total_dur:
            break
        wi += 1

        window_recs = [r for r in imu_records if t_s <= r[0] < t_e]
        if not window_recs:
            lines.append(f"  {sec_to_hhmmss(t_s)}~{sec_to_hhmmss(min(t_e, total_dur))}  无IMU数据")
            continue

        gyro_vals = [r[2] for r in window_recs]
        acc_vals = [r[1] for r in window_recs]
        az_vals = [r[5] for r in window_recs]

        gyro_mean = sum(gyro_vals) / len(gyro_vals)
        gyro_max = max(gyro_vals)
        acc_mean = sum(acc_vals) / len(acc_vals)
        acc_std = (sum((a - acc_mean) ** 2 for a in acc_vals) / len(acc_vals)) ** 0.5
        az_mean = sum(az_vals) / len(az_vals)

        posture = _posture_from_az(az_mean)
        intensity = _acc_std_label(acc_std)
        peak_count = _count_acc_peaks(acc_vals)

        # 综合判断提示
        hint = ""
        if acc_std > 0.15 and peak_count >= 3:
            hint = f" → 可能在做{posture}力量训练"
        elif acc_std > 0.05 and posture == "站姿":
            hint = " → 可能在行走或调整位置"
        elif acc_std <= 0.05:
            hint = f" → 静止休息({posture})"

        t_s_str = sec_to_hhmmss(t_s)
        t_e_str = sec_to_hhmmss(min(t_e, total_dur))
        lines.append(
            f"  {t_s_str}~{t_e_str}  "
            f"运动强度: {intensity}(acc_std={acc_std:.2f})  "
            f"姿态: {posture}  "
            f"峰值计数: {peak_count}  "
            f"(角速度均值={gyro_mean:.1f}, 峰值={gyro_max:.1f})"
            f"{hint}"
        )

    return "\n".join(lines)


def format_imu_for_exercise(
    imu_records: list[ImuRecord],
    t_start: float,
    t_end: float,
) -> str:
    """生成单个 EXERCISE 区间的 IMU 综合摘要，供 Phase 2 辅助动作识别。
    v8 增强：按子窗口细分、峰值计数(rep hint)、组间休息检测。
    """
    if not imu_records:
        return ""

    pad = 5.0
    window_recs = [r for r in imu_records if (t_start - pad) <= r[0] <= (t_end + pad)]

    if not window_recs:
        return (
            f"[IMU传感器数据] "
            f"该时间段 ({sec_to_hhmmss(t_start)}~{sec_to_hhmmss(t_end)}) 无IMU记录"
        )

    # 整体统计
    gyro_vals = [r[2] for r in window_recs]
    acc_vals = [r[1] for r in window_recs]
    az_vals = [r[5] for r in window_recs]

    gyro_mean = sum(gyro_vals) / len(gyro_vals)
    gyro_max = max(gyro_vals)
    acc_mean = sum(acc_vals) / len(acc_vals)
    acc_max = max(acc_vals)
    acc_std = (sum((a - acc_mean) ** 2 for a in acc_vals) / len(acc_vals)) ** 0.5
    az_mean = sum(az_vals) / len(az_vals)

    posture = _posture_from_az(az_mean)
    intensity = _acc_std_label(acc_std)
    total_peaks = _count_acc_peaks(acc_vals)

    # 周期性估计
    threshold = gyro_mean
    transitions = sum(
        1 for i in range(1, len(gyro_vals))
        if (gyro_vals[i - 1] > threshold) != (gyro_vals[i] > threshold)
    )
    period_hint = ""
    if transitions >= 4 and (t_end - t_start) > 0:
        est_period = (t_end - t_start) / (transitions / 2)
        period_hint = f"  估计运动周期≈{est_period:.1f}s"

    label = _gyro_label(gyro_mean)

    lines = [
        f"[IMU传感器综合数据（运动段 {sec_to_hhmmss(t_start)}~{sec_to_hhmmss(t_end)}）]",
        f"整体: 角速度均值={gyro_mean:.1f}°/s 峰值={gyro_max:.1f}°/s{period_hint}",
        f"  加速度: 均值={acc_mean:.2f}g 峰值={acc_max:.2f}g std={acc_std:.3f}g",
        f"  运动强度: {intensity}({label})  姿态: {posture}  加速度峰值计数(rep_count_hint): {total_peaks}",
    ]

    # 子窗口细分（10s 窗口）
    sub_window = 10.0
    seg_recs = [r for r in imu_records if t_start <= r[0] <= t_end]
    if len(seg_recs) > 20 and (t_end - t_start) > sub_window * 1.5:
        lines.append(f"子窗口细分（每{sub_window:.0f}s）：")
        t = t_start
        while t < t_end:
            te = min(t + sub_window, t_end)
            sw_recs = [r for r in seg_recs if t <= r[0] < te]
            if len(sw_recs) >= 3:
                sw_acc = [r[1] for r in sw_recs]
                sw_az = [r[5] for r in sw_recs]
                sw_mean = sum(sw_acc) / len(sw_acc)
                sw_std = (sum((a - sw_mean) ** 2 for a in sw_acc) / len(sw_acc)) ** 0.5
                sw_az_m = sum(sw_az) / len(sw_az)
                sw_peaks = _count_acc_peaks(sw_acc)
                sw_posture = _posture_from_az(sw_az_m)
                sw_int = _acc_std_label(sw_std)
                lines.append(
                    f"  {sec_to_hhmmss(t)}~{sec_to_hhmmss(te)}  "
                    f"强度:{sw_int}(acc_std={sw_std:.3f})  "
                    f"姿态:{sw_posture}  峰值:{sw_peaks}"
                )
            t += sub_window

    # 组间休息检测
    rest_periods = _detect_rest_periods(imu_records, t_start, t_end)
    if rest_periods:
        lines.append("IMU检测到的组间休息段（acc_std < 0.05g 持续 > 10s）：")
        for rp in rest_periods:
            lines.append(
                f"  休息: {rp['start_time']}~{rp['end_time']} ({rp['duration_sec']}s)"
            )

    return "\n".join(lines)


# ──────────────────────────────────────────────
# LLM 调用
# ──────────────────────────────────────────────

def _gemini_generate(
    system_prompt: str,
    user_content: list[dict],
    max_retries: int = 5,
) -> str:
    """调用 Gemini API（通过 nextrouter）。"""
    api_key = os.getenv("NEXTROUTER_API_KEY")
    base_url = os.getenv("NEXTROUTER_BASE_URL", "https://nextrouter.cc")
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")

    if not api_key:
        raise EnvironmentError("未设置 NEXTROUTER_API_KEY")

    # 确保 base_url 以 /v1 结尾
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    url = f"{base_url}/chat/completions"
    img_count = sum(1 for c in user_content if c.get("type") == "image_url")
    tprint(f"  → LLM 请求: model={model}, {img_count} 张图片")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 16384,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 绕过 Windows 注册表系统代理，直连 API 网关
    session = requests.Session()
    session.trust_env = False

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=600)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            wait = min(30 * attempt, 180)
            tprint(f"  [网络错误] {type(e).__name__}: {e}")
            if attempt < max_retries:
                tprint(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time_module.sleep(wait)
                continue
            raise

        if resp.status_code == 429:
            wait = 60 * attempt
            tprint(f"  [429] 等待 {wait}s 后重试（{attempt}/{max_retries}）...")
            time_module.sleep(wait)
            continue
        if resp.status_code >= 500:
            wait = min(30 * attempt, 180)
            tprint(f"  [HTTP {resp.status_code}] 服务端错误")
            if attempt < max_retries:
                tprint(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time_module.sleep(wait)
                continue
        if not resp.ok:
            tprint(f"  [HTTP {resp.status_code}] {resp.text[:300]}")
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        finish = data["choices"][0].get("finish_reason", "")
        if not content:
            tprint(f"  [警告] 空响应! finish_reason={finish!r} 完整响应: {str(data)[:500]}")
        return content or ""

    raise RuntimeError("超过最大重试次数")


def _image_to_data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()


_DIRTY_CHAR_RE = re.compile(r'[?\x00-\x1f]')


_UNKNOWN_EXERCISE_PATTERNS = {
    "unknown_action", "unknown", "unknown_equipment",
    "未知动作", "未知", "不确定", "无法识别",
}


def _is_unknown_exercise(exercise: str) -> bool:
    """判断动作名称是否属于'未知/无法识别'类别。"""
    if not exercise:
        return True
    val = exercise.strip().lower()
    if val in _UNKNOWN_EXERCISE_PATTERNS:
        return True
    # 覆盖以 unknown 开头的任意变体（如 unknown_xxx）
    if val.startswith("unknown"):
        return True
    return False


def _validate_exercise_result(data: dict) -> list[str]:
    """Validate Phase 2 Gemini response structure. Returns list of error messages."""
    errors = []
    if not isinstance(data, dict):
        return [f"result is {type(data).__name__}, expected dict"]

    for field in ("equipment", "exercise"):
        val = data.get(field)
        if val is not None and not isinstance(val, str):
            errors.append(f"{field} is {type(val).__name__}({val!r}), expected str")
        elif isinstance(val, str) and _DIRTY_CHAR_RE.search(val):
            errors.append(f"{field} contains illegal chars: {val!r}")

    conf = data.get("confidence")
    if conf is not None:
        try:
            cv = float(conf)
            if not (0.0 <= cv <= 1.0):
                errors.append(f"confidence out of range: {cv}")
        except (TypeError, ValueError):
            errors.append(f"confidence not numeric: {conf!r}")

    sets_val = data.get("sets")
    if sets_val is not None:
        if not isinstance(sets_val, list):
            errors.append(f"sets is {type(sets_val).__name__}, expected list")
        else:
            for i, s in enumerate(sets_val):
                if not isinstance(s, dict):
                    errors.append(f"sets[{i}] is {type(s).__name__}, expected dict")
                else:
                    reps = s.get("reps")
                    if reps is not None and not isinstance(reps, (int, float)):
                        errors.append(f"sets[{i}].reps is {type(reps).__name__}({reps!r})")

    for field in ("total_sets", "total_reps"):
        val = data.get(field)
        if val is not None and not isinstance(val, (int, float)):
            errors.append(f"{field} is {type(val).__name__}({val!r}), expected int")

    return errors


def _sanitize_exercise_result(data: dict) -> dict:
    """Fix recoverable dirty data in Phase 2 result."""
    if not isinstance(data, dict):
        return data
    for field in ("equipment", "exercise", "exercise_id"):
        val = data.get(field)
        if isinstance(val, str):
            data[field] = _DIRTY_CHAR_RE.sub('', val).strip()
        elif val is not None and not isinstance(val, str):
            data[field] = str(val)

    if "confidence" in data:
        try:
            data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
        except (TypeError, ValueError):
            data["confidence"] = 0.0

    sets_val = data.get("sets")
    if isinstance(sets_val, list):
        clean_sets = []
        for s in sets_val:
            if not isinstance(s, dict):
                continue
            if "reps" in s:
                try:
                    s["reps"] = int(float(s["reps"]))
                except (TypeError, ValueError):
                    s["reps"] = 0
            clean_sets.append(s)
        data["sets"] = clean_sets

    for field in ("total_sets", "total_reps"):
        if field in data:
            try:
                data[field] = int(float(data[field]))
            except (TypeError, ValueError):
                data[field] = 0

    if "sets" in data and isinstance(data["sets"], list):
        if "total_sets" not in data:
            data["total_sets"] = len(data["sets"])
        if "total_reps" not in data:
            data["total_reps"] = sum(s.get("reps", 0) for s in data["sets"] if isinstance(s, dict))

    return data


def _extract_json(text: str):
    """从 LLM 响应中提取 JSON。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试找 { 或 [
        for sc, ec in [("{", "}"), ("[", "]")]:
            s = text.find(sc)
            e = text.rfind(ec)
            if s != -1 and e != -1:
                try:
                    return json.loads(text[s:e + 1])
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"无法解析 JSON：\n{text[:500]}")


def _save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tprint(f"  [OK] 已保存: {path}")


# ──────────────────────────────────────────────
# Phase 1：阶段划分（一次性调用）
# ──────────────────────────────────────────────

def run_phase1(
    frame_metas: list[FrameMeta],
    grids: list[dict],
    flow_data: list[dict],
    prompt: PromptConfig,
    output_dir: Path,
    imu_records: list[ImuRecord] | None = None,
) -> list[dict]:
    """
    Phase 1：将所有窗口拼图 + 光流摘要一次性传给 LLM。

    Args:
        frame_metas:  全部帧元数据
        grids:        stitch_phase1_grids 的输出
        flow_data:    光流数据
        prompt:       phase1 PromptConfig
        output_dir:   结果输出目录
        imu_records:  IMU 数据（可选），由 load_imu_data() 返回

    Returns:
        list[dict]（segments）
    """
    tprint(f"\n{'=' * 60}")
    tprint(f"Phase 1: 阶段划分 ({Path(prompt.source_file).name})")
    tprint(f"{'=' * 60}")

    total_dur = frame_metas[-1].timestamp if frame_metas else 0

    # ── 大视频分块处理 ──
    if len(grids) > PHASE1_CHUNK_THRESHOLD:
        tprint(f"  视频较大 ({len(grids)} grids > {PHASE1_CHUNK_THRESHOLD})，启用分块处理")
        chunks = []
        i = 0
        while i < len(grids):
            end = min(i + PHASE1_CHUNK_SIZE, len(grids))
            chunks.append(grids[i:end])
            i = end - PHASE1_CHUNK_OVERLAP if end < len(grids) else end

        tprint(f"  分为 {len(chunks)} 块")
        all_segs = []
        for ci, chunk in enumerate(chunks):
            segs = _run_phase1_single_chunk(
                frame_metas, chunk, flow_data, prompt,
                ci, len(chunks), total_dur,
                imu_records=imu_records,
            )
            all_segs.append(segs)

        segments = _merge_chunked_segments(all_segs)

        # 保存
        output_dir.mkdir(parents=True, exist_ok=True)
        version_tag = Path(prompt.source_file).stem.replace("phase1_period_recognize_", "")
        meta = {
            "version": version_tag,
            "phase1_prompt": Path(prompt.source_file).name,
            "total_1fps_frames": len(frame_metas),
            "num_windows": len(grids),
            "num_chunks": len(chunks),
            "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
            "created_at": datetime.now().isoformat(),
            "segments": segments,
        }
        _save_json(meta, output_dir / "period_result.json")

        ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
        tprint(f"  Phase 1 (分块) 完成: {len(segments)} 段, 其中 EXERCISE {ex_count} 段")
        for seg in segments:
            tprint(f"    {seg.get('start_time', '?')} → {seg.get('end_time', '?')}  "
                   f"{seg.get('state', '?')}  conf={seg.get('confidence', '?')}  "
                   f"{seg.get('reason', '')}")
        return segments

    # ── 构造 user content ──
    imu_phase1_text = format_imu_for_phase1(imu_records or [], total_dur) if imu_records else ""

    intro = (
        f"以下是一段健身视频的关键帧（第一人称胸前相机），"
        f"共 {len(frame_metas)} 帧 (1fps)，总时长 {total_dur:.0f}s ({sec_to_hhmmss(total_dur)})。\n\n"
        f"按时间顺序分成 {len(grids)} 个窗口，每个窗口一张网格图 + 对应光流摘要。\n"
        f"网格读取顺序：从左到右、从上到下。\n\n"
        f"请综合所有窗口的关键帧画面与光流信息，将整段视频划分为 EXERCISE / REST 两种状态，\n"
        f"并在每个时间段上标注用户当前最可能交互的器材名称。\n\n"
        f"关键规则：\n"
        f"- 第一人称胸前相机，用户本人不完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象\n"
        f"- 仅关注用户双手、正在接触的器械、视角运动变化\n"
        f"- 用户双手与器械持续交互 + 光流显示周期性运动 → EXERCISE\n"
        f"- 不同器械上的运动必须拆分为不同 EXERCISE 段（如跑步机 → 深蹲架 = 两段独立 EXERCISE，中间有 REST）\n"
        f"- 器械切换、行走、调整位置、组间休息 → 全部归为 REST\n"
        f"- 每个 segment 都必须填写 equipment 字段（当前最可能交互的器材），REST 段也不例外\n"
        f"- 相同器材的连续使用区间（含组间休息）视为一个器材交互周期\n"
    )
    if imu_phase1_text:
        intro += f"\n\n{imu_phase1_text}\n"

    user_content: list[dict] = [{"type": "text", "text": intro}]

    for g in grids:
        flow_text = summarize_window_flow(flow_data, g["time_start"], g["time_end"])
        header = (
            f"\n--- 窗口 {g['grid_index'] + 1}/{len(grids)} "
            f"({sec_to_hhmmss(g['time_start'])} ~ {sec_to_hhmmss(g['time_end'])}, "
            f"{g['frame_count']} 帧, {g['cols']}×{g['rows']}) ---\n"
            f"光流:\n{flow_text}"
        )
        user_content.append({"type": "text", "text": header})
        user_content.append({
            "type": "image_url",
            "image_url": {"url": _image_to_data_url(g["jpeg_bytes"])},
        })

    output_fmt = (
        f"\n\n请输出覆盖 00:00:00 ~ {sec_to_hhmmss(total_dur)} 的完整时间线，"
        f"严格按 JSON 格式，不要包含 Markdown 代码块或注释：\n"
        f'{{"segments": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", '
        f'"state": "EXERCISE|REST", "confidence": 0.0~1.0, '
        f'"reason": "判断依据", '
        f'"equipment": "器材英文名或UNKNOWN", '
        f'"posture": "standing|seated|supine|prone|bending"'
        f'}}], '
        f'"equipment_timeline": [{{"time": "HH:MM:SS", "equipment": "器材名", "event": "开始使用|切换到新器材"}}]}}'
    )
    user_content.append({"type": "text", "text": output_fmt})

    # ── 调用 LLM ──
    raw = _gemini_generate(prompt.system, user_content)
    tprint(f"  响应长度: {len(raw)} 字符")

    # 保存原始响应
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "period_raw_response.txt").write_text(raw, encoding="utf-8")

    # ── 解析 JSON ──
    try:
        result = _extract_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        tprint(f"  [警告] JSON 解析失败: {e}")
        result = {"raw_response": raw}

    segments = []
    equipment_timeline = []
    if isinstance(result, dict):
        segments = result.get("segments", [])
        equipment_timeline = result.get("equipment_timeline", [])
    elif isinstance(result, list):
        segments = result

    # 补充 start_sec / end_sec
    for seg in segments:
        if "start_time" in seg and "start_sec" not in seg:
            seg["start_sec"] = mmss_to_sec(str(seg["start_time"]))
        if "end_time" in seg and "end_sec" not in seg:
            seg["end_sec"] = mmss_to_sec(str(seg["end_time"]))

    # 保存结果
    version_tag = Path(prompt.source_file).stem.replace("phase1_period_recognize_", "")
    meta = {
        "version": version_tag,
        "phase1_prompt": Path(prompt.source_file).name,
        "total_1fps_frames": len(frame_metas),
        "num_windows": len(grids),
        "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "segments": segments,
        "equipment_timeline": equipment_timeline,
    }
    _save_json(meta, output_dir / "period_result.json")

    ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
    tprint(f"  Phase 1 完成: {len(segments)} 段, 其中 EXERCISE {ex_count} 段")
    for seg in segments:
        equip = seg.get("equipment", "")
        equip_str = f"  [{equip}]" if equip else ""
        tprint(f"    {seg.get('start_time', '?')} → {seg.get('end_time', '?')}  "
               f"{seg.get('state', '?')}  conf={seg.get('confidence', '?')}{equip_str}  "
               f"{seg.get('reason', '')}")
    if equipment_timeline:
        tprint(f"  器材切换事件: {len(equipment_timeline)} 个")
        for et in equipment_timeline:
            tprint(f"    {et.get('time', '?')}  {et.get('equipment', '?')}  {et.get('event', '')}")

    return segments


# ── Phase 1 分块处理（大视频）──

PHASE1_CHUNK_SIZE = 20      # 每块最多 20 个窗口
PHASE1_CHUNK_OVERLAP = 2    # 相邻块重叠 2 个窗口
PHASE1_CHUNK_THRESHOLD = 25 # 超过此数量才分块


def _run_phase1_single_chunk(
    frame_metas: list[FrameMeta],
    grids_chunk: list[dict],
    flow_data: list[dict],
    prompt: PromptConfig,
    chunk_idx: int,
    total_chunks: int,
    total_dur: float,
    imu_records: list[ImuRecord] | None = None,
) -> list[dict]:
    """对一个 grid 子集执行 Phase 1 识别，返回 segments。"""
    chunk_start = grids_chunk[0]["time_start"]
    chunk_end = grids_chunk[-1]["time_end"]

    imu_chunk_text = (
        format_imu_for_phase1(imu_records, chunk_end, window_sec=IMU_WINDOW_SEC)
        if imu_records else ""
    )

    intro = (
        f"以下是一段健身视频的关键帧（第一人称胸前相机），"
        f"共 {len(frame_metas)} 帧 (1fps)，总时长 {total_dur:.0f}s ({sec_to_hhmmss(total_dur)})。\n\n"
        f"当前为第 {chunk_idx + 1}/{total_chunks} 段，"
        f"时间范围 {sec_to_hhmmss(chunk_start)} ~ {sec_to_hhmmss(chunk_end)}，"
        f"包含 {len(grids_chunk)} 个窗口。\n"
        f"网格读取顺序：从左到右、从上到下。\n\n"
        f"请将本段时间范围内的视频划分为 EXERCISE / REST 两种状态。\n\n"
        f"关键规则：\n"
        f"- 第一人称胸前相机，用户本人不完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象\n"
        f"- 仅关注用户双手、正在接触的器械、视角运动变化\n"
        f"- 用户双手与器械持续交互 + 光流显示周期性运动 → EXERCISE\n"
        f"- 不同器械上的运动必须拆分为不同 EXERCISE 段\n"
        f"- 器械切换、行走、调整位置、组间休息 → 全部归为 REST\n"
    )
    if imu_chunk_text:
        intro += f"\n\n{imu_chunk_text}\n"

    user_content: list[dict] = [{"type": "text", "text": intro}]

    for g in grids_chunk:
        flow_text = summarize_window_flow(flow_data, g["time_start"], g["time_end"])
        header = (
            f"\n--- 窗口 {g['grid_index'] + 1} "
            f"({sec_to_hhmmss(g['time_start'])} ~ {sec_to_hhmmss(g['time_end'])}, "
            f"{g['frame_count']} 帧, {g['cols']}×{g['rows']}) ---\n"
            f"光流:\n{flow_text}"
        )
        user_content.append({"type": "text", "text": header})
        user_content.append({
            "type": "image_url",
            "image_url": {"url": _image_to_data_url(g["jpeg_bytes"])},
        })

    output_fmt = (
        f"\n\n请输出覆盖 {sec_to_hhmmss(chunk_start)} ~ {sec_to_hhmmss(chunk_end)} 的时间线，"
        f"严格按 JSON 格式，不要包含 Markdown 代码块或注释：\n"
        f'{{"segments": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", '
        f'"state": "EXERCISE|REST", "confidence": 0.0~1.0, '
        f'"reason": "判断依据", '
        f'"equipment": "器材英文名或UNKNOWN", '
        f'"posture": "standing|seated|supine|prone|bending"'
        f'}}], '
        f'"equipment_timeline": [{{"time": "HH:MM:SS", "equipment": "器材名", "event": "开始使用|切换到新器材"}}]}}'
    )
    user_content.append({"type": "text", "text": output_fmt})

    tprint(f"  [chunk {chunk_idx + 1}/{total_chunks}] "
           f"{sec_to_hhmmss(chunk_start)}~{sec_to_hhmmss(chunk_end)}, "
           f"{len(grids_chunk)} grids")

    raw = _gemini_generate(prompt.system, user_content)

    try:
        result = _extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        return []

    segs = []
    if isinstance(result, dict):
        segs = result.get("segments", [])
    elif isinstance(result, list):
        segs = result

    for seg in segs:
        if "start_time" in seg and "start_sec" not in seg:
            seg["start_sec"] = mmss_to_sec(str(seg["start_time"]))
        if "end_time" in seg and "end_sec" not in seg:
            seg["end_sec"] = mmss_to_sec(str(seg["end_time"]))

    return segs


def _merge_chunked_segments(all_chunk_segs: list[list[dict]]) -> list[dict]:
    """合并分块结果，处理重叠区域的去重。"""
    if not all_chunk_segs:
        return []

    merged = []
    for segs in all_chunk_segs:
        for seg in segs:
            start = seg.get("start_sec", 0)
            end = seg.get("end_sec", 0)
            # 跳过与已有段完全重叠的
            duplicate = False
            for existing in merged:
                es = existing.get("start_sec", 0)
                ee = existing.get("end_sec", 0)
                overlap = min(end, ee) - max(start, es)
                duration = max(end - start, 1)
                if overlap / duration > 0.5:
                    duplicate = True
                    break
            if not duplicate:
                merged.append(seg)

    merged.sort(key=lambda s: s.get("start_sec", 0))

    # 修正相邻段的时间间隙/重叠
    for i in range(1, len(merged)):
        prev_end = merged[i - 1].get("end_sec", 0)
        curr_start = merged[i].get("start_sec", 0)
        if abs(curr_start - prev_end) <= 5:
            merged[i]["start_sec"] = prev_end
            merged[i]["start_time"] = sec_to_hhmmss(prev_end)

    return merged


# ──────────────────────────────────────────────
# Phase 2：单个 EXERCISE 识别
# ──────────────────────────────────────────────

def _recognize_one_exercise(
    seg: dict,
    frame_metas: list[FrameMeta],
    frames_dir: Path,
    output_dir: Path,
    flow_data: list[dict],
    system_prompt: str,
    imu_records: list[ImuRecord] | None = None,
    equipment_timeline: list[dict] | None = None,
) -> dict | None:
    """识别单个 EXERCISE 区间。"""
    seg_id = seg.get("segmentId", "?")
    t_start = seg.get("start_sec", 0.0)
    t_end = seg.get("end_sec", 0.0)
    dur = t_end - t_start

    tprint(f"\n  ── {seg_id}: {sec_to_hhmmss(t_start)} ~ {sec_to_hhmmss(t_end)} ({dur:.0f}s)")

    # 前后扩展
    total_dur = frame_metas[-1].timestamp if frame_metas else 0
    pad_start = max(0.0, t_start - EXERCISE_BOUNDARY_PAD)
    pad_end = min(total_dur, t_end + EXERCISE_BOUNDARY_PAD)
    tprint(f"    [{seg_id}] 扩展取帧范围: {sec_to_hhmmss(pad_start)} ~ {sec_to_hhmmss(pad_end)}")

    # 拼图
    result = stitch_exercise_grid(
        metas=frame_metas,
        frames_dir=frames_dir,
        output_dir=output_dir,
        start_sec=pad_start,
        end_sec=pad_end,
        seg_id=seg_id,
    )
    if result is None:
        tprint(f"    [{seg_id}] [警告] 无匹配帧，跳过")
        return None

    jpeg_bytes, g_cols, g_rows, frame_count = result

    # 提取进场帧原图（运动开始前 5 秒内的帧，此时用户已在器械旁/上，能看清器械细节）
    entrance_frames: list[bytes] = []
    ent_start = max(0.0, t_start - 5)
    ent_end = t_start + 3
    entrance_metas = [
        m for m in frame_metas
        if ent_start <= m.timestamp <= ent_end
    ][:3]
    for em in entrance_metas:
        img_path = resolve_frame_path(em, frames_dir, output_dir)
        if img_path:
            img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                if max(h, w) > 800:
                    scale = 800 / max(h, w)
                    img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
                if ok:
                    entrance_frames.append(bytes(buf))

    # 光流摘要
    flow_summary = format_flow_for_exercise(flow_data, t_start, t_end)

    # IMU 摘要
    imu_exercise_text = format_imu_for_exercise(imu_records or [], t_start, t_end) if imu_records else ""

    # 构造 user prompt
    phase1_reason = seg.get("reason", "")
    phase1_equipment = seg.get("equipment", "UNKNOWN")
    phase1_posture = seg.get("posture", "")
    phase1_context = ""
    if phase1_reason or phase1_equipment != "UNKNOWN":
        phase1_lines = []
        if phase1_reason:
            phase1_lines.append(f"  描述: {phase1_reason}")
        if phase1_equipment and phase1_equipment != "UNKNOWN":
            phase1_lines.append(f"  器材预识别: {phase1_equipment}（请根据关键帧独立验证）")
        if phase1_posture:
            phase1_lines.append(f"  用户姿态: {phase1_posture}")
        phase1_context = (
            f"- Phase 1 参考信息（器材名需独立验证）:\n" + "\n".join(phase1_lines) + "\n"
        )

    # 注入器材切换时间线（帮助 Phase 2 理解全局器材使用顺序）
    if equipment_timeline:
        timeline_lines = [f"- 器材切换时间线（Phase 1 全局识别结果）:"]
        for et in equipment_timeline:
            timeline_lines.append(f"  {et.get('time', '?')}  {et.get('equipment', '?')}  ({et.get('event', '')})")
        phase1_context += "\n".join(timeline_lines) + "\n"

    entrance_hint = ""
    if entrance_frames:
        entrance_hint = (
            f"\n**下面先展示 {len(entrance_frames)} 张进场帧原图（未经缩小），请仔细观察器械外观、"
            f"配件类型（宽横杆？绳索？D型把手？）、座椅、腿部挡板等细节：**\n\n"
        )

    user_text = (
        f"以下是 EXERCISE 段 [{seg_id}] 的关键帧网格图（第一人称胸前相机）：\n"
        f"- 网格列数: {g_cols}, 行数: {g_rows}\n"
        f"- 有效帧数: {frame_count}, 帧间隔: {INTERVAL:.1f}s\n"
        f"- 时间范围: {sec_to_hhmmss(t_start)} ~ {sec_to_hhmmss(t_end)} (共 {dur:.0f}s)\n"
        f"- 读取顺序: 从左到右、从上到下\n"
        f"- 注意: 网格图前 2~3 帧为进场帧（扩展取帧），可能包含器械全貌\n"
        f"{phase1_context}\n"
        f"---\n\n"
        f"{flow_summary}\n\n"
        + (f"{imu_exercise_text}\n\n" if imu_exercise_text else "")
        + f"---\n\n"
        f"## 器械识别规则（按优先级依次使用）\n\n"
        f"### 规则一：进场帧优先\n"
        f"训练时相机贴近器械只能看到局部，必须回看网格图前 2~3 帧（进场帧），\n"
        f"在那里寻找器械完整轮廓和环境特征。\n"
        f"进场帧与训练帧指向不同器械 → 以进场帧为准。\n\n"
        f"### 规则二：相机朝向 + 身体姿态 → 缩小器械范围\n"
        f"| 相机朝向 | 身体姿态 | 典型器械/动作 |\n"
        f"|---------|---------|-------------|\n"
        f"| 天花板/正上方 | 仰卧 | 卧推（杠铃/哑铃/史密斯）、仰卧飞鸟 |\n"
        f"| 地面/脚部 | 弯腰/俯身 | 硬拉、俯身划船、俯身飞鸟 |\n"
        f"| 平视器械（画面稳定） | 坐姿 | 坐姿器械（推胸机、肩推机、腿屈伸、腿弯举） |\n"
        f"| 平视器械（画面稳定） | 站姿 | 龙门架、哑铃弯举、侧平举 |\n"
        f"| 从下往上看横杆 | 悬挂（脚离地） | 引体向上、悬垂举腿 |\n"
        f"| 低角度看地面（无器械） | 俯卧/跪撑 | 俯卧撑、平板支撑 |\n"
        f"| 45°斜下方看踏板 | 坐姿/半躺 | 腿举机 |\n\n"
        f"### 规则三：龙门架绳索方向判定\n"
        f"龙门架通过【绳索来向】+【身体姿态（站/坐）】+【动作方向】三者共同判断，必须严格按下表逐项匹配：\n\n"
        f"**★ 龙门架动作判定总流程（必须按此顺序）：**\n"
        f"**第一步：判断身体姿态——站姿还是坐姿？**\n"
        f"- 坐姿（屁股坐在凳子/座椅上，相机视角从下往上看配重塔/滑轮） → 第二步A\n"
        f"- 站姿（双脚站立，相机视角平视或微微俯视） → 第二步B\n\n"
        f"**第二步A（坐姿）：判断绳索来向**\n"
        f"- 绳索从头顶上方垂下 → **高位下拉**（见规则 6A）\n"
        f"- 绳索从正前方低位水平拉来，可见踏脚板 → **坐姿绳索划船**\n\n"
        f"**第二步B（站姿）：判断绳索来向 + 动作方向**\n"
        f"| 绳索来向 | 动作方向 | 配件 | 判定 |\n"
        f"|---------|---------|------|-----|\n"
        f"| 从上方 | 肘部固定贴身两侧，仅前臂向下推压 | 直杆/V杆/绳索 | **绳索下压**（三头肌） |\n"
        f"| 从上方 | 双手在胸前合拢 | D型把手 | **高位夹胸** |\n"
        f"| 从上方 | 肘部抬高外展，手拉向面部两侧 | 绳索 | **面拉** |\n"
        f"| 从下方 | 双手向上弯举（前臂向肩膀方向弯曲） | 直杆/EZ杆/绳索 | **绳索弯举**（二头肌） |\n"
        f"| 从下方 | 双手向上飞鸟 | D型把手 | **低位夹胸** |\n"
        f"| 水平方向 | 向后拉至腹部 | 各种把手 | **绳索划船** |\n\n"
        f"**龙门架常见动作详细对比表：**\n\n"
        f"| 区分维度 | 绳索下压（三头下压） | 绳索弯举（二头弯举） | 面拉 | 高位下拉 |\n"
        f"|---------|-------------------|-------------------|------|--------|\n"
        f"| **身体姿态（第一判据）** | ★站姿 | ★站姿 | ★站姿 | ★坐姿 |\n"
        f"| **绳索来向（第二判据）** | ★从上方（高位滑轮） | ★从下方（低位滑轮） | ★从上方（中高位滑轮） | ★从上方（高位滑轮） |\n"
        f"| **肘部位置** | 肘部固定贴近身体两侧，全程不动 | 肘部固定贴近身体两侧，全程不动 | 肘部抬高至肩膀高度并向两侧外展 | 肘部从上方向身体两侧/后方收 |\n"
        f"| **手的运动方向** | 手从胸前向下推至大腿前方 | 手从大腿侧向上弯举至肩膀/胸前 | 手拉向面部/耳朵两侧 | 手从头顶拉至锁骨/胸口 |\n"
        f"| **第一人称视角** | 平视/微俯视，看到手向下方推 | 平视/微俯视，看到手从下方向上抬起 | 平视，看到手向面部方向收拢 | 从下往上看配重塔/滑轮，手从头顶拉下 |\n"
        f"| **常用配件** | 直杆/V杆/绳索 | 直杆/EZ曲杆/绳索 | 绳索（几乎只用绳索） | 宽杆/窄杆/V杆/绳索 |\n"
        f"| **训练部位** | 手臂（肱三头肌） | 手臂（肱二头肌） | 肩后束/上背 | 背部（背阔肌） |\n"
        f"| **光流特征** | UP/DOWN交替，幅度小 | UP/DOWN交替，幅度小 | FORWARD/BACKWARD为主 | UP/DOWN交替，幅度大 |\n\n"
        f"**绳索下压 vs 绳索弯举的关键区分（最易混淆，方向完全相反）：**\n"
        f"- ★ 绳索下压：绳索从【上方】来，手向【下方】推（发力方向向下）\n"
        f"- ★ 绳索弯举：绳索从【下方】来，手向【上方】举（发力方向向上）\n"
        f"- 看绳索连接的滑轮位置：滑轮在头顶以上 = 下压，滑轮在腰部以下 = 弯举\n"
        f"- 两者肘部都贴近身体两侧，但运动方向完全相反\n\n"
        f"**绳索下压细分（配件不同，动作名称相同，都叫【绳索下压】）：**\n"
        f"- 直杆下压：用直杆/V杆，双手正握或反握，向下推压\n"
        f"- 绳索下压：用绳索（rope），双手各握绳索一端，向下推压时手腕可外旋\n"
        f"- 不管用什么配件，只要是站姿、肘部固定、从上方向下推压的三头肌动作，都统一归为【绳索下压】（exercise_id: cable_triceps_pushdown）\n\n"
        f"**面拉核心特征（容易被误判为绳索下压）：**\n"
        f"- ★ 手拉向面部/耳朵两侧，不是向下推\n"
        f"- ★ 肘部抬高至肩膀高度并向两侧展开（像做投降姿势）\n"
        f"- ★ 几乎只用绳索配件，不用直杆\n"
        f"- 如果映射表中没有面拉，exercise 填【UNKNOWN_ACTION】\n\n"
        f"**高位下拉 vs 绳索下压的关键区分（都是从上方向下的动作）：**\n"
        f"- ★ 最关键区分：高位下拉是【坐姿】，绳索下压是【站姿】\n"
        f"- 高位下拉：坐着，第一人称相机视角从下往上看（能看到上方的配重塔/滑轮/钢缆），手从头顶大幅度拉至胸口\n"
        f"- 绳索下压：站着，第一人称相机视角平视或微微俯视，手从胸前小幅度向下推至大腿\n"
        f"- 如果画面视角是从下往上看配重塔 → 大概率是坐姿 → 高位下拉\n\n"
        f"**坐姿绳索划船的区分（容易与高位下拉混淆）：**\n"
        f"- 高位下拉：绳索/杆从【头顶上方】垂下来，向下拉至锁骨/胸口\n"
        f"- 坐姿绳索划船：绳索从【正前方低位】水平拉来，向腹部拉，画面中可见前方的踏脚板和低位滑轮\n"
        f"- 绳索方向是最关键的判据：从上方来 = 高位下拉，从前方水平来 = 划船\n\n"
        f"### 规则四：第一人称典型画面速查\n"
        f"| 器械 | 胸前相机训练时典型画面 |\n"
        f"|------|----------------------|\n"
        f"| 跑步机 | 控制面板正对镜头，数字变化；画面持续节奏性上下晃动 |\n"
        f"| 椭圆机 | 站姿，两侧长臂动杆随身体前后摆动；无车座 |\n"
        f"| 登山机/踏步机 | 站姿直立，大型控制面板正对面部（有红色急停按钮、多排按键），双手握固定扶手栏杆；无车座；画面上下起伏明显 |\n"
        f"| 划船机 | 画面随身体前后大幅滑动；中心可见拉绳被拉紧/松弛 |\n"
        f"| 杠铃卧推 | 相机朝天花板，横杆从胸口上方上下移动 |\n"
        f"| 杠铃深蹲 | 下蹲时视角降低看地面，站起时横杆升回肩部 |\n"
        f"| 杠铃硬拉 | 相机朝地面，杠铃杆从地面经膝盖拉起 |\n"
        f"| 史密斯机 | 进场帧可见双立柱 + 固定导轨；训练时杠铃沿导轨上下 |\n"
        f"| 哑铃弯举 | 平视，手持哑铃从腰侧弯举至胸前，可见前臂旋转 |\n"
        f"| 哑铃肩推 | 仰角偏上，哑铃从肩部推至头顶 |\n"
        f"| 龙门架 | 绳索从画面上/下/侧边延伸连接配重塔；动作多样需看绳索方向 |\n"
        f"| 高位下拉 | 平视，大腿被挡板固定，宽杆从头顶拉向锁骨 |\n"
        f"| 坐姿划船 | 平视，双手握把向腹部拉，可见前方踏脚板和配重片 |\n"
        f"| 腿举机 | 视角低，看到 45° 斜板和脚踩踏板被推动 |\n"
        f"| 腿屈伸机 | 坐姿平视，小腿前方有滚垫，向上踢伸 |\n"
        f"| 腿弯举机 | 俯卧或坐姿，小腿后方有滚垫，向后弯曲 |\n"
        f"| 蝴蝶机/夹胸机 | 坐姿平视，把手在身体左右两侧（不是胸前），两侧弧形臂带泡棉垫从两侧向胸前合拢；配重片塔在后方 |\n"
        f"| 悍马机（推胸） | 坐姿平视，把手在胸前/正前方，双手正握水平把手向前推出；可见圆形杠铃片挂载在摆臂上 |\n"
        f"| 悍马机（夹胸） | 坐姿平视，把手在身体左右两侧，双臂从两侧向胸前合拢；可见圆形杠铃片，前臂贴泡棉垫或握垂直把手 |\n"
        f"| 固定器械推胸机 | 坐姿平视，双手握固定把手向前推；有配重片塔（插销选重），把手通过连杆连接 |\n"
        f"| 引体向上 | 从下往上看横杆，身体上升时横杆靠近胸口 |\n\n"
        f"### 规则五：镜子画面处理\n"
        f"- 如果画面中出现镜子，先判断镜中人是否为用户本人（位置居中、动作与光流一致）\n"
        f"- 镜中为用户本人 → 可参考镜中姿态辅助判断动作\n"
        f"- 镜中为他人 → 完全忽略\n\n"
        f"### 规则六：易混淆器械区分\n\n"
        f"#### 6A. 高位下拉机 vs 龙门架绳索下拉\n\n"
        f"这两者都是【从上方向下拉】，但属于完全不同的器械，必须严格区分：\n\n"
        f"| 区分维度 | 高位下拉机（独立器械） | 龙门架高位下拉（龙门架站位做下拉） | 龙门架其他动作（三头下压/面拉等） |\n"
        f"|---------|---------------------|-------------------------------|-------------------------------|\n"
        f"| **动作方向（最关键）** | 坐姿，从头顶大幅度拉至锁骨/胸口 | 坐姿（自带凳子或拉一把凳子坐），从头顶大幅度拉至锁骨/胸口 | 站姿，小幅度下压/面拉/夹胸（手不过头顶） |\n"
        f"| 腿部固定 | 大腿被泡棉挡板/滚垫从上方压住固定 | 无腿部固定，双脚踩地 | 无腿部固定，站立 |\n"
        f"| 座椅 | 有专用固定座椅 | 可能有凳子（龙门架附属或自搬），坐姿 | 无座椅，站姿 |\n"
        f"| 握持配件 | 宽横杆（>肩宽，通常 >100cm）或宽 V 杆 | 各种配件均可：宽杆/窄杆/V杆/绳索/D型把手 | 绳索头/短直杆/V型短杆/D型把手 |\n"
        f"| 拉动轨迹 | 从头顶拉至锁骨，肘部向两侧展开 | 从头顶拉至胸口/锁骨，肘部展开或向后收 | 下压：手从胸前向下；面拉：手拉向面部；夹胸：两侧向中间合拢 |\n"
        f"| 进场帧 | 独立机器框架 + 座椅 + 腿部挡板 | 龙门架双立柱 + 配重塔 + 上方滑轮，旁边有凳子 | 龙门架双立柱 + 配重塔 + 滑轮 |\n"
        f"| 配重片位置 | 在身体后方/上方，通常看不到 | 在身体前方/侧方，常可见配重塔 | 在身体前方/侧方 |\n\n"
        f"**前置判断——拉 vs 推（必须先做，防止推胸被误判为高位下拉）：**\n"
        f"- 【拉】的特征：手从远处向身体方向收回，背部肌肉发力，肘部向后收\n"
        f"- 【推】的特征：手从身体向前方/上方推出，胸/肩肌肉发力，肘部向前伸展\n"
        f"- 如果用户坐着双手向前推（不是向下拉），这是推胸动作 → 跳过规则 6A，去规则 6C 判断胸部器械\n"
        f"- 只有确认是【从上方向下拉】的动作，才进入下面的判定流程\n\n"
        f"**判定流程（确认是从上方向下拉的动作后，按顺序检查）：**\n"
        f"1. 上方滑轮连接的是宽杆/长杆（>肩宽） → **高位下拉机**（equipment 填【高位下拉机】，exercise 填【高位下拉】）\n"
        f"2. 画面下方可见大腿挡板/泡棉垫 → **高位下拉机**\n"
        f"3. 在龙门架/综合训练架上坐着做高位下拉（可见龙门架立柱/配重塔，用窄杆/V杆/绳索等配件） → **高位下拉机**（equipment 仍填【高位下拉机】，exercise 填【高位下拉】）\n"
        f"   注意：即使是在龙门架上做的，只要动作确实是坐姿从上方大幅度拉至胸口，就判定为高位下拉，不要判成绳索划船或三头下压。\n"
        f"4. 站姿 + 上方滑轮 + 小幅度动作 → **龙门架**（用规则三判定具体动作：绳索下压/面拉/高位夹胸等）\n\n"
        f"**高位下拉 vs 坐姿绳索划船的关键区分（都是坐姿拉的动作）：**\n"
        f"- 高位下拉：绳索/杆从【头顶上方】垂下来，向下拉至锁骨/胸口，画面中可见上方的滑轮和钢缆\n"
        f"- 坐姿绳索划船：绳索从【正前方低位】水平拉来，向腹部拉，画面中可见前方的踏脚板和低位滑轮\n"
        f"- 绳索方向是最关键的判据：从上方来 = 高位下拉，从前方水平来 = 划船\n\n"
        f"**禁止事项：**\n"
        f"- 禁止把【坐姿向前推】的动作判成高位下拉——向前推是推胸，向下拉才是高位下拉\n"
        f"- 禁止把坐姿从上方向下拉的动作判成【绳索划船】——划船是水平方向拉，不是从上往下拉\n"
        f"- 禁止把坐姿从上方向下拉的动作判成【三头下压】——三头下压是站姿小幅度下压\n"
        f"- 禁止把面拉判成绳索下压——面拉的手拉向面部两侧且肘部抬高外展，绳索下压的手向下推且肘部贴身\n"
        f"- 禁止因为【看不到腿部挡板】就否定高位下拉。第一人称胸前相机拍不到身体下方\n"
        f"- 禁止因为【在龙门架上做】就否定高位下拉。龙门架上坐着从上方拉 = 高位下拉\n\n"
        f"#### 6B. 动感单车 vs 登山机（踏步机/楼梯机） vs 椭圆机\n\n"
        f"三者都是有氧器械、画面持续节奏性运动，但视觉特征有明显差异：\n\n"
        f"| 区分维度 | 动感单车 | 登山机（踏步机/楼梯机） | 椭圆机 |\n"
        f"|---------|---------|---------------------|-------|\n"
        f"| **身体姿态（最关键）** | 上半身明显前倾俯身，相机朝斜下方看车把 | 上半身直立站立，相机平视或微微朝下 | 上半身直立或微前倾，相机平视 |\n"
        f"| **把手类型（关键）** | 低位固定车把，短且弯曲，双手向前下方握住 | 两侧固定扶手栏杆（不动），或无把手；把手不随身体运动 | 两侧长臂动杆（随身体前后摆动），把手从上方延伸下来 |\n"
        f"| **控制面板** | 小型显示屏，嵌在车把中央，视角俯视看 | ★大型独立控制面板，正对面部，面板上常有红色急停按钮、多个按键和LED显示 | 中型面板，位于两个动臂之间的中央位置 |\n"
        f"| 画面晃动模式 | 以腰部为轴的小幅左右摇摆为主，上下晃动较小 | ★明显的上下节奏性起伏（随踏步上下），左右晃动小 | 前后平滑滑动为主，上下晃动较小 |\n"
        f"| 光流特征 | avg_flow 较低（2-5），方向以左右为主 | avg_flow 中等偏高（5-10），方向以上下（UP/DOWN）交替为主 | avg_flow 中等（3-6），方向以前后为主 |\n"
        f"| 脚部运动 | 看不到脚（被车身遮挡），腿部做圆周踩踏 | 画面下方可能看到台阶/踏板在循环向下移动 | 看不到脚，脚部做椭圆轨迹运动 |\n"
        f"| 进场帧 | 可见车座（鞍座）、弯曲车把、飞轮侧面 | 可见高大机身、大面板、扶手栏杆、旋转台阶/踏板带 | 可见两侧长动臂杆、脚踏板、中央面板 |\n"
        f"| **有无车座** | ★有车座（鞍座），用户骑坐其上 | 无车座，用户站立踏步 | 无车座，用户站立 |\n\n"
        f"**登山机核心识别特征（容易被误判为动感单车或椭圆机）：**\n"
        f"- ★ 大型控制面板正对镜头/面部，面板上有红色急停按钮、多排按键、LED数字显示\n"
        f"- ★ 用户身体直立，相机视角平视或微微向下看面板（不是俯身看低位车把）\n"
        f"- ★ 把手是固定的扶手栏杆（不动的），不是随身体摆动的动臂\n"
        f"- ★ 无车座（鞍座），用户始终站立\n"
        f"- 画面有明显的上下节奏性起伏（随踏步上下移动）\n"
        f"- 光流 avg_flow 通常较高（5-10），UP/DOWN 方向交替明显\n\n"
        f"**判定流程：**\n"
        f"1. 进场帧可见车座（鞍座）+ 弯曲车把 + 飞轮 → **动感单车**\n"
        f"2. 大型控制面板正对镜头 + 红色急停按钮 + 身体直立 + 无车座 → **登山机**\n"
        f"3. 进场帧可见旋转台阶/踏板带 → **登山机**\n"
        f"4. 两侧有随身体前后摆动的长臂动杆 → **椭圆机**\n"
        f"5. 身体明显前倾俯身 + 手握低位弯曲把手 → **动感单车**\n"
        f"6. 身体直立 + 把手固定不动 + 明显上下起伏 → **登山机**\n"
        f"7. 身体直立 + 把手前后摆动 + 画面前后滑动 → **椭圆机**\n\n"
        f"**易错提醒：**\n"
        f"- 登山机的大型面板 + 红色按钮容易被误认为动感单车的仪表盘，区别在于：登山机面板大且正对面部（平视），动感单车面板小且在低位（俯视）\n"
        f"- 登山机和椭圆机都是站姿，区别在于：登山机把手固定不动，椭圆机把手随身体前后摆动\n"
        f"- 只有动感单车有车座（鞍座），登山机和椭圆机都没有\n\n"
        f"#### 6C. 胸部训练器械区分（推胸 vs 夹胸是两种完全不同的动作！）\n\n"
        f"**★★★ 推胸 vs 夹胸的核心区别（最重要，必须先判断）：**\n"
        f"- **推胸**：把手在【胸前/身体正前方】，双手向前推出，肘部从弯曲到伸直\n"
        f"- **夹胸**：把手在【身体左右两侧】，双臂从两侧向胸前合拢，肘部始终保持微弯固定角度\n"
        f"- 判断方法：看把手的起始位置！把手从胸前出发 = 推胸，把手从身体两侧出发 = 夹胸\n"
        f"- 抓握姿势也不同：推胸是双手正握水平把手（掌心朝前），夹胸是前臂贴泡棉垫或双手握垂直把手（掌心相对）\n\n"
        f"胸部训练器械在第一人称视角下容易混淆，必须严格区分：\n\n"
        f"| 区分维度 | 悍马机推胸 | 悍马机夹胸 | 蝴蝶机/夹胸机（Pec Deck） | 固定器械推胸机 | 龙门架夹胸 | 杠铃/哑铃卧推 |\n"
        f"|---------|-----------|-----------|------------------------|-------------|-----------|-------------|\n"
        f"| **把手位置（最关键）** | ★把手在胸前/正前方 | ★把手在身体左右两侧 | ★把手在身体左右两侧 | ★把手在胸前/正前方 | 把手在两侧（绳索） | 杠铃/哑铃在胸口上方 |\n"
        f"| **运动方向** | 向前推出 | 从两侧向中间合拢 | 从两侧向中间合拢 | 向前推出 | 从两侧向中间合拢 | 向上推起 |\n"
        f"| **抓握方式** | 双手正握水平把手（掌心朝前） | 前臂贴泡棉垫或握垂直把手（掌心相对） | 前臂贴泡棉垫或握垂直把手（掌心相对） | 双手正握水平把手 | 握D型把手 | 握杠铃杆/哑铃 |\n"
        f"| **配重方式** | 杠铃片（圆盘），无配重片塔 | 杠铃片（圆盘），无配重片塔 | 配重片塔（插销选重） | 配重片塔（插销选重） | 龙门架配重塔 | 杠铃片/哑铃 |\n"
        f"| **器械结构** | 厚重金属框架，独立杠杆臂 | 厚重金属框架，独立杠杆臂 | 弧形导轨，泡棉垫手臂挡板 | 固定导轨或连杆 | 双立柱+绳索 | 卧推架 |\n"
        f"| **相机朝向** | 坐姿平视，可见前方把手 | 坐姿平视，可见两侧把手向中间靠拢 | 坐姿平视，可见两侧弧形臂合拢 | 坐姿平视 | 站姿平视 | 仰卧朝天花板 |\n"
        f"| **光流特征** | 前后为主（FORWARD/BACKWARD） | 左右对称向中间（LEFT+RIGHT→CENTER） | 左右对称向中间 | 前后为主 | 左右对称向中间 | 上下为主（UP/DOWN） |\n\n"
        f"**悍马机（Hammer Strength）识别特征：**\n"
        f"- ★ 画面中可见【挂载的杠铃片（圆形金属片）】而非【配重片塔（方形插销选重）】\n"
        f"- ★ 两侧有【独立的粗壮杠杆臂/摆臂】，从机器框架向用户方向延伸\n"
        f"- ★ 金属框架厚重、结构粗犷，整体看起来像工业级器械\n"
        f"- ⚠️ 悍马机有【推胸款】和【夹胸款】两种！识别出悍马机后，必须进一步判断是推胸还是夹胸：\n"
        f"  - 悍马机推胸：把手在胸前，向前推 → equipment 填【悍马机】，exercise 填【固定器械推胸】\n"
        f"  - 悍马机夹胸：把手在身体两侧，从两侧向中间合拢 → equipment 填【悍马机】，exercise 填【蝴蝶机夹胸】\n\n"
        f"**蝴蝶机（Pec Deck）识别特征：**\n"
        f"- ★ 两侧有【弧形轨道/弧形臂】，臂端有泡棉垫或垂直把手\n"
        f"- ★ 把手在身体左右两侧，动作是双臂从两侧向胸前合拢\n"
        f"- 配重片塔在座椅后方（用插销选重）\n"
        f"- equipment 填【蝴蝶机】，exercise 填【蝴蝶机夹胸】\n\n"
        f"**判定流程（胸部训练动作专用）：**\n"
        f"1. 相机朝天花板 + 仰卧 → **杠铃/哑铃卧推**（用规则二判断具体器械）\n"
        f"2. 进场帧可见杠铃片 + 独立杠杆臂（悍马机特征） → 进入第 2a 步\n"
        f"   2a. 看把手位置和运动方向：\n"
        f"     - 把手在胸前，向前推出 → **悍马机推胸**（exercise 填【固定器械推胸】）\n"
        f"     - 把手在身体两侧，从两侧向中间合拢 → **悍马机夹胸**（exercise 填【蝴蝶机夹胸】）\n"
        f"3. 进场帧可见弧形轨道/弧形臂 + 泡棉垫 + 把手在两侧 → **蝴蝶机夹胸**\n"
        f"4. 坐姿 + 把手在胸前向前推 + 配重片塔 → **固定器械推胸机**\n"
        f"5. 站姿 + 龙门架 + 双臂从两侧向中间合拢 → **龙门架夹胸**\n\n"
        f"**★ 光流纠正机制（推胸 vs 夹胸的最终验证，必须执行）：**\n"
        f"- 如果初步判定为【推胸】，但光流主方向是 LEFT 或 RIGHT（左右方向），而非 FORWARD/BACKWARD → 必须纠正为【夹胸】\n"
        f"- 如果初步判定为【夹胸】，但光流主方向是 FORWARD/BACKWARD（前后方向），而非 LEFT/RIGHT → 必须纠正为【推胸】\n"
        f"- 推胸 = 手向前推出再收回 → 光流以 FORWARD/BACKWARD 为主\n"
        f"- 夹胸 = 手从两侧向中间合拢再张开 → 光流以 LEFT/RIGHT 为主\n"
        f"- ⚠️ 第一人称相机贴在胸前，很难直接看出把手在胸前还是两侧，但光流方向不会骗人！\n"
        f"- ⛔ 禁止用「相机安装角度偏转」「相机侧向安装」等理由来解释光流方向的偏差！光流的 LEFT/RIGHT/FORWARD/BACKWARD 已经是相对于画面的方向，不需要你做坐标变换。如果光流主方向是 LEFT/RIGHT，就说明运动方向确实是左右（=夹胸），不要自己发明「其实是前后方向被相机旋转了」这种解释。\n\n"
        f"**易错提醒：**\n"
        f"- ★ 悍马机不等于推胸！悍马机也有夹胸款，必须结合光流方向判断\n"
        f"- 推胸 vs 夹胸最简单的判断：光流以前后为主=推胸，光流以左右为主=夹胸\n"
        f"- 悍马机 vs 固定器械推胸机：看配重方式！杠铃片（圆盘）= 悍马机，配重片塔（插销）= 固定器械推胸机\n"
        f"- 蝴蝶机 vs 龙门架夹胸：弧形轨道+座椅 = 蝴蝶机，双立柱+绳索+站姿 = 龙门架夹胸\n\n"
        f"---\n\n"
        f"{_build_standard_names_prompt()}"
        f"请严格按以下步骤分析，必须先输出分析过程，再输出 JSON：\n\n"
        f"Step 1 — 进场帧分析: 描述网格图前 2~3 帧看到的器械外观（座椅？腿部挡板？立柱？配重塔？车座？踏板？杠铃片/圆盘？独立摆臂/杠杆臂？弧形轨道？泡棉垫？）\n"
        f"Step 2 — 器械识别: 依次使用规则一~六排查。特别注意：\n"
        f"  - 如果在龙门架/综合训练架区域，必须先用规则三的【总流程】判断：先看站姿/坐姿，再看绳索来向，最后看动作方向\n"
        f"  - 坐姿 + 从上方拉 = 高位下拉（不是绳索下压！），站姿 + 从上方向下推 = 绳索下压，站姿 + 从下方向上弯 = 绳索弯举\n"
        f"  - 如果动作涉及从上方下拉，必须用规则 6A 逐项检查是【高位下拉机】还是【龙门架绳索动作】\n"
        f"  - 如果是有氧器械持续运动，必须用规则 6B 逐项检查是【动感单车】【登山机】还是【椭圆机】（重点看：有无车座、面板大小和位置、把手是否随身体摆动）\n"
        f"  - 如果是坐姿推胸/夹胸类动作，必须用规则 6C 逐项检查是【悍马机】【蝴蝶机】【固定器械推胸机】还是【龙门架夹胸】\n"
        f"Step 3 — 光流验证: 结合光流方向验证或修正器械判断。特别注意：如果是胸部器械，光流主方向LEFT/RIGHT→夹胸，FORWARD/BACKWARD→推胸，必须用光流纠正初步判断！\n"
        f"Step 4 — 动作判定: 综合器械 + 光流 + 画面判定具体动作名称\n"
        f"Step 5 — 组次统计: 利用光流周期性统计组数和每组次数\n\n"
        f"关键约束：\n"
        f"- 第一人称胸前相机 → 用户自身不会完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象（见规则五）\n"
        f"- 必须看到用户双手或器械的运动证据才能判定动作\n"
        f"- 如果器械无法确定，equipment 填 \"UNKNOWN_EQUIPMENT\"\n"
        f"- 如果动作无法确定，exercise 填 \"UNKNOWN_ACTION\"\n\n"
        f"输出格式：先写分析过程（每个 Step 1~2 句话），最后一行输出 JSON（不要包含 Markdown 代码块）：\n"
        f'{{"equipment": "器械名称", "exercise": "标准动作名称（从上表选择）", "exercise_id": "对应的exercise_id", "confidence": 0.0~1.0, '
        f'"sets": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", "reps": N}}], '
        f'"phase1_adjustment": {{"expand_before_sec": N, "expand_after_sec": N, '
        f'"reason": "扩展原因"}}}}'
    )

    user_content = [{"type": "text", "text": user_text}]

    # 先发送进场帧原图
    if entrance_frames:
        user_content.append({"type": "text", "text": entrance_hint})
        for i, ef_bytes in enumerate(entrance_frames):
            user_content.append({
                "type": "image_url",
                "image_url": {"url": _image_to_data_url(ef_bytes)},
            })
        user_content.append({
            "type": "text",
            "text": "\n**以上是进场帧原图。下面是完整的网格图（用于动作分析和计数）：**\n",
        })

    # 再发送网格图
    user_content.append({
        "type": "image_url",
        "image_url": {"url": _image_to_data_url(jpeg_bytes)},
    })

    MAX_VALIDATE_RETRIES = 3
    seg_result = None

    for v_attempt in range(MAX_VALIDATE_RETRIES):
        raw = _gemini_generate(system_prompt, user_content)
        tprint(f"    [{seg_id}] 响应长度: {len(raw)} 字符")

        # 保存原始响应
        raw_path = output_dir / f"exercise_raw_{seg_id}.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")

        try:
            seg_result = _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            tprint(f"    [{seg_id}] [警告] JSON 解析失败: {e}")
            if v_attempt < MAX_VALIDATE_RETRIES - 1:
                tprint(f"    [{seg_id}] 重试 ({v_attempt + 1}/{MAX_VALIDATE_RETRIES})...")
                continue
            seg_result = {"raw_response": raw}
            break

        # 校验 Gemini 返回数据质量
        validation_errors = _validate_exercise_result(seg_result)
        if validation_errors and v_attempt < MAX_VALIDATE_RETRIES - 1:
            tprint(f"    [{seg_id}] 数据校验失败 ({len(validation_errors)} 项问题):")
            for err in validation_errors[:3]:
                tprint(f"      - {err}")
            tprint(f"    [{seg_id}] 重试 ({v_attempt + 1}/{MAX_VALIDATE_RETRIES})...")
            continue

        if validation_errors:
            tprint(f"    [{seg_id}] 最终仍有 {len(validation_errors)} 项问题，执行清洗")

        # UNKNOWN_ACTION 自检：添加额外提示后重试
        exercise_val = seg_result.get("exercise") or ""
        if _is_unknown_exercise(exercise_val) and v_attempt < MAX_VALIDATE_RETRIES - 1:
            tprint(f"    [{seg_id}] 识别结果为未知动作({exercise_val!r})，添加补充提示后重试 ({v_attempt + 1}/{MAX_VALIDATE_RETRIES})...")
            retry_hint = {
                "type": "text",
                "text": (
                    "\n\n⚠️ 上一次你返回了未知动作，这是不可接受的。请重新仔细分析：\n"
                    "1. 禁止输出 UNKNOWN_ACTION、UNKNOWN_EQUIPMENT、未知动作、未知 等。必须给出你最有可能的判断。\n"
                    "2. 即使不确定具体动作名称，也请根据观察到的运动模式给出最接近的标准动作名。\n"
                    "3. 重点关注：器械外观特征、手部运动方向、光流周期模式。\n"
                    "4. 如果是热身/拉伸动作，请识别为具体的热身动作（如 动态拉伸、泡沫轴放松 等）。\n"
                    "5. 如果是有氧运动，请识别为具体的有氧器械动作（如 跑步机慢跑、登山机、椭圆机 等）。\n"
                    "6. confidence 可以设低（如 0.5），但必须给出具体的 exercise 名称。\n"
                ),
            }
            if retry_hint not in user_content:
                user_content.append(retry_hint)
            continue

        seg_result = _sanitize_exercise_result(seg_result)
        break

    # 标准化动作名称
    if isinstance(seg_result, dict) and "exercise" in seg_result:
        raw_exercise = seg_result["exercise"]
        std_name, exercise_id = _normalize_exercise_name(raw_exercise)
        if exercise_id:
            seg_result["exercise"] = std_name
            seg_result["exercise_id"] = exercise_id
            if std_name != raw_exercise:
                tprint(f"    [{seg_id}] 名称标准化: {raw_exercise} → {std_name} ({exercise_id})")

    return {
        "segmentId": seg_id,
        "startTime": t_start,
        "endTime": t_end,
        "startTimeStr": sec_to_hhmmss(t_start),
        "endTimeStr": sec_to_hhmmss(t_end),
        "duration": dur,
        "frames_analyzed": frame_count,
        "grid": {"cols": g_cols, "rows": g_rows},
        "result": seg_result,
    }


# ──────────────────────────────────────────────
# Phase 1 区间修正
# ──────────────────────────────────────────────

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
    """根据 Phase 2 的 phase1_adjustment 回填修正 Phase 1 区间。"""
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
                    seg["start_time"] = sec_to_hhmmss(new_start)
                    if new_start < prev_seg.get("end_sec", 0.0):
                        prev_seg["end_sec"] = new_start
                        prev_seg["end_time"] = sec_to_hhmmss(new_start)
                    applied += 1

        if after > 0 and i < len(adjusted) - 1:
            next_seg = adjusted[i + 1]
            new_end = min(next_seg.get("end_sec", total_dur), seg.get("end_sec", 0.0) + after)
            if new_end > seg.get("start_sec", 0.0):
                if new_end > seg.get("end_sec", 0.0):
                    seg["end_sec"] = new_end
                    seg["end_time"] = sec_to_hhmmss(new_end)
                    if new_end > next_seg.get("start_sec", 0.0):
                        next_seg["start_sec"] = new_end
                        next_seg["start_time"] = sec_to_hhmmss(new_end)
                    applied += 1

    if adjusted:
        adjusted[0]["start_sec"] = max(0.0, adjusted[0].get("start_sec", 0.0))
        adjusted[0]["start_time"] = sec_to_hhmmss(adjusted[0]["start_sec"])
        adjusted[-1]["end_sec"] = min(total_dur, adjusted[-1].get("end_sec", total_dur))
        adjusted[-1]["end_time"] = sec_to_hhmmss(adjusted[-1]["end_sec"])

    return adjusted, applied


# ──────────────────────────────────────────────
# Phase 2：运动识别（并发）
# ──────────────────────────────────────────────

def run_phase2(
    frame_metas: list[FrameMeta],
    frames_dir: Path,
    flow_data: list[dict],
    segments: list[dict],
    prompt: PromptConfig,
    output_dir: Path,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
    imu_records: list[ImuRecord] | None = None,
    equipment_timeline: list[dict] | None = None,
) -> list[dict]:
    """
    Phase 2：对每个 EXERCISE 区间并发识别。

    Returns:
        list[dict]（exercise results）
    """
    tprint(f"\n{'=' * 60}")
    tprint(f"Phase 2: 运动识别 ({Path(prompt.source_file).name})")
    tprint(f"{'=' * 60}")

    system_prompt = prompt.system

    # 筛出 EXERCISE 段并编号
    exercise_segs = [
        s for s in segments if s.get("state", "").upper() == "EXERCISE"
    ]
    for i, s in enumerate(exercise_segs, 1):
        s.setdefault("segmentId", f"exercise_{i:03d}")

    tprint(f"  共 {len(exercise_segs)} 个 EXERCISE 段待识别（并发: {exercise_workers}）")
    if not exercise_segs:
        version_tag = Path(prompt.source_file).stem.replace("phase2_exercise_recognize_", "")
        _save_json(
            {"version": version_tag, "message": "no exercise segments", "results": []},
            output_dir / "exercise_result.json",
        )
        return []

    all_results: list[dict] = []
    workers = min(exercise_workers, len(exercise_segs))

    if workers <= 1:
        for seg in exercise_segs:
            result = _recognize_one_exercise(
                seg, frame_metas, frames_dir, output_dir, flow_data, system_prompt,
                imu_records=imu_records, equipment_timeline=equipment_timeline)
            if result:
                all_results.append(result)
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for seg in exercise_segs:
                fut = executor.submit(
                    _recognize_one_exercise,
                    seg, frame_metas, frames_dir, output_dir, flow_data, system_prompt,
                    imu_records, equipment_timeline,
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

    # ── 第二轮：对仍为未知动作的区间重新识别 ──
    unknown_results = [
        r for r in all_results
        if _is_unknown_exercise((r.get("result") or {}).get("exercise", ""))
    ]
    if unknown_results:
        tprint(f"\n  [Phase 2 第二轮] 仍有 {len(unknown_results)} 个 EXERCISE 识别为未知动作，重新识别...")
        # 找回对应的原始 segment
        seg_map = {s.get("segmentId"): s for s in exercise_segs}
        retry_results: list[dict] = []
        retry_workers = min(exercise_workers, len(unknown_results))
        if retry_workers <= 1:
            for r in unknown_results:
                seg = seg_map.get(r["segmentId"])
                if seg is None:
                    continue
                new_result = _recognize_one_exercise(
                    seg, frame_metas, frames_dir, output_dir, flow_data, system_prompt,
                    imu_records=imu_records, equipment_timeline=equipment_timeline)
                if new_result:
                    retry_results.append(new_result)
        else:
            retry_futures = {}
            with ThreadPoolExecutor(max_workers=retry_workers) as executor:
                for r in unknown_results:
                    seg = seg_map.get(r["segmentId"])
                    if seg is None:
                        continue
                    fut = executor.submit(
                        _recognize_one_exercise,
                        seg, frame_metas, frames_dir, output_dir, flow_data, system_prompt,
                        imu_records, equipment_timeline,
                    )
                    retry_futures[fut] = r["segmentId"]
                for fut in as_completed(retry_futures):
                    sid = retry_futures[fut]
                    try:
                        new_result = fut.result()
                        if new_result:
                            retry_results.append(new_result)
                    except Exception as e:
                        tprint(f"    [{sid}] [第二轮错误] {e}")

        # 用重试结果替换原来的 unknown 结果（以 segmentId 为键）
        retry_map = {r["segmentId"]: r for r in retry_results}
        all_results = [
            retry_map.get(r["segmentId"], r) for r in all_results
        ]
        all_results.sort(key=lambda r: r["startTime"])

        still_unknown = [
            r for r in all_results
            if _is_unknown_exercise((r.get("result") or {}).get("exercise", ""))
        ]
        tprint(f"  [Phase 2 第二轮] 完成，剩余未知: {len(still_unknown)} 个")

    # ── 保存 exercise_result.json ──
    version_tag = Path(prompt.source_file).stem.replace("phase2_exercise_recognize_", "")
    _save_json(
        {
            "version": version_tag,
            "phase2_prompt": Path(prompt.source_file).name,
            "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
            "created_at": datetime.now().isoformat(),
            "results": all_results,
        },
        output_dir / "exercise_result.json",
    )

    # ── 应用 Phase 1 区间修正 ──
    total_dur = frame_metas[-1].timestamp if frame_metas else 0
    adjusted_segments, applied = apply_phase1_adjustments(segments, all_results, total_dur)
    _save_json(
        {
            "version": version_tag,
            "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
            "created_at": datetime.now().isoformat(),
            "adjustments_applied": applied,
            "segments": adjusted_segments,
        },
        output_dir / "period_result_adjusted.json",
    )

    tprint(f"\n  Phase 2 完成: {len(all_results)} 个 EXERCISE, "
           f"区间修正 {applied} 处")
    return all_results
