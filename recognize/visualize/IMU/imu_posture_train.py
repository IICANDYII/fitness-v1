#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 姿态分类器训练脚本

从 (IMU.txt, ground_truth.json) 配对数据自动生成标注, 训练 7 类姿态模型:
  0 = standing    站立
  1 = sitting     坐姿
  2 = hanging     悬挂
  3 = lying       平躺
  4 = incline     斜躺
  5 = side_lying  侧身
  6 = bending     俯身

用法:
  # 从多个数据目录构建数据集并训练
  python imu_posture_train.py --data_dirs dir1 dir2 ... --outdir output

  # 每个 data_dir 下需包含:
  #   IMU.txt          — WT901BLE67 原始数据 (tab分隔, 22列)
  #   ground_truth.json — 动作标注 [{start, end, type, label}, ...]

  # 自动扫描 shared 目录下所有配对数据
  python imu_posture_train.py --scan --outdir output

  # 仅生成标注数据集 (不训练)
  python imu_posture_train.py --scan --export_only --outdir output

  # 用已有模型推理
  python imu_posture_train.py --predict --input data.txt --model output/posture7_model.joblib --outdir output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent

# ──────────────────────────────────────────────────
# 7 类姿态定义
# ──────────────────────────────────────────────────

POSTURE_LABELS = [
    "standing",     # 0
    "sitting",      # 1
    "hanging",      # 2
    "lying",        # 3
    "incline",      # 4
    "side_lying",   # 5
    "bending",      # 6
]

LABEL_ZH = {
    "standing":   "站立",
    "sitting":    "坐姿",
    "hanging":    "悬挂",
    "lying":      "平躺",
    "incline":    "斜躺",
    "side_lying": "侧身",
    "bending":    "俯身",
}

LABEL_TO_IDX = {label: i for i, label in enumerate(POSTURE_LABELS)}
IDX_TO_LABEL = {i: label for label, i in LABEL_TO_IDX.items()}

# exercise_posture.json 中文姿态 → 7 类标签
ZH_TO_LABEL = {
    "站立": "standing",
    "坐姿": "sitting",
    "悬挂": "hanging",
    "平躺": "lying",
    "斜躺": "incline",
    "侧身": "side_lying",
    "俯身": "bending",
}

# ──────────────────────────────────────────────────
# 13 维特征 (复用已有设计)
# ──────────────────────────────────────────────────

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
# 数据加载
# ──────────────────────────────────────────────────

def load_exercise_posture_map(path: Path | None = None) -> Dict[str, str]:
    """加载 exercise_posture.json, 返回 {动作名: 7类标签}"""
    if path is None:
        path = SCRIPT_DIR / "exercise_posture.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mapping = {}
    for item in data["exercises"]:
        zh_posture = item["posture"]
        label = ZH_TO_LABEL.get(zh_posture)
        if label:
            mapping[item["exercise"]] = label
    return mapping


def load_imu_txt(filepath: Path) -> pd.DataFrame:
    """加载 WT901BLE67 原始 IMU 数据 (22列 tab 分隔)"""
    df = pd.read_csv(filepath, sep="\t", header=0, encoding="utf-8")
    col_names = [
        "time", "device",
        "ax", "ay", "az",
        "gx", "gy", "gz",
        "angleX", "angleY", "angleZ",
        "magX", "magY", "magZ",
        "q0", "q1", "q2", "q3",
        "temp", "alt", "pressure", "ver", "battery",
    ]
    if len(df.columns) == len(col_names):
        df.columns = col_names
    else:
        # 尝试自动映射
        df.columns = [c.strip() for c in df.columns]
        rename = {
            "时间": "time", "设备名称": "device",
            "加速度X(g)": "ax", "加速度Y(g)": "ay", "加速度Z(g)": "az",
            "角速度X(°/s)": "gx", "角速度Y(°/s)": "gy", "角速度Z(°/s)": "gz",
            "角度X(°)": "angleX", "角度Y(°)": "angleY", "角度Z(°)": "angleZ",
        }
        df = df.rename(columns=rename)

    df = df.replace("null", np.nan)
    df["time"] = pd.to_datetime(df["time"], errors="coerce")

    for col in ["ax", "ay", "az", "gx", "gy", "gz", "angleX", "angleY", "angleZ"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["time", "ax", "ay", "az"]).reset_index(drop=True)
    df["time_sec"] = (df["time"] - df["time"].iloc[0]).dt.total_seconds()
    return df


