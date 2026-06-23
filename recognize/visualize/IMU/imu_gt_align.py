#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IMU 数据与视频 ground_truth 时间对齐脚本
对齐原理: 两路录制同时结束，时长差即为时间偏移
  offset = video_duration - imu_duration
  video_time = imu_time + offset

Usage:
    python imu_gt_align.py [imu_dir] [gt_json]
"""

import os, sys, json
import pandas as pd
import numpy as np
from datetime import datetime

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMU  = os.path.join(SCRIPT_DIR, "617")
DEFAULT_GT   = os.path.normpath(os.path.join(
    SCRIPT_DIR, "../result/shared/健身-高孟琦/ground_truth.json"
))

GT_COLORS = {
    "哑铃侧举":   "#f59e0b",
    "哑铃夹胸":   "#3b82f6",
    "卧推":       "#ef4444",
    "绳索下拉":   "#22c55e",
    "过渡":       "#6b7280",
}

IMU_COLORS = {
    "vigorous":      "#ef4444",
    "walking":       "#22c55e",
    "slight":        "#3b82f6",
    "active":        "#f97316",
    "still":         "#a855f7",
    "squat_sit":     "#eab308",
    "lying":         "#06b6d4",
    "bending":       "#ec4899",
    "still_nonvert": "#8b5cf6",
    "unknown":       "#6b7280",
}
IMU_ZH = {
    "vigorous": "剧烈运动", "walking": "行走", "slight": "轻微移动",
    "active": "运动中", "still": "原地不动", "squat_sit": "下蹲/坐下",
    "lying": "躺卧", "bending": "弯腰", "still_nonvert": "静止(非竖立)",
    "unknown": "未知",
}


def load_imu(data_dir):
    txt_files = sorted(f for f in os.listdir(data_dir) if f.endswith(".txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt in {data_dir}")
    fp = os.path.join(data_dir, txt_files[0])
    df = pd.read_csv(fp, sep="\t", header=0, encoding="utf-8")
    df.columns = ["time","device","ax","ay","az","gx","gy","gz",
                  "angleX","angleY","angleZ","magX","magY","magZ",
                  "q0","q1","q2","q3","temp","alt","pressure","ver","battery"]
    df = df.replace("null", np.nan)
    df["time"] = pd.to_datetime(df["time"])
    for c in ["ax","ay","az","gx","gy","gz","angleX","angleY","angleZ"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[["time","ax","ay","az","gx","gy","gz","angleX","angleY","angleZ"]
            ].dropna().reset_index(drop=True)
    df["time_sec"]  = (df["time"] - df["time"].iloc[0]).dt.total_seconds()
    df["gyro_mag"]  = np.sqrt(df["gx"]**2 + df["gy"]**2 + df["gz"]**2)
    df["acc_mag"]   = np.sqrt(df["ax"]**2 + df["ay"]**2 + df["az"]**2)
    return df, fp


def compute_offset(imu_df, gt_list):
    """时长差法计算偏移量 + AccZ特征验证"""
    imu_dur = imu_df["time_sec"].iloc[-1]
    vid_dur = gt_list[-1]["end"]
    offset  = vid_dur - imu_dur          # video_time = imu_time + offset

    # 验证：卧推期间 az_mean 应接近 0
    lying_segs = [s for s in gt_list if s["type"]=="exercise" and s["label"]=="卧推"]
    evidence = []
    for seg in lying_segs:
        is_ = seg["start"] - offset
        ie_ = seg["end"]   - offset
        mask = (imu_df["time_sec"] >= is_) & (imu_df["time_sec"] < ie_)
        sub  = imu_df[mask]
        if len(sub):
            evidence.append({"label": seg["label"], "az_mean": sub["az"].mean()})

    return offset, evidence


def segment_imu(df):
    """复用 imu_posture_analyze 的分类逻辑（1.5s窗口）"""
    from collections import Counter

    TH = dict(still_gyro=6, still_acc_std=0.04, slight_gyro=15,
              slight_acc_std=0.10, walk_gyro_max=55,
              walk_acc_std_lo=0.05, walk_acc_std_hi=0.35,
              vigorous_gyro=100, vigorous_acc_std=0.35,
              lying_az_thresh=0.40, bend_angle_y_std=8.0,
              window_sec=1.5, stride_sec=0.75, smooth_k=3, min_seg_sec=1.0)

    total = df["time_sec"].iloc[-1]
    rows  = []
    t = 0.0
    while t < total:
        m   = (df["time_sec"] >= t) & (df["time_sec"] < t + TH["window_sec"])
        win = df[m]
        if len(win) < 3:
            t += TH["stride_sec"]; continue
        gm  = win["gyro_mag"].mean()
        gx  = win["gyro_mag"].max()
        as_ = win["acc_mag"].std()
        az  = win["az"].mean()
        vg  = abs(az)
        hg  = np.sqrt(win["ax"].mean()**2 + win["ay"].mean()**2)
        axs = win["angleX"].std()
        ays = win["angleY"].std()

        if vg < TH["lying_az_thresh"] and gm < 12:
            label = "lying"
        elif gm < TH["still_gyro"] and as_ < TH["still_acc_std"]:
            label = "still" if vg > 0.80 else "still_nonvert"
        elif gm < TH["slight_gyro"] and as_ < TH["slight_acc_std"]:
            label = "bending" if ays > TH["bend_angle_y_std"] and gm < 25 else "slight"
        elif gx > TH["vigorous_gyro"] or as_ > TH["vigorous_acc_std"]:
            label = "vigorous"
        elif (TH["walk_acc_std_lo"] <= as_ <= TH["walk_acc_std_hi"]
              and gm <= TH["walk_gyro_max"]):
            label = "walking"
        elif ays > TH["bend_angle_y_std"] and as_ < 0.25 and gm < 50:
            label = "bending"
        elif axs > 6 and as_ < 0.25 and 10 < gm < 60:
            label = "squat_sit"
        elif gm >= TH["slight_gyro"]:
            label = "active"
        else:
            label = "unknown"

        rows.append({"time_sec": t, "label": label})
        t += TH["stride_sec"]

    # 平滑
    k = TH["smooth_k"]
    labels = [r["label"] for r in rows]
    smooth = labels[:]
    for i in range(k, len(labels)-k):
        smooth[i] = Counter(labels[i-k:i+k+1]).most_common(1)[0][0]

    # 合并片段
    segs = []
    cur  = smooth[0]
    s0   = rows[0]["time_sec"]
    for i in range(1, len(rows)):
        if smooth[i] != cur:
            dur = rows[i]["time_sec"] - s0
            if dur >= TH["min_seg_sec"]:
                segs.append({"label": cur, "start_sec": s0,
                             "end_sec": rows[i]["time_sec"], "dur": dur})
            cur = smooth[i]
            s0  = rows[i]["time_sec"]
    dur = rows[-1]["time_sec"] - s0
    if dur >= TH["min_seg_sec"]:
        segs.append({"label": cur, "start_sec": s0,
                     "end_sec": rows[-1]["time_sec"], "dur": dur})
    return segs


def imu_seg_stats(imu_df, imu_segs, offset):
    """为每段 IMU 片段补充统计特征"""
    out = []
    for seg in imu_segs:
        m   = (imu_df["time_sec"] >= seg["start_sec"]) & (imu_df["time_sec"] < seg["end_sec"])
        sub = imu_df[m]
        rec = dict(seg)
        rec["label_zh"]  = IMU_ZH.get(seg["label"], seg["label"])
        rec["vtime_s"]   = round(seg["start_sec"] + offset, 1)
        rec["vtime_e"]   = round(seg["end_sec"]   + offset, 1)
        rec["gyro_mean"] = round(float(sub["gyro_mag"].mean()), 1) if len(sub) else 0
        rec["az_mean"]   = round(float(sub["az"].mean()), 3)     if len(sub) else 0
        rec["acc_std"]   = round(float(sub["acc_mag"].std()), 3) if len(sub) else 0
        out.append(rec)
    return out


def save_report(data_dir, offset, evidence, gt_list, imu_segs_aug,
                imu_start_ts, vid_total_sec, imu_total_sec):
    os.makedirs(data_dir, exist_ok=True)

    report = {
        "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "imu_start":      str(imu_start_ts),
        "imu_duration_s": round(imu_total_sec, 1),
        "video_duration_s": round(vid_total_sec, 1),
        "offset_s":       round(offset, 2),
        "note":           "video_time = imu_time + offset",
        "offset_evidence": evidence,
        "ground_truth":   gt_list,
        "imu_segments":   imu_segs_aug,
    }
    p = os.path.join(data_dir, "aligned_report.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[OK] JSON -> " + p)
    return report


def print_alignment_table(gt_list, imu_segs_aug, offset):
    print("\n=== GT vs IMU 对齐 (offset=%.1fs) ===" % offset)
    for gt in gt_list:
        vs, ve = gt["start"], gt["end"]
        is_, ie_ = vs - offset, ve - offset
        # find overlapping IMU segs
        overlaps = [s for s in imu_segs_aug
                    if s["end_sec"] > is_ and s["start_sec"] < ie_]
        az_vals  = [s["az_mean"] for s in overlaps]
        top_lbl  = max([(o["dur"], o["label_zh"]) for o in overlaps],
                       default=(0, "-"))[1] if overlaps else "-"
        print("[video %5.1f-%5.1f] %-12s | IMU %5.1f-%5.1f | top: %-8s az_mean=%+.3f" % (
            vs, ve, gt["label"], is_, ie_, top_lbl,
            float(np.mean(az_vals)) if az_vals else 0.0
        ))


def main():
    imu_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMU
    gt_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_GT

    imu_df, imu_file = load_imu(imu_dir)
    with open(gt_path, encoding="utf-8") as f:
        gt_list = json.load(f)

    offset, evidence = compute_offset(imu_df, gt_list)
    print("Offset = %.2fs  (video_time = imu_time + offset)" % offset)
    print("Evidence (bench press az_mean should be ~0 when lying):")
    for e in evidence:
        print("  %s az_mean=%.3f" % (e["label"], e["az_mean"]))

    imu_segs      = segment_imu(imu_df)
    imu_segs_aug  = imu_seg_stats(imu_df, imu_segs, offset)

    print_alignment_table(gt_list, imu_segs_aug, offset)

    report = save_report(
        imu_dir, offset, evidence, gt_list, imu_segs_aug,
        imu_df["time"].iloc[0], gt_list[-1]["end"], imu_df["time_sec"].iloc[-1]
    )
    return report


if __name__ == "__main__":
    main()
