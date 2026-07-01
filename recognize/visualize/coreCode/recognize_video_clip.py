"""
recognize_video_clip.py
-----------------------
视频片段直传 LLM 的两阶段识别脚本。

核心变化（相比 recognize_video.py）：
  Phase 2 不再将关键帧拼成网格图，而是直接从原始视频截取 EXERCISE 区间的
  视频片段，作为 video 类型参数传给 Gemini，由 LLM 直接观看视频识别动作。

用法:
  python recognize_video_clip.py <video_path> [--output OUTPUT_DIR]

  video_path   原始视频文件 (.mp4)
  --output     结果输出目录（默认 recognize/visualize/result/visual1）
"""

import argparse
import base64
import json
import os
import re
import sys
import threading
import time as time_module
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests
import yaml
from dotenv import load_dotenv

# ── 加载环境变量 ──
for _env in [
    Path(__file__).resolve().parents[3] / ".env",
    Path(__file__).resolve().parents[3] / "gym_analyzer" / ".env",
]:
    if _env.exists():
        load_dotenv(_env)
        break

# ── 路径 ──
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMPT_DIR = PROJECT_ROOT / "gym_analyzer" / "prompts"
EXERCISE_MAPPING_PATH = PROJECT_ROOT / "gym_analyzer" / "exercises_data" / "exercise_mapping_v1.json"

# ── LLM ──
NEXTROUTER_API_KEY = os.getenv("NEXTROUTER_API_KEY")
NEXTROUTER_BASE_URL = os.getenv("NEXTROUTER_BASE_URL", "https://nextrouter.cc")
GEMINI_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")

# ── 参数 ──
EXERCISE_BOUNDARY_PAD = 10       # Phase 2 视频片段前后扩展秒数
MAX_EXERCISE_WORKERS = 4
MAX_CLIP_DURATION = 300          # 单个片段最长 5 分钟
CLIP_MAX_SIZE_MB = 18            # 片段最大 18MB（Gemini 限制 20MB inline）

_print_lock = threading.Lock()


def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
# 标准动作名称映射
# ═══════════════════════════════════════════════════════════════

