from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


ACTION_RE = re.compile(r"动作(\d+)")


def natural_action_key(path: Path) -> tuple[str, int, str]:
    match = ACTION_RE.search(path.stem)
    idx = int(match.group(1)) if match else 9999
    return (path.parent.name, idx, path.name)


def action_index(path: Path) -> int | None:
    match = ACTION_RE.search(path.stem)
    return int(match.group(1)) if match else None


def load_predictions(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item.get("image_path", ""): item for item in data.get("results", [])}


def should_merge(prev: dict, curr: dict, threshold: float) -> bool:
    prev_pred = prev.get("prediction", {})
    curr_pred = curr.get("prediction", {})
    prev_ex = prev_pred.get("selected_exercise")
    curr_ex = curr_pred.get("selected_exercise")
    if not prev_ex or not curr_ex:
        return False
    if prev_ex in {"UNKNOWN_ACTION", "UNKNOWN_EXERCISE"}:
        return False
    if prev_ex != curr_ex:
        return False
    try:
        prev_conf = float(prev_pred.get("selected_confidence", 0))
        curr_conf = float(curr_pred.get("selected_confidence", 0))
    except (TypeError, ValueError):
        return False
    return prev_conf >= threshold and curr_conf >= threshold


def group_graph_actions(
    graph_paths: list[Path],
    predictions: dict[str, dict],
    project_root: Path,
    merge_confidence_threshold: float,
) -> list[dict]:
    groups: list[dict] = []
    for graph_path in graph_paths:
        rel_path = graph_path.relative_to(project_root).as_posix()
        pred = predictions.get(rel_path, {})
        item = {
            "graph_action_ids": [graph_path.stem],
            "graph_image_paths": [rel_path],
            "prediction": pred,
            "merge_reason": None,
        }
        if groups and should_merge(groups[-1], item, merge_confidence_threshold):
            groups[-1]["graph_action_ids"].append(graph_path.stem)
            groups[-1]["graph_image_paths"].append(rel_path)
            groups[-1]["merge_reason"] = (
                f"adjacent_same_prediction_conf>={merge_confidence_threshold}"
            )
            # Keep the most conservative confidence for the merged group.
            prev_pred = groups[-1]["prediction"]
            try:
                prev_conf = float(prev_pred.get("selected_confidence", 0))
                curr_conf = float(pred.get("selected_confidence", 0))
                if curr_conf < prev_conf:
                    groups[-1]["prediction"] = pred
            except (TypeError, ValueError):
                pass
        else:
            groups.append(item)
    return groups