def load_ground_truth(filepath: Path) -> List[Dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def estimate_fs(df: pd.DataFrame) -> float:
    dt = df["time"].diff().dt.total_seconds().dropna()
    dt = dt[(dt > 0) & np.isfinite(dt)]
    if len(dt) == 0:
        return 10.0
    return float(np.clip(round(1.0 / dt.median()), 5, 100))


# ──────────────────────────────────────────────────
# 标注生成: ground_truth + exercise_posture → 每个窗口的姿态标签
# ──────────────────────────────────────────────────

def _parse_gt_time_to_sec(
    seg: Dict,
    key: str,
    imu_start_time: Optional[pd.Timestamp] = None,
) -> float:
    """
    将 ground_truth 的时间字段统一转换为 IMU 相对秒.

    兼容两种 GT 格式:
      1. 老格式: {"start": 11.5, "end": 103.8}
      2. 新格式: {"start": "2026-...+08:00", "end": "2026-...+08:00",
                 "start_offset": 0, "end_offset": 89.2}

    优先使用绝对时间与 IMU 第一条时间对齐；如果没有 imu_start_time，
    再回退到 start_offset/end_offset；最后才尝试直接 float(start/end)。
    """
    value = seg.get(key)

    # 老格式: start/end 本身就是相对秒
    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    # 新格式最佳路径: ISO 绝对时间 - IMU 第一条绝对时间
    if imu_start_time is not None and value is not None:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.notna(ts):
            # WT901 IMU 文件中的时间通常是不带时区的本地时间；
            # GT 的 +08:00 也是同一块本地时钟。这里去掉 tzinfo，
            # 不做 UTC 转换，否则会错误平移 8 小时。
            if ts.tzinfo is not None:
                ts = ts.tz_localize(None)
            if getattr(imu_start_time, "tzinfo", None) is not None:
                imu_start_time = imu_start_time.tz_localize(None)
            return float((ts - imu_start_time).total_seconds())

    # 新格式回退路径: start_offset/end_offset，通常是视频相对秒
    offset_key = f"{key}_offset"
    if offset_key in seg:
        return float(seg[offset_key])

    raise ValueError(f"无法解析 GT 时间字段 {key}: {value!r}")


def build_posture_labels_from_gt(
    gt: List[Dict],
    exercise_map: Dict[str, str],
    total_sec: float,
    imu_start_time: Optional[pd.Timestamp] = None,
) -> List[Tuple[float, float, str]]:
    """
    将 ground_truth 区间转换为 (start, end, posture_label) 列表.

    输出时间统一为 IMU time_sec 坐标系:
      - 如果 GT start/end 是数字: 直接当作相对秒
      - 如果 GT start/end 是 ISO 时间: 减去 IMU 第一条 timestamp
      - 如果无法解析 ISO: 使用 start_offset/end_offset 回退

    exercise 区间: 通过 exercise_posture.json 查找姿态
    transition 区间: 标记为 standing (过渡/走路通常是站立)
    """
    labeled_intervals = []
    for seg in gt:
        t0 = _parse_gt_time_to_sec(seg, "start", imu_start_time)
        t1 = _parse_gt_time_to_sec(seg, "end", imu_start_time)

        # 裁剪到 IMU 有效范围，避免视频和 IMU 起点有小偏移时越界
        t0 = max(0.0, min(float(t0), float(total_sec)))
        t1 = max(0.0, min(float(t1), float(total_sec)))
        if t1 <= t0:
            continue

        seg_type = seg.get("type", "")
        exercise = seg.get("label", "")

        if seg_type == "exercise" and exercise in exercise_map:
            posture = exercise_map[exercise]
            labeled_intervals.append((t0, t1, posture))
        elif seg_type == "transition":
            labeled_intervals.append((t0, t1, "standing"))

    return labeled_intervals


def assign_window_label(
    win_start: float,
    win_end: float,
    labeled_intervals: List[Tuple[float, float, str]],
    overlap_threshold: float = 0.6,
) -> Optional[str]:
    """
    为一个窗口分配姿态标签.
    选择与窗口重叠比例最大的区间标签, 要求重叠 >= overlap_threshold.
    """
    win_len = win_end - win_start
    if win_len <= 0:
        return None

    best_label = None
    best_overlap = 0.0

    for t0, t1, label in labeled_intervals:
        overlap = max(0, min(win_end, t1) - max(win_start, t0))
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = label

    if best_overlap / win_len >= overlap_threshold:
        return best_label
    return None


# ──────────────────────────────────────────────────
# 特征提取
# ──────────────────────────────────────────────────

def angle_dist_180(angle: float) -> float:
    return abs((angle - ANGLE_Z_UPRIGHT + 180.0) % 360.0 - 180.0)


def extract_features(win: pd.DataFrame, fs: float) -> Optional[np.ndarray]:
    if len(win) < max(5, int(fs * 0.5)):
        return None

    angleZ = win["angleZ"].values if "angleZ" in win.columns else np.full(len(win), 180.0)
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

    z_dist = np.array([angle_dist_180(z) for z in angleZ])
    angleZ_to_180_mean = float(np.nanmean(z_dist))
    angleZ_to_180_std = float(np.nanstd(z_dist))
    angleZ_to_180_range = float(np.nanmax(z_dist) - np.nanmin(z_dist))

    if np.any(np.isfinite(angleX)):
        ax_vals = angleX[np.isfinite(angleX)]
        angleX_drift_mean = float(np.mean(np.abs(np.diff(ax_vals)))) if len(ax_vals) > 1 else 0.0
    else:
        angleX_drift_mean = 0.0

    if np.any(np.isfinite(angleY)):
        ay_vals = angleY[np.isfinite(angleY)]
        angleY_delta = float(np.abs(ay_vals[-1] - ay_vals[0])) if len(ay_vals) > 1 else 0.0
    else:
        angleY_delta = 0.0

    acc_norm_mean = float(np.nanmean(acc_norm))
    acc_norm_std = float(np.nanstd(acc_norm))
    gyro_norm_mean = float(np.nanmean(gyro_norm))
    gyro_norm_std = float(np.nanstd(gyro_norm))

    az_vals = az.copy()
    vertical_acc_energy = float(np.var(az_vals - np.mean(az_vals)))

    dominant_freq, periodic_score = _compute_freq_features(acc_norm, fs)
    peak_count = float(_count_peaks(acc_norm, fs))

    return np.array([
        angleZ_to_180_mean,
        angleZ_to_180_std,
        angleZ_to_180_range,
        angleX_drift_mean,
        angleY_delta,
        acc_norm_mean,
        acc_norm_std,
        gyro_norm_mean,
        gyro_norm_std,
        vertical_acc_energy,
        dominant_freq,
        periodic_score,
        peak_count,
    ], dtype=np.float64)


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
    return dominant_freq, float(np.clip(periodic_score, 0.0, 1.0))


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
# 核心: 从一对 (IMU, GT) 提取带标签的窗口特征
# ──────────────────────────────────────────────────

def extract_labeled_windows(
    imu_df: pd.DataFrame,
    labeled_intervals: List[Tuple[float, float, str]],
    window_sec: float = DEFAULT_WINDOW_SEC,
    stride_sec: float = DEFAULT_STRIDE_SEC,
    overlap_threshold: float = 0.6,
    source: str = "",
) -> pd.DataFrame:
    """滑动窗口提取特征, 同时根据标注区间分配标签"""
    fs = estimate_fs(imu_df)
    total_sec = imu_df["time_sec"].iloc[-1]

    rows = []
    t = 0.0
    while t + window_sec <= total_sec + 0.01:
        mask = (imu_df["time_sec"] >= t) & (imu_df["time_sec"] < t + window_sec)
        win = imu_df[mask]
        feats = extract_features(win, fs)
        if feats is None:
            t += stride_sec
            continue

        label = assign_window_label(t, t + window_sec, labeled_intervals, overlap_threshold)
        if label is None:
            t += stride_sec
            continue

        row = {
            "window_start_sec": round(t, 2),
            "window_end_sec": round(t + window_sec, 2),
            "source": source,
            "label": label,
            "label_idx": LABEL_TO_IDX[label],
            "label_zh": LABEL_ZH[label],
        }
        for i, name in enumerate(FEATURE_NAMES):
            row[name] = feats[i]
        rows.append(row)
        t += stride_sec

    return pd.DataFrame(rows)


def build_dataset(
    data_dirs: List[Path],
    exercise_map: Dict[str, str],
    window_sec: float = DEFAULT_WINDOW_SEC,
    stride_sec: float = DEFAULT_STRIDE_SEC,
) -> pd.DataFrame:
    """从多个 (IMU.txt, ground_truth.json) 目录构建完整数据集"""
    all_dfs = []
    for d in data_dirs:
        imu_path = d / "IMU.txt"
        gt_path = d / "ground_truth.json"
        if not imu_path.exists() or not gt_path.exists():
            print(f"  [跳过] {d.name}: 缺少 IMU.txt 或 ground_truth.json")
            continue

        print(f"  [加载] {d.name}")
        imu_df = load_imu_txt(imu_path)
        gt = load_ground_truth(gt_path)

        labeled_intervals = build_posture_labels_from_gt(
            gt, exercise_map, imu_df["time_sec"].iloc[-1], imu_df["time"].iloc[0]
        )
        if not labeled_intervals:
            print(f"    → 无有效标注区间, 跳过")
            continue

        windows_df = extract_labeled_windows(
            imu_df, labeled_intervals, window_sec, stride_sec, source=d.name,
        )
        print(f"    → {len(windows_df)} 个窗口, IMU时长 {imu_df['time_sec'].iloc[-1]:.1f}s")

        if not windows_df.empty:
            label_dist = windows_df["label"].value_counts().to_dict()
            print(f"    → 标签分布: {label_dist}")
            all_dfs.append(windows_df)

    if not all_dfs:
        print("[错误] 未获取到任何有效数据")
        return pd.DataFrame()

    dataset = pd.concat(all_dfs, ignore_index=True)
    print(f"\n[数据集] 总窗口数: {len(dataset)}")
    print(f"[标签分布]\n{dataset['label'].value_counts().to_string()}")
    return dataset


# ──────────────────────────────────────────────────
# 训练
# ──────────────────────────────────────────────────

def train(dataset: pd.DataFrame, outdir: Path, model_type: str = "extra_trees"):
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.metrics import classification_report, confusion_matrix
    import joblib

    X = dataset[FEATURE_NAMES].values.astype(np.float64)
    y = dataset["label_idx"].values.astype(int)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    present_classes = sorted(set(y))
    n_classes = len(present_classes)
    print(f"\n[训练] 模型: {model_type}, 样本: {len(X)}, 类别: {n_classes}")

    model = _create_model(model_type)

    n_splits = min(5, min(np.bincount(y)[np.bincount(y) > 0]))
    if n_splits >= 2:
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, y, cv=skf, scoring="accuracy")
        print(f"[交叉验证] Accuracy: {scores.mean():.4f} ± {scores.std():.4f}")
    else:
        scores = np.array([0.0])
        print("[警告] 样本太少, 跳过交叉验证")

    model.fit(X, y)

    y_pred = model.predict(X)
    target_names = [IDX_TO_LABEL[i] for i in present_classes]
    report_text = classification_report(y, y_pred, labels=present_classes, target_names=target_names)
    report_dict = classification_report(y, y_pred, labels=present_classes,
                                        target_names=target_names, output_dict=True)
    cm = confusion_matrix(y, y_pred, labels=present_classes)

    print(f"\n[分类报告]\n{report_text}")

    outdir.mkdir(parents=True, exist_ok=True)

    model_path = outdir / f"posture7_model_{model_type}.joblib"
    joblib.dump({
        "model": model,
        "model_type": model_type,
        "feature_names": FEATURE_NAMES,
        "label_to_idx": LABEL_TO_IDX,
        "idx_to_label": IDX_TO_LABEL,
        "label_zh": LABEL_ZH,
        "posture_labels": POSTURE_LABELS,
        "window_sec": DEFAULT_WINDOW_SEC,
        "stride_sec": DEFAULT_STRIDE_SEC,
    }, model_path)
    print(f"[保存] 模型 → {model_path}")

    meta = {
        "model_type": model_type,
        "n_samples": int(len(X)),
        "n_classes": n_classes,
        "posture_labels": POSTURE_LABELS,
        "label_zh": LABEL_ZH,
        "present_classes": target_names,
        "cv_accuracy_mean": float(scores.mean()),
        "cv_accuracy_std": float(scores.std()),
        "classification_report": report_dict,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": target_names,
        "data_sources": dataset["source"].unique().tolist(),
        "label_distribution": dataset["label"].value_counts().to_dict(),
    }
    meta_path = outdir / f"training_report_{model_type}.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[保存] 报告 → {meta_path}")

    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        pairs = sorted(zip(FEATURE_NAMES, imp), key=lambda x: x[1], reverse=True)
        print("\n[特征重要性]")
        for name, score in pairs:
            bar = "█" * int(score * 50)
            print(f"  {name:<25} {score:.4f}  {bar}")

    return model, meta


