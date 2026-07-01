#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 用户姿态分类器 (ML版)

基于 2~3s 滑动窗口 + 13维特征 + 集成学习模型 (RandomForest / ExtraTrees / XGBoost / LightGBM)

输入: 胸前佩戴 WT901BLE67 IMU 数据 (.txt/.csv/.xlsx)
输出: 9 类姿态标签

使用方式:
  # 1. 用规则引导生成伪标签训练集
  python imu_posture_classifier.py bootstrap --input data.txt --outdir output

  # 2. 用标注数据训练模型
  python imu_posture_classifier.py train --dataset labeled.csv --outdir output

  # 3. 推理
  python imu_posture_classifier.py predict --input data.txt --model output/model.joblib --outdir output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

# ──────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────

POSTURE_LABELS = [
    "standing_like",      # 站立系 (站立/行走/站姿训练)
    "upright_periodic",   # 竖直周期运动 (深蹲/站姿反复动作)
    "squatting",          # 下蹲/蹲坐
    "supine",             # 仰卧/平躺
    "incline_lying",      # 斜躺 (上斜卧推等)
    "bending_forward",    # 俯身/弯腰
    "side_lying",         # 侧身/侧卧
    "hanging_like",       # 悬挂系 (引体/悬垂举腿)
    "unknown",            # 未知
]

LABEL_ZH = {
    "standing_like":    "站立系",
    "upright_periodic": "竖直周期运动",
    "squatting":        "下蹲/蹲坐",
    "supine":           "仰卧/平躺",
    "incline_lying":    "斜躺",
    "bending_forward":  "俯身/弯腰",
    "side_lying":       "侧身/侧卧",
    "hanging_like":     "悬挂系",
    "unknown":          "未知",
}

LABEL_TO_IDX = {label: i for i, label in enumerate(POSTURE_LABELS)}
IDX_TO_LABEL = {i: label for label, i in LABEL_TO_IDX.items()}

FEATURE_NAMES = [
    "angleZ_to_180_mean",
    "angleZ_to_180_std",
    "angleZ_to_180_range",
    "angleX_drift_mean",
    "angleY_delta",
    "acc_norm_mean",
    "acc_norm_std",
    "gyro_norm_mean",
    "gyro_norm_std",
    "vertical_acc_energy",
    "dominant_freq",
    "periodic_score",
    "peak_count",
]

DEFAULT_WINDOW_SEC = 2.0
DEFAULT_STRIDE_SEC = 0.5
ANGLE_Z_UPRIGHT = 180.0

EPS = 1e-8


# ──────────────────────────────────────────────────
# 数据加载 (复用已有格式)
# ──────────────────────────────────────────────────

def load_imu_data(filepath: str) -> pd.DataFrame:
    p = Path(filepath)
    suffix = p.suffix.lower()

    if suffix in [".xlsx", ".xls"]:
        raw = pd.read_excel(p)
    elif suffix == ".csv":
        try:
            raw = pd.read_csv(p)
        except UnicodeDecodeError:
            raw = pd.read_csv(p, encoding="gbk")
    else:
        try:
            raw = pd.read_csv(p, sep=None, engine="python")
        except UnicodeDecodeError:
            raw = pd.read_csv(p, sep=None, engine="python", encoding="gbk")

    col_map = _auto_map_columns(raw)
    df = pd.DataFrame()
    df["time"] = pd.to_datetime(raw[col_map["time"]], errors="coerce")

    for key in ["ax", "ay", "az", "gx", "gy", "gz", "angleX", "angleY", "angleZ"]:
        if key in col_map:
            df[key] = pd.to_numeric(raw[col_map[key]], errors="coerce")

    df = df.dropna(subset=["time", "ax", "ay", "az", "angleZ"]).reset_index(drop=True)
    df["time_sec"] = (df["time"] - df["time"].iloc[0]).dt.total_seconds()
    return df


