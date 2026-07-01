#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imu_anglez_posture_recognizer.py

基于“胸前固定 IMU + 已知角度通道语义”的用户姿态识别脚本。

已知信息:
1. IMU 固定在用户胸前，无明显相对运动。
2. 角度X: IMU 单元相对于用户胸前的旋转偏移，用于判断设备是否松动/旋转漂移。
3. 角度Y: 用户左转/右转，左转角度增大；主要表示 yaw，不作为姿态主特征。
4. 角度Z: 竖直方向姿态角，用户躯干垂直于地面时约 180°。
5. 姿态主判断:
   - angleZ 距离 180° 越小，躯干越竖直。
   - angleZ 距离 180° 接近 70°~90°，躯干接近水平。
6. 加速度用于辅助判断:
   - 平躺 / 俯卧 / 侧身
   - 周期性 / 下蹲蹲起
   - 运动强度

支持输入:
- .csv
- .txt / .tsv
- .xlsx / .xls

典型中文列名:
时间
加速度X(g), 加速度Y(g), 加速度Z(g)
角速度X(°/s), 角速度Y(°/s), 角速度Z(°/s)
角度X(°), 角度Y(°), 角度Z(°)

输出:
outdir/posture_windows.csv
outdir/posture_segments.csv
outdir/posture_summary.json

使用示例:
python imu_anglez_posture_recognizer.py --input IMU_data.csv --outdir output

如果已知胸口朝外/用户右侧对应的加速度轴:
python imu_anglez_posture_recognizer.py \
  --input IMU_data.csv \
  --outdir output \
  --body-forward +Y \
  --body-right +X

如果不知道 body-forward/body-right:
脚本仍可基于 angleZ 输出 竖直/倾斜/水平/周期 状态；
但平躺、俯卧、侧身、斜躺、俯身的细分置信度会降低。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


EPS = 1e-8


# -----------------------------
# 角度工具
# -----------------------------

def angle_distance_deg(angle: float, target: float = 180.0) -> float:
    """
    计算 angle 到 target 的最小环形距离，单位: 度。
    支持角度范围为 -180~180 或 0~360。
    """
    if not np.isfinite(angle):
        return np.nan
    return abs((angle - target + 180.0) % 360.0 - 180.0)


