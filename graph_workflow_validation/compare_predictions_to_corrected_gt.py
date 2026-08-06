from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ALIASES = {
    "UNKNOWN_ACTION": "未知动作",
    "UNKNOWN_EXERCISE": "未知动作",
    "UNKNOWN": "未知动作",
    "unknown_action": "未知动作",
    "unknown_exercise": "未知动作",
    "cable_triceps_pushdown": "绳索下压",
    "triceps_pushdown": "绳索下压",
    "绳索直臂下压": "绳索下压",
    "cable_lat_pulldown": "高位下拉",
    "lat_pulldown": "高位下拉",
    "高位直杆下拉": "高位下拉",
    "直杆高位下拉": "高位下拉",
    "反握器械高位下拉": "高位下拉",
    "宽距高位下拉": "高位下拉",
    "绳索下拉": "绳索下拉",
    "单臂绳索下拉": "单臂绳索下拉",
    "face_pull": "面拉",
    "cable_face_pull": "面拉",
    "绳索面拉": "面拉",
    "坐姿绳索划船": "划船",
    "坐姿划船": "划船",
    "固定器械坐姿划船": "划船",
    "seated_cable_row": "划船",
    "row": "划船",
    "跑步机": "跑步",
    "跑步": "跑步",
    "treadmill": "跑步",
    "爬楼": "爬楼机",
    "爬楼机": "爬楼机",
    "登阶机/爬楼机": "爬楼机",
    "登阶机": "爬楼机",
    "stepmill": "爬楼机",
    "stair_climber": "爬楼机",
    "椭圆机": "椭圆机",
    "elliptical": "椭圆机",
    "smith_bench_press": "史密斯卧推",
    "史密斯卧推": "史密斯卧推",
    "上斜史密斯卧推": "史密斯卧推",
    "史密斯上斜卧推": "史密斯卧推",
    "barbell_bench_press": "杠铃卧推",
    "dumbbell_bench_press": "哑铃卧推",
    "哑铃卧推": "哑铃卧推",
    "水平哑铃卧推": "哑铃卧推",
    "上斜 30 度哑铃卧推": "哑铃卧推",
    "上斜哑铃卧推": "哑铃卧推",
    "cable_chest_fly": "夹胸",
    "chest_fly": "夹胸",
    "绳索夹胸": "夹胸",
    "蝴蝶机夹胸": "夹胸",
    "夹胸": "夹胸",
    "固定器械推胸": "推胸",
    "machine_chest_press": "推胸",
    "barbell_squat": "杠铃深蹲",
    "杠铃深蹲": "杠铃深蹲",
    "smith_squat": "史密斯深蹲",
    "史密斯深蹲": "史密斯深蹲",
    "dumbbell_squat": "哑铃深蹲",
    "哑铃深蹲": "哑铃深蹲",
    "leg_press": "倒蹬机",
    "腿举": "倒蹬机",
    "倒蹬机": "倒蹬机",
    "坐姿腿屈伸": "坐姿腿屈伸",
    "leg_extension": "坐姿腿屈伸",
    "杠铃弯举": "杠铃弯举",
    "barbell_curl": "杠铃弯举",
    "哑铃弯举": "哑铃弯举",
    "dumbbell_curl": "哑铃弯举",
    "绳索锤式弯举": "绳索锤式弯举",
    "绳索弯举": "绳索锤式弯举",
    "cable_curl": "绳索锤式弯举",
    "dumbbell_lateral_raise": "哑铃侧举",
    "哑铃侧平举": "哑铃侧举",
    "绳索侧平举": "绳索侧举",
    "dumbbell_romanian_deadlift": "哑铃罗马尼亚硬拉",
    "哑铃罗马尼亚硬拉": "哑铃罗马尼亚硬拉",
    "拉伸/跑步机": "拉伸/跑步机",
}