def _auto_map_columns(df: pd.DataFrame) -> Dict[str, str]:
    patterns = {
        "time":   ["时间", "timestamp", "time"],
        "ax":     ["加速度x(g)", "加速度x", "ax", "acc_x"],
        "ay":     ["加速度y(g)", "加速度y", "ay", "acc_y"],
        "az":     ["加速度z(g)", "加速度z", "az", "acc_z"],
        "gx":     ["角速度x(°/s)", "角速度x", "gx", "gyro_x"],
        "gy":     ["角速度y(°/s)", "角速度y", "gy", "gyro_y"],
        "gz":     ["角速度z(°/s)", "角速度z", "gz", "gyro_z"],
        "angleX": ["角度x(°)", "角度x", "anglex", "angle_x"],
        "angleY": ["角度y(°)", "角度y", "angley", "angle_y"],
        "angleZ": ["角度z(°)", "角度z", "anglez", "angle_z"],
    }

    result = {}
    cols_lower = {c: c.strip().lower().replace(" ", "").replace("（", "(").replace("）", ")")
                  for c in df.columns}

    for key, pats in patterns.items():
        for pat in pats:
            pat_n = pat.lower().replace(" ", "")
            for orig, norm in cols_lower.items():
                if pat_n == norm or pat_n in norm:
                    result[key] = orig
                    break
            if key in result:
                break

    required = ["time", "ax", "ay", "az", "angleZ"]
    missing = [k for k in required if k not in result]
    if missing:
        raise ValueError(f"缺少必要列: {missing}。当前列: {list(df.columns)}")

    return result


def estimate_fs(df: pd.DataFrame) -> float:
    dt = df["time"].diff().dt.total_seconds().dropna()
    dt = dt[(dt > 0) & np.isfinite(dt)]
    if len(dt) == 0:
        return 10.0
    return float(np.clip(round(1.0 / dt.median()), 5, 100))


# ──────────────────────────────────────────────────
# 角度工具
# ──────────────────────────────────────────────────

def angle_dist_180(angle: float) -> float:
    return abs((angle - ANGLE_Z_UPRIGHT + 180.0) % 360.0 - 180.0)


def circular_mean(angles: np.ndarray) -> float:
    rad = np.deg2rad(angles[np.isfinite(angles)])
    if len(rad) == 0:
        return np.nan
    return float(np.rad2deg(np.arctan2(np.mean(np.sin(rad)), np.mean(np.cos(rad)))))


# ──────────────────────────────────────────────────
# 13 维特征提取
# ──────────────────────────────────────────────────

