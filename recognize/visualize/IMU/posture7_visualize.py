#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对所有 IMU+ground_truth 配对数据做推理, 生成可视化对比 HTML.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import joblib

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from imu_posture_train import (
    load_imu_txt, load_ground_truth, load_exercise_posture_map,
    build_posture_labels_from_gt, extract_features, estimate_fs,
    FEATURE_NAMES, LABEL_TO_IDX, IDX_TO_LABEL, LABEL_ZH, ZH_TO_LABEL,
    DEFAULT_WINDOW_SEC, DEFAULT_STRIDE_SEC,
    _smooth_labels, _merge_segments,
)


POSTURE_COLORS = {
    "standing":   "#4CAF50",
    "sitting":    "#2196F3",
    "hanging":    "#9C27B0",
    "lying":      "#FF9800",
    "incline":    "#FF5722",
    "side_lying": "#00BCD4",
    "bending":    "#795548",
}

POSTURE_COLORS_LIGHT = {
    "standing":   "#C8E6C9",
    "sitting":    "#BBDEFB",
    "hanging":    "#E1BEE7",
    "lying":      "#FFE0B2",
    "incline":    "#FFCCBC",
    "side_lying": "#B2EBF2",
    "bending":    "#D7CCC8",
}


def predict_one(imu_df: pd.DataFrame, model, bundle: dict,
                window_sec: float = DEFAULT_WINDOW_SEC,
                stride_sec: float = DEFAULT_STRIDE_SEC) -> pd.DataFrame:
    fs = estimate_fs(imu_df)
    total_sec = imu_df["time_sec"].iloc[-1]

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
        return windows_df

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

    return windows_df


def build_gt_segments(gt: List[Dict], exercise_map: Dict[str, str], total_sec: float):
    intervals = build_posture_labels_from_gt(gt, exercise_map, total_sec)
    segments = []
    for t0, t1, label in intervals:
        segments.append({
            "label": label,
            "label_zh": LABEL_ZH.get(label, label),
            "start_sec": round(t0, 1),
            "end_sec": round(t1, 1),
            "duration_sec": round(t1 - t0, 1),
            "exercise": "",
        })
    # 附加动作名
    for seg_gt, seg_out in zip(gt, segments):
        seg_out["exercise"] = seg_gt.get("label", "")
    return segments


def compute_accuracy(pred_windows: pd.DataFrame, gt_intervals, total_sec: float) -> dict:
    if pred_windows.empty:
        return {"accuracy": 0, "n_windows": 0}

    correct = 0
    total = 0
    for _, row in pred_windows.iterrows():
        t0 = row["window_start_sec"]
        t1 = row["window_end_sec"]
        win_len = t1 - t0

        best_label = None
        best_overlap = 0
        for gt_t0, gt_t1, gt_label in gt_intervals:
            overlap = max(0, min(t1, gt_t1) - max(t0, gt_t0))
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = gt_label

        if best_label and best_overlap / win_len >= 0.6:
            total += 1
            if row["label"] == best_label:
                correct += 1

    return {
        "accuracy": round(correct / total, 4) if total > 0 else 0,
        "correct": correct,
        "total": total,
    }