def normalize(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return ALIASES.get(text, text)


def load_corrected_gt(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = {}
    for row in data.get("rows", []):
        image_path = row.get("graph_image_path")
        label = row.get("corrected_ground_truth_label")
        if image_path and label:
            rows[image_path] = row
    return rows


def compare(predictions_path: Path, gt_path: Path) -> dict:
    pred_data = json.loads(predictions_path.read_text(encoding="utf-8"))
    gt_by_path = load_corrected_gt(gt_path)
    rows = []
    by_folder: dict[str, Counter] = defaultdict(Counter)

    for pred in pred_data.get("results", []):
        image_path = pred.get("image_path", "")
        gt = gt_by_path.get(image_path)
        if not gt:
            continue
        gt_label = gt.get("corrected_ground_truth_label")
        pred_exercise = pred.get("selected_exercise")
        norm_gt = normalize(gt_label)
        norm_pred = normalize(pred_exercise)
        status = "match" if norm_gt == norm_pred else "mismatch"
        if "error" in pred:
            status = "api_error"
        folder = gt.get("folder") or pred.get("user_folder")
        by_folder[folder]["total"] += 1
        by_folder[folder][status] += 1
        rows.append(
            {
                "folder": folder,
                "action_id": gt.get("action_id") or pred.get("action_id"),
                "image_path": image_path,
                "ground_truth": gt_label,
                "prediction": pred_exercise,
                "prediction_equipment": pred.get("selected_equipment"),
                "confidence": pred.get("selected_confidence"),
                "prediction_policy": pred.get("confidence_policy"),
                "normalized_ground_truth": norm_gt,
                "normalized_prediction": norm_pred,
                "status": status,
                "correction_status": gt.get("correction_status"),
                "top_candidates": pred.get("top_candidates", []),
                "context": pred.get("context", {}),
                "sets": pred.get("sets"),
                "total_sets": pred.get("total_sets"),
                "total_reps": pred.get("total_reps"),
                "error": pred.get("error"),
            }
        )

    rows.sort(key=lambda r: (str(r["folder"]), int(str(r["action_id"]).replace("动作", "") or 9999)))
    summary = Counter(row["status"] for row in rows)
    return {
        "created_at": datetime.now().isoformat(),
        "prompt_mode": pred_data.get("prompt_mode"),
        "predictions_path": predictions_path.as_posix(),
        "ground_truth_path": gt_path.as_posix(),
        "total_evaluated": len(rows),
        "matches": summary["match"],
        "mismatches": summary["mismatch"],
        "api_errors": summary["api_error"],
        "by_folder": {folder: dict(counter) for folder, counter in sorted(by_folder.items())},
        "rows": rows,
    }


def write_markdown(payload: dict, path: Path) -> None:
    lines = [
        "# Image Main Focus Prediction Comparison",
        "",
        f"Prompt mode: `{payload.get('prompt_mode')}`",
        f"Total evaluated: {payload['total_evaluated']}",
        f"Matches: {payload['matches']}",
        f"Mismatches: {payload['mismatches']}",
        f"API errors: {payload['api_errors']}",
        "",
        "## By Folder",
        "",
        "| folder | total | match | mismatch | api_error |",
        "|---|---:|---:|---:|---:|",
    ]
    for folder, stats in payload["by_folder"].items():
        lines.append(
            f"| {folder} | {stats.get('total', 0)} | {stats.get('match', 0)} | {stats.get('mismatch', 0)} | {stats.get('api_error', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| folder | action | ground truth | prediction | conf | normalized GT | normalized pred | status |",
            "|---|---|---|---|---:|---|---|---|",
        ]
    )
    for row in payload["rows"]:
        pred = row.get("prediction") or row.get("error") or ""
        equip = row.get("prediction_equipment")
        if equip and row.get("prediction"):
            pred = f"{equip} / {pred}"
        lines.append(
            "| {folder} | {action} | {gt} | {pred} | {conf} | {ngt} | {npred} | {status} |".format(
                folder=row.get("folder", ""),
                action=row.get("action_id", ""),
                gt=str(row.get("ground_truth", "")).replace("|", "\\|"),
                pred=str(pred).replace("|", "\\|"),
                conf=row.get("confidence") if row.get("confidence") is not None else "",
                ngt=row.get("normalized_ground_truth", ""),
                npred=row.get("normalized_prediction", ""),
                status=row.get("status", ""),
            )
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument(
        "--ground-truth",
        default="graph_workflow_validation/ground_truth_alignment/corrected_ground_truth_by_graph.json",
    )
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args()

    payload = compare(Path(args.predictions), Path(args.ground_truth))
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload, Path(args.out_md))
    print(args.out_json)
    print(args.out_md)
    print(f"total={payload['total_evaluated']} match={payload['matches']} mismatch={payload['mismatches']} api_error={payload['api_errors']}")


if __name__ == "__main__":
    main()
