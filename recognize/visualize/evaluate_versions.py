"""
Evaluate exercise recognition accuracy across versions v9-v15.
Computes: Action_F1, SetRep_Accuracy@1, Joint_Log_F1@1
"""
import json
import os
import glob
import re
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, "result")
SHARED_DIR = os.path.join(RESULT_DIR, "shared")

IOU_THRESHOLD = 0.3
GT_COVERAGE_THRESHOLD = 0.5
REP_TOLERANCE = 1

ACTION_ALIASES = {
    # 有氧/热身/拉伸
    "跑步": "跑步机",
    "跑步机": "跑步机",
    "热身（跑步机）": "跑步机",
    "拉伸（跑步机）": "跑步机",
    "爬楼机": "爬楼机",
    "爬楼": "爬楼机",
    "登阶机/爬楼机": "爬楼机",
    "登阶机": "爬楼机",
    "健身车/动感单车": "动感单车",
    "动态拉伸": "拉伸",
    "泡沫轴放松": "拉伸",
    # 深蹲
    "史密斯机深蹲": "史密斯深蹲",
    "史密斯深蹲": "史密斯深蹲",
    "杠铃深蹲": "杠铃深蹲",
    # 卧推
    "卧推": "杠铃卧推",
    "杠铃卧推": "杠铃卧推",
    "水平哑铃卧推": "哑铃卧推",
    "上斜 30 度哑铃卧推": "哑铃卧推",
    "哑铃卧推": "哑铃卧推",
    "史密斯卧推": "史密斯卧推",
    "上斜史密斯卧推": "史密斯卧推",
    "上斜推胸": "器械推胸",
    # 推胸/夹胸
    "器械推胸": "器械推胸",
    "固定器械推胸": "器械推胸",
    "器械夹胸": "蝴蝶机夹胸",
    "蝴蝶机飞鸟": "蝴蝶机夹胸",
    "蝴蝶机夹胸": "蝴蝶机夹胸",
    "绳索夹胸": "绳索夹胸",
    "夹胸": "绳索夹胸",
    "哑铃夹胸": "哑铃夹胸",
    "蝴蝶机反向飞鸟": "蝴蝶机反向飞鸟",
    # 下拉
    "高位下拉": "高位下拉",
    "直杆高位下拉": "高位下拉",
    "宽距高位下拉": "高位下拉",
    "高位宽距下拉": "高位下拉",
    "高位V把下拉": "高位下拉",
    "反握器械高位下拉": "高位下拉",
    # 划船
    "坐姿划船": "坐姿划船",
    "坐姿划船（V型把手）": "坐姿划船",
    "坐姿绳索划船": "坐姿划船",
    "固定器械坐姿划船": "坐姿划船",
    "划船": "坐姿划船",
    "杠铃俯身划船": "杠铃划船",
    "杠铃划船": "杠铃划船",
    # 面拉
    "绳索面拉": "面拉",
    "面拉": "面拉",
    # 弯举
    "杠铃弯举": "杠铃弯举",
    "哑铃弯举": "哑铃弯举",
    "器械弯举": "器械弯举",
    "绳索弯举": "绳索弯举",
    # 侧平举
    "哑铃侧举": "哑铃侧平举",
    "哑铃侧平举": "哑铃侧平举",
    "绳索侧平举": "哑铃侧平举",
    # 推肩
    "反向推肩": "反向推肩",
    "固定器械推肩": "器械推肩",
    "史密斯推肩": "史密斯推肩",
    "哑铃推肩": "哑铃推肩",
    "竖直位哑铃推举": "哑铃推肩",
    # 绳索下压/臂屈伸
    "绳索下压": "绳索下压",
  "绳索下拉": "绳索下压",
    "直杆绳索下压": "绳索下压",
    "绳索直杆下压·1": "绳索下压",
    "绳索直杆下压·2": "绳索下压",
    "绳索直臂下压": "绳索直臂下压",
    "龙门架直臂下压": "绳索直臂下压",
    "绳索臂屈伸": "绳索臂屈伸",
    "辅助双杠臂屈伸": "臂屈伸",
    "单臂绳索下拉": "绳索下拉",
    "绳索上拉": "绳索上拉",
    # 举腿
    "举腿": "悬垂举腿",
    "悬垂举腿": "悬垂举腿",
    # 腿部
    "腿举": "腿举",
    "坐姿腿屈伸": "坐姿腿屈伸",
    "坐姿腿弯举": "坐姿腿弯举",
    # 其他
    "提拉杠铃": "杠铃提拉",
    "杠铃提拉": "杠铃提拉",
    "杠铃硬拉": "杠铃硬拉",
    "反向推胸": "反向推胸",
    "推拉": "推拉",
    "引体向上": "引体向上",
    "俯卧撑": "俯卧撑",
    "肩背练习": "肩背练习",
}