def extract_features(win: pd.DataFrame, fs: float) -> Optional[np.ndarray]:
    if len(win) < max(5, int(fs * 0.5)):
        return None

    angleZ = win["angleZ"].values
    angleX = win["angleX"].values if "angleX" in win.columns else np.full(len(win), np.nan)
    angleY = win["angleY"].values if "angleY" in win.columns else np.full(len(win), np.nan)

    ax, ay, az = win["ax"].values, win["ay"].values, win["az"].values
    acc_norm = np.sqrt(ax**2 + ay**2 + az**2)

    has_gyro = all(c in win.columns for c in ["gx", "gy", "gz"])
    if has_gyro:
        gx, gy, gz = win["gx"].values, win["gy"].values, win["gz"].values
        gyro_norm = np.sqrt(gx**2 + gy**2 + gz**2)
    else:
        gyro_norm = np.zeros(len(win))

    # --- 1~3: angleZ 到 180° 的距离统计 ---
    z_dist = np.array([angle_dist_180(z) for z in angleZ])
    angleZ_to_180_mean = float(np.nanmean(z_dist))
    angleZ_to_180_std = float(np.nanstd(z_dist))
    angleZ_to_180_range = float(np.nanmax(z_dist) - np.nanmin(z_dist))

    # --- 4: angleX 漂移均值 (设备松动指标) ---
    if np.any(np.isfinite(angleX)):
        ax_vals = angleX[np.isfinite(angleX)]
        angleX_drift_mean = float(np.mean(np.abs(np.diff(ax_vals)))) if len(ax_vals) > 1 else 0.0
    else:
        angleX_drift_mean = 0.0

    # --- 5: angleY 窗口内变化量 (左右转) ---
    if np.any(np.isfinite(angleY)):
        ay_vals = angleY[np.isfinite(angleY)]
        angleY_delta = float(np.abs(ay_vals[-1] - ay_vals[0])) if len(ay_vals) > 1 else 0.0
    else:
        angleY_delta = 0.0

    # --- 6~7: 加速度范数统计 ---
    acc_norm_mean = float(np.nanmean(acc_norm))
    acc_norm_std = float(np.nanstd(acc_norm))

    # --- 8~9: 陀螺仪范数统计 ---
    gyro_norm_mean = float(np.nanmean(gyro_norm))
    gyro_norm_std = float(np.nanstd(gyro_norm))

    # --- 10: 竖直方向加速度能量 (az 去均值后的方差) ---
    az_vals = az.copy()
    vertical_acc_energy = float(np.var(az_vals - np.mean(az_vals)))

    # --- 11~12: 频域特征 (FFT 主频 + 周期性得分) ---
    dominant_freq, periodic_score = _compute_freq_features(acc_norm, fs)

    # --- 13: 峰值计数 (加速度范数的局部峰) ---
    peak_count = float(_count_peaks(acc_norm, fs))

    features = np.array([
        angleZ_to_180_mean,   # 0
        angleZ_to_180_std,    # 1
        angleZ_to_180_range,  # 2
        angleX_drift_mean,    # 3
        angleY_delta,         # 4
        acc_norm_mean,        # 5
        acc_norm_std,         # 6
        gyro_norm_mean,       # 7
        gyro_norm_std,        # 8
        vertical_acc_energy,  # 9
        dominant_freq,        # 10
        periodic_score,       # 11
        peak_count,           # 12
    ], dtype=np.float64)

    return features


def _compute_freq_features(signal: np.ndarray, fs: float,
                           min_freq: float = 0.2, max_freq: float = 3.0) -> Tuple[float, float]:
    x = signal.copy()
    x = x - np.mean(x)
    n = len(x)
    if n < max(8, int(fs)):
        return 0.0, 0.0

    std = np.std(x)
    if std < EPS:
        return 0.0, 0.0
    x = x / std

    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    spec = np.abs(np.fft.rfft(x * np.hanning(n))) ** 2

    band = (freqs >= min_freq) & (freqs <= max_freq)
    if band.sum() == 0:
        return 0.0, 0.0

    band_freqs = freqs[band]
    band_spec = spec[band]

    peak_idx = int(np.argmax(band_spec))
    dominant_freq = float(band_freqs[peak_idx])
    total_power = float(np.sum(band_spec) + EPS)
    peak_ratio = float(band_spec[peak_idx] / total_power)

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

    return dominant_freq, periodic_score


def _count_peaks(signal: np.ndarray, fs: float) -> int:
    if len(signal) < 5:
        return 0
    x = signal - np.mean(signal)
    threshold = np.std(x) * 0.3
    peaks = 0
    for i in range(1, len(x) - 1):
        if x[i] > x[i - 1] and x[i] > x[i + 1] and x[i] > threshold:
            peaks += 1
    return peaks


# ──────────────────────────────────────────────────
# 滑动窗口特征提取
# ──────────────────────────────────────────────────