def generate_html(results: List[dict], outpath: Path):
    html_parts = ["""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>IMU 姿态分类推理结果</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }
h1 { text-align: center; margin-bottom: 30px; color: #333; }
.session { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; padding: 24px; }
.session-title { font-size: 20px; font-weight: 600; margin-bottom: 6px; }
.session-meta { color: #666; font-size: 14px; margin-bottom: 18px; }
.accuracy-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 14px; margin-left: 8px; }
.accuracy-high { background: #C8E6C9; color: #2E7D32; }
.accuracy-mid { background: #FFF9C4; color: #F57F17; }
.accuracy-low { background: #FFCDD2; color: #C62828; }
.timeline-label { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 4px; }
.timeline-container { position: relative; height: 38px; border-radius: 6px; overflow: hidden; margin-bottom: 2px; border: 1px solid #e0e0e0; }
.timeline-seg { position: absolute; top: 0; height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 500; color: #333; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
  border-right: 1px solid rgba(255,255,255,0.6); cursor: default; transition: filter 0.15s; }
.timeline-seg:hover { filter: brightness(0.92); z-index: 2; }
.timeline-seg .seg-tip { display: none; position: absolute; bottom: 42px; left: 50%; transform: translateX(-50%);
  background: #333; color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 12px; white-space: nowrap; z-index: 10; pointer-events: none; }
.timeline-seg:hover .seg-tip { display: block; }
.time-axis { position: relative; height: 22px; margin-bottom: 14px; }
.time-tick { position: absolute; top: 0; font-size: 10px; color: #999; transform: translateX(-50%); }
.time-tick::before { content: ''; position: absolute; top: -4px; left: 50%; width: 1px; height: 4px; background: #ccc; }
.legend { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; margin-bottom: 8px; }
.legend-item { display: flex; align-items: center; gap: 5px; font-size: 13px; }
.legend-color { width: 16px; height: 16px; border-radius: 3px; }
.diff-section { margin-top: 14px; }
.diff-title { font-size: 14px; font-weight: 600; color: #555; margin-bottom: 6px; }
table.diff-table { width: 100%; border-collapse: collapse; font-size: 13px; }
table.diff-table th, table.diff-table td { padding: 6px 10px; border: 1px solid #e0e0e0; text-align: center; }
table.diff-table th { background: #fafafa; font-weight: 600; }
tr.match { background: #f1f8e9; }
tr.mismatch { background: #fff3e0; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
.summary-card { background: #fafafa; border-radius: 8px; padding: 16px; text-align: center; }
.summary-card .val { font-size: 28px; font-weight: 700; color: #333; }
.summary-card .lbl { font-size: 13px; color: #888; margin-top: 4px; }
</style>
</head>
<body>
<h1>IMU 姿态分类推理可视化</h1>
"""]

    # 汇总卡片
    total_windows = sum(r["n_windows"] for r in results)
    total_correct = sum(r["acc_info"]["correct"] for r in results)
    total_total = sum(r["acc_info"]["total"] for r in results)
    overall_acc = total_correct / total_total if total_total > 0 else 0

    html_parts.append(f"""
<div class="summary-grid">
  <div class="summary-card"><div class="val">{len(results)}</div><div class="lbl">数据集数量</div></div>
  <div class="summary-card"><div class="val">{total_windows}</div><div class="lbl">总推理窗口</div></div>
  <div class="summary-card"><div class="val">{overall_acc:.1%}</div><div class="lbl">总体准确率</div></div>
  <div class="summary-card"><div class="val">{total_correct}/{total_total}</div><div class="lbl">正确/有标注窗口</div></div>
</div>
""")

    # 图例
    html_parts.append('<div class="legend">')
    for label, color in POSTURE_COLORS.items():
        zh = LABEL_ZH.get(label, label)
        html_parts.append(f'<div class="legend-item"><div class="legend-color" style="background:{color}"></div>{zh} ({label})</div>')
    html_parts.append('</div>')

    # 每个数据集
    for r in results:
        name = r["name"]
        total_sec = r["total_sec"]
        acc = r["acc_info"]["accuracy"]
        acc_cls = "accuracy-high" if acc >= 0.85 else ("accuracy-mid" if acc >= 0.7 else "accuracy-low")

        html_parts.append(f"""
<div class="session">
  <div class="session-title">{name}
    <span class="accuracy-badge {acc_cls}">{acc:.1%}</span>
  </div>
  <div class="session-meta">时长 {total_sec:.0f}s | 窗口 {r['n_windows']} | 正确 {r['acc_info']['correct']}/{r['acc_info']['total']}</div>
""")

        # GT timeline
        html_parts.append('<div class="timeline-label">标注 (Ground Truth)</div>')
        html_parts.append('<div class="timeline-container">')
        for seg in r["gt_segments"]:
            left = seg["start_sec"] / total_sec * 100
            width = max(seg["duration_sec"] / total_sec * 100, 0.3)
            color = POSTURE_COLORS.get(seg["label"], "#999")
            exercise = seg.get("exercise", "")
            tip = f'{seg["start_sec"]:.0f}s-{seg["end_sec"]:.0f}s {seg["label_zh"]} ({exercise})'
            show = seg["label_zh"] if width > 4 else ""
            if width > 8 and exercise:
                show = f'{seg["label_zh"]}({exercise})'
            html_parts.append(
                f'<div class="timeline-seg" style="left:{left:.2f}%;width:{width:.2f}%;background:{color};">'
                f'{show}<span class="seg-tip">{tip}</span></div>'
            )
        html_parts.append('</div>')

        # Pred timeline
        html_parts.append('<div class="timeline-label">预测 (Model Prediction)</div>')
        html_parts.append('<div class="timeline-container">')
        for seg in r["pred_segments"]:
            left = seg["start_sec"] / total_sec * 100
            width = max(seg["duration_sec"] / total_sec * 100, 0.3)
            color = POSTURE_COLORS.get(seg["label"], "#999")
            tip = f'{seg["start_sec"]:.0f}s-{seg["end_sec"]:.0f}s {seg["label_zh"]}'
            show = seg["label_zh"] if width > 4 else ""
            html_parts.append(
                f'<div class="timeline-seg" style="left:{left:.2f}%;width:{width:.2f}%;background:{color};">'
                f'{show}<span class="seg-tip">{tip}</span></div>'
            )
        html_parts.append('</div>')

        # Time axis
        html_parts.append('<div class="time-axis">')
        n_ticks = min(int(total_sec // 30) + 1, 20)
        for i in range(n_ticks + 1):
            t = i * (total_sec / n_ticks)
            pct = t / total_sec * 100
            minutes = int(t) // 60
            secs = int(t) % 60
            html_parts.append(f'<span class="time-tick" style="left:{pct:.1f}%">{minutes}:{secs:02d}</span>')
        html_parts.append('</div>')

        # Diff table
        html_parts.append('<div class="diff-section"><div class="diff-title">区间对比明细</div>')
        html_parts.append('<table class="diff-table"><tr><th>时间</th><th>标注动作</th><th>标注姿态</th><th>预测姿态</th><th>结果</th></tr>')
        for seg in r["gt_segments"]:
            t0, t1 = seg["start_sec"], seg["end_sec"]
            gt_label = seg["label"]
            exercise = seg.get("exercise", "")

            # 找该区间内的主要预测
            pred_labels_in_range = []
            for _, row in r["pred_windows_df"].iterrows():
                wt0, wt1 = row["window_start_sec"], row["window_end_sec"]
                overlap = max(0, min(t1, wt1) - max(t0, wt0))
                if overlap > 0:
                    pred_labels_in_range.append(row["label"])
            if pred_labels_in_range:
                from collections import Counter
                pred_label = Counter(pred_labels_in_range).most_common(1)[0][0]
            else:
                pred_label = "—"

            match = pred_label == gt_label
            cls = "match" if match else "mismatch"
            icon = "✓" if match else "✗"
            pred_zh = LABEL_ZH.get(pred_label, pred_label)

            html_parts.append(
                f'<tr class="{cls}"><td>{t0:.0f}s - {t1:.0f}s</td>'
                f'<td>{exercise}</td><td>{seg["label_zh"]}</td>'
                f'<td>{pred_zh}</td><td>{icon}</td></tr>'
            )
        html_parts.append('</table></div>')

        html_parts.append('</div>')  # .session

    html_parts.append('</body></html>')

    outpath.parent.mkdir(parents=True, exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
    print(f"[可视化] → {outpath}")


def main():
    model_path = SCRIPT_DIR / "posture7_output" / "posture7_model_extra_trees.joblib"
    bundle = joblib.load(model_path)
    model = bundle["model"]
    print(f"[模型] {bundle['model_type']}, 已加载")

    exercise_map = load_exercise_posture_map()
    print(f"[映射] {len(exercise_map)} 个动作")

    shared = Path("D:/WorkPath/fitness_new/recognize/visualize/result/shared")
    data_dirs = []
    for d in sorted(shared.iterdir()):
        if d.is_dir() and (d / "IMU.txt").exists() and (d / "ground_truth.json").exists():
            data_dirs.append(d)
    print(f"[数据] 找到 {len(data_dirs)} 个配对目录")

    results = []
    for d in data_dirs:
        print(f"\n[推理] {d.name}")
        imu_df = load_imu_txt(d / "IMU.txt")
        gt = load_ground_truth(d / "ground_truth.json")
        total_sec = imu_df["time_sec"].iloc[-1]
        print(f"  IMU 时长: {total_sec:.1f}s, 样本: {len(imu_df)}")

        pred_windows = predict_one(imu_df, model, bundle)
        pred_segments = _merge_segments(pred_windows, bundle["label_zh"])
        print(f"  预测窗口: {len(pred_windows)}, 预测片段: {len(pred_segments)}")

        gt_segments = build_gt_segments(gt, exercise_map, total_sec)
        gt_intervals = build_posture_labels_from_gt(gt, exercise_map, total_sec)

        acc_info = compute_accuracy(pred_windows, gt_intervals, total_sec)
        print(f"  准确率: {acc_info['accuracy']:.1%} ({acc_info['correct']}/{acc_info['total']})")

        results.append({
            "name": d.name,
            "total_sec": total_sec,
            "n_windows": len(pred_windows),
            "pred_windows_df": pred_windows,
            "pred_segments": pred_segments,
            "gt_segments": gt_segments,
            "acc_info": acc_info,
        })

    outpath = SCRIPT_DIR / "posture7_output" / "posture7_results.html"
    generate_html(results, outpath)
    print(f"\n[完成] 可视化报告: {outpath}")


if __name__ == "__main__":
    main()
