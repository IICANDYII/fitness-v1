from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ACTION_RE = re.compile(r"动作(\d+)")


MANUAL_CORRECTIONS: dict[str, dict[int, dict[str, str | bool]]] = {
    "3": {
        1: {"label": "史密斯卧推"},
        2: {"label": "史密斯卧推"},
        5: {"label": "哑铃卧推"},
        6: {"label": "哑铃卧推"},
        10: {"label": "绳索下拉"},
        11: {"label": "绳索下拉"},
    },
    "4": {
        3: {"label": "反握器械高位下拉"},
        4: {"label": "反握器械高位下拉"},
        5: {"label": "绳索锤式弯举"},
        6: {"label": "绳索锤式弯举"},
        7: {"label": "杠铃弯举"},
        8: {"label": "杠铃弯举"},
        9: {"label": "哑铃弯举"},
        10: {"label": "哑铃弯举"},
    },
    "8": {
        4: {"label": "史密斯卧推"},
        5: {"label": "史密斯卧推"},
        8: {"label": "划船"},
        9: {"label": "夹胸"},
    },
    "健身-高孟琦": {
        1: {"label": "哑铃深蹲"},
        2: {"label": "高位直杆下拉"},
        3: {"label": "绳索下压"},
    },
    "肩-秦紫渝": {
        4: {"label": "单臂绳索下拉"},
        5: {"label": "单臂绳索下拉"},
    },
    "肩-背-秦紫渝": {
        4: {"label": "绳索划船"},
        5: {"label": "拉伸/跑步机"},
    },
    "肩背-叶翔": {
        2: {"label": "直杆高位下拉"},
        3: {"label": "直杆高位下拉"},
        4: {"label": "直杆高位下拉"},
        5: {"label": "直杆高位下拉"},
        6: {"label": "绳索面拉"},
        7: {"label": "绳索面拉"},
        8: {"label": "绳索面拉"},
        9: {"label": "绳索面拉"},
        10: {"label": "坐姿划船"},
        11: {"label": "坐姿划船"},
    },
    "腿-张开": {
        1: {"label": "跑步机"},
        2: {"label": "杠铃深蹲"},
        3: {"label": "杠铃深蹲"},
        4: {"label": "杠铃深蹲"},
        5: {"label": "坐姿腿屈伸"},
        6: {"label": "未知动作"},
        7: {"label": "倒蹬机"},
        8: {"label": "未知动作"},
    },
}


def action_num(path: Path) -> int:
    match = ACTION_RE.search(path.stem)
    return int(match.group(1)) if match else 9999


def load_predictions(project_root: Path) -> dict[str, dict]:
    path = project_root / "graph_workflow_validation" / "results" / "graph_action_predictions.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item.get("image_path", ""): item for item in data.get("results", [])}


def load_base_alignment(project_root: Path) -> dict[str, dict]:
    """Use the merged alignment as the base; manual corrections override it."""
    path = (
        project_root
        / "graph_workflow_validation"
        / "ground_truth_alignment"
        / "ground_truth_alignment.json"
    )
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    base: dict[str, dict] = {}
    for row in data.get("rows", []):
        label = row.get("ground_truth_label")
        if not label:
            continue
        for image_path in row.get("graph_image_paths", []):
            base[image_path] = {
                "label": label,
                "source": "base_ground_truth_alignment",
                "alignment_status": row.get("alignment_status"),
                "graph_action_id": row.get("graph_action_id"),
            }
    return base


def build_rows(project_root: Path) -> list[dict]:
    predictions = load_predictions(project_root)
    base_alignment = load_base_alignment(project_root)
    rows: list[dict] = []
    for folder, corrections in MANUAL_CORRECTIONS.items():
        graph_dir = project_root / "graph" / folder
        seen_actions = set()
        for img in sorted(graph_dir.glob("*.jpg"), key=action_num):
            num = action_num(img)
            seen_actions.add(num)
            rel_path = img.relative_to(project_root).as_posix()
            correction = corrections.get(num)
            pred = predictions.get(rel_path, {})
            if correction is None:
                base = base_alignment.get(rel_path, {})
                label = base.get("label")
                status = (
                    "base_ground_truth_kept"
                    if label
                    else "no_ground_truth_after_base_alignment"
                )
            elif correction.get("deleted"):
                label = None
                status = "deleted_by_user"
            else:
                label = correction.get("label")
                status = "corrected_by_user"
            rows.append(
                {
                    "folder": folder,
                    "action_id": img.stem,
                    "action_number": num,
                    "graph_image_path": rel_path,
                    "corrected_ground_truth_label": label,
                    "correction_status": status,
                    "prediction_equipment": pred.get("selected_equipment"),
                    "prediction_exercise": pred.get("selected_exercise"),
                    "prediction_confidence": pred.get("selected_confidence"),
                    "prediction_policy": pred.get("confidence_policy"),
                }
            )
        for num, correction in sorted(corrections.items()):
            if num in seen_actions:
                continue
            rows.append(
                {
                    "folder": folder,
                    "action_id": f"动作{num}",
                    "action_number": num,
                    "graph_image_path": None,
                    "corrected_ground_truth_label": correction.get("label"),
                    "correction_status": (
                        "deleted_by_user"
                        if correction.get("deleted")
                        else "corrected_by_user_missing_image"
                    ),
                    "prediction_equipment": None,
                    "prediction_exercise": None,
                    "prediction_confidence": None,
                    "prediction_policy": None,
                }
            )
    return rows