def circular_mean_deg(angles: np.ndarray) -> float:
    """
    环形平均，避免 179° 和 -179° 被普通平均成 0°。
    """
    a = np.asarray(angles, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return np.nan
    rad = np.deg2rad(a)
    s = np.nanmean(np.sin(rad))
    c = np.nanmean(np.cos(rad))
    return float(np.rad2deg(np.arctan2(s, c)))


def circular_delta_deg(angle: float, baseline: float) -> float:
    """
    angle 相对 baseline 的最小环形差值，保留方向，范围约 [-180, 180]。
    """
    return float((angle - baseline + 180.0) % 360.0 - 180.0)


# -----------------------------
# 向量工具
# -----------------------------

def normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n < EPS or not np.isfinite(n):
        return v * 0.0
    return v / n


def parse_axis(axis: Optional[str]) -> Optional[np.ndarray]:
    """
    '+X' -> [1,0,0]
    '-Y' -> [0,-1,0]
    None 或 '' -> None
    """
    if axis is None:
        return None
    s = str(axis).strip().upper()
    if s in ["", "NONE", "UNKNOWN", "NULL"]:
        return None

    if not re.fullmatch(r"[+-][XYZ]", s):
        raise ValueError(f"轴定义错误: {axis}. 合法格式: +X, -X, +Y, -Y, +Z, -Z 或 unknown")

    sign = 1.0 if s[0] == "+" else -1.0
    name = s[1]
    if name == "X":
        return np.array([sign, 0.0, 0.0], dtype=float)
    if name == "Y":
        return np.array([0.0, sign, 0.0], dtype=float)
    return np.array([0.0, 0.0, sign], dtype=float)


def zscore_safe(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = pd.Series(x).interpolate(limit_direction="both").fillna(0).to_numpy()
    std = float(np.nanstd(x))
    if std < EPS:
        return x * 0.0
    return (x - float(np.nanmean(x))) / std


def moving_average_2d(x: np.ndarray, win: int) -> np.ndarray:
    if win <= 1:
        return x.copy()

    y = np.zeros_like(x, dtype=float)
    kernel = np.ones(win, dtype=float) / float(win)

    for j in range(x.shape[1]):
        col = pd.Series(x[:, j]).interpolate(limit_direction="both").fillna(0).to_numpy()
        y[:, j] = np.convolve(col, kernel, mode="same")

    return y


# -----------------------------
# 读文件和列名映射
# -----------------------------

def read_imu_file(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    suffix = p.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        return pd.read_excel(p)

    if suffix == ".csv":
        try:
            return pd.read_csv(p)
        except UnicodeDecodeError:
            return pd.read_csv(p, encoding="gbk")

    if suffix in [".txt", ".tsv"]:
        try:
            return pd.read_csv(p, sep=None, engine="python")
        except UnicodeDecodeError:
            return pd.read_csv(p, sep=None, engine="python", encoding="gbk")

    try:
        return pd.read_csv(p, sep=None, engine="python")
    except UnicodeDecodeError:
        return pd.read_csv(p, sep=None, engine="python", encoding="gbk")


def norm_col_name(c: str) -> str:
    c = str(c).strip().lower()
    c = c.replace(" ", "")
    c = c.replace("_", "")
    c = c.replace("-", "")
    c = c.replace("（", "(").replace("）", ")")
    return c


def find_column(df: pd.DataFrame, patterns: List[str]) -> Optional[str]:
    cols = list(df.columns)
    normalized = {c: norm_col_name(c) for c in cols}

    for p in patterns:
        pn = norm_col_name(p)
        for c, cn in normalized.items():
            if cn == pn:
                return c

    for p in patterns:
        pn = norm_col_name(p)
        for c, cn in normalized.items():
            if pn in cn:
                return c

    return None


def map_columns(df: pd.DataFrame) -> Dict[str, str]:
    patterns = {
        "time": ["时间", "timestamp", "time", "datetime", "日期时间"],
        "ax": ["加速度x(g)", "加速度x", "accx", "acc_x", "accelerometerx", "ax"],
        "ay": ["加速度y(g)", "加速度y", "accy", "acc_y", "accelerometery", "ay"],
        "az": ["加速度z(g)", "加速度z", "accz", "acc_z", "accelerometerz", "az"],
        "gx": ["角速度x(°/s)", "角速度x", "gyrox", "gyro_x", "gx"],
        "gy": ["角速度y(°/s)", "角速度y", "gyroy", "gyro_y", "gy"],
        "gz": ["角速度z(°/s)", "角速度z", "gyroz", "gyro_z", "gz"],
        "angle_x": ["角度x(°)", "角度x", "anglex", "angle_x", "roll"],
        "angle_y": ["角度y(°)", "角度y", "angley", "angle_y", "yaw", "heading"],
        "angle_z": ["角度z(°)", "角度z", "anglez", "angle_z", "pitch"],
        "height": ["高度(m)", "高度", "height", "altitude"],
        "pressure": ["气压(kpa)", "气压", "pressure", "barometer"],
    }

    mapping = {}
    for k, pats in patterns.items():
        col = find_column(df, pats)
        if col is not None:
            mapping[k] = col

    required = ["time", "ax", "ay", "az", "angle_z"]
    missing = [k for k in required if k not in mapping]
    if missing:
        raise ValueError(
            "缺少必要列: "
            + ", ".join(missing)
            + "\n必须至少包含: 时间、加速度X/Y/Z、角度Z。"
            + "\n当前列名: "
            + ", ".join(map(str, df.columns))
            + "\n已识别映射: "
            + json.dumps(mapping, ensure_ascii=False)
        )

    return mapping


def standardize_dataframe(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    out = pd.DataFrame()
    out["time"] = pd.to_datetime(df[mapping["time"]], errors="coerce")

    for key in [
        "ax", "ay", "az",
        "gx", "gy", "gz",
        "angle_x", "angle_y", "angle_z",
        "height", "pressure"
    ]:
        if key in mapping:
            out[key] = pd.to_numeric(df[mapping[key]], errors="coerce")

    out = out.dropna(subset=["time", "ax", "ay", "az", "angle_z"])
    out = out.sort_values("time").drop_duplicates(subset=["time"]).reset_index(drop=True)
    return out


def estimate_sample_rate(df: pd.DataFrame) -> float:
    t = df["time"].diff().dt.total_seconds().dropna()
    t = t[(t > 0) & np.isfinite(t)]
    if len(t) == 0:
        return 50.0
    fs = 1.0 / float(t.median())
    return float(np.clip(round(fs), 10, 100))


def resample_dataframe(df: pd.DataFrame, fs: float) -> pd.DataFrame:
    df = df.copy()
    df = df.set_index("time")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    rule_ms = max(1, int(round(1000.0 / fs)))

    out = df[numeric_cols].resample(f"{rule_ms}ms").mean().interpolate(limit_direction="both")
    out = out.reset_index()
    return out


# -----------------------------
# 周期性检测
# -----------------------------

def compute_periodicity(signal: np.ndarray, fs: float, min_freq: float = 0.2, max_freq: float = 3.0) -> Tuple[float, float, Optional[float], float]:
    """
    返回:
    periodic_score, dominant_freq_hz, period_sec, estimated_reps
    """
    x = np.asarray(signal, dtype=float)
    x = pd.Series(x).interpolate(limit_direction="both").fillna(0).to_numpy()
    n = len(x)

    if n < max(16, int(fs * 1.5)):
        return 0.0, 0.0, None, 0.0

    x = x - np.mean(x)
    std = np.std(x)
    if std < 1e-6:
        return 0.0, 0.0, None, 0.0
    x = x / std

    # FFT 主峰
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    spec = np.abs(np.fft.rfft(x * np.hanning(n))) ** 2

    band = (freqs >= min_freq) & (freqs <= max_freq)
    if band.sum() == 0:
        return 0.0, 0.0, None, 0.0

    band_freqs = freqs[band]
    band_spec = spec[band]

    peak_idx = int(np.argmax(band_spec))
    dominant_freq = float(band_freqs[peak_idx])
    total_power = float(np.sum(band_spec) + EPS)
    peak_ratio = float(band_spec[peak_idx] / total_power)

    # 自相关峰
    ac = np.correlate(x, x, mode="full")[n - 1:]
    ac = ac / (ac[0] + EPS)

    min_lag = max(1, int(fs / max_freq))
    max_lag = min(len(ac) - 1, int(fs / min_freq))
    if max_lag <= min_lag:
        ac_score = 0.0
    else:
        ac_score = float(np.max(ac[min_lag:max_lag]))

    periodic_score = 0.55 * ac_score + 0.45 * min(1.0, peak_ratio * 3.0)
    periodic_score = float(np.clip(periodic_score, 0.0, 1.0))

    period_sec = 1.0 / dominant_freq if dominant_freq > 0 else None
    reps = (n / fs) * dominant_freq if dominant_freq > 0 else 0.0

    return periodic_score, dominant_freq, period_sec, float(reps)


# -----------------------------
# 姿态识别规则
# -----------------------------

def infer_upright_baseline(angle_z: np.ndarray, acc: np.ndarray, gyro: Optional[np.ndarray], fs: float) -> Dict:
    """
    自动估计 angleZ 竖直基准。
    已知竖直约 180°，所以 baseline 默认围绕 180°。
    如果数据里存在大量稳定竖直片段，则用接近 180°的稳定片段环形均值修正。
    """
    n = len(angle_z)
    win = max(10, int(2.0 * fs))
    stride = max(1, int(0.5 * fs))

    acc_norm = np.linalg.norm(acc, axis=1)
    if gyro is not None:
        gyro_norm = np.linalg.norm(gyro, axis=1)
    else:
        gyro_norm = np.zeros(n)

    candidates = []

    for s in range(0, max(1, n - win + 1), stride):
        e = s + win
        a_norm = acc_norm[s:e]
        g_norm = gyro_norm[s:e]
        z_win = angle_z[s:e]

        stable = (
            abs(float(np.nanmean(a_norm)) - 1.0) < 0.15
            and float(np.nanstd(a_norm)) < 0.10
            and float(np.nanmean(g_norm)) < 25.0
        )

        z_mean = circular_mean_deg(z_win)
        z_dist = angle_distance_deg(z_mean, 180.0)

        # 优先选接近 180 的稳定窗口，作为竖直基准候选
        if stable and z_dist < 25.0:
            candidates.append(z_mean)

    if len(candidates) >= 3:
        baseline = circular_mean_deg(np.array(candidates))
        source = "stable_windows_near_180"
    else:
        baseline = 180.0
        source = "default_180"

    return {
        "angle_z_upright_baseline": float(baseline),
        "source": source,
        "candidate_count": int(len(candidates)),
    }


def classify_posture_rule(
    torso_tilt: float,
    chest_score: Optional[float],
    side_score: Optional[float],
    motion_intensity: float,
    gyro_intensity: float,
    periodic_score: float,
    dominant_freq: float,
    angle_x_drift_abs: Optional[float],
) -> Tuple[str, float, str]:
    """
    基于 angleZ 主特征 + 加速度方向辅助的规则分类。
    """

    has_chest = chest_score is not None and np.isfinite(chest_score)
    has_side = side_score is not None and np.isfinite(side_score)

    reason_parts = []

    # 设备旋转漂移惩罚
    drift_penalty = 1.0
    if angle_x_drift_abs is not None and np.isfinite(angle_x_drift_abs):
        if angle_x_drift_abs > 25:
            drift_penalty = 0.65
            reason_parts.append(f"angleX漂移较大({angle_x_drift_abs:.1f}°)，设备可能松动")
        elif angle_x_drift_abs > 15:
            drift_penalty = 0.80
            reason_parts.append(f"angleX存在漂移({angle_x_drift_abs:.1f}°)")

    def pack(label: str, conf: float, reason: str) -> Tuple[str, float, str]:
        if reason_parts:
            reason = reason + "；" + "；".join(reason_parts)
        return label, float(np.clip(conf * drift_penalty, 0.05, 0.98)), reason

    # 1. 水平类
    if torso_tilt >= 70:
        if has_chest and chest_score <= -0.60:
            return pack("平躺", 0.92, "angleZ显示躯干接近水平，且胸口朝上")
        if has_chest and chest_score >= 0.60:
            return pack("俯卧", 0.92, "angleZ显示躯干接近水平，且胸口朝下")
        if has_side and abs(side_score) >= 0.60:
            if side_score > 0:
                return pack("右侧身", 0.88, "angleZ显示躯干接近水平，且右侧方向重力投影明显")
            else:
                return pack("左侧身", 0.88, "angleZ显示躯干接近水平，且左侧方向重力投影明显")
        return pack("水平姿态", 0.68, "angleZ显示躯干接近水平，但缺少胸口/侧身方向信息")

    # 2. 明显倾斜类
    if 35 <= torso_tilt < 70:
        if has_chest and chest_score <= -0.35:
            return pack("斜躺", 0.84, "angleZ显示中等倾斜，且胸口偏向上")
        if has_chest and chest_score >= 0.25:
            return pack("俯身", 0.84, "angleZ显示中等倾斜，且胸口偏向下/前下方")
        if has_side and abs(side_score) >= 0.55:
            return pack("侧倾", 0.76, "angleZ显示中等倾斜，且侧向重力投影明显")
        return pack("明显倾斜", 0.65, "angleZ显示躯干明显偏离竖直，但缺少方向信息")

    # 3. 轻度倾斜
    if 20 <= torso_tilt < 35:
        # 轻度倾斜且低频周期，可能是下蹲/蹲起或站姿动作
        if periodic_score >= 0.58 and 0.2 <= dominant_freq <= 1.6:
            return pack("轻度倾斜周期运动", 0.68, "angleZ轻度倾斜，且存在低频周期")
        return pack("轻度倾斜", 0.62, "angleZ显示躯干轻度偏离竖直")

    # 4. 竖直类
    if torso_tilt < 20:
        # 下蹲/蹲起：躯干近竖直 + 低频周期
        if periodic_score >= 0.60 and 0.2 <= dominant_freq <= 1.6:
            return pack("下蹲/蹲起周期", 0.74, "angleZ接近竖直，且存在低频上下周期")
        if periodic_score >= 0.65 and 0.8 <= dominant_freq <= 2.8:
            return pack("竖直周期运动", 0.70, "angleZ接近竖直，且存在周期运动，可能是行走/跑步/站姿训练")
        if motion_intensity < 0.08 and gyro_intensity < 12:
            return pack("竖直静止", 0.72, "angleZ接近竖直且运动强度低；站立/坐姿/悬挂需外部上下文区分")
        return pack("竖直运动", 0.68, "angleZ接近竖直但存在运动；站立/坐姿/悬挂需外部上下文区分")

    return pack("未知姿态", 0.35, "不满足主要姿态规则")


# -----------------------------
# 主识别流程
# -----------------------------

def recognize(
    input_path: str,
    outdir: str,
    fs: Optional[float] = None,
    window_sec: float = 2.0,
    stride_sec: float = 0.5,
    gravity_lowpass_sec: float = 0.6,
    angle_z_upright: Optional[float] = None,
    angle_x_baseline: Optional[float] = None,
    body_forward_axis: Optional[str] = None,
    body_right_axis: Optional[str] = None,
    smooth_min_windows: int = 2,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:

    raw = read_imu_file(input_path)
    mapping = map_columns(raw)
    df = standardize_dataframe(raw, mapping)

    if fs is None:
        fs = estimate_sample_rate(df)

    df = resample_dataframe(df, fs)

    acc = df[["ax", "ay", "az"]].to_numpy(dtype=float)

    # 加速度单位自动转换。如果模长接近 9.8，则认为单位为 m/s^2，转为 g。
    acc_norm_med = float(np.nanmedian(np.linalg.norm(acc, axis=1)))
    if acc_norm_med > 3.0:
        acc = acc / 9.80665

    gyro = None
    if all(c in df.columns for c in ["gx", "gy", "gz"]):
        gyro = df[["gx", "gy", "gz"]].to_numpy(dtype=float)

    angle_z = df["angle_z"].to_numpy(dtype=float)
    angle_x = df["angle_x"].to_numpy(dtype=float) if "angle_x" in df.columns else None
    angle_y = df["angle_y"].to_numpy(dtype=float) if "angle_y" in df.columns else None

    # 重力估计
    lp_win = max(3, int(gravity_lowpass_sec * fs))
    gravity = moving_average_2d(acc, lp_win)

    # 竖直基准
    if angle_z_upright is None:
        baseline_info = infer_upright_baseline(angle_z, acc, gyro, fs)
        angle_z_upright = float(baseline_info["angle_z_upright_baseline"])
    else:
        baseline_info = {
            "angle_z_upright_baseline": float(angle_z_upright),
            "source": "user_provided",
            "candidate_count": None,
        }

    # angleX baseline
    if angle_x_baseline is None and angle_x is not None:
        # 优先取前 2 秒的环形均值
        n0 = max(1, int(2.0 * fs))
        angle_x_baseline = circular_mean_deg(angle_x[:n0])

    body_forward = parse_axis(body_forward_axis)
    body_right = parse_axis(body_right_axis)

    # 用于周期检测的线性加速度
    linear_acc = acc - gravity

    win = max(5, int(window_sec * fs))
    stride = max(1, int(stride_sec * fs))

    rows: List[Dict] = []

    for s in range(0, max(1, len(df) - win + 1), stride):
        e = s + win
        if e > len(df):
            break

        z_mean = circular_mean_deg(angle_z[s:e])
        torso_tilt = angle_distance_deg(z_mean, angle_z_upright)

        x_mean = circular_mean_deg(angle_x[s:e]) if angle_x is not None else np.nan
        y_mean = circular_mean_deg(angle_y[s:e]) if angle_y is not None else np.nan

        x_drift = None
        if angle_x is not None and angle_x_baseline is not None and np.isfinite(angle_x_baseline):
            x_drift = circular_delta_deg(x_mean, angle_x_baseline)
            x_drift_abs = abs(x_drift)
        else:
            x_drift_abs = None

        g = normalize(np.nanmean(gravity[s:e], axis=0))

        chest_score = None
        if body_forward is not None:
            chest_score = float(np.dot(normalize(body_forward), g))

        side_score = None
        if body_right is not None:
            side_score = float(np.dot(normalize(body_right), g))

        lin = linear_acc[s:e]
        lin_norm = np.linalg.norm(lin, axis=1)
        motion_intensity = float(np.nanstd(lin_norm))

        if gyro is not None:
            gyro_norm = np.linalg.norm(gyro[s:e], axis=1)
            gyro_intensity = float(np.nanmean(gyro_norm))
        else:
            gyro_intensity = 0.0

        # 周期信号:
        # - 线性加速度模长
        # - angleZ 的相对倾角变化
        tilt_series = np.array([angle_distance_deg(v, angle_z_upright) for v in angle_z[s:e]], dtype=float)
        periodic_signal = 0.55 * zscore_safe(lin_norm) + 0.45 * zscore_safe(tilt_series)

        periodic_score, dominant_freq, period_sec, reps = compute_periodicity(periodic_signal, fs)

        posture, confidence, reason = classify_posture_rule(
            torso_tilt=torso_tilt,
            chest_score=chest_score,
            side_score=side_score,
            motion_intensity=motion_intensity,
            gyro_intensity=gyro_intensity,
            periodic_score=periodic_score,
            dominant_freq=dominant_freq,
            angle_x_drift_abs=x_drift_abs,
        )

        rows.append({
            "start_time": pd.Timestamp(df["time"].iloc[s]).isoformat(),
            "end_time": pd.Timestamp(df["time"].iloc[e - 1]).isoformat(),
            "start_idx": s,
            "end_idx": e,
            "posture": posture,
            "confidence": confidence,
            "angle_z_mean": z_mean,
            "angle_z_upright_baseline": angle_z_upright,
            "torso_tilt_deg": torso_tilt,
            "angle_x_mean": x_mean,
            "angle_x_baseline": angle_x_baseline,
            "angle_x_drift_abs": x_drift_abs,
            "angle_y_mean": y_mean,
            "chest_score": chest_score,
            "side_score": side_score,
            "motion_intensity": motion_intensity,
            "gyro_intensity": gyro_intensity,
            "periodic_score": periodic_score,
            "dominant_freq_hz": dominant_freq,
            "estimated_period_sec": period_sec,
            "estimated_reps_in_window": reps,
            "reason": reason,
        })

    windows_df = pd.DataFrame(rows)
    windows_df = smooth_windows(windows_df, min_windows=smooth_min_windows)
    segments_df = merge_segments(windows_df)
    summary = build_summary(
        windows_df=windows_df,
        segments_df=segments_df,
        mapping=mapping,
        fs=fs,
        baseline_info=baseline_info,
        angle_x_baseline=angle_x_baseline,
        body_forward_axis=body_forward_axis,
        body_right_axis=body_right_axis,
        parameters={
            "window_sec": window_sec,
            "stride_sec": stride_sec,
            "gravity_lowpass_sec": gravity_lowpass_sec,
            "smooth_min_windows": smooth_min_windows,
        },
    )

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    windows_df.to_csv(out / "posture_windows.csv", index=False, encoding="utf-8-sig")
    segments_df.to_csv(out / "posture_segments.csv", index=False, encoding="utf-8-sig")

    with open(out / "posture_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return windows_df, segments_df, summary


def smooth_windows(df: pd.DataFrame, min_windows: int = 2) -> pd.DataFrame:
    if df.empty or min_windows <= 1:
        return df

    labels = df["posture"].tolist()
    n = len(labels)

    runs = []
    i = 0
    while i < n:
        j = i + 1
        while j < n and labels[j] == labels[i]:
            j += 1
        runs.append([i, j, labels[i]])
        i = j

    new_labels = labels[:]

    for idx, (s, e, lab) in enumerate(runs):
        length = e - s
        if length >= min_windows:
            continue

        prev_lab = runs[idx - 1][2] if idx > 0 else None
        next_lab = runs[idx + 1][2] if idx < len(runs) - 1 else None

        if prev_lab is not None and next_lab is not None:
            if prev_lab == next_lab:
                fill = prev_lab
            else:
                prev_len = runs[idx - 1][1] - runs[idx - 1][0]
                next_len = runs[idx + 1][1] - runs[idx + 1][0]
                fill = prev_lab if prev_len >= next_len else next_lab
        elif prev_lab is not None:
            fill = prev_lab
        elif next_lab is not None:
            fill = next_lab
        else:
            fill = lab

        for k in range(s, e):
            new_labels[k] = fill

    out = df.copy()
    out["posture_raw"] = out["posture"]
    out["posture"] = new_labels
    return out


def merge_segments(windows_df: pd.DataFrame) -> pd.DataFrame:
    if windows_df.empty:
        return pd.DataFrame()

    rows = []
    labels = windows_df["posture"].tolist()
    n = len(labels)

    i = 0
    while i < n:
        j = i + 1
        while j < n and labels[j] == labels[i]:
            j += 1

        seg = windows_df.iloc[i:j]
        start_time = pd.to_datetime(seg["start_time"].iloc[0])
        end_time = pd.to_datetime(seg["end_time"].iloc[-1])
        duration = float((end_time - start_time).total_seconds())

        rows.append({
            "start_time": seg["start_time"].iloc[0],
            "end_time": seg["end_time"].iloc[-1],
            "duration_sec": duration,
            "posture": labels[i],
            "mean_confidence": float(seg["confidence"].mean()),
            "window_count": int(len(seg)),
            "mean_torso_tilt_deg": float(seg["torso_tilt_deg"].mean()),
            "std_torso_tilt_deg": float(seg["torso_tilt_deg"].std(ddof=0)),
            "mean_angle_z": float(seg["angle_z_mean"].mean()),
            "mean_angle_x_drift_abs": float(seg["angle_x_drift_abs"].dropna().mean()) if seg["angle_x_drift_abs"].notna().any() else None,
            "mean_chest_score": float(seg["chest_score"].dropna().mean()) if seg["chest_score"].notna().any() else None,
            "mean_side_score": float(seg["side_score"].dropna().mean()) if seg["side_score"].notna().any() else None,
            "mean_periodic_score": float(seg["periodic_score"].mean()),
            "dominant_freq_hz": float(seg["dominant_freq_hz"].median()),
            "estimated_period_sec": float(seg["estimated_period_sec"].dropna().median()) if seg["estimated_period_sec"].notna().any() else None,
        })

        i = j

    return pd.DataFrame(rows)


def build_summary(
    windows_df: pd.DataFrame,
    segments_df: pd.DataFrame,
    mapping: Dict,
    fs: float,
    baseline_info: Dict,
    angle_x_baseline: Optional[float],
    body_forward_axis: Optional[str],
    body_right_axis: Optional[str],
    parameters: Dict,
) -> Dict:
    if windows_df.empty:
        return {
            "error": "no_windows",
            "sample_rate_hz": fs,
            "column_mapping": mapping,
            "parameters": parameters,
        }

    posture_distribution = windows_df["posture"].value_counts(normalize=True).to_dict()
    dominant_posture = max(posture_distribution, key=posture_distribution.get)

    return {
        "dominant_posture": dominant_posture,
        "posture_distribution": posture_distribution,
        "sample_rate_hz": fs,
        "window_count": int(len(windows_df)),
        "segment_count": int(len(segments_df)),
        "angle_z_calibration": baseline_info,
        "angle_x_baseline": None if angle_x_baseline is None or not np.isfinite(angle_x_baseline) else float(angle_x_baseline),
        "axis_config": {
            "body_forward_axis": body_forward_axis,
            "body_right_axis": body_right_axis,
            "note": "如果 body_forward/body_right 未提供，脚本只能稳定输出竖直/倾斜/水平，无法高置信度细分平躺/俯卧/侧身/斜躺/俯身。",
        },
        "periodic": {
            "mean_periodic_score": float(windows_df["periodic_score"].mean()),
            "periodic_window_ratio": float((windows_df["periodic_score"] >= 0.58).mean()),
        },
        "column_mapping": mapping,
        "parameters": parameters,
        "label_notes": {
            "竖直静止": "可能是站立、坐姿或悬挂静止；胸前 IMU 单独难以区分。",
            "竖直运动": "可能是行走、站姿动作或悬挂摆动。",
            "下蹲/蹲起周期": "基于 angleZ 接近竖直 + 低频周期判断，最好结合视频确认。",
            "水平姿态": "angleZ 显示水平，但缺少 body_forward/body_right 或方向分数不足。",
            "平躺/俯卧/侧身": "需要提供正确的 body_forward/body_right 轴配置。"
        }
    }


# -----------------------------
# CLI
# -----------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="基于胸前固定 IMU angleZ 的用户姿态识别脚本")
    p.add_argument("--input", required=True, help="输入 IMU 文件，支持 csv/txt/tsv/xlsx")
    p.add_argument("--outdir", default="imu_posture_output", help="输出目录")
    p.add_argument("--fs", type=float, default=None, help="重采样频率 Hz，默认自动估计并限制在 10~100Hz")

    p.add_argument("--window-sec", type=float, default=2.0, help="滑动窗口长度，秒")
    p.add_argument("--stride-sec", type=float, default=0.5, help="滑动窗口步长，秒")
    p.add_argument("--gravity-lowpass-sec", type=float, default=0.6, help="重力低通平滑窗口，秒")

    p.add_argument("--angle-z-upright", type=float, default=None, help="竖直时 angleZ 基准，默认自动估计；已知可填 180")
    p.add_argument("--angle-x-baseline", type=float, default=None, help="angleX 佩戴基准，默认取前2秒均值")

    p.add_argument("--body-forward", default=None, help="胸口朝外对应的加速度轴，例如 +Y；未知可不填")
    p.add_argument("--body-right", default=None, help="用户右侧对应的加速度轴，例如 +X；未知可不填")

    p.add_argument("--smooth-min-windows", type=int, default=2, help="短状态平滑的最小窗口数")
    return p


def main():
    args = build_argparser().parse_args()

    windows_df, segments_df, summary = recognize(
        input_path=args.input,
        outdir=args.outdir,
        fs=args.fs,
        window_sec=args.window_sec,
        stride_sec=args.stride_sec,
        gravity_lowpass_sec=args.gravity_lowpass_sec,
        angle_z_upright=args.angle_z_upright,
        angle_x_baseline=args.angle_x_baseline,
        body_forward_axis=args.body_forward,
        body_right_axis=args.body_right,
        smooth_min_windows=args.smooth_min_windows,
    )

    print("IMU 姿态识别完成")
    print(f"输出目录: {args.outdir}")
    print("- posture_windows.csv   逐窗口姿态")
    print("- posture_segments.csv  合并后的姿态区间")
    print("- posture_summary.json  汇总信息")
    print("")
    print("主姿态:", summary.get("dominant_posture"))
    print("姿态分布:")
    print(json.dumps(summary.get("posture_distribution", {}), ensure_ascii=False, indent=2))
    print("")
    print("angleZ 竖直基准:")
    print(json.dumps(summary.get("angle_z_calibration", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
