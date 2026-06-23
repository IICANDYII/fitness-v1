#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 运动姿态分析脚本
设备: WT901BLE67 腕式IMU传感器
目标: 识别走路/躺卧/下蹲/坐下/弯腰/原地不动等关键姿态

Usage:
    python imu_posture_analyze.py [data_dir]
    默认分析: recognize/visualize/IMU/617/
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import Counter

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 分类阈值（胸部佩戴IMU，单位: g=加速度, °/s=角速度）
# 胸部传感器物理关系（Z轴朝上直立佩戴）：
#   直立站/走：az ≈ −0.95g，ay ≈ 0g
#   弯腰前倾：az 从 −0.95g 向 0 偏移，|ay| 增大
#   躺卧（仰卧）：az ≈ 0g（近零或正值），ay 承受大部分重力
THRESHOLDS = {
    "still_gyro":        6.0,   # °/s  静止陀螺仪上限
    "still_acc_std":     0.04,  # g    静止加速度标准差上限
    "slight_gyro":       15.0,  # °/s  轻微移动陀螺仪上限
    "slight_acc_std":    0.10,  # g    轻微移动加速度标准差上限
    "walk_gyro_max":     55.0,  # °/s  行走陀螺仪上限
    "walk_acc_std_lo":   0.05,  # g    行走加速度标准差下限
    "walk_acc_std_hi":   0.35,  # g    行走加速度标准差上限
    "vigorous_gyro":     100.0, # °/s  剧烈运动陀螺仪峰值下限
    "vigorous_acc_std":  0.35,  # g    剧烈运动加速度标准差下限
    # ── 胸部专用阈值 ──────────────────────────────────────────
    # 躺卧：az 偏离 −1g 基线，趋近 0 或正值
    "lying_az_hi":      -0.35,  # g    az > 此值 → 躺卧（仰卧/侧卧）
    "lying_gyro_max":   15.0,   # °/s  躺卧时允许的最大陀螺仪（排除动作中途）
    # 弯腰：az 在直立和躺卧之间的中间区域（躯干前倾）
    "bend_az_lo":       -0.78,  # g    az > 此值 → 躯干已偏离竖直（开始弯腰）
    "bend_az_hi":       -0.35,  # g    az < 此值 → 未进入躺卧区
    "bend_ay_thresh":    0.25,  # g    |ay| > 此值辅助确认躯干倾斜
    "bend_gyro_max":    25.0,   # °/s  弯腰是受控动作，排除高速运动
    # 下蹲/坐下：躯干大体直立（az接近直立基线），但有一次性姿态变换
    "squat_az_upright": -0.75,  # g    az < 此值认为躯干仍直立
    "squat_gyro_lo":    10.0,   # °/s  存在明显动作
    "squat_gyro_hi":    60.0,   # °/s  但不到剧烈运动级别
    "squat_acc_std_hi":  0.25,  # g    加速度适中（有控制）
    # 直立基线参考（从本数据静止段估算）
    "upright_az_ref":   -0.95,  # g    直立时的 az 参考值
    # ────────────────────────────────────────────────────────
    "window_sec":        1.5,   # s    分类窗口
    "stride_sec":        0.75,  # s    滑动步长
    "smooth_k":          3,     #      标签平滑邻域（±k 点多数投票）
    "min_seg_sec":       1.0,   # s    最小有效片段
}