def extract_all_windows(df: pd.DataFrame, window_sec: float = DEFAULT_WINDOW_SEC,
                        stride_sec: float = DEFAULT_STRIDE_SEC) -> pd.DataFrame:
    fs = estimate_fs(df)
    total_sec = df["time_sec"].iloc[-1]

    rows = []
    t = 0.0
    while t + window_sec <= total_sec + 0.01:
        mask = (df["time_sec"] >= t) & (df["time_sec"] < t + window_sec)
        win = df[mask]
        feats = extract_features(win, fs)
        if feats is not None:
            row = {"window_start_sec": round(t, 2), "window_end_sec": round(t + window_sec, 2)}
            row["start_time"] = str(win["time"].iloc[0])
            for i, name in enumerate(FEATURE_NAMES):
                row[name] = feats[i]
            rows.append(row)
        t += stride_sec

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────
# 规则引导伪标签 (Bootstrap)
# ──────────────────────────────────────────────────

def rule_based_label(feats: Dict[str, float]) -> Tuple[str, float]:
    tilt = feats["angleZ_to_180_mean"]
    tilt_std = feats["angleZ_to_180_std"]
    acc_std = feats["acc_norm_std"]
    gyro_mean = feats["gyro_norm_mean"]
    periodic = feats["periodic_score"]
    freq = feats["dominant_freq"]
    v_energy = feats["vertical_acc_energy"]

    # 水平姿态 (tilt >= 70°)
    if tilt >= 70:
        if acc_std < 0.08 and gyro_mean < 15:
            return "supine", 0.85
        return "side_lying", 0.65

    # 明显倾斜 (35~70°)
    if 35 <= tilt < 70:
        if acc_std < 0.10:
            return "incline_lying", 0.75
        return "bending_forward", 0.65

    # 轻度倾斜 (20~35°)
    if 20 <= tilt < 35:
        if periodic >= 0.55 and 0.2 <= freq <= 1.8:
            return "upright_periodic", 0.60
        return "bending_forward", 0.55

    # 竖直 (< 20°)
    if tilt < 20:
        if periodic >= 0.55 and 0.2 <= freq <= 1.8:
            return "upright_periodic", 0.70

        if acc_std < 0.04 and gyro_mean < 8:
            return "standing_like", 0.80

        if periodic >= 0.50 and freq >= 1.5:
            return "standing_like", 0.60

        if gyro_mean > 40 and v_energy > 0.02:
            return "squatting", 0.55

        return "standing_like", 0.60

    return "unknown", 0.30


def generate_pseudo_labels(windows_df: pd.DataFrame) -> pd.DataFrame:
    labels = []
    confs = []
    for _, row in windows_df.iterrows():
        feats = {name: row[name] for name in FEATURE_NAMES}
        label, conf = rule_based_label(feats)
        labels.append(label)
        confs.append(conf)

    df = windows_df.copy()
    df["label"] = labels
    df["label_zh"] = [LABEL_ZH[l] for l in labels]
    df["label_confidence"] = confs
    df["label_idx"] = [LABEL_TO_IDX[l] for l in labels]
    return df


# ──────────────────────────────────────────────────
# 模型训练
# ──────────────────────────────────────────────────