def group_rows(rows: list[dict]) -> list[dict]:
    grouped: list[dict] = []
    by_folder: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_folder[row["folder"]].append(row)

    for folder, folder_rows in by_folder.items():
        current = None
        for row in sorted(folder_rows, key=lambda r: r["action_number"]):
            key = (row["corrected_ground_truth_label"], row["correction_status"])
            if current and current["key"] == key:
                current["action_ids"].append(row["action_id"])
                current["graph_image_paths"].append(row["graph_image_path"])
                current["predictions"].append(
                    {
                        "exercise": row.get("prediction_exercise"),
                        "confidence": row.get("prediction_confidence"),
                    }
                )
            else:
                if current:
                    grouped.append(current)
                current = {
                    "folder": folder,
                    "key": key,
                    "action_ids": [row["action_id"]],
                    "graph_image_paths": [row["graph_image_path"]],
                    "corrected_ground_truth_label": row["corrected_ground_truth_label"],
                    "correction_status": row["correction_status"],
                    "predictions": [
                        {
                            "exercise": row.get("prediction_exercise"),
                            "confidence": row.get("prediction_confidence"),
                        }
                    ],
                }
        if current:
            grouped.append(current)

    for item in grouped:
        item.pop("key", None)
    return grouped


def write_markdown(rows: list[dict], groups: list[dict], path: Path) -> None:
    lines = [
        "# Corrected Ground Truth By Graph Image",
        "",
        "这份文件按用户人工审阅结果修正 ground truth。人工提到的图覆盖原标注；未提到的图沿用原始/合并后的 ground truth 对齐结果；明确删除的图才标记为 `deleted_by_user`。",
        "",
        "## Grouped View",
        "",
        "| folder | graph actions | corrected ground truth | status | model predictions |",
        "|---|---|---|---|---|",
    ]
    for item in groups:
        preds = []
        for pred in item["predictions"]:
            ex = pred.get("exercise") or ""
            conf = pred.get("confidence")
            preds.append(f"{ex}({conf})" if conf is not None else ex)
        lines.append(
            "| {folder} | {actions} | {gt} | {status} | {preds} |".format(
                folder=item["folder"],
                actions="+".join(item["action_ids"]),
                gt=item.get("corrected_ground_truth_label") or "",
                status=item["correction_status"],
                preds="<br>".join(preds),
            )
        )

    lines.extend(
        [
            "",
            "## Action-Level View",
            "",
            "| folder | action | corrected ground truth | status | prediction | conf |",
            "|---|---|---|---|---|---:|",
        ]
    )
    for row in rows:
        pred = row.get("prediction_exercise") or ""
        if row.get("prediction_equipment"):
            pred = f"{row['prediction_equipment']} / {pred}"
        lines.append(
            "| {folder} | {action} | {gt} | {status} | {pred} | {conf} |".format(
                folder=row["folder"],
                action=row["action_id"],
                gt=row.get("corrected_ground_truth_label") or "",
                status=row["correction_status"],
                pred=pred.replace("|", "\\|"),
                conf=row.get("prediction_confidence")
                if row.get("prediction_confidence") is not None
                else "",
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_dir = project_root / "graph_workflow_validation" / "ground_truth_alignment"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows(project_root)
    groups = group_rows(rows)
    payload = {
        "created_at": datetime.now().isoformat(),
        "note": "Manual corrected ground truth from user review. Original shared ground_truth.json files are not modified.",
        "manual_corrections": MANUAL_CORRECTIONS,
        "rows": rows,
        "groups": groups,
    }
    (out_dir / "corrected_ground_truth_by_graph.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(rows, groups, out_dir / "corrected_ground_truth_by_graph.md")
    print(out_dir / "corrected_ground_truth_by_graph.json")
    print(out_dir / "corrected_ground_truth_by_graph.md")


if __name__ == "__main__":
    main()