def normalize_action(name):
    if not name:
        return ""
    name = name.strip()
    if name in ACTION_ALIASES:
        return ACTION_ALIASES[name]
    stripped = re.sub(r'[（(].*?[）)]', '', name).strip()
    if stripped in ACTION_ALIASES:
        return ACTION_ALIASES[stripped]
    return stripped


def parse_gt_reps(reps_str):
    if not reps_str:
        return None, None
    parts = reps_str.strip().split()
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            pass
    if not nums:
        return None, None
    return len(nums), sum(nums)


def load_ground_truth(video_id):
    gt_path = os.path.join(SHARED_DIR, video_id, "ground_truth.json")
    if not os.path.exists(gt_path):
        return []
    with open(gt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    events = []
    for item in data:
        if item.get("type") != "exercise":
            continue
        label = item.get("label", "")
        if label in ("热身", "拉伸", "未知动作（无器材 ）"):
            continue
        reps_str = item.get("reps")
        gt_sets, gt_reps = parse_gt_reps(reps_str)
        if gt_sets is None:
            gt_sets = 1
        events.append({
            "start": float(item["start"]),
            "end": float(item["end"]),
            "label": label,
            "action": normalize_action(label),
            "sets": gt_sets,
            "reps": gt_reps,
        })
    return events


def load_exercise_result(version, video_id):
    path = os.path.join(RESULT_DIR, version, video_id, "exercise_result.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    events = []
    for item in data.get("results", []):
        result = item.get("result", {})
        exercise_name = result.get("exercise", "")
        sets_list = result.get("sets", [])
        total_sets = result.get("total_sets")
        if total_sets is None:
            total_sets = len(sets_list)
        total_reps = result.get("total_reps")
        if total_reps is None:
            total_reps = sum(s.get("reps", 0) for s in sets_list)
        events.append({
            "start": float(item.get("startTime", 0)),
            "end": float(item.get("endTime", 0)),
            "label": exercise_name,
            "action": normalize_action(exercise_name),
            "sets": total_sets,
            "reps": total_reps,
        })
    return events


def merge_consecutive_preds(pred_events, gap_threshold=120):
    if not pred_events:
        return []
    sorted_preds = sorted(pred_events, key=lambda x: x["start"])
    merged = [dict(sorted_preds[0])]
    for p in sorted_preds[1:]:
        last = merged[-1]
        if p["action"] == last["action"] and (p["start"] - last["end"]) <= gap_threshold:
            last["end"] = max(last["end"], p["end"])
            last["sets"] = last["sets"] + p["sets"]
            last["reps"] = (last["reps"] or 0) + (p["reps"] or 0)
            last["label"] = last["label"]
        else:
            merged.append(dict(p))
    return merged


def compute_overlap(p_start, p_end, g_start, g_end):
    return max(0, min(p_end, g_end) - max(p_start, g_start))


def compute_iou(p, g):
    overlap = compute_overlap(p["start"], p["end"], g["start"], g["end"])
    p_dur = p["end"] - p["start"]
    g_dur = g["end"] - g["start"]
    union = p_dur + g_dur - overlap
    if union <= 0:
        return 0
    return overlap / union


def compute_gt_coverage(p, g):
    overlap = compute_overlap(p["start"], p["end"], g["start"], g["end"])
    g_dur = g["end"] - g["start"]
    if g_dur <= 0:
        return 0
    return overlap / g_dur


def match_events(gt_events, pred_events):
    candidates = []
    for gi, g in enumerate(gt_events):
        for pi, p in enumerate(pred_events):
            iou = compute_iou(p, g)
            gt_cov = compute_gt_coverage(p, g)
            if iou >= IOU_THRESHOLD or gt_cov >= GT_COVERAGE_THRESHOLD:
                candidates.append((iou, gi, pi))
    candidates.sort(key=lambda x: -x[0])
    matched_gt = set()
    matched_pred = set()
    pairs = []
    for iou, gi, pi in candidates:
        if gi in matched_gt or pi in matched_pred:
            continue
        matched_gt.add(gi)
        matched_pred.add(pi)
        pairs.append((gi, pi, iou))
    return pairs, matched_gt, matched_pred


def evaluate_video(gt_events, pred_events):
    pred_events = merge_consecutive_preds(pred_events)

    if not gt_events:
        return {
            "action_tp": 0, "action_fp": len(pred_events), "action_fn": 0,
            "setrep_ok": 0, "gt_count": 0,
            "joint_tp": 0, "joint_fp": len(pred_events), "joint_fn": 0,
            "details": [],
        }

    pairs, matched_gt, matched_pred = match_events(gt_events, pred_events)
    action_tp = 0
    action_fp = 0
    action_fn = 0
    setrep_ok = 0
    set_ok_count = 0
    joint_tp = 0
    joint_fp = 0
    joint_fn = 0
    details = []

    for gi, pi, iou in pairs:
        g = gt_events[gi]
        p = pred_events[pi]
        a_ok = (g["action"] == p["action"]) if g["action"] and p["action"] else False
        s_ok = (g["sets"] == p["sets"])
        if g["reps"] is None:
            r_ok_1 = True
        else:
            r_ok_1 = abs(p["reps"] - g["reps"]) <= REP_TOLERANCE
        count_ok = r_ok_1
        j_ok = a_ok and count_ok

        if a_ok:
            action_tp += 1
        else:
            action_fp += 1
            action_fn += 1
        if count_ok:
            setrep_ok += 1
        if s_ok:
            set_ok_count += 1
        if j_ok:
            joint_tp += 1
        else:
            joint_fp += 1
            joint_fn += 1

        error_type = "fully_correct" if j_ok else (
            "wrong_action" if not a_ok else "rep_error"
        )
        details.append({
            "gt_action": g["label"], "pred_action": p["label"],
            "iou": round(iou, 3),
            "action_ok": a_ok, "set_ok": s_ok, "rep_ok@1": r_ok_1,
            "gt_sets": g["sets"], "pred_sets": p["sets"],
            "gt_reps": g["reps"], "pred_reps": p["reps"],
            "joint_ok": j_ok, "error_type": error_type,
        })

    unmatched_pred = len(pred_events) - len(matched_pred)
    unmatched_gt = len(gt_events) - len(matched_gt)
    action_fp += unmatched_pred
    action_fn += unmatched_gt
    joint_fp += unmatched_pred
    joint_fn += unmatched_gt

    for gi in range(len(gt_events)):
        if gi not in matched_gt:
            g = gt_events[gi]
            details.append({
                "gt_action": g["label"], "pred_action": "(漏识别)",
                "iou": 0, "action_ok": False,
                "gt_sets": g["sets"], "pred_sets": None,
                "gt_reps": g["reps"], "pred_reps": None,
                "set_ok": False, "rep_ok@1": False,
                "joint_ok": False, "error_type": "missed_action",
            })
    for pi in range(len(pred_events)):
        if pi not in matched_pred:
            p = pred_events[pi]
            details.append({
                "gt_action": "(多识别)", "pred_action": p["label"],
                "iou": 0, "action_ok": False,
                "gt_sets": None, "pred_sets": p["sets"],
                "gt_reps": None, "pred_reps": p["reps"],
                "set_ok": False, "rep_ok@1": False,
                "joint_ok": False, "error_type": "extra_action",
            })

    gt_total_reps = sum(g["reps"] for g in gt_events if g["reps"] is not None)
    pred_total_reps = sum(p["reps"] for p in pred_events if p["reps"] is not None)
    gt_action_count = len(gt_events)
    pred_action_count = len(pred_events)

    return {
        "action_tp": action_tp, "action_fp": action_fp, "action_fn": action_fn,
        "setrep_ok": setrep_ok, "set_ok_count": set_ok_count, "gt_count": gt_action_count,
        "joint_tp": joint_tp, "joint_fp": joint_fp, "joint_fn": joint_fn,
        "gt_total_reps": gt_total_reps, "pred_total_reps": pred_total_reps,
        "gt_action_count": gt_action_count, "pred_action_count": pred_action_count,
        "details": details,
    }


def f1(tp, fp, fn):
    if tp == 0:
        return 0.0
    p = tp / (tp + fp) if (tp + fp) > 0 else 0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def get_all_video_ids():
    ids = set()
    for name in os.listdir(SHARED_DIR):
        gt_path = os.path.join(SHARED_DIR, name, "ground_truth.json")
        if os.path.exists(gt_path):
            ids.add(name)
    return sorted(ids)


def evaluate_version(version, video_ids):
    total = defaultdict(int)
    per_video = {}
    all_details = {}

    for vid in video_ids:
        gt = load_ground_truth(vid)
        pred = load_exercise_result(version, vid)
        if not gt and not pred:
            continue
        result = evaluate_video(gt, pred)
        total["action_tp"] += result["action_tp"]
        total["action_fp"] += result["action_fp"]
        total["action_fn"] += result["action_fn"]
        total["setrep_ok"] += result["setrep_ok"]
        total["set_ok_count"] += result["set_ok_count"]
        total["gt_count"] += result["gt_count"]
        total["joint_tp"] += result["joint_tp"]
        total["joint_fp"] += result["joint_fp"]
        total["joint_fn"] += result["joint_fn"]
        total["gt_total_reps"] += result["gt_total_reps"]
        total["pred_total_reps"] += result["pred_total_reps"]
        total["gt_action_count"] += result["gt_action_count"]
        total["pred_action_count"] += result["pred_action_count"]

        vid_action_f1 = f1(result["action_tp"], result["action_fp"], result["action_fn"])
        vid_set_acc = result["set_ok_count"] / result["gt_count"] if result["gt_count"] > 0 else 0
        vid_setrep = result["setrep_ok"] / result["gt_count"] if result["gt_count"] > 0 else 0
        vid_joint_f1 = f1(result["joint_tp"], result["joint_fp"], result["joint_fn"])

        per_video[vid] = {
            "action_f1": vid_action_f1,
            "set_acc": vid_set_acc,
            "setrep_acc": vid_setrep,
            "joint_f1": vid_joint_f1,
            **result,
        }
        all_details[vid] = result["details"]

    tp, fp, fn = total["action_tp"], total["action_fp"], total["action_fn"]
    micro_action_p = tp / (tp + fp) if (tp + fp) > 0 else 0
    micro_action_r = tp / (tp + fn) if (tp + fn) > 0 else 0
    micro_action_f1 = f1(tp, fp, fn)
    micro_setrep = total["setrep_ok"] / total["gt_count"] if total["gt_count"] > 0 else 0
    micro_set_acc = total["set_ok_count"] / total["gt_count"] if total["gt_count"] > 0 else 0
    micro_joint_f1 = f1(total["joint_tp"], total["joint_fp"], total["joint_fn"])

    vids_with_data = [v for v in per_video.values() if v["gt_count"] > 0]
    n = len(vids_with_data) if vids_with_data else 1
    macro_action_f1 = sum(v["action_f1"] for v in vids_with_data) / n
    macro_setrep = sum(v["setrep_acc"] for v in vids_with_data) / n
    macro_joint_f1 = sum(v["joint_f1"] for v in vids_with_data) / n

    return {
        "micro": {
            "action_precision": micro_action_p,
            "action_recall": micro_action_r,
            "action_f1": micro_action_f1,
            "set_acc": micro_set_acc,
            "setrep_acc": micro_setrep,
            "joint_f1": micro_joint_f1,
        },
        "macro": {
            "action_f1": macro_action_f1,
            "setrep_acc": macro_setrep,
            "joint_f1": macro_joint_f1,
        },
        "totals": dict(total),
        "per_video": per_video,
        "details": all_details,
    }


def generate_html(all_results, versions):
    version_labels = json.dumps(versions)
    micro_action_p = json.dumps([round(all_results[v]["micro"]["action_precision"] * 100, 1) for v in versions])
    micro_action_r = json.dumps([round(all_results[v]["micro"]["action_recall"] * 100, 1) for v in versions])
    micro_action = json.dumps([round(all_results[v]["micro"]["action_f1"] * 100, 1) for v in versions])
    micro_setrep = json.dumps([round(all_results[v]["micro"]["setrep_acc"] * 100, 1) for v in versions])
    micro_joint = json.dumps([round(all_results[v]["micro"]["joint_f1"] * 100, 1) for v in versions])
    macro_action = json.dumps([round(all_results[v]["macro"]["action_f1"] * 100, 1) for v in versions])
    macro_setrep = json.dumps([round(all_results[v]["macro"]["setrep_acc"] * 100, 1) for v in versions])
    macro_joint = json.dumps([round(all_results[v]["macro"]["joint_f1"] * 100, 1) for v in versions])

    per_video_data = {}
    all_vids = set()
    for v in versions:
        for vid in all_results[v]["per_video"]:
            all_vids.add(vid)
    all_vids = sorted(all_vids)

    for vid in all_vids:
        per_video_data[vid] = {
            "action_f1": [],
            "setrep_acc": [],
            "joint_f1": [],
        }
        for ver in versions:
            pv = all_results[ver]["per_video"].get(vid)
            if pv:
                per_video_data[vid]["action_f1"].append(round(pv["action_f1"] * 100, 1))
                per_video_data[vid]["setrep_acc"].append(round(pv["setrep_acc"] * 100, 1))
                per_video_data[vid]["joint_f1"].append(round(pv["joint_f1"] * 100, 1))
            else:
                per_video_data[vid]["action_f1"].append(None)
                per_video_data[vid]["setrep_acc"].append(None)
                per_video_data[vid]["joint_f1"].append(None)

    details_data = {}
    for v in versions:
        details_data[v] = {}
        for vid, dets in all_results[v]["details"].items():
            details_data[v][vid] = dets

    totals_data = {}
    for v in versions:
        totals_data[v] = all_results[v]["totals"]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>健身动作识别评估报告 v9-v15</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f7fa; color: #333; padding: 20px; }}
h1 {{ text-align: center; margin: 20px 0 10px; font-size: 24px; color: #1a1a2e; }}
.subtitle {{ text-align: center; color: #666; margin-bottom: 30px; font-size: 14px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
.card {{ background: #fff; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
.card h2 {{ font-size: 16px; color: #555; margin-bottom: 16px; border-bottom: 2px solid #e8e8e8; padding-bottom: 8px; }}
.card.full {{ grid-column: 1 / -1; }}
canvas {{ max-height: 400px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 8px 12px; text-align: center; border-bottom: 1px solid #eee; }}
th {{ background: #f8f9fa; font-weight: 600; color: #555; position: sticky; top: 0; }}
tr:hover {{ background: #f0f7ff; }}
.good {{ color: #27ae60; font-weight: 600; }}
.mid {{ color: #f39c12; font-weight: 600; }}
.bad {{ color: #e74c3c; font-weight: 600; }}
.metric-cards {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
.metric-card {{ flex: 1; min-width: 180px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; border-radius: 12px; padding: 20px; text-align: center; }}
.metric-card.green {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }}
.metric-card.orange {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
.metric-card .value {{ font-size: 32px; font-weight: 700; }}
.metric-card .label {{ font-size: 12px; opacity: .85; margin-top: 4px; }}
.metric-card .sub {{ font-size: 11px; opacity: .7; margin-top: 2px; }}
.tabs {{ display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }}
.tab {{ padding: 6px 16px; border-radius: 20px; cursor: pointer; font-size: 13px; border: 1px solid #ddd; background: #fff; transition: .2s; }}
.tab.active {{ background: #667eea; color: #fff; border-color: #667eea; }}
.tab:hover {{ background: #e8ecf8; }}
.tab.active:hover {{ background: #5a6fd6; }}
.detail-table {{ max-height: 400px; overflow-y: auto; }}
.legend {{ display: flex; gap: 16px; justify-content: center; margin: 10px 0; font-size: 12px; color: #888; }}
.legend span::before {{ content: ''; display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
</style>
</head>
<body>
<h1>健身动作识别评估报告</h1>
<p class="subtitle">版本对比：v9 → v15 | 指标：Action_F1 · SetRep_Accuracy@1 · Joint_Log_F1@1</p>

<div class="metric-cards" id="latestMetrics"></div>

<div class="grid">
  <div class="card full">
    <h2>📊 Micro 指标趋势（主指标，所有样本汇总）</h2>
    <canvas id="microChart"></canvas>
  </div>
  <div class="card full">
    <h2>📊 Macro 指标趋势（视频级平均，稳定性参考）</h2>
    <canvas id="macroChart"></canvas>
  </div>
</div>

<div class="card full" style="margin-bottom: 20px;">
  <h2>📋 各版本指标汇总表</h2>
  <table>
    <thead>
      <tr>
        <th>版本</th>
        <th>Action_Precision</th>
        <th>Action_Recall</th>
        <th>Action_F1</th>
        <th>SetRep_Acc@1</th>
        <th>Joint_F1@1</th>
      </tr>
    </thead>
    <tbody id="summaryTable"></tbody>
  </table>
</div>

<div class="card full" style="margin-bottom: 20px;">
  <h2>📋 各视频各版本指标明细</h2>
  <div class="tabs" id="metricTabs"></div>
  <div class="detail-table">
    <table>
      <thead id="videoTableHead"></thead>
      <tbody id="videoTableBody"></tbody>
    </table>
  </div>
</div>

<div class="card full" style="margin-bottom: 20px;">
  <h2>🔍 动作级明细（选择版本和视频）</h2>
  <div style="display:flex;gap:12px;margin-bottom:12px;">
    <select id="selVersion" style="padding:6px 12px;border-radius:8px;border:1px solid #ddd;"></select>
    <select id="selVideo" style="padding:6px 12px;border-radius:8px;border:1px solid #ddd;"></select>
  </div>
  <div class="detail-table">
    <table>
      <thead>
        <tr>
          <th>GT动作</th><th>预测动作</th><th>IoU</th>
          <th>动作✓</th><th>GT组</th><th>预测组</th><th>GT次</th><th>预测次</th>
          <th>组✓</th><th>次@1✓</th><th>综合✓</th><th>错误类型</th>
        </tr>
      </thead>
      <tbody id="detailTable"></tbody>
    </table>
  </div>
</div>

<script>
const VERSIONS = {version_labels};
const MICRO_ACTION_P = {micro_action_p};
const MICRO_ACTION_R = {micro_action_r};
const MICRO_ACTION = {micro_action};
const MICRO_SETREP = {micro_setrep};
const MICRO_JOINT = {micro_joint};
const MACRO_ACTION = {macro_action};
const MACRO_SETREP = {macro_setrep};
const MACRO_JOINT = {macro_joint};
const PER_VIDEO = {json.dumps(per_video_data, ensure_ascii=False)};
const DETAILS = {json.dumps(details_data, ensure_ascii=False)};
const TOTALS = {json.dumps(totals_data, ensure_ascii=False)};
const ALL_VIDS = {json.dumps(all_vids, ensure_ascii=False)};

function colorVal(v) {{
  if (v === null || v === undefined) return '<span class="mid">-</span>';
  if (v >= 80) return `<span class="good">${{v}}%</span>`;
  if (v >= 50) return `<span class="mid">${{v}}%</span>`;
  return `<span class="bad">${{v}}%</span>`;
}}

// Latest version metric cards
const latest = VERSIONS[VERSIONS.length - 1];
const li = VERSIONS.length - 1;
document.getElementById('latestMetrics').innerHTML = `
  <div class="metric-card">
    <div class="value">${{MICRO_ACTION[li]}}%</div>
    <div class="label">Action_F1 (动作识别)</div>
    <div class="sub">${{latest}} · Micro</div>
  </div>
  <div class="metric-card green">
    <div class="value">${{MICRO_SETREP[li]}}%</div>
    <div class="label">SetRep_Accuracy@1 (组别个数)</div>
    <div class="sub">${{latest}} · Micro</div>
  </div>
  <div class="metric-card orange">
    <div class="value">${{MICRO_JOINT[li]}}%</div>
    <div class="label">Joint_Log_F1@1 (综合)</div>
    <div class="sub">${{latest}} · Micro</div>
  </div>
`;

function makeChart(id, data1, data2, data3) {{
  new Chart(document.getElementById(id), {{
    type: 'line',
    data: {{
      labels: VERSIONS,
      datasets: [
        {{ label: 'Action_F1', data: data1, borderColor: '#667eea', backgroundColor: 'rgba(102,126,234,.1)', fill: true, tension: .3, pointRadius: 5, pointHoverRadius: 8 }},
        {{ label: 'SetRep_Accuracy@1', data: data2, borderColor: '#11998e', backgroundColor: 'rgba(17,153,142,.1)', fill: true, tension: .3, pointRadius: 5, pointHoverRadius: 8 }},
        {{ label: 'Joint_Log_F1@1', data: data3, borderColor: '#f5576c', backgroundColor: 'rgba(245,87,108,.1)', fill: true, tension: .3, pointRadius: 5, pointHoverRadius: 8 }},
      ]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ position: 'top' }},
        tooltip: {{ callbacks: {{ label: ctx => ctx.dataset.label + ': ' + ctx.parsed.y + '%' }} }}
      }},
      scales: {{
        y: {{ min: 0, max: 100, ticks: {{ callback: v => v + '%' }} }},
      }}
    }}
  }});
}}
makeChart('microChart', MICRO_ACTION, MICRO_SETREP, MICRO_JOINT);
makeChart('macroChart', MACRO_ACTION, MACRO_SETREP, MACRO_JOINT);

// Summary table
let stHtml = '';
VERSIONS.forEach((v, i) => {{
  stHtml += `<tr>
    <td><b>${{v}}</b></td>
    <td>${{colorVal(MICRO_ACTION_P[i])}}</td>
    <td>${{colorVal(MICRO_ACTION_R[i])}}</td>
    <td>${{colorVal(MICRO_ACTION[i])}}</td>
    <td>${{colorVal(MICRO_SETREP[i])}}</td>
    <td>${{colorVal(MICRO_JOINT[i])}}</td>
  </tr>`;
}});
document.getElementById('summaryTable').innerHTML = stHtml;

// Per-video table
let currentMetric = 'action_f1';
const metricLabels = {{action_f1: 'Action_F1', setrep_acc: 'SetRep_Accuracy@1', joint_f1: 'Joint_Log_F1@1'}};
function renderVideoTable() {{
  let th = '<tr><th>视频</th>';
  VERSIONS.forEach(v => th += `<th>${{v}}</th>`);
  th += '</tr>';
  document.getElementById('videoTableHead').innerHTML = th;
  let tbody = '';
  ALL_VIDS.forEach(vid => {{
    const d = PER_VIDEO[vid];
    if (!d) return;
    tbody += `<tr><td style="text-align:left">${{vid}}</td>`;
    d[currentMetric].forEach(val => {{
      tbody += `<td>${{colorVal(val)}}</td>`;
    }});
    tbody += '</tr>';
  }});
  document.getElementById('videoTableBody').innerHTML = tbody;
}}
function renderTabs() {{
  let html = '';
  for (const [k, label] of Object.entries(metricLabels)) {{
    html += `<div class="tab ${{k===currentMetric?'active':''}}" onclick="currentMetric='${{k}}';renderTabs();renderVideoTable();">${{label}}</div>`;
  }}
  document.getElementById('metricTabs').innerHTML = html;
}}
renderTabs();
renderVideoTable();

// Detail selectors
const selV = document.getElementById('selVersion');
const selVid = document.getElementById('selVideo');
VERSIONS.forEach(v => {{ const o = document.createElement('option'); o.value = v; o.textContent = v; selV.appendChild(o); }});
selV.value = VERSIONS[VERSIONS.length - 1];
function updateVideoSelect() {{
  selVid.innerHTML = '';
  const v = selV.value;
  const vids = Object.keys(DETAILS[v] || {{}});
  vids.sort();
  vids.forEach(vid => {{ const o = document.createElement('option'); o.value = vid; o.textContent = vid; selVid.appendChild(o); }});
  renderDetails();
}}
function renderDetails() {{
  const v = selV.value;
  const vid = selVid.value;
  const dets = (DETAILS[v] || {{}})[vid] || [];
  let html = '';
  dets.forEach(d => {{
    const bg = d.joint_ok ? '#f0fff0' : (d.error_type === 'missed_action' ? '#fff0f0' : (d.error_type === 'extra_action' ? '#fff8e0' : '#fff5f5'));
    html += `<tr style="background:${{bg}}">
      <td>${{d.gt_action}}</td><td>${{d.pred_action}}</td><td>${{d.iou}}</td>
      <td>${{d.action_ok?'✅':'❌'}}</td>
      <td>${{d.gt_sets ?? '-'}}</td><td>${{d.pred_sets ?? '-'}}</td>
      <td>${{d.gt_reps ?? '-'}}</td><td>${{d.pred_reps ?? '-'}}</td>
      <td>${{d.set_ok?'✅':'❌'}}</td><td>${{d['rep_ok@1']?'✅':'❌'}}</td>
      <td>${{d.joint_ok?'✅':'❌'}}</td><td>${{d.error_type}}</td>
    </tr>`;
  }});
  document.getElementById('detailTable').innerHTML = html || '<tr><td colspan="12">无数据</td></tr>';
}}
selV.addEventListener('change', updateVideoSelect);
selVid.addEventListener('change', renderDetails);
updateVideoSelect();
</script>
</body>
</html>"""
    return html


def main():
    video_ids = get_all_video_ids()
    print(f"Found {len(video_ids)} videos with ground truth:")
    for vid in video_ids:
        print(f"  - {vid}")

    versions = []
    for v in range(9, 16):
        vname = f"v{v}"
        vdir = os.path.join(RESULT_DIR, vname)
        if os.path.isdir(vdir):
            versions.append(vname)
    print(f"\nEvaluating versions: {', '.join(versions)}")

    all_results = {}
    for ver in versions:
        result = evaluate_version(ver, video_ids)
        all_results[ver] = result
        m = result["micro"]
        print(f"\n{'='*50}")
        print(f"  {ver} Micro Metrics:")
        print(f"    Action_Precision:    {m['action_precision']*100:.1f}%")
        print(f"    Action_Recall:       {m['action_recall']*100:.1f}%")
        print(f"    Action_F1:           {m['action_f1']*100:.1f}%")
        print(f"    SetRep_Accuracy@1:   {m['setrep_acc']*100:.1f}%")
        print(f"    Joint_Log_F1@1:      {m['joint_f1']*100:.1f}%")

    html = generate_html(all_results, versions)
    output_path = os.path.join(RESULT_DIR, "evaluation_report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