def train_model(dataset_path: str, outdir: str, model_type: str = "extra_trees"):
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.metrics import classification_report, confusion_matrix
    import joblib

    df = pd.read_csv(dataset_path)

    if "label" not in df.columns:
        raise ValueError("数据集需包含 'label' 列")

    missing_feats = [f for f in FEATURE_NAMES if f not in df.columns]
    if missing_feats:
        raise ValueError(f"数据集缺少特征列: {missing_feats}")

    X = df[FEATURE_NAMES].values.astype(np.float64)
    y = np.array([LABEL_TO_IDX.get(l, LABEL_TO_IDX["unknown"]) for l in df["label"]])

    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    model = _create_model(model_type)
    print(f"[训练] 模型: {model_type}, 样本数: {len(X)}, 特征: {len(FEATURE_NAMES)}")

    skf = StratifiedKFold(n_splits=min(5, len(np.unique(y))), shuffle=True, random_state=42)
    scores = cross_val_score(model, X, y, cv=skf, scoring="accuracy")
    print(f"[交叉验证] Accuracy: {scores.mean():.4f} ± {scores.std():.4f}")

    model.fit(X, y)

    y_pred = model.predict(X)
    present_labels = sorted(set(y) | set(y_pred))
    target_names = [IDX_TO_LABEL[i] for i in present_labels]
    report = classification_report(y, y_pred, labels=present_labels,
                                   target_names=target_names, output_dict=True)
    cm = confusion_matrix(y, y_pred, labels=present_labels)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    model_path = out / f"posture_model_{model_type}.joblib"
    joblib.dump({
        "model": model,
        "model_type": model_type,
        "feature_names": FEATURE_NAMES,
        "label_map": LABEL_TO_IDX,
        "label_map_inv": IDX_TO_LABEL,
    }, model_path)
    print(f"[保存] 模型 -> {model_path}")

    report_text = classification_report(y, y_pred, labels=present_labels, target_names=target_names)
    print("\n[分类报告]")
    print(report_text)

    meta = {
        "model_type": model_type,
        "n_samples": int(len(X)),
        "n_features": len(FEATURE_NAMES),
        "feature_names": FEATURE_NAMES,
        "labels": POSTURE_LABELS,
        "cv_accuracy_mean": float(scores.mean()),
        "cv_accuracy_std": float(scores.std()),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": target_names,
    }
    with open(out / f"training_report_{model_type}.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return model, meta


def _create_model(model_type: str):
    if model_type == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    elif model_type == "extra_trees":
        from sklearn.ensemble import ExtraTreesClassifier
        return ExtraTreesClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=3,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    elif model_type == "xgboost":
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=200, max_depth=8, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            use_label_encoder=False, eval_metric="mlogloss",
            random_state=42, n_jobs=-1,
        )
    elif model_type == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(
            n_estimators=200, max_depth=8, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            class_weight="balanced", random_state=42, n_jobs=-1,
            verbose=-1,
        )
    else:
        raise ValueError(f"不支持的模型: {model_type}。可选: random_forest, extra_trees, xgboost, lightgbm")


# ──────────────────────────────────────────────────
# 推理
# ──────────────────────────────────────────────────

