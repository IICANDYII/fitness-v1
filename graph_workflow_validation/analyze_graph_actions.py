from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gym_analyzer.recognizer import (
    _build_standard_names_prompt,
    _gemini_generate,
    _image_to_data_url,
    _recognize_one_exercise,
)
from gym_analyzer.yaml_loader import load_prompts


ACTION_RE = re.compile(r"动作(\d+)")


def natural_key(path: Path) -> tuple[str, int, str]:
    match = ACTION_RE.search(path.stem)
    idx = int(match.group(1)) if match else 9999
    return (path.parent.name, idx, path.name)


def load_image_bytes(path: Path) -> bytes:
    return path.read_bytes()


def extract_validation_json(text: str) -> dict:
    """Extract the graph-validation JSON when the model also emits pipeline-style JSON."""
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    objects = []
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            objects.append(obj)

    for obj in reversed(objects):
        if "selected_exercise" in obj or "top_candidates" in obj:
            return obj
    for obj in reversed(objects):
        if "exercise" in obj and ("equipment" in obj or "confidence" in obj):
            return obj
    if objects:
        return objects[-1]
    raise ValueError(f"无法解析 JSON：\n{text[:500]}")


def normalize_result(data: dict, image_path: Path, raw_path: Path | None = None) -> dict:
    data = dict(data)
    data.setdefault("user_folder", image_path.parent.name)
    data.setdefault("action_id", image_path.stem)
    data.setdefault("image_path", image_path.as_posix())

    if "selected_exercise" not in data and "exercise" in data:
        data["selected_exercise"] = data.get("exercise")
    if "selected_equipment" not in data and "equipment" in data:
        data["selected_equipment"] = data.get("equipment")
    if "selected_confidence" not in data and "confidence" in data:
        data["selected_confidence"] = data.get("confidence")

    if "confidence_policy" not in data:
        try:
            conf = float(data.get("selected_confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        candidates = data.get("top_candidates")
        if isinstance(candidates, list) and len(candidates) > 1 and conf <= 0.7:
            data["confidence_policy"] = "multiple_close"
        elif conf < 0.5:
            data["confidence_policy"] = "insufficient_evidence"
        else:
            data["confidence_policy"] = "single_clear"

    if "top_candidates" not in data:
        data["top_candidates"] = [
            {
                "equipment": data.get("selected_equipment", "UNKNOWN_EQUIPMENT"),
                "exercise": data.get("selected_exercise", "UNKNOWN_ACTION"),
                "confidence": data.get("selected_confidence", 0),
                "support": "主流水线原生 JSON 输出，未单独提供验证 schema support 字段",
            }
        ]

    data.setdefault("context", {})
    data.setdefault("action_disambiguation", {})
    data.setdefault("needs_manual_review", True)
    if raw_path is not None:
        data["raw_response_path"] = raw_path.as_posix()
    return data


def is_complete_result(item: dict) -> bool:
    return bool(
        item
        and "error" not in item
        and item.get("selected_exercise")
        and item.get("selected_equipment")
        and item.get("selected_confidence") is not None
    )


def build_user_text(
    image_path: Path,
    prompt_source: str,
    main_pipeline_prompt_source: str,
    prompt_mode: str,
    yaml_user_prompt: str,
) -> str:
    user = image_path.parent.name
    action_id = image_path.stem
    if prompt_mode == "full-pipeline":
        prompt_context = f"""
主流水线一致性要求：
- 下面附上 gym_analyzer/recognizer.py 中主流水线 Phase 2 `_recognize_one_exercise` 的当前 prompt 构造源码。
- 你必须严格按这段主流水线 Phase 2 规则口径判断动作，包括器械优先、龙门架/高位下拉/胸部器械/有氧器械/易混动作规则。
- 本轮 graph 输入缺少主流水线通常会提供的 Phase 1、光流、IMU 和入场帧原图；这些缺失只能用于降低置信度，不能改写主流水线规则。

主流水线 Phase 2 prompt 构造源码：
```python
{main_pipeline_prompt_source}
```
""".strip()
    elif prompt_mode == "image-main-focus":
        prompt_context = """
主流水线图片验证口径：
- 这一步模拟 Phase 1 已切出一个 EXERCISE 片段后，对每一段运动单独调用一次 AI 识别。
- 本轮 graph 只有抽帧拼图，没有真实光流、IMU、Phase 1 equipment/posture、入场帧原图和时间戳；请跳过所有依赖光流/IMU/Phase 1 参考值的硬约束，不要因为缺失这些信息而强行改判。
- 仍然保持主流水线 Phase 2 的核心输出目标：判断当前用户本人的器械、动作、动作方向、分了几组、每组几次，并给出后处理所需的置信度、候选动作和上下文。
- 器械优先：先识别用户正在接触/操作的器械，再判断动作；不要只根据一个局部视觉印象套动作名。
- 第一人称胸前相机：只关注佩戴者本人；镜子、远处别人、旁边器械只能作为环境信息，不能替代当前用户动作。
- 同一拼图内如果器械、姿态、动作方向连续一致，应视为同一个动作片段；若像多组训练，只输出 sets/rest_periods 或在 notes 中说明，不要把前半段和后半段识别成不同动作。
- 对容易混淆的动作必须保留接近候选：高位下拉/绳索下压/面拉/绳索锤式弯举，推胸/夹胸/卧推，杠铃深蹲/史密斯深蹲，有氧器械之间。
- 只能从拼图目测次数和组数；看不清则 total_sets/total_reps 用 null，不要编造精确数字。
""".strip()
    else:
        prompt_context = f"""
主要 YAML prompt 的 user 说明如下。本轮只按这个主要 prompt 的口径识别，不注入 recognizer.py 动态长规则：
```text
{yaml_user_prompt}
```
""".strip()

    return f"""
以下是一张已经抽帧并拼接好的关键帧网格图，来自 graph 文件夹中的一个用户动作片段。

图像信息：
- user_folder: {user}
- action_id: {action_id}
- image_path: {image_path.as_posix()}
- 网格读取顺序：从左到右、从上到下
- 本轮没有额外的 Phase 1、光流、IMU、入场帧原图；请只根据这张拼图中的视觉证据判断。
- 使用当前动作识别 prompt 的判别原则，尤其注意第一人称胸前相机、忽略其他人、器械优先、易混动作候选与置信度。
- prompt_source: {prompt_source}
- prompt_mode: {prompt_mode}

{prompt_context}

置信度输出规则：
- 如果存在一个候选动作的证据显著高于其他候选：selected_exercise 输出该动作，selected_confidence 可高于 0.70。
- 如果若干候选证据接近：selected_exercise 输出最可能的一个，但 top_candidates 必须保留所有接近候选；selected_confidence 不要超过 0.70。
- 如果只能确定大类或器械，不能确定具体动作：selected_exercise 填 UNKNOWN_ACTION，并在 top_candidates 中给出具体候选。
- 如果无法确定器械：selected_equipment 填 UNKNOWN_EQUIPMENT。
- 置信度必须反映“只看拼图、缺少光流/IMU/Phase1”的不确定性，不要虚高。

请严格输出 JSON，不要 Markdown，不要额外解释。格式：
{{
  "user_folder": "{user}",
  "action_id": "{action_id}",
  "image_path": "{image_path.as_posix()}",
  "selected_equipment": "器械名或UNKNOWN_EQUIPMENT",
  "selected_exercise": "动作名或UNKNOWN_ACTION",
  "selected_confidence": 0.0,
  "confidence_policy": "single_clear|multiple_close|insufficient_evidence",
  "top_candidates": [
    {{
      "equipment": "器械名",
      "exercise": "动作名",
      "confidence": 0.0,
      "support": "可观察证据，简短说明"
    }}
  ],
  "context": {{
    "visible_equipment": ["画面中可见的器械/结构"],
    "body_posture": "standing|seated|supine|prone|bending|unknown",
    "motion_cues_from_grid": "从连续帧中能观察到的运动方向/身体或器械变化；若不明显请说明",
    "movement_direction": "up_down|left_right|forward_backward|mixed|unknown",
    "first_person_subject_evidence": "哪些证据表明这是佩戴者本人动作，或为什么不确定",
    "uncertainty_notes": "缺失光流/IMU/Phase1导致的不确定点"
  }},
  "sets": [
    {{"set_number": 1, "reps": null, "evidence": "只能根据拼图目测；看不清则写null"}}
  ],
  "total_sets": null,
  "total_reps": null,
  "action_disambiguation": {{
    "selected_evidence": "支持主判定的关键证据",
    "rejected_or_close_candidates": [
      {{"exercise": "候选动作", "reason": "为什么被排除或为什么仍接近"}}
    ]
  }},
  "needs_manual_review": true
}}

{_build_standard_names_prompt()}
""".strip()


def analyze_one(
    image_path: Path,
    system_prompt: str,
    prompt_source: str,
    main_pipeline_prompt_source: str,
    prompt_mode: str,
    yaml_user_prompt: str,
    raw_dir: Path,
) -> dict:
    content = [
        {
            "type": "text",
            "text": build_user_text(
                image_path,
                prompt_source,
                main_pipeline_prompt_source,
                prompt_mode,
                yaml_user_prompt,
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": _image_to_data_url(load_image_bytes(image_path))},
        },
    ]
    raw = _gemini_generate(system_prompt, content)
    raw_path = raw_dir / image_path.parent.name / f"{image_path.stem}.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw, encoding="utf-8")
    data = extract_validation_json(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object for {image_path}, got {type(data).__name__}")
    return normalize_result(data, image_path, raw_path)


def write_markdown(results: list[dict], path: Path) -> None:
    lines = [
        "# Graph Action Recognition Round 1",
        "",
        "| user | action | selected | conf | policy | top candidates | notes |",
        "|---|---:|---|---:|---|---|---|",
    ]
    for item in results:
        candidates = []
        for c in item.get("top_candidates", [])[:4]:
            ex = c.get("exercise", "?")
            conf = c.get("confidence", "?")
            candidates.append(f"{ex}({conf})")
        context = item.get("context", {}) if isinstance(item.get("context"), dict) else {}
        notes = context.get("uncertainty_notes", "")
        lines.append(
            "| {user} | {action} | {equip} / {exercise} | {conf} | {policy} | {cands} | {notes} |".format(
                user=item.get("user_folder", ""),
                action=item.get("action_id", ""),
                equip=item.get("selected_equipment", ""),
                exercise=item.get("selected_exercise", ""),
                conf=item.get("selected_confidence", ""),
                policy=item.get("confidence_policy", ""),
                cands="<br>".join(candidates),
                notes=str(notes).replace("|", "\\|"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze graph action collage images with the current Phase 2 prompt.")
    parser.add_argument("--graph-dir", default="graph")
    parser.add_argument("--prompts-dir", default="gym_analyzer/prompts")
    parser.add_argument("--out-dir", default="graph_workflow_validation/results")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--prompt-mode",
        choices=["full-pipeline", "yaml-only", "image-main-focus"],
        default="full-pipeline",
        help="full-pipeline injects recognizer.py prompt builder; yaml-only uses only the YAML prompt; image-main-focus keeps Phase 2 image-recognition duties but skips unavailable flow/IMU constraints.",
    )
    parser.add_argument(
        "--only-mismatches-from",
        default=None,
        help="Comparison JSON path; when set, only rows with status=mismatch are analyzed.",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = PROJECT_ROOT
    load_dotenv(root / ".env")

    graph_dir = Path(args.graph_dir)
    out_dir = Path(args.out_dir)
    raw_dir = out_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    _, phase2_prompt = load_prompts(args.prompts_dir)
    system_prompt = phase2_prompt.system
    yaml_user_prompt = phase2_prompt.user
    prompt_source = Path(phase2_prompt.source_file).name
    main_pipeline_prompt_source = inspect.getsource(_recognize_one_exercise)

    snapshot_dir = out_dir / "prompt_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / prompt_source).write_text(Path(phase2_prompt.source_file).read_text(encoding="utf-8"), encoding="utf-8")
    (snapshot_dir / "recognizer_phase2_prompt_builder.py").write_text(main_pipeline_prompt_source, encoding="utf-8")

    image_paths = sorted(graph_dir.glob("*/*.jpg"), key=natural_key)
    if args.only_mismatches_from:
        comparison_path = Path(args.only_mismatches_from)
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        wanted = {
            (row.get("folder"), row.get("action_id"))
            for row in comparison.get("rows", [])
            if row.get("status") == "mismatch"
        }
        image_paths = [
            p for p in image_paths
            if (p.parent.name, p.stem) in wanted
        ]
    if args.limit is not None:
        image_paths = image_paths[: args.limit]

    result_path = out_dir / "graph_action_predictions.json"
    existing: dict[str, dict] = {}
    if result_path.exists() and not args.overwrite:
        prev = json.loads(result_path.read_text(encoding="utf-8"))
        for item in prev.get("results", []):
            existing[item.get("image_path", "")] = item

    results_by_path: dict[str, dict] = {}
    pending: list[Path] = []
    for idx, image_path in enumerate(image_paths, 1):
        key = image_path.as_posix()
        if key in existing and is_complete_result(existing[key]):
            print(f"[{idx}/{len(image_paths)}] cache {key}")
            results_by_path[key] = existing[key]
            continue
        pending.append(image_path)

    def save_progress() -> None:
        ordered = [results_by_path[p.as_posix()] for p in image_paths if p.as_posix() in results_by_path]
        payload = {
            "created_at": datetime.now().isoformat(),
            "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
            "prompt_source": prompt_source,
            "prompt_mode": args.prompt_mode,
            "graph_dir": graph_dir.as_posix(),
            "workers": args.workers,
            "results": ordered,
        }
        result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        write_markdown(ordered, out_dir / "graph_action_predictions.md")

    if pending:
        print(f"Pending: {len(pending)} / {len(image_paths)} images, workers={args.workers}")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {}
        for image_path in pending:
            key = image_path.as_posix()
            print(f"submit {key}")
            future = executor.submit(
                analyze_one,
                image_path,
                system_prompt,
                prompt_source,
                main_pipeline_prompt_source,
                args.prompt_mode,
                yaml_user_prompt,
                raw_dir,
            )
            future_map[future] = image_path

        completed = 0
        for future in as_completed(future_map):
            image_path = future_map[future]
            key = image_path.as_posix()
            completed += 1
            try:
                item = future.result()
                print(f"[{completed}/{len(pending)}] done {key} -> {item.get('selected_exercise')} conf={item.get('selected_confidence')}")
            except Exception as exc:
                item = {
                    "user_folder": image_path.parent.name,
                    "action_id": image_path.stem,
                    "image_path": key,
                    "error": str(exc),
                    "needs_manual_review": True,
                }
                print(f"[{completed}/{len(pending)}] error {key}: {exc}")
            results_by_path[key] = item
            save_progress()

    save_progress()

    print(f"Saved {result_path}")
    print(f"Saved {out_dir / 'graph_action_predictions.md'}")


if __name__ == "__main__":
    main()