def _create_model(model_type: str):
    if model_type == "random_forest":
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=2,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )
    elif model_type == "extra_trees":
        from sklearn.ensemble import ExtraTreesClassifier
        return ExtraTreesClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=2,
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
            class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1,
        )
    else:
        raise ValueError(f"不支持: {model_type}。可选: random_forest, extra_trees, xgboost, lightgbm")


# ──────────────────────────────────────────────────
# 推理
# ──────────────────────────────────────────────────

def predict(input_path: Path, model_path: Path, outdir: Path,
            window_sec: float = DEFAULT_WINDOW_SEC,
            stride_sec: float = DEFAULT_STRIDE_SEC):
    import joblib

    bundle = joblib.load(model_path)
    model = bundle["model"]

    print(f"[推理] 模型: {bundle['model_type']}, 输入: {input_path}")

    imu_df = load_imu_txt(input_path)
    fs = estimate_fs(imu_df)
    total_sec = imu_df["time_sec"].iloc[-1]
    print(f"[数据] 样本: {len(imu_df)}, 时长: {total_sec:.1f}s, 采样率: {fs:.0f}Hz")

    rows = []
    t = 0.0
    while t + window_sec <= total_sec + 0.01:
        mask = (imu_df["time_sec"] >= t) & (imu_df["time_sec"] < t + window_sec)
        win = imu_df[mask]
        feats = extract_features(win, fs)
        if feats is not None:
            row = {"window_start_sec": round(t, 2), "window_end_sec": round(t + window_sec, 2)}
            for i, name in enumerate(FEATURE_NAMES):
                row[name] = feats[i]
            rows.append(row)
        t += stride_sec

    windows_df = pd.DataFrame(rows)
    X = windows_df[FEATURE_NAMES].values.astype(np.float64)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    y_pred = model.predict(X)
    y_proba = model.predict_proba(X) if hasattr(model, "predict_proba") else None

    idx_to_label = bundle["idx_to_label"]
    label_zh = bundle["label_zh"]

    windows_df["label"] = [idx_to_label[int(i)] for i in y_pred]
    windows_df["label_idx"] = [int(i) for i in y_pred]
    windows_df["label_zh"] = [label_zh[idx_to_label[int(i)]] for i in y_pred]
    if y_proba is not None:
        windows_df["confidence"] = np.max(y_proba, axis=1)

    segments = _merge_segments(windows_df, label_zh)

    outdir.mkdir(parents=True, exist_ok=True)
    windows_df.to_csv(outdir / "predict_windows.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(segments).to_csv(outdir / "predict_segments.csv", index=False, encoding="utf-8-sig")

    summary = {
        "total_sec": round(total_sec, 1),
        "n_windows": len(windows_df),
        "n_segments": len(segments),
        "segments": segments,
    }
    with open(outdir / "predict_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'开始':>8}  {'结束':>8}  {'时长':>6}  {'姿态':<12}  {'中文'}")
    print("─" * 55)
    for seg in segments:
        print(f"{seg['start_sec']:>8.1f}  {seg['end_sec']:>8.1f}  "
              f"{seg['duration_sec']:>6.1f}  {seg['label']:<12}  {seg['label_zh']}")

    print(f"\n[保存] → {outdir}/")
    return windows_df, segments


def _merge_segments(windows_df: pd.DataFrame, label_zh: Dict, min_seg_sec: float = 1.0):
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
                    "label": cur, "label_zh": label_zh.get(cur, cur),
                    "label_idx": LABEL_TO_IDX.get(cur, -1),
                    "start_sec": round(start, 1), "end_sec": round(end, 1),
                    "duration_sec": round(dur, 1),
                })
            cur = labels[i]
            start = windows_df["window_start_sec"].iloc[i]

    end = windows_df["window_end_sec"].iloc[-1]
    dur = end - start
    if dur >= min_seg_sec:
        segments.append({
            "label": cur, "label_zh": label_zh.get(cur, cur),
            "label_idx": LABEL_TO_IDX.get(cur, -1),
            "start_sec": round(start, 1), "end_sec": round(end, 1),
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


# ──────────────────────────────────────────────────
# 测试: 推理 + GT对比 + HTML可视化
# ──────────────────────────────────────────────────

def test_with_gt(
    data_dirs: List[Path],
    model_path: Path,
    outdir: Path,
    window_sec: float = DEFAULT_WINDOW_SEC,
    stride_sec: float = DEFAULT_STRIDE_SEC,
):
    import joblib
    from collections import Counter

    bundle = joblib.load(model_path)
    model = bundle["model"]
    idx_to_label = bundle["idx_to_label"]
    label_zh_map = bundle["label_zh"]
    print(f"[模型] {bundle['model_type']}, 已加载: {model_path}")

    exercise_map = load_exercise_posture_map()
    print(f"[映射] {len(exercise_map)} 个动作→姿态")

    results = []
    print(f"[测试] 输入目录数: {len(data_dirs)}")
    for d in data_dirs:
        print(f"\n[检查目录] {d}")
        imu_path = d / "IMU.txt"
        gt_path = d / "ground_truth.json"
        if not imu_path.exists() or not gt_path.exists():
            print(f"[跳过] {d.name}: 缺少 IMU.txt 或 ground_truth.json")
            continue

        print(f"\n[测试] {d.name}")
        imu_df = load_imu_txt(imu_path)
        gt = load_ground_truth(gt_path)
        total_sec = imu_df["time_sec"].iloc[-1]
        fs = estimate_fs(imu_df)

        # 推理
        rows = []
        t = 0.0
        while t + window_sec <= total_sec + 0.01:
            mask = (imu_df["time_sec"] >= t) & (imu_df["time_sec"] < t + window_sec)
            win = imu_df[mask]
            feats = extract_features(win, fs)
            if feats is not None:
                row = {"window_start_sec": round(t, 2), "window_end_sec": round(t + window_sec, 2)}
                for i, name in enumerate(FEATURE_NAMES):
                    row[name] = feats[i]
                rows.append(row)
            t += stride_sec

        windows_df = pd.DataFrame(rows)
        if windows_df.empty:
            print(f"  无有效窗口, 跳过")
            continue

        X = windows_df[FEATURE_NAMES].values.astype(np.float64)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        y_pred = model.predict(X)
        y_proba = model.predict_proba(X) if hasattr(model, "predict_proba") else None

        windows_df["label"] = [idx_to_label[int(i)] for i in y_pred]
        windows_df["label_idx"] = [int(i) for i in y_pred]
        windows_df["label_zh"] = [label_zh_map[idx_to_label[int(i)]] for i in y_pred]
        if y_proba is not None:
            windows_df["confidence"] = np.max(y_proba, axis=1)

        pred_segments = _merge_segments(windows_df, label_zh_map)

        # GT → 标注区间 (带原始动作名)
        imu_start_time = imu_df["time"].iloc[0]
        gt_intervals = build_posture_labels_from_gt(gt, exercise_map, total_sec, imu_start_time)

        gt_segments = []
        for t0, t1, posture in gt_intervals:
            exercise_name = ""
            for seg in gt:
                seg_t0 = _parse_gt_time_to_sec(seg, "start", imu_start_time)
                if abs(seg_t0 - t0) < 2.0:
                    exercise_name = seg.get("label", "")
                    break
            gt_segments.append({
                "label": posture, "label_zh": LABEL_ZH.get(posture, posture),
                "start_sec": round(t0, 1), "end_sec": round(t1, 1),
                "duration_sec": round(t1 - t0, 1),
                "exercise": exercise_name,
            })

        # 区间级对比
        interval_results = []
        for seg in gt_segments:
            t0, t1 = seg["start_sec"], seg["end_sec"]
            gt_label = seg["label"]
            preds_in = []
            for _, row in windows_df.iterrows():
                overlap = max(0, min(t1, row["window_end_sec"]) - max(t0, row["window_start_sec"]))
                if overlap > 0:
                    preds_in.append(row["label"])
            pred_label = Counter(preds_in).most_common(1)[0][0] if preds_in else "—"
            interval_results.append({
                "time": f"{t0:.0f}-{t1:.0f}s",
                "exercise": seg["exercise"],
                "gt": LABEL_ZH.get(gt_label, gt_label),
                "pred": LABEL_ZH.get(pred_label, pred_label),
                "match": pred_label == gt_label,
            })

        # 窗口级准确率
        correct = 0
        total_eval = 0
        for _, row in windows_df.iterrows():
            wt0, wt1 = row["window_start_sec"], row["window_end_sec"]
            wlen = wt1 - wt0
            best_label, best_overlap = None, 0
            for gt_t0, gt_t1, gt_label in gt_intervals:
                overlap = max(0, min(wt1, gt_t1) - max(wt0, gt_t0))
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_label = gt_label
            if best_label and best_overlap / wlen >= 0.6:
                total_eval += 1
                if row["label"] == best_label:
                    correct += 1

        acc = correct / total_eval if total_eval > 0 else 0
        n_match = sum(1 for r in interval_results if r["match"])
        n_total = len(interval_results)

        print(f"  IMU: {total_sec:.0f}s | 窗口: {len(windows_df)} | 窗口准确率: {acc:.1%} ({correct}/{total_eval})")
        print(f"  区间: {n_match}/{n_total} 正确")
        for r in interval_results:
            icon = "O" if r["match"] else "X"
            print(f"    {icon} {r['time']:>12}  {r['exercise']:<12}  GT={r['gt']:<4}  Pred={r['pred']}")

        gt_t0 = min(s["start_sec"] for s in gt_segments) if gt_segments else 0
        gt_t1 = max(s["end_sec"] for s in gt_segments) if gt_segments else total_sec
        pred_in_range = [s for s in pred_segments
                         if s["end_sec"] > gt_t0 and s["start_sec"] < gt_t1]
        for s in pred_in_range:
            s["start_sec"] = max(s["start_sec"], gt_t0)
            s["end_sec"] = min(s["end_sec"], gt_t1)

        results.append({
            "name": d.name, "total_sec": total_sec,
            "gt_start": gt_t0, "gt_end": gt_t1,
            "n_windows": len(windows_df),
            "window_accuracy": round(acc, 4),
            "window_correct": correct, "window_total": total_eval,
            "interval_correct": n_match, "interval_total": n_total,
            "intervals": interval_results,
            "gt_segments": gt_segments,
            "pred_segments": pred_in_range,
        })

    if not results:
        print("[错误] 无有效测试结果")
        return

    # 汇总
    total_w_cor = sum(r["window_correct"] for r in results)
    total_w_tot = sum(r["window_total"] for r in results)
    total_i_cor = sum(r["interval_correct"] for r in results)
    total_i_tot = sum(r["interval_total"] for r in results)
    overall_acc = total_w_cor / total_w_tot if total_w_tot > 0 else 0

    print(f"\n{'='*60}")
    print(f"[汇总] 数据集: {len(results)}  窗口准确率: {overall_acc:.1%} ({total_w_cor}/{total_w_tot})  区间: {total_i_cor}/{total_i_tot}")
    print(f"{'='*60}")
    print(f"{'数据集':<16} {'窗口准确率':>10} {'区间':>8}")
    print(f"{'-'*40}")
    for r in results:
        print(f"{r['name']:<16} {r['window_accuracy']:>10.1%} {r['interval_correct']}/{r['interval_total']:>6}")

    # 保存 JSON 报告
    outdir.mkdir(parents=True, exist_ok=True)
    report = {
        "model": str(model_path),
        "overall_window_accuracy": round(overall_acc, 4),
        "overall_window_correct": total_w_cor,
        "overall_window_total": total_w_tot,
        "overall_interval_correct": total_i_cor,
        "overall_interval_total": total_i_tot,
        "datasets": results,
    }
    report_path = outdir / "test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n[保存] 测试报告 → {report_path}")

    # 生成 HTML 可视化
    _generate_test_html(results, outdir / "test_results.html")


def _generate_test_html(results: List[Dict], outpath: Path):
    """生成测试结果的可视化 HTML"""
    COLORS = {
        "standing": "#4CAF50", "sitting": "#2196F3", "hanging": "#9C27B0",
        "lying": "#FF9800", "incline": "#FF5722", "side_lying": "#00BCD4", "bending": "#795548",
    }
    total_w_cor = sum(r["window_correct"] for r in results)
    total_w_tot = sum(r["window_total"] for r in results)
    total_i_cor = sum(r["interval_correct"] for r in results)
    total_i_tot = sum(r["interval_total"] for r in results)
    overall = total_w_cor / total_w_tot if total_w_tot > 0 else 0

    parts = [f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>IMU 姿态测试报告</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#f5f5f5;padding:20px}}
h1{{text-align:center;margin-bottom:24px;color:#333}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#fff;border-radius:10px;padding:16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.08)}}
.card .v{{font-size:26px;font-weight:700}}.card .l{{font-size:13px;color:#888;margin-top:4px}}
.legend{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px}}
.legend span{{display:flex;align-items:center;gap:5px;font-size:13px}}
.legend i{{width:14px;height:14px;border-radius:3px;display:inline-block}}
.sess{{background:#fff;border-radius:12px;box-shadow:0 1px 6px rgba(0,0,0,0.08);margin-bottom:20px;padding:20px}}
.sess-t{{font-size:18px;font-weight:600;margin-bottom:4px}}.sess-m{{color:#666;font-size:13px;margin-bottom:14px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:13px;font-weight:600;margin-left:8px}}
.bh{{background:#C8E6C9;color:#2E7D32}}.bm{{background:#FFF9C4;color:#F57F17}}.bl{{background:#FFCDD2;color:#C62828}}
.tl{{font-size:12px;font-weight:600;color:#555;margin-bottom:3px}}
.bar{{position:relative;height:34px;border-radius:6px;overflow:hidden;margin-bottom:2px;border:1px solid #e0e0e0}}
.seg{{position:absolute;top:0;height:100%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:500;overflow:hidden;white-space:nowrap;border-right:1px solid rgba(255,255,255,0.5)}}
.ax{{position:relative;height:18px;margin-bottom:10px}}
.ax span{{position:absolute;font-size:10px;color:#999;transform:translateX(-50%)}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
th{{background:#fafafa;padding:6px 8px;border:1px solid #e0e0e0;font-weight:600;text-align:center}}
td{{padding:5px 8px;border:1px solid #e0e0e0;text-align:center}}
.ok{{background:#f1f8e9}}.ng{{background:#fff3e0}}
</style></head><body>
<h1>IMU 姿态分类测试报告</h1>
<div class="grid">
  <div class="card"><div class="v">{len(results)}</div><div class="l">数据集</div></div>
  <div class="card"><div class="v">{overall:.1%}</div><div class="l">窗口准确率</div></div>
  <div class="card"><div class="v">{total_w_cor}/{total_w_tot}</div><div class="l">正确/有标注窗口</div></div>
  <div class="card"><div class="v">{total_i_cor}/{total_i_tot}</div><div class="l">区间正确</div></div>
</div>
<div class="legend">"""]

    for label, color in COLORS.items():
        zh = LABEL_ZH.get(label, label)
        parts.append(f'<span><i style="background:{color}"></i>{zh}({label})</span>')
    parts.append('</div>')

    def fmtime(s):
        return f"{int(s)//60}:{int(s)%60:02d}"

    for r in results:
        acc = r["window_accuracy"]
        bcls = "bh" if acc >= 0.85 else ("bm" if acc >= 0.7 else "bl")
        parts.append(f'<div class="sess"><div class="sess-t">{r["name"]}'
                     f'<span class="badge {bcls}">{acc:.1%}</span></div>')
        parts.append(f'<div class="sess-m">{r["total_sec"]:.0f}s | 窗口 {r["n_windows"]} | '
                     f'窗口准确率 {r["window_correct"]}/{r["window_total"]} | '
                     f'区间 {r["interval_correct"]}/{r["interval_total"]}</div>')

        T0 = r.get("gt_start", 0)
        T1 = r.get("gt_end", r["total_sec"])
        T_range = max(T1 - T0, 1)

        def bar_left(sec):
            return (sec - T0) / T_range * 100

        def bar_width(s0, s1):
            return max((s1 - s0) / T_range * 100, 0.3)

        # GT bar
        parts.append('<div class="tl">标注 (Ground Truth)</div><div class="bar">')
        for seg in r["gt_segments"]:
            left = bar_left(seg["start_sec"])
            w = bar_width(seg["start_sec"], seg["end_sec"])
            c = COLORS.get(seg["label"], "#999")
            txt = f'{seg["label_zh"]}({seg["exercise"]})' if w > 6 else (seg["label_zh"] if w > 3 else "")
            parts.append(f'<div class="seg" style="left:{left:.2f}%;width:{w:.2f}%;background:{c}" '
                         f'title="{fmtime(seg["start_sec"])}-{fmtime(seg["end_sec"])} {seg["label_zh"]} ({seg["exercise"]})">{txt}</div>')
        parts.append('</div>')

        # Pred bar
        parts.append('<div class="tl">预测 (Prediction)</div><div class="bar">')
        for seg in r["pred_segments"]:
            left = bar_left(seg["start_sec"])
            w = bar_width(seg["start_sec"], seg["end_sec"])
            c = COLORS.get(seg["label"], "#999")
            txt = seg["label_zh"] if w > 6 else ""
            parts.append(f'<div class="seg" style="left:{left:.2f}%;width:{w:.2f}%;background:{c}" '
                         f'title="{fmtime(seg["start_sec"])}-{fmtime(seg["end_sec"])} {seg["label_zh"]}">{txt}</div>')
        parts.append('</div>')

        # Time axis
        parts.append('<div class="ax">')
        nt = min(int(T_range // 60) + 1, 12)
        for i in range(nt + 1):
            t = T0 + i * (T_range / nt)
            parts.append(f'<span style="left:{(t - T0) / T_range * 100:.1f}%">{fmtime(t)}</span>')
        parts.append('</div>')

        # Diff table
        parts.append('<table><tr><th>时间</th><th>动作</th><th>标注</th><th>预测</th><th></th></tr>')
        for iv in r["intervals"]:
            cls = "ok" if iv["match"] else "ng"
            icon = "✓" if iv["match"] else "✗"
            parts.append(f'<tr class="{cls}"><td>{iv["time"]}</td><td>{iv["exercise"]}</td>'
                         f'<td>{iv["gt"]}</td><td>{iv["pred"]}</td><td>{icon}</td></tr>')
        parts.append('</table></div>')

    parts.append('</body></html>')

    outpath.parent.mkdir(parents=True, exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"[可视化] → {outpath}")


# ──────────────────────────────────────────────────
# 扫描 shared 目录
# ──────────────────────────────────────────────────

def scan_shared_dirs() -> List[Path]:
    shared = SCRIPT_DIR.parent.parent.parent / "recognize" / "visualize" / "result" / "shared"
    if not shared.exists():
        shared = Path("D:/WorkPath/fitness_new/recognize/visualize/result/shared")
    dirs = []
    for d in sorted(shared.iterdir()):
        if d.is_dir() and (d / "IMU.txt").exists() and (d / "ground_truth.json").exists():
            dirs.append(d)
    return dirs


# ──────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IMU 7类姿态分类器训练")
    parser.add_argument("--data_dirs", nargs="*", help="包含 IMU.txt + ground_truth.json 的目录列表")
    parser.add_argument("--scan", action="store_true", help="自动扫描 shared 目录下所有配对数据")
    parser.add_argument("--outdir", default="posture7_output", help="输出目录")
    parser.add_argument("--model_type", default="extra_trees",
                        choices=["random_forest", "extra_trees", "xgboost", "lightgbm"])
    parser.add_argument("--window_sec", type=float, default=DEFAULT_WINDOW_SEC)
    parser.add_argument("--stride_sec", type=float, default=DEFAULT_STRIDE_SEC)
    parser.add_argument("--export_only", action="store_true", help="仅导出数据集不训练")
    parser.add_argument("--posture_map", help="exercise_posture.json 路径")

    parser.add_argument("--predict", action="store_true", help="推理模式")
    parser.add_argument("--input", help="推理输入 IMU 文件")
    parser.add_argument("--model", help="模型文件路径 (.joblib)")

    parser.add_argument("--test", action="store_true", help="测试模式: 推理 + GT对比 + 可视化")

    args = parser.parse_args()
    outdir = Path(args.outdir)

    if args.predict:
        if not args.input or not args.model:
            parser.error("推理模式需要 --input 和 --model")
        predict(Path(args.input), Path(args.model), outdir, args.window_sec, args.stride_sec)
        return

    if args.test:
        test_dirs = []
        if args.scan:
            test_dirs = scan_shared_dirs()
        if args.data_dirs:
            test_dirs.extend([Path(d) for d in args.data_dirs])
        if not test_dirs:
            parser.error("测试模式需要 --data_dirs 或 --scan 指定数据目录")
        model_path = Path(args.model) if args.model else SCRIPT_DIR / "posture7_output" / "posture7_model_extra_trees.joblib"
        test_with_gt(test_dirs, model_path, outdir, args.window_sec, args.stride_sec)
        return

    # 收集数据目录
    data_dirs = []
    if args.scan:
        data_dirs = scan_shared_dirs()
        print(f"[扫描] 找到 {len(data_dirs)} 个配对数据目录:")
        for d in data_dirs:
            print(f"  - {d.name}")
    if args.data_dirs:
        data_dirs.extend([Path(d) for d in args.data_dirs])

    if not data_dirs:
        parser.error("请指定 --data_dirs 或 --scan")

    # 加载动作→姿态映射
    posture_map_path = Path(args.posture_map) if args.posture_map else None
    exercise_map = load_exercise_posture_map(posture_map_path)
    print(f"[映射] 加载 {len(exercise_map)} 个动作→姿态映射")

    # 构建数据集
    print("\n[构建数据集]")
    dataset = build_dataset(data_dirs, exercise_map, args.window_sec, args.stride_sec)
    if dataset.empty:
        print("[错误] 数据集为空, 退出")
        sys.exit(1)

    # 保存数据集
    outdir.mkdir(parents=True, exist_ok=True)
    dataset_path = outdir / "posture7_dataset.csv"
    dataset.to_csv(dataset_path, index=False, encoding="utf-8-sig")
    print(f"\n[保存] 数据集 → {dataset_path}")

    if args.export_only:
        print("[完成] 仅导出数据集")
        return

    # 训练
    train(dataset, outdir, args.model_type)
    print("\n[完成]")


if __name__ == "__main__":
    main()