def predict(input_path: str, model_path: str, outdir: str,
            window_sec: float = DEFAULT_WINDOW_SEC, stride_sec: float = DEFAULT_STRIDE_SEC):
    import joblib

    bundle = joblib.load(model_path)
    model = bundle["model"]
    model_type = bundle["model_type"]

    print(f"[推理] 模型: {model_type}, 输入: {input_path}")

    df = load_imu_data(input_path)
    print(f"[数据] 样本数: {len(df)}, 时长: {df['time_sec'].iloc[-1]:.1f}s")

    windows_df = extract_all_windows(df, window_sec, stride_sec)
    print(f"[窗口] 提取 {len(windows_df)} 个窗口")

    X = windows_df[FEATURE_NAMES].values.astype(np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    y_pred = model.predict(X)
    y_proba = model.predict_proba(X) if hasattr(model, "predict_proba") else None

    windows_df["label"] = [IDX_TO_LABEL[int(i)] for i in y_pred]
    windows_df["label_zh"] = [LABEL_ZH[IDX_TO_LABEL[int(i)]] for i in y_pred]
    if y_proba is not None:
        windows_df["confidence"] = np.max(y_proba, axis=1)

    segments = _merge_prediction_segments(windows_df)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    windows_df.to_csv(out / "predict_windows.csv", index=False, encoding="utf-8-sig")
    segments_df = pd.DataFrame(segments)
    segments_df.to_csv(out / "predict_segments.csv", index=False, encoding="utf-8-sig")

    summary = _build_prediction_summary(windows_df, segments, df)
    with open(out / "predict_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n[结果] 识别片段数: {len(segments)}")
    print(f"{'开始(s)':>8}  {'时长(s)':>7}  {'姿态':<20}  {'中文'}")
    print("─" * 60)
    for seg in segments:
        print(f"{seg['start_sec']:>8.1f}  {seg['duration_sec']:>7.1f}  "
              f"{seg['label']:<20}  {seg['label_zh']}")

    print(f"\n[保存] -> {outdir}/")
    return windows_df, segments, summary


def _merge_prediction_segments(windows_df: pd.DataFrame, min_seg_sec: float = 1.0) -> List[Dict]:
    if windows_df.empty:
        return []

    labels = _smooth_labels(windows_df["label"].tolist(), k=2)

    segments = []
    cur = labels[0]
    start = windows_df["window_start_sec"].iloc[0]

    for i in range(1, len(labels)):
        if labels[i] != cur:
            end = windows_df["window_start_sec"].iloc[i]
            dur = end - start
            if dur >= min_seg_sec:
                segments.append({
                    "label": cur,
                    "label_zh": LABEL_ZH.get(cur, cur),
                    "start_sec": round(start, 1),
                    "end_sec": round(end, 1),
                    "duration_sec": round(dur, 1),
                })
            cur = labels[i]
            start = windows_df["window_start_sec"].iloc[i]

    end = windows_df["window_end_sec"].iloc[-1]
    dur = end - start
    if dur >= min_seg_sec:
        segments.append({
            "label": cur,
            "label_zh": LABEL_ZH.get(cur, cur),
            "start_sec": round(start, 1),
            "end_sec": round(end, 1),
            "duration_sec": round(dur, 1),
        })

    return segments


def _smooth_labels(labels: List[str], k: int = 2) -> List[str]:
    from collections import Counter
    out = labels[:]
    for i in range(k, len(labels) - k):
        window = labels[i - k: i + k + 1]
        out[i] = Counter(window).most_common(1)[0][0]
    return out


def _build_prediction_summary(windows_df: pd.DataFrame, segments: List[Dict],
                               raw_df: pd.DataFrame) -> Dict:
    total_sec = raw_df["time_sec"].iloc[-1]
    dist = {}
    for seg in segments:
        label = seg["label"]
        dist[label] = dist.get(label, 0.0) + seg["duration_sec"]

    for k in dist:
        dist[k] = round(dist[k], 1)

    return {
        "total_sec": round(total_sec, 1),
        "segment_count": len(segments),
        "window_count": len(windows_df),
        "posture_duration": dist,
        "posture_distribution_pct": {k: round(v / total_sec * 100, 1) for k, v in dist.items()},
    }


# ──────────────────────────────────────────────────
# 多模型对比训练
# ──────────────────────────────────────────────────

def train_compare(dataset_path: str, outdir: str):
    results = {}
    model_types = ["random_forest", "extra_trees"]

    try:
        import xgboost  # noqa: F401
        model_types.append("xgboost")
    except ImportError:
        print("[跳过] xgboost 未安装")

    try:
        import lightgbm  # noqa: F401
        model_types.append("lightgbm")
    except ImportError:
        print("[跳过] lightgbm 未安装")

    for mt in model_types:
        print(f"\n{'='*60}")
        print(f"  训练模型: {mt}")
        print(f"{'='*60}")
        _, meta = train_model(dataset_path, outdir, model_type=mt)
        results[mt] = {
            "cv_accuracy_mean": meta["cv_accuracy_mean"],
            "cv_accuracy_std": meta["cv_accuracy_std"],
        }

    print(f"\n{'='*60}")
    print("  模型对比结果")
    print(f"{'='*60}")
    print(f"{'模型':<16} {'CV Accuracy':>14}")
    print("─" * 32)
    for mt, r in sorted(results.items(), key=lambda x: -x[1]["cv_accuracy_mean"]):
        print(f"{mt:<16} {r['cv_accuracy_mean']:>10.4f} ± {r['cv_accuracy_std']:.4f}")

    with open(Path(outdir) / "model_comparison.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


# ──────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IMU 用户姿态分类器 (ML版)")
    sub = parser.add_subparsers(dest="command", help="子命令")

    # bootstrap: 规则伪标签生成
    p_boot = sub.add_parser("bootstrap", help="从IMU数据用规则生成伪标签训练集")
    p_boot.add_argument("--input", required=True, help="IMU 数据文件")
    p_boot.add_argument("--outdir", default="posture_ml_output", help="输出目录")
    p_boot.add_argument("--window-sec", type=float, default=DEFAULT_WINDOW_SEC)
    p_boot.add_argument("--stride-sec", type=float, default=DEFAULT_STRIDE_SEC)

    # train: 训练模型
    p_train = sub.add_parser("train", help="训练姿态分类模型")
    p_train.add_argument("--dataset", required=True, help="标注数据 CSV (含 label 列和 13 特征列)")
    p_train.add_argument("--outdir", default="posture_ml_output", help="输出目录")
    p_train.add_argument("--model-type", default="extra_trees",
                         choices=["random_forest", "extra_trees", "xgboost", "lightgbm"],
                         help="模型类型")

    # train-compare: 多模型对比
    p_cmp = sub.add_parser("train-compare", help="多模型对比训练")
    p_cmp.add_argument("--dataset", required=True, help="标注数据 CSV")
    p_cmp.add_argument("--outdir", default="posture_ml_output", help="输出目录")

    # predict: 推理
    p_pred = sub.add_parser("predict", help="用训练好的模型推理")
    p_pred.add_argument("--input", required=True, help="IMU 数据文件")
    p_pred.add_argument("--model", required=True, help="模型文件 (.joblib)")
    p_pred.add_argument("--outdir", default="posture_ml_output", help="输出目录")
    p_pred.add_argument("--window-sec", type=float, default=DEFAULT_WINDOW_SEC)
    p_pred.add_argument("--stride-sec", type=float, default=DEFAULT_STRIDE_SEC)

    # extract: 仅提取特征
    p_ext = sub.add_parser("extract", help="仅提取滑动窗口特征 (不分类)")
    p_ext.add_argument("--input", required=True, help="IMU 数据文件")
    p_ext.add_argument("--outdir", default="posture_ml_output", help="输出目录")
    p_ext.add_argument("--window-sec", type=float, default=DEFAULT_WINDOW_SEC)
    p_ext.add_argument("--stride-sec", type=float, default=DEFAULT_STRIDE_SEC)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "bootstrap":
        df = load_imu_data(args.input)
        print(f"[数据] 样本: {len(df)}, 时长: {df['time_sec'].iloc[-1]:.1f}s")
        windows_df = extract_all_windows(df, args.window_sec, args.stride_sec)
        print(f"[窗口] 提取 {len(windows_df)} 个窗口, 特征: {len(FEATURE_NAMES)}")
        labeled = generate_pseudo_labels(windows_df)
        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        csv_path = out / "pseudo_labeled_dataset.csv"
        labeled.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[保存] 伪标签数据集 -> {csv_path}")
        print(f"\n[标签分布]")
        print(labeled["label"].value_counts().to_string())
        print(f"\n下一步: 人工校验/修正 label 列，然后运行:")
        print(f"  python {__file__} train --dataset {csv_path} --outdir {args.outdir}")

    elif args.command == "train":
        train_model(args.dataset, args.outdir, args.model_type)

    elif args.command == "train-compare":
        train_compare(args.dataset, args.outdir)

    elif args.command == "predict":
        predict(args.input, args.model, args.outdir, args.window_sec, args.stride_sec)

    elif args.command == "extract":
        df = load_imu_data(args.input)
        print(f"[数据] 样本: {len(df)}, 时长: {df['time_sec'].iloc[-1]:.1f}s")
        windows_df = extract_all_windows(df, args.window_sec, args.stride_sec)
        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        csv_path = out / "features.csv"
        windows_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"[保存] 特征 -> {csv_path} ({len(windows_df)} windows x {len(FEATURE_NAMES)} features)")


if __name__ == "__main__":
    main()