# ─────────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────────
def load_data(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, sep="\t", header=0, encoding="utf-8")
    df.columns = [
        "time", "device",
        "ax", "ay", "az",
        "gx", "gy", "gz",
        "angleX", "angleY", "angleZ",
        "magX", "magY", "magZ",
        "q0", "q1", "q2", "q3",
        "temp", "alt", "pressure", "ver", "battery",
    ]
    df = df.replace("null", np.nan)
    df["time"] = pd.to_datetime(df["time"])
    numeric_cols = ["ax", "ay", "az", "gx", "gy", "gz", "angleX", "angleY", "angleZ"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[["time"] + numeric_cols].dropna().reset_index(drop=True)
    return df


# ─────────────────────────────────────────────
# 特征计算
# ─────────────────────────────────────────────
def add_pointwise_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["acc_mag"]   = np.sqrt(df["ax"]**2 + df["ay"]**2 + df["az"]**2)
    df["gyro_mag"]  = np.sqrt(df["gx"]**2 + df["gy"]**2 + df["gz"]**2)
    df["time_sec"]  = (df["time"] - df["time"].iloc[0]).dt.total_seconds()

    # 水平重力分量（与Z轴垂直平面上的重力投影）
    df["horiz_g"]   = np.sqrt(df["ax"]**2 + df["ay"]**2)
    # 加速度抖动（jerk近似，相邻采样差分）
    df["acc_jerk"]  = df["acc_mag"].diff().abs().fillna(0)
    return df


def window_features(win: pd.DataFrame) -> dict:
    if len(win) < 3:
        return None
    return {
        "acc_mag_mean":  win["acc_mag"].mean(),
        "acc_mag_std":   win["acc_mag"].std(),
        "gyro_mean":     win["gyro_mag"].mean(),
        "gyro_max":      win["gyro_mag"].max(),
        "az_mean":       win["az"].mean(),
        "az_std":        win["az"].std(),
        "ax_mean":       win["ax"].mean(),
        "ay_mean":       win["ay"].mean(),
        "ay_abs_mean":   win["ay"].abs().mean(),   # 胸部弯腰/躺卧辅助指标
        "horiz_g_mean":  win["horiz_g"].mean(),
        "angleX_std":    win["angleX"].std(),
        "angleY_std":    win["angleY"].std(),
        "angleY_mean":   win["angleY"].mean(),
        "jerk_mean":     win["acc_jerk"].mean(),
        "n":             len(win),
    }


# ─────────────────────────────────────────────
# 步频检测（行走验证）
# ─────────────────────────────────────────────
def estimate_step_freq(df: pd.DataFrame, t0: float, t1: float) -> float:
    """在时间片 [t0,t1] 内估算步频(步/秒)，返回0表示非周期"""
    seg = df[(df["time_sec"] >= t0) & (df["time_sec"] < t1)]
    if len(seg) < 10:
        return 0.0
    sig = seg["acc_mag"].values
    # 去均值
    sig = sig - sig.mean()
    # 计算自相关
    n = len(sig)
    corr = np.correlate(sig, sig, mode="full")[n - 1:]
    corr = corr / (corr[0] + 1e-9)
    # 寻找第一个局部最大值（0.3s~1.5s 对应步频0.67~3.3 Hz）
    fs = n / max(t1 - t0, 0.01)
    lo = max(1, int(0.30 * fs))
    hi = min(len(corr) - 1, int(1.50 * fs))
    if lo >= hi:
        return 0.0
    sub = corr[lo:hi]
    pk = np.argmax(sub)
    peak_val = sub[pk]
    if peak_val < 0.25:   # 相关性太低，不是周期信号
        return 0.0
    lag = pk + lo
    freq = fs / lag
    return round(freq, 2)


# ─────────────────────────────────────────────
# 姿态分类
# ─────────────────────────────────────────────
LABEL_ZH = {
    "still":          "原地不动",
    "still_nonvert":  "静止(非竖立)",
    "slight":         "轻微移动",
    "walking":        "行走",
    "running":        "跑步",
    "lying":          "躺卧",
    "bending":        "弯腰",
    "squat_sit":      "下蹲/坐下",
    "active":         "运动中",
    "vigorous":       "剧烈运动",
    "unknown":        "未知",
}

def classify_window(feats: dict, step_freq: float = 0.0) -> str:
    """
    胸部佩戴IMU姿态分类（规则优先级从上到下）。

    核心物理关系（Z轴朝上直立佩戴）：
      直立：az ≈ −0.95g，ay ≈ 0g
      弯腰：az 偏离 −0.95g 趋近 0，|ay| 增大
      躺卧：az ≈ 0g（近零或正值），ay 承受重力 ≈ ±0.6g
    """
    th          = THRESHOLDS
    acc_std     = feats["acc_mag_std"]
    gyro_mean   = feats["gyro_mean"]
    gyro_max    = feats["gyro_max"]
    az_mean     = feats["az_mean"]
    ay_abs      = feats["ay_abs_mean"]
    ay_mean     = feats["ay_mean"]

    # ── 【躺卧】─────────────────────────────────────────────
    # az 偏离直立基线（趋近 0 或正值），同时 |ay| 增大（Y 承受重力）
    # 要求 gyro 不能太大（排除动作翻转过程中的短暂状态）
    if az_mean > th["lying_az_hi"] and gyro_mean < th["lying_gyro_max"]:
        return "lying"

    # ── 【原地不动】──────────────────────────────────────────
    # 极低旋转 + 极低加速度波动 → 静止站立或静止坐着
    if gyro_mean < th["still_gyro"] and acc_std < th["still_acc_std"]:
        if az_mean < -0.75:
            return "still"          # 躯干竖立静止
        return "still_nonvert"      # 静止但躯干非竖立（不常见）

    # ── 【轻微移动】──────────────────────────────────────────
    # 小动作（坐着调整姿势、缓慢移动等），先排除弯腰
    if gyro_mean < th["slight_gyro"] and acc_std < th["slight_acc_std"]:
        return "slight"

    # ── 【弯腰】─────────────────────────────────────────────
    # 胸部传感器专用：az 进入中间区域（躯干前倾但未达到躺卧）
    # 条件：az 偏离直立但未进入躺卧区，且 |ay| 有所增大，且动作受控（低陀螺仪）
    if (th["bend_az_lo"] < az_mean < th["bend_az_hi"]
            and ay_abs > th["bend_ay_thresh"]
            and gyro_mean < th["bend_gyro_max"]):
        return "bending"

    # ── 【剧烈运动】──────────────────────────────────────────
    # 窗口内陀螺仪峰值超限 或 加速度波动极大
    if gyro_max > th["vigorous_gyro"] or acc_std > th["vigorous_acc_std"]:
        return "vigorous"

    # ── 【行走 / 跑步】───────────────────────────────────────
    # 胸部传感器：AccZ 垂直弹跳是走路的最清晰信号
    # 加速度波动在合理范围，陀螺仪中等，可选步频验证
    if (th["walk_acc_std_lo"] <= acc_std <= th["walk_acc_std_hi"]
            and gyro_mean <= th["walk_gyro_max"]
            and az_mean < th["bend_az_lo"]):   # 排除弯腰中的移动
        if step_freq > 0:
            return "running" if step_freq > 2.5 else "walking"
        if gyro_mean < 30:
            return "walking"

    # ── 【下蹲 / 坐下】───────────────────────────────────────
    # 胸部传感器：躯干仍大体直立（az 接近直立基线），但有明显动作幅度
    # 下蹲时躯干略微前倾，加速度有一次性变化，但不剧烈
    if (az_mean < th["squat_az_upright"]
            and th["squat_gyro_lo"] < gyro_mean < th["squat_gyro_hi"]
            and acc_std < th["squat_acc_std_hi"]):
        return "squat_sit"

    # ── 【运动中】────────────────────────────────────────────
    # 中等强度不规律运动，兜底类别
    if gyro_mean >= th["slight_gyro"]:
        return "active"

    return "unknown"


# ─────────────────────────────────────────────
# 主分析流程
# ─────────────────────────────────────────────
def analyze(df: pd.DataFrame) -> pd.DataFrame:
    df = add_pointwise_features(df)
    total_sec = df["time_sec"].iloc[-1]
    ws = THRESHOLDS["window_sec"]
    ss = THRESHOLDS["stride_sec"]

    rows = []
    t = 0.0
    while t < total_sec:
        mask = (df["time_sec"] >= t) & (df["time_sec"] < t + ws)
        win = df[mask]
        feats = window_features(win)
        if feats:
            sf = estimate_step_freq(df, t, t + ws)
            label_key = classify_window(feats, sf)
            rows.append({
                "time_sec":   t,
                "timestamp":  df["time"].iloc[0] + pd.Timedelta(seconds=t),
                "label":      label_key,
                "label_zh":   LABEL_ZH[label_key],
                "step_freq":  sf,
                **feats,
            })
        t += ss

    return pd.DataFrame(rows)


def smooth_labels(labels: list, k: int = 3) -> list:
    out = labels[:]
    for i in range(k, len(labels) - k):
        window = labels[i - k: i + k + 1]
        most_common = Counter(window).most_common(1)[0][0]
        out[i] = most_common
    return out


def merge_segments(res_df: pd.DataFrame) -> list:
    if len(res_df) == 0:
        return []
    labels = smooth_labels(res_df["label"].tolist(), THRESHOLDS["smooth_k"])
    res_df = res_df.copy()
    res_df["label"] = labels
    res_df["label_zh"] = [LABEL_ZH[l] for l in labels]

    segments = []
    cur_label = labels[0]
    cur_start_sec = res_df["time_sec"].iloc[0]
    cur_start_ts  = res_df["timestamp"].iloc[0]

    for i in range(1, len(res_df)):
        if labels[i] != cur_label:
            dur = res_df["time_sec"].iloc[i] - cur_start_sec
            if dur >= THRESHOLDS["min_seg_sec"]:
                segments.append({
                    "label":        cur_label,
                    "label_zh":     LABEL_ZH[cur_label],
                    "start_ts":     str(cur_start_ts),
                    "start_sec":    round(cur_start_sec, 1),
                    "end_sec":      round(res_df["time_sec"].iloc[i], 1),
                    "duration_sec": round(dur, 1),
                })
            cur_label     = labels[i]
            cur_start_sec = res_df["time_sec"].iloc[i]
            cur_start_ts  = res_df["timestamp"].iloc[i]

    # 最后一段
    dur = res_df["time_sec"].iloc[-1] - cur_start_sec
    if dur >= THRESHOLDS["min_seg_sec"]:
        segments.append({
            "label":        cur_label,
            "label_zh":     LABEL_ZH[cur_label],
            "start_ts":     str(cur_start_ts),
            "start_sec":    round(cur_start_sec, 1),
            "end_sec":      round(res_df["time_sec"].iloc[-1], 1),
            "duration_sec": round(dur, 1),
        })

    return segments


# ─────────────────────────────────────────────
# 统计汇总
# ─────────────────────────────────────────────
def summarize(segments: list, total_sec: float) -> dict:
    duration_by_label = Counter()
    count_by_label    = Counter()
    for seg in segments:
        key = seg["label_zh"]
        duration_by_label[key] += seg["duration_sec"]
        count_by_label[key]    += 1

    breakdown = []
    for label, dur in sorted(duration_by_label.items(), key=lambda x: -x[1]):
        breakdown.append({
            "姿态":    label,
            "总时长s": round(dur, 1),
            "占比%":   round(dur / total_sec * 100, 1),
            "片段数":  count_by_label[label],
        })

    return {
        "总时长s":       round(total_sec, 1),
        "片段总数":      len(segments),
        "姿态时长分布":  breakdown,
    }


# ─────────────────────────────────────────────
# 报告生成
# ─────────────────────────────────────────────
REPORT_HEADER = """
╔══════════════════════════════════════════════════════════════════╗
║             IMU 运动姿态分析报告                                 ║
║  设备: WT901BLE67  |  传感器位置: 腕部                          ║
╚══════════════════════════════════════════════════════════════════╝
"""

POSTURE_LEGEND = """
【姿态说明】
  原地不动  — 几乎不动，竖立，加速度稳定 (gyro<6°/s)
  静止(非竖立) — 静止但传感器非竖立方向（如坐姿放桌上）
  轻微移动  — 小幅活动（坐着调整姿势等）
  行走      — 步频0.7~2.5 Hz，加速度有节律周期变化
  跑步      — 步频>2.5 Hz，高频冲击
  弯腰      — AngleY显著变化，加速度中等
  下蹲/坐下 — AngleX显著变化，角速度中等
  躺卧      — Z轴重力分量<0.4g（腕部趋于水平）
  运动中    — 中等强度，不规律运动
  剧烈运动  — 高角速度(>100°/s)或高加速度方差(>0.35g)
"""

def format_timeline(segments: list) -> str:
    lines = ["\n【时间轴姿态片段】"]
    lines.append(f"  {'开始(s)':>8}  {'时长(s)':>7}  {'姿态':<12}  {'时间戳'}")
    lines.append("  " + "─" * 60)
    for seg in segments:
        lines.append(
            f"  {seg['start_sec']:>8.1f}  {seg['duration_sec']:>7.1f}  "
            f"{seg['label_zh']:<12}  {seg['start_ts'][:19]}"
        )
    return "\n".join(lines)


def format_summary(summary: dict) -> str:
    lines = ["\n【统计汇总】"]
    lines.append(f"  总录制时长: {summary['总时长s']} s  ({summary['总时长s']/60:.1f} min)")
    lines.append(f"  识别片段数: {summary['片段总数']}")
    lines.append("")
    lines.append(f"  {'姿态':<12} {'总时长(s)':>9} {'占比':>7} {'片段数':>6}")
    lines.append("  " + "─" * 42)
    for row in summary["姿态时长分布"]:
        lines.append(
            f"  {row['姿态']:<12} {row['总时长s']:>9.1f} {row['占比%']:>6.1f}% {row['片段数']:>6}"
        )
    return "\n".join(lines)


def save_report(segments, summary, report_dir, data_file):
    os.makedirs(report_dir, exist_ok=True)

    # ── JSON 报告 ──────────────────────────────
    json_path = os.path.join(report_dir, "posture_report.json")
    report_data = {
        "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file":    data_file,
        "summary":        summary,
        "segments":       segments,
        "thresholds":     THRESHOLDS,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # ── 文本报告 ──────────────────────────────
    txt_path = os.path.join(report_dir, "posture_report.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(REPORT_HEADER)
        f.write(f"\n数据文件: {data_file}")
        f.write(f"\n生成时间: {report_data['generated_at']}\n")
        f.write(POSTURE_LEGEND)
        f.write(format_summary(summary))
        f.write("\n")
        f.write(format_timeline(segments))
        f.write("\n\n")

    print(f"[OK] JSON 报告 -> {json_path}")
    print(f"[OK] 文本报告 -> {txt_path}")
    return txt_path, json_path


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────
def main():
    # 确定数据目录
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    else:
        data_dir = os.path.join(SCRIPT_DIR, "617")

    # 找到 .txt 数据文件
    txt_files = [f for f in os.listdir(data_dir) if f.endswith(".txt")]
    if not txt_files:
        print(f"[错误] 在 {data_dir} 中未找到 .txt 数据文件")
        sys.exit(1)

    data_file = os.path.join(data_dir, sorted(txt_files)[0])
    print(f"[→] 加载数据: {data_file}")

    df = load_data(data_file)
    total_sec = (df["time"].iloc[-1] - df["time"].iloc[0]).total_seconds()
    print(f"[→] 样本数: {len(df)}  时长: {total_sec:.1f}s  ({total_sec/60:.1f} min)")
    print(f"[→] 时间范围: {df['time'].iloc[0]}  →  {df['time'].iloc[-1]}")

    print("[→] 运行滑动窗口分类...")
    result_df = analyze(df)

    print("[→] 合并连续片段...")
    segments = merge_segments(result_df)

    summary = summarize(segments, total_sec)

    # 打印到终端
    print(format_summary(summary))
    print(format_timeline(segments))

    # 保存报告
    save_report(segments, summary, data_dir, data_file)

    return segments, summary


if __name__ == "__main__":
    main()