def _load_exercise_mapping() -> dict:
    if not EXERCISE_MAPPING_PATH.exists():
        return {}
    with open(EXERCISE_MAPPING_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

_EXERCISE_MAPPING: dict = _load_exercise_mapping()


def _build_standard_names_prompt() -> str:
    if not _EXERCISE_MAPPING:
        return ""
    lines = ["### 标准动作名称列表（你的输出必须从中选择）\n"]
    lines.append("| exercise_id | exercise（动作名称） | equipment（器械名称） | 训练部位 |")
    lines.append("|------------|---------------------|---------------------|---------|")
    for eid, info in _EXERCISE_MAPPING.items():
        ex_name = info.get("product_action_cn", "")
        equip = info.get("standard_equipment", "")
        part = info.get("training_part_cn", "")
        lines.append(f"| {eid} | {ex_name} | {equip} | {part} |")
    lines.append("")
    lines.append("**重要约束：**")
    lines.append("- `exercise` 字段必须填写上表中 exercise（动作名称）列的值")
    lines.append("- `exercise_id` 字段填写上表中对应的 exercise_id")
    lines.append("- `equipment` 字段用中文填写器械名称")
    lines.append("- 如果动作确实不在列表中，exercise 填 `UNKNOWN_ACTION`，exercise_id 填空字符串")
    lines.append("")
    return "\n".join(lines)


def _build_alias_map() -> dict[str, tuple[str, str]]:
    alias_map: dict[str, tuple[str, str]] = {}
    for eid, info in _EXERCISE_MAPPING.items():
        cn = info.get("product_action_cn", "")
        for name in cn.split("/"):
            name = name.strip()
            if name:
                alias_map[name] = (eid, cn)
        alias_map[cn] = (eid, cn)
        alias_map[eid] = (eid, cn)
    return alias_map

_ALIAS_MAP: dict[str, tuple[str, str]] = _build_alias_map()


def _normalize_exercise_name(exercise: str) -> tuple[str, str | None]:
    if not exercise or not _ALIAS_MAP:
        return exercise, None
    ex = exercise.strip()
    if ex in _ALIAS_MAP:
        eid, cn = _ALIAS_MAP[ex]
        return cn, eid
    for alias, (eid, cn) in _ALIAS_MAP.items():
        if alias in ex or ex in alias:
            return cn, eid
    return ex, None


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def secs_to_hhmmss(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def hhmmss_to_secs(t: str) -> float:
    parts = t.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


def extract_json(text: str):
    text = text.strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        text = "\n".join(inner).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    return json.loads(text)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tprint(f"  [OK] 已保存: {path}")


# ═══════════════════════════════════════════════════════════════
# 视频片段截取
# ═══════════════════════════════════════════════════════════════

def clip_video(video_path: Path, start_sec: float, end_sec: float, output_path: Path) -> bool:
    """使用 OpenCV 截取视频片段。若片段过大，降低分辨率。"""
    duration = end_sec - start_sec
    if duration <= 0:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        tprint(f"    [错误] 无法打开视频: {video_path}")
        return False

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 限制分辨率到 720p
    scale = min(720 / max(width, 1), 1.0)
    out_w = int(width * scale)
    out_h = int(height * scale)
    # 确保偶数（编码器要求）
    out_w = out_w - (out_w % 2)
    out_h = out_h - (out_h % 2)

    # 降帧率到 2fps 以减小文件体积
    target_fps = 2.0
    frame_interval = max(1, int(fps / target_fps))

    start_frame = int(start_sec * fps)
    end_frame = int(min(end_sec, start_sec + MAX_CLIP_DURATION) * fps)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, target_fps, (out_w, out_h))
    if not writer.isOpened():
        cap.release()
        tprint(f"    [错误] 无法创建输出视频")
        return False

    frame_idx = start_frame
    written = 0
    while frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        if (frame_idx - start_frame) % frame_interval == 0:
            if scale < 1.0:
                frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
            writer.write(frame)
            written += 1

        frame_idx += 1

    writer.release()
    cap.release()

    if written == 0:
        if output_path.exists():
            output_path.unlink()
        return False

    # 检查文件大小，若超限则进一步降采样
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    if file_size_mb > CLIP_MAX_SIZE_MB:
        tprint(f"    片段 {file_size_mb:.1f}MB 超过限制，降低分辨率和帧率重新编码...")
        cap2 = cv2.VideoCapture(str(video_path))
        scale2 = min(480 / max(width, 1), 1.0)
        out_w2 = int(width * scale2) - (int(width * scale2) % 2)
        out_h2 = int(height * scale2) - (int(height * scale2) % 2)
        frame_interval2 = max(1, int(fps / 1.0))  # 降到 1fps

        cap2.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        writer2 = cv2.VideoWriter(str(output_path), fourcc, 1.0, (out_w2, out_h2))

        frame_idx = start_frame
        while frame_idx < end_frame:
            ret, frame = cap2.read()
            if not ret:
                break
            if (frame_idx - start_frame) % frame_interval2 == 0:
                frame = cv2.resize(frame, (out_w2, out_h2), interpolation=cv2.INTER_AREA)
                writer2.write(frame)
            frame_idx += 1

        writer2.release()
        cap2.release()

    return output_path.exists() and output_path.stat().st_size > 0


def video_to_data_url(video_path: Path) -> str:
    with open(video_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    return f"data:video/mp4;base64,{b64}"


def image_to_data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()


# ═══════════════════════════════════════════════════════════════
# 光流计算（复用）
# ═══════════════════════════════════════════════════════════════

FLOW_RESIZE_W = 320
FLOW_RESIZE_H = 240
INTERVAL = 1.0


def _classify_direction(angle_deg: float) -> str:
    a = angle_deg % 360
    if 315 <= a or a < 45:
        return "RIGHT"
    if 45 <= a < 135:
        return "DOWN"
    if 135 <= a < 225:
        return "LEFT"
    return "UP"


def _intensity_label(avg: float) -> str:
    if avg < 1.0: return "极低"
    if avg < 3.0: return "低"
    if avg < 6.0: return "中"
    if avg < 10.0: return "高"
    return "极高"


def load_optical_flow(flow_path: Path) -> list[dict] | None:
    if not flow_path.exists():
        return None
    try:
        with open(flow_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("flow", []) if isinstance(data, dict) else None
    except Exception:
        return None


def format_flow_for_exercise(flow_data: list[dict], start_sec: float, end_sec: float) -> str:
    seg = [d for d in flow_data if start_sec - 0.5 <= d["time_sec"] <= end_sec + 0.5]
    if not seg:
        return "该区间无光流数据"

    lines = [f"=== 运动区间光流 [{start_sec:.0f}s-{end_sec:.0f}s] ==="]

    if len(seg) <= 40:
        for d in seg:
            lines.append(
                f"  t={d['time_sec']:.0f}s: flow={d['avg_flow']:.2f}, "
                f"方向={d['dominant_direction']}, 能量={d['motion_energy']:.2f}"
            )
    else:
        cs = 5
        for i in range(0, len(seg), cs):
            chunk = seg[i : i + cs]
            t_s = chunk[0]["time_sec"]
            t_e = chunk[-1]["time_sec"]
            avg = float(np.mean([d["avg_flow"] for d in chunk]))
            main_dir = Counter(d["dominant_direction"] for d in chunk).most_common(1)[0][0]
            lines.append(f"  [{t_s:.0f}s-{t_e:.0f}s]: avg_flow={avg:.2f}, 主方向={main_dir}")

    all_avg = float(np.mean([d["avg_flow"] for d in seg]))
    all_energy = float(np.mean([d["motion_energy"] for d in seg]))
    dir_dist = Counter(d["dominant_direction"] for d in seg)
    dir_str = ", ".join(f"{k}:{v}" for k, v in dir_dist.most_common())

    lines += [
        "",
        f"整体: avg_flow={all_avg:.2f}, avg_energy={all_energy:.2f}",
        f"方向分布: {dir_str}",
    ]

    dirs = [d["dominant_direction"] for d in seg]
    reversals = sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i - 1])
    if reversals > len(dirs) * 0.3:
        lines.append(f"运动模式: 频繁方向切换({reversals}次), 疑似往复运动")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def gemini_generate(system_prompt: str, user_content: list[dict], max_retries: int = 5) -> str:
    base_url = NEXTROUTER_BASE_URL.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"
    url = f"{base_url}/chat/completions"

    img_count = sum(1 for c in user_content if c.get("type") == "image_url")
    vid_count = sum(1 for c in user_content if c.get("type") == "video_url")
    tprint(f"  → LLM 请求: model={GEMINI_MODEL}, {img_count} 张图片, {vid_count} 个视频")

    payload = {
        "model": GEMINI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 16384,
    }
    headers = {
        "Authorization": f"Bearer {NEXTROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    session = requests.Session()
    session.trust_env = False

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=600)
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            wait = min(30 * attempt, 180)
            tprint(f"  [网络错误] {type(e).__name__}: {e}")
            if attempt < max_retries:
                tprint(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time_module.sleep(wait)
                continue
            raise

        if resp.status_code == 429:
            wait = 60 * attempt
            tprint(f"  [429] 等待 {wait}s 后重试（{attempt}/{max_retries}）...")
            time_module.sleep(wait)
            continue
        if resp.status_code >= 500:
            wait = min(30 * attempt, 180)
            tprint(f"  [HTTP {resp.status_code}] 服务端错误")
            if attempt < max_retries:
                tprint(f"  等待 {wait}s 后重试...")
                time_module.sleep(wait)
                continue
        if not resp.ok:
            tprint(f"  [HTTP {resp.status_code}] {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content or ""

    raise RuntimeError("超过最大重试次数")


# ═══════════════════════════════════════════════════════════════
# Phase 1：加载已有结果或运行
# ═══════════════════════════════════════════════════════════════

def load_or_run_phase1(
    video_path: Path,
    work_dir: Path,
    output_dir: Path,
) -> list[dict]:
    """
    尝试加载已有的 Phase 1 结果。
    优先从 output_dir 加载，其次从 work_dir 加载。
    如果都没有，则调用 pipeline 运行 Phase 1。
    """
    # 尝试加载：output_dir, work_dir, gym_analyzer/results/
    video_name = work_dir.name
    results_dir = PROJECT_ROOT / "gym_analyzer" / "results" / video_name
    for candidate in [
        output_dir / "period_result.json",
        work_dir / "period_result.json",
        results_dir / "period_result.json",
    ]:
        if candidate.exists():
            tprint(f"  Phase 1 使用缓存: {candidate}")
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            segments = data.get("segments", [])
            for seg in segments:
                if "start_time" in seg and "start_sec" not in seg:
                    seg["start_sec"] = hhmmss_to_secs(str(seg["start_time"]))
                if "end_time" in seg and "end_sec" not in seg:
                    seg["end_sec"] = hhmmss_to_secs(str(seg["end_time"]))
            return segments

    # 没有缓存，使用 pipeline 运行 Phase 1
    tprint("  未找到 Phase 1 缓存，使用 pipeline 运行...")
    sys.path.insert(0, str(PROJECT_ROOT))
    from gym_analyzer.pipeline import run_pipeline
    run_pipeline(work_dir=work_dir, output_dir=output_dir)

    result_path = output_dir / "period_result.json"
    if result_path.exists():
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        segments = data.get("segments", [])
        for seg in segments:
            if "start_time" in seg and "start_sec" not in seg:
                seg["start_sec"] = hhmmss_to_secs(str(seg["start_time"]))
            if "end_time" in seg and "end_sec" not in seg:
                seg["end_sec"] = hhmmss_to_secs(str(seg["end_time"]))
        return segments

    return []


# ═══════════════════════════════════════════════════════════════
# Phase 2：视频片段直传识别
# ═══════════════════════════════════════════════════════════════

def _load_phase2_prompt() -> dict:
    """加载 Phase 2 prompt (v11)。"""
    yaml_path = PROMPT_DIR / "phase2_exercise_recognize_v11.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Phase 2 prompt 文件不存在: {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _recognize_one_exercise_video(
    seg: dict,
    video_path: Path,
    flow_data: list[dict] | None,
    system_prompt: str,
    output_dir: Path,
    clips_dir: Path,
    total_dur: float,
) -> dict | None:
    """使用视频片段识别单个 EXERCISE 区间。"""
    seg_id = seg.get("segmentId", "?")
    t_start = seg.get("start_sec", 0.0)
    t_end = seg.get("end_sec", 0.0)
    dur = t_end - t_start

    tprint(f"\n  ── {seg_id}: {secs_to_hhmmss(t_start)} ~ {secs_to_hhmmss(t_end)} ({dur:.0f}s)")

    # 前后扩展
    pad_start = max(0.0, t_start - EXERCISE_BOUNDARY_PAD)
    pad_end = min(total_dur, t_end + EXERCISE_BOUNDARY_PAD)
    tprint(f"    [{seg_id}] 截取范围: {secs_to_hhmmss(pad_start)} ~ {secs_to_hhmmss(pad_end)}")

    # 截取视频片段
    clip_path = clips_dir / f"clip_{seg_id}.mp4"
    if not clip_video(video_path, pad_start, pad_end, clip_path):
        tprint(f"    [{seg_id}] [警告] 视频截取失败，跳过")
        return None

    clip_size_mb = clip_path.stat().st_size / (1024 * 1024)
    tprint(f"    [{seg_id}] 视频片段: {clip_size_mb:.1f}MB")

    # 光流摘要
    flow_summary = ""
    if flow_data:
        flow_summary = format_flow_for_exercise(flow_data, t_start, t_end)

    # Phase 1 上下文
    phase1_equipment = seg.get("equipment", "UNKNOWN")
    phase1_posture = seg.get("posture", "")
    phase1_reason = seg.get("reason", "")
    phase1_context = ""
    if phase1_reason or phase1_equipment != "UNKNOWN":
        phase1_lines = []
        if phase1_reason:
            phase1_lines.append(f"  描述: {phase1_reason}")
        if phase1_equipment and phase1_equipment != "UNKNOWN":
            phase1_lines.append(f"  器材预识别: {phase1_equipment}（请根据视频独立验证）")
        if phase1_posture:
            phase1_lines.append(f"  用户姿态: {phase1_posture}")
        equipment_features = seg.get("equipment_features", [])
        if equipment_features:
            phase1_lines.append(f"  器材特征: {', '.join(equipment_features)}")
        global_motion = seg.get("global_motion")
        if global_motion is not None:
            phase1_lines.append(f"  全局运动: {'是（身体整体运动）' if global_motion else '否（局部肢体运动）'}")
        cable_anchor = seg.get("cable_anchor")
        if cable_anchor:
            phase1_lines.append(f"  绳索挂点: {cable_anchor}")
        phase1_context = "- Phase 1 参考信息（需独立验证）:\n" + "\n".join(phase1_lines) + "\n"

    # 构造 user prompt
    user_text = (
        f"以下是一段 EXERCISE 区间 [{seg_id}] 的视频片段（第一人称胸前相机）：\n"
        f"- 时间范围: {secs_to_hhmmss(t_start)} ~ {secs_to_hhmmss(t_end)} (共 {dur:.0f}s)\n"
        f"- 视频截取范围（含前后缓冲）: {secs_to_hhmmss(pad_start)} ~ {secs_to_hhmmss(pad_end)}\n"
        f"{phase1_context}\n"
        f"---\n\n"
    )

    if flow_summary:
        user_text += f"{flow_summary}\n\n---\n\n"

    user_text += (
        f"请直接观看视频，按以下步骤分析：\n"
        f"Step 1 — 器械识别: 观察视频开头几秒（进场画面）和训练画面中用户接触的器械\n"
        f"Step 2 — 光流/运动验证: 结合光流摘要和视频中观察到的运动方向、幅度\n"
        f"Step 3 — 动作判定: 综合器械+运动模式判定具体动作\n"
        f"Step 4 — 组次统计: 观察视频中的重复运动次数和组间休息\n\n"
        f"关键约束：\n"
        f"- 第一人称胸前相机 → 用户自身不会完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象\n"
        f"- 必须看到用户双手或器械的运动证据才能判定动作\n"
        f"- 如果器械无法确定，equipment 填 \"UNKNOWN_EQUIPMENT\"\n"
        f"- 如果动作无法确定，exercise 填 \"UNKNOWN_ACTION\"\n\n"
        f"{_build_standard_names_prompt()}"
        f"严格按以下 JSON 格式输出，不要包含 Markdown 代码块或注释。\n"
        f"输出格式参考：\n"
        f'{{"equipment": "器械中文名称", '
        f'"exercise": "标准动作名称（从上表选择）", '
        f'"exercise_id": "对应的exercise_id", '
        f'"exercise_reason": "动作判别解释", '
        f'"confidence": 0.0~1.0, '
        f'"phase1_equipment_match": true/false, '
        f'"motion_direction": "UP/DOWN 或 LEFT/RIGHT 等", '
        f'"top_candidates": [{{"exercise": "...", "confidence": 0.0, "support": "..."}}], '
        f'"action_disambiguation": {{'
        f'"equipment_verification": "...", '
        f'"selected_evidence": "...", '
        f'"posture_flow_norm": "...", '
        f'"flow_alignment": "...", '
        f'"imu_alignment": null, '
        f'"phase1_alignment": "...", '
        f'"rejected_candidates": [{{"exercise": "...", "reason": "..."}}]'
        f'}}, '
        f'"consistency_check": {{"same_exercise_across_interval": true, "consistency_key": "...", "notes": "..."}}, '
        f'"sets": [{{"set_number": 1, "start_time": "HH:MM:SS", "end_time": "HH:MM:SS", "reps": N}}], '
        f'"rest_periods": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", "duration_sec": N, "evidence": "..."}}], '
        f'"phase1_adjustment": {{"expand_before_sec": N, "expand_after_sec": N, "reason": "..."}}'
        f'}}'
    )

    # 构造 user_content —— 视频 + 文本
    user_content: list[dict] = [
        {"type": "text", "text": user_text},
    ]

    # 发送视频片段
    video_data_url = video_to_data_url(clip_path)
    user_content.append({
        "type": "image_url",
        "image_url": {"url": video_data_url},
    })

    # LLM 调用（带重试）
    MAX_VALIDATE_RETRIES = 3
    seg_result = None

    for v_attempt in range(MAX_VALIDATE_RETRIES):
        raw = gemini_generate(system_prompt, user_content)
        tprint(f"    [{seg_id}] 响应长度: {len(raw)} 字符")

        raw_path = output_dir / f"exercise_raw_{seg_id}.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")

        try:
            seg_result = extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            tprint(f"    [{seg_id}] [警告] JSON 解析失败: {e}")
            if v_attempt < MAX_VALIDATE_RETRIES - 1:
                tprint(f"    [{seg_id}] 重试 ({v_attempt + 1}/{MAX_VALIDATE_RETRIES})...")
                continue
            seg_result = {"raw_response": raw}
            break

        # 检查是否 UNKNOWN
        exercise_val = (seg_result.get("exercise") or "").strip().lower()
        if exercise_val in ("unknown_action", "unknown", "") and v_attempt < MAX_VALIDATE_RETRIES - 1:
            tprint(f"    [{seg_id}] 识别为未知动作，重试...")
            user_content.append({
                "type": "text",
                "text": (
                    "\n⚠️ 请重新仔细观看视频，给出最可能的动作判断。"
                    "禁止输出 UNKNOWN_ACTION。confidence 可以设低（0.5），但必须给出具体动作名称。"
                ),
            })
            continue

        break

    # 标准化动作名称
    if isinstance(seg_result, dict) and "exercise" in seg_result:
        raw_exercise = seg_result["exercise"]
        std_name, exercise_id = _normalize_exercise_name(raw_exercise)
        if exercise_id:
            seg_result["exercise"] = std_name
            seg_result["exercise_id"] = exercise_id
            if std_name != raw_exercise:
                tprint(f"    [{seg_id}] 名称标准化: {raw_exercise} → {std_name} ({exercise_id})")

    return {
        "segmentId": seg_id,
        "startTime": t_start,
        "endTime": t_end,
        "startTimeStr": secs_to_hhmmss(t_start),
        "endTimeStr": secs_to_hhmmss(t_end),
        "duration": dur,
        "clip_path": str(clip_path),
        "clip_size_mb": round(clip_path.stat().st_size / (1024 * 1024), 1),
        "result": seg_result,
    }


def run_phase2_video(
    video_path: Path,
    segments: list[dict],
    flow_data: list[dict] | None,
    output_dir: Path,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
) -> list[dict]:
    """Phase 2：对每个 EXERCISE 区间截取视频片段并发送给 LLM 识别。"""
    tprint(f"\n{'=' * 60}")
    tprint(f"Phase 2: 视频片段直传识别")
    tprint(f"{'=' * 60}")

    prompt_cfg = _load_phase2_prompt()
    system_prompt = prompt_cfg["system"]

    # 获取视频总时长
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_dur = total_frames / fps
    cap.release()
    tprint(f"  视频总时长: {total_dur:.0f}s ({secs_to_hhmmss(total_dur)})")

    # 筛出 EXERCISE 段
    exercise_segs = [s for s in segments if s.get("state", "").upper() == "EXERCISE"]
    for i, s in enumerate(exercise_segs, 1):
        s.setdefault("segmentId", f"exercise_{i:03d}")

    tprint(f"  共 {len(exercise_segs)} 个 EXERCISE 段待识别 (并发: {exercise_workers})")
    if not exercise_segs:
        save_json(
            {"version": "visual1", "message": "no exercise segments", "results": []},
            output_dir / "exercise_result.json",
        )
        return []

    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []
    workers = min(exercise_workers, len(exercise_segs))

    if workers <= 1:
        for seg in exercise_segs:
            result = _recognize_one_exercise_video(
                seg, video_path, flow_data, system_prompt,
                output_dir, clips_dir, total_dur,
            )
            if result:
                all_results.append(result)
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for seg in exercise_segs:
                fut = executor.submit(
                    _recognize_one_exercise_video,
                    seg, video_path, flow_data, system_prompt,
                    output_dir, clips_dir, total_dur,
                )
                futures[fut] = seg.get("segmentId", "?")

            for fut in as_completed(futures):
                seg_id = futures[fut]
                try:
                    result = fut.result()
                    if result:
                        all_results.append(result)
                except Exception as e:
                    tprint(f"    [{seg_id}] [错误] 处理失败: {e}")

        all_results.sort(key=lambda r: r["startTime"])

    # 保存结果
    save_json(
        {
            "version": "visual1",
            "method": "video_clip_direct",
            "phase2_prompt": "phase2_exercise_recognize_v11.yaml",
            "model": GEMINI_MODEL,
            "video_source": str(video_path),
            "created_at": datetime.now().isoformat(),
            "results": all_results,
        },
        output_dir / "exercise_result.json",
    )

    tprint(f"\n  Phase 2 完成: {len(all_results)} 个 EXERCISE 已识别")
    return all_results


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="视频片段直传 LLM 两阶段识别")
    parser.add_argument(
        "video_path",
        help="原始视频文件路径 (.mp4)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="结果输出目录（默认 recognize/visualize/result/visual1）",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=MAX_EXERCISE_WORKERS,
        help=f"Phase 2 并发数（默认 {MAX_EXERCISE_WORKERS}）",
    )
    args = parser.parse_args()

    if not NEXTROUTER_API_KEY:
        tprint("[错误] NEXTROUTER_API_KEY 未设置")
        sys.exit(1)

    video_path = Path(args.video_path)
    if not video_path.exists():
        tprint(f"[错误] 视频文件不存在: {video_path}")
        sys.exit(1)

    video_name = video_path.stem

    # 工作目录（已抽帧的目录）
    work_dir = video_path.parent / video_name
    if not work_dir.exists():
        work_dir = video_path.parent

    # 输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = PROJECT_ROOT / "recognize" / "visualize" / "result" / "visual1"
    output_dir = output_dir / video_name
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time_module.time()

    tprint(f"\n{'=' * 60}")
    tprint(f"视频片段直传识别")
    tprint(f"  视频: {video_path}")
    tprint(f"  工作目录: {work_dir}")
    tprint(f"  输出目录: {output_dir}")
    tprint(f"{'=' * 60}\n")

    # ── Step 1: Phase 1 区间识别 ──
    tprint("[Step 1] 加载 Phase 1 区间结果...")
    segments = load_or_run_phase1(video_path, work_dir, output_dir)
    ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
    tprint(f"  → {len(segments)} 个区间，其中 {ex_count} 个 EXERCISE")

    if ex_count == 0:
        tprint("[WARN] 无 EXERCISE 区间，退出")
        return

    # ── Step 2: 加载光流 ──
    flow_data = None
    flow_path = work_dir / "optical_flow.json"
    if flow_path.exists():
        flow_data = load_optical_flow(flow_path)
        if flow_data:
            tprint(f"[Step 2] 光流已加载: {len(flow_data)} 帧对")
    if not flow_data:
        tprint("[Step 2] 未找到光流数据，将仅依赖视频")

    # ── Step 3: Phase 2 视频片段识别 ──
    tprint("[Step 3] Phase 2: 视频片段直传识别")
    exercise_results = run_phase2_video(
        video_path=video_path,
        segments=segments,
        flow_data=flow_data,
        output_dir=output_dir,
        exercise_workers=args.workers,
    )

    # ── 汇总 ──
    elapsed = time_module.time() - t0
    tprint(f"\n{'=' * 60}")
    tprint(f"完成！耗时 {elapsed:.1f}s")
    tprint(f"结果文件: {output_dir / 'exercise_result.json'}")
    tprint(f"EXERCISE 识别结果：")
    for r in exercise_results:
        res = r.get("result", {})
        equip = res.get("equipment", "?")
        exer = res.get("exercise", "?")
        eid = res.get("exercise_id", "")
        conf = res.get("confidence", "?")
        sets = res.get("sets", [])
        eid_str = f" [{eid}]" if eid else ""
        tprint(f"  {r['startTimeStr']}→{r['endTimeStr']}  "
               f"{equip} / {exer}{eid_str}  {len(sets)} 组  conf={conf}  "
               f"(clip: {r.get('clip_size_mb', '?')}MB)")
    tprint(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
