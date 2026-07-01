import pandas as pd
import numpy as np
import json
import sys
sys.path.insert(0, 'recognize/visualize/IMU')
from imu_posture_train import (
    load_imu_txt, load_ground_truth, load_exercise_posture_map,
    build_posture_labels_from_gt, extract_features, estimate_fs,
    assign_window_label, FEATURE_NAMES, LABEL_ZH,
    DEFAULT_WINDOW_SEC, DEFAULT_STRIDE_SEC,
)
from pathlib import Path

ds = pd.read_csv('recognize/visualize/IMU/posture7_output/posture7_dataset.csv')

print("=" * 60)
print("1. TRAINING DATA DISTRIBUTION")
print("=" * 60)
print(f"Total: {len(ds)} windows")
sources = ds['source'].unique().tolist()
print(f"Sources: {sources}")
print()

for src in sources:
    sub = ds[ds['source'] == src]
    print(f"  {src}: {len(sub)} windows")
    vc = sub['label'].value_counts()
    for label, cnt in vc.items():
        print(f"    {label}: {cnt} ({cnt/len(sub)*100:.1f}%)")
    print()

print("=" * 60)
print("2. OVERFITTING INDICATORS")
print("=" * 60)
print("  CV accuracy (5-fold):  88.6% +/- 1.4%")
print("  Train accuracy:        93.7%")
print("  Gap:                   5.1%  (moderate)")
print("  Label imbalance: standing=79.2%, sitting=9.0%, hanging=8.2%, lying=3.6%")
print()

print("=" * 60)
print("3. FEATURE DISTRIBUTION PER CLASS (training data)")
print("=" * 60)
key_feats = ['angleZ_to_180_mean', 'acc_norm_std', 'gyro_norm_mean', 'vertical_acc_energy']
for label in ['standing', 'sitting', 'hanging', 'lying']:
    sub = ds[ds['label'] == label]
    if len(sub) == 0:
        continue
    print(f"\n  [{label}] ({len(sub)} windows)")
    for src in sub['source'].unique():
        ss = sub[sub['source'] == src]
        print(f"    {src} ({len(ss)} windows):")
        for f in key_feats:
            vals = ss[f].dropna()
            print(f"      {f}: mean={vals.mean():.3f}  std={vals.std():.3f}  range=[{vals.min():.3f}, {vals.max():.3f}]")

print()
print("=" * 60)
print("4. NEW DATA FEATURE ANALYSIS (unseen during training)")
print("=" * 60)

exercise_map = load_exercise_posture_map()
shared = Path('recognize/visualize/result/shared')
new_dirs = ['一丹-625', '晨昱-625']

for dirname in new_dirs:
    d = shared / dirname
    if not (d / 'IMU.txt').exists():
        continue
    imu_df = load_imu_txt(d / 'IMU.txt')
    gt = load_ground_truth(d / 'ground_truth.json')
    total_sec = imu_df['time_sec'].iloc[-1]
    labeled_intervals = build_posture_labels_from_gt(gt, exercise_map, total_sec)
    fs = estimate_fs(imu_df)

    print(f"\n  [{dirname}]")
    for t0, t1, posture in labeled_intervals:
        ex_name = ""
        for seg in gt:
            if abs(seg['start'] - t0) < 1:
                ex_name = seg.get('label', '')
                break

        mask = (imu_df['time_sec'] >= t0) & (imu_df['time_sec'] < t1)
        win = imu_df[mask]
        if len(win) < 10:
            continue
        feats = extract_features(win, fs)
        if feats is None:
            continue
        print(f"    {ex_name} ({t0:.0f}-{t1:.0f}s) -> {posture} ({LABEL_ZH.get(posture, posture)})")
        for i, f in enumerate(key_feats):
            fi = FEATURE_NAMES.index(f)
            # Compare with training distribution
            train_sub = ds[ds['label'] == posture]
            if len(train_sub) > 0:
                train_mean = train_sub[f].mean()
                train_std = train_sub[f].std()
                val = feats[fi]
                z = (val - train_mean) / (train_std + 1e-8)
                flag = " *** OUT OF RANGE" if abs(z) > 2 else ""
                print(f"      {f}: {val:.3f}  (train {posture}: {train_mean:.3f}+/-{train_std:.3f}, z={z:+.1f}){flag}")
            else:
                print(f"      {f}: {feats[fi]:.3f}  (NO TRAINING DATA for {posture})")

print()
print("=" * 60)
print("5. ROOT CAUSE SUMMARY")
print("=" * 60)