def build_alignment(project_root: Path, merge_confidence_threshold: float = 0.8) -> dict:
    shared_dir = project_root / "shared"
    graph_dir = project_root / "graph"
    results_dir = project_root / "graph_workflow_validation" / "results"
    predictions = load_predictions(results_dir / "graph_action_predictions.json")

    folders = sorted(
        [p.parent.name for p in shared_dir.glob("*/ground_truth.json")],
        key=lambda x: (x.encode("utf-8")),
    )

    rows = []
    folder_summaries = []
    for folder in folders:
        gt_path = shared_dir / folder / "ground_truth.json"
        graph_paths = sorted((graph_dir / folder).glob("*.jpg"), key=natural_action_key)

        raw_gt = json.loads(gt_path.read_text(encoding="utf-8"))
        exercises = [item for item in raw_gt if item.get("type") == "exercise"]
        raw_status = "ok" if len(exercises) == len(graph_paths) else "count_mismatch"
        if raw_status == "count_mismatch":
            graph_groups = group_graph_actions(
                graph_paths, predictions, project_root, merge_confidence_threshold
            )
        else:
            graph_groups = [
                {
                    "graph_action_ids": [p.stem],
                    "graph_image_paths": [p.relative_to(project_root).as_posix()],
                    "prediction": predictions.get(p.relative_to(project_root).as_posix(), {}),
                    "merge_reason": None,
                }
                for p in graph_paths
            ]
        max_len = max(len(exercises), len(graph_groups))
        status = "ok" if len(exercises) == len(graph_groups) else "count_mismatch"

        folder_summaries.append(
            {
                "folder": folder,
                "ground_truth_exercise_count": len(exercises),
                "raw_graph_action_count": len(graph_paths),
                "merged_graph_group_count": len(graph_groups),
                "raw_alignment_status": raw_status,
                "alignment_status": status,
                "merged_group_count_delta": len(graph_paths) - len(graph_groups),
            }
        )

        for i in range(max_len):
            gt = exercises[i] if i < len(exercises) else None
            graph_group = graph_groups[i] if i < len(graph_groups) else None
            pred = graph_group.get("prediction", {}) if graph_group else {}
            rows.append(
                {
                    "folder": folder,
                    "sequence_index": i + 1,
                    "alignment_status": status,
                    "raw_alignment_status": raw_status,
                    "graph_action_id": (
                        "+".join(graph_group["graph_action_ids"]) if graph_group else None
                    ),
                    "graph_action_ids": graph_group["graph_action_ids"] if graph_group else [],
                    "graph_image_paths": graph_group["graph_image_paths"] if graph_group else [],
                    "merge_reason": graph_group.get("merge_reason") if graph_group else None,
                    "ground_truth_label": gt.get("label") if gt else None,
                    "ground_truth_equipment": gt.get("equipment") if gt else None,
                    "ground_truth_reps": gt.get("reps") if gt else None,
                    "ground_truth_start": gt.get("start") if gt else None,
                    "ground_truth_end": gt.get("end") if gt else None,
                    "prediction_exercise": pred.get("selected_exercise"),
                    "prediction_equipment": pred.get("selected_equipment"),
                    "prediction_confidence": pred.get("selected_confidence"),
                    "prediction_policy": pred.get("confidence_policy"),
                    "prediction_error": pred.get("error"),
                    "notes": (
                        "ground_truth_extra_without_graph_group"
                        if gt and not graph_group
                        else "graph_image_extra_without_ground_truth"
                        if graph_group and not gt
                        else ""
                    ),
                }
            )

    return {
        "created_at": datetime.now().isoformat(),
        "source": {
            "ground_truth_dir": "shared/*/ground_truth.json",
            "graph_dir": "graph/*/动作N.jpg",
            "prediction_file": "graph_workflow_validation/results/graph_action_predictions.json",
        },
        "alignment_method": "Order-match type=exercise entries in each shared/<folder>/ground_truth.json to graph/<folder>/动作N.jpg by natural action number. Count mismatches are flagged and not silently corrected.",
        "merge_rule": {
            "enabled": True,
            "confidence_threshold": merge_confidence_threshold,
            "rule": "Before order alignment, merge adjacent graph actions when selected_exercise is identical and both confidences are >= threshold. UNKNOWN actions are never merged.",
        },
        "summary": {
            "folders": len(folder_summaries),
            "total_rows": len(rows),
            "status_counts": dict(Counter(item["alignment_status"] for item in folder_summaries)),
            "folder_summaries": folder_summaries,
        },
        "rows": rows,
    }


def write_markdown(data: dict, path: Path) -> None:
    lines = [
        "# Graph Ground Truth Alignment",
        "",
        "先把相邻且高置信、同预测动作的 graph 图片合并成一个 group，再按每个 `shared/<folder>/ground_truth.json` 中 `type=exercise` 的顺序对齐。数量不一致的 folder 标记为 `count_mismatch`。",
        "",
        "## Folder Summary",
        "",
        "| folder | ground truth exercises | raw graph actions | merged graph groups | raw status | merged status |",
        "|---|---:|---:|---:|---|---|",
    ]
    for item in data["summary"]["folder_summaries"]:
        lines.append(
            f"| {item['folder']} | {item['ground_truth_exercise_count']} | {item['raw_graph_action_count']} | {item['merged_graph_group_count']} | {item['raw_alignment_status']} | {item['alignment_status']} |"
        )

    lines.extend(
        [
            "",
            "## Row Alignment",
            "",
            "| folder | seq | graph group | ground truth | reps | prediction | conf | status | merge | notes |",
            "|---|---:|---|---|---|---|---:|---|---|---|",
        ]
    )
    for row in data["rows"]:
        pred = row.get("prediction_exercise") or ""
        if row.get("prediction_equipment"):
            pred = f"{row['prediction_equipment']} / {pred}"
        lines.append(
            "| {folder} | {seq} | {action} | {gt} | {reps} | {pred} | {conf} | {status} | {notes} |".format(
                folder=row["folder"],
                seq=row["sequence_index"],
                action=row.get("graph_action_id") or "",
                gt=row.get("ground_truth_label") or "",
                reps=row.get("ground_truth_reps") or "",
                pred=pred.replace("|", "\\|"),
                conf=row.get("prediction_confidence") if row.get("prediction_confidence") is not None else "",
                status=row["alignment_status"],
                merge=row.get("merge_reason") or "",
                notes=row.get("notes") or "",
            )
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_dir = project_root / "graph_workflow_validation" / "ground_truth_alignment"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_alignment(project_root)
    (out_dir / "ground_truth_alignment.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(data, out_dir / "ground_truth_alignment.md")
    print(f"wrote {out_dir / 'ground_truth_alignment.json'}")
    print(f"wrote {out_dir / 'ground_truth_alignment.md'}")


if __name__ == "__main__":
    main()
