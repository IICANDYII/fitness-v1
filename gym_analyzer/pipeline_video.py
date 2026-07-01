"""
pipeline_video.py - 基于视频片段的两阶段识别流水线

与 pipeline.py 的区别：
  - Phase 1 输入为低码率压缩视频片段（90s窗口，15s重叠），而非关键帧网格图
  - Phase 2 输入为运动区间前后15s的低码率视频片段，而非关键帧网格图
  - 视频通过 ffmpeg 压缩后以 base64 编码发送给 LLM

用法：
  python -m gym_analyzer.pipeline_video <视频路径> [--output <输出目录>]

流程：
  Step 1  将视频切分为 90s 窗口（15s 重叠）并压缩
  Step 2  Phase 1：依次发送视频窗口给 LLM，识别 EXERCISE/REST 区间
  Step 3  合并不同窗口的区间信息（处理重叠区域）
  Step 4  Phase 2：截取运动区间（前后各扩展15s）压缩后发送给 LLM
  Step 5  汇总所有动作识别结果
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import threading
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .optical_flow import (
    compute_optical_flow,
    analyze_periodicity,
    save_flow,
    load_flow,
    summarize_window_flow,
    format_flow_for_exercise,
)
from .stitcher import sec_to_hhmmss, sec_to_mmss, mmss_to_sec
from .yaml_loader import load_prompt, PromptConfig
from .recognizer import (
    load_imu_data,
    format_imu_for_phase1,
    format_imu_for_exercise,
    ImuRecord,
    _extract_json,
    _save_json,
    _validate_exercise_result,
    _sanitize_exercise_result,
    _normalize_exercise_name,
    _is_unknown_exercise,
    _build_standard_names_prompt,
    _extract_output_format,
    apply_phase1_adjustments,
    tprint,
    IMU_WINDOW_SEC,
)
from .extractor import FrameMeta


# ──────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────

WINDOW_SEC = 90           # Phase 1 视频窗口大小（秒）
WINDOW_OVERLAP_SEC = 15   # 相邻窗口重叠秒数
EXERCISE_PAD_SEC = 15     # Phase 2 运动区间前后扩展秒数
MAX_EXERCISE_WORKERS = 4  # Phase 2 并发数

VIDEO_CRF = 35            # 视频压缩质量（越大体积越小，画质越差）
VIDEO_SCALE = 480         # 压缩视频短边像素
VIDEO_BITRATE = "300k"    # 最大码率


# ──────────────────────────────────────────────
# ffmpeg 视频处理
# ──────────────────────────────────────────────

def _find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件路径。"""
    for candidate in ["ffmpeg", "ffmpeg.exe"]:
        try:
            subprocess.run(
                [candidate, "-version"],
                capture_output=True, timeout=10,
            )
            return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    # 尝试通过 imageio-ffmpeg 获取
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            return path
    except ImportError:
        pass
    raise FileNotFoundError(
        "找不到 ffmpeg，请安装：\n"
        "  pip install imageio-ffmpeg\n"
        "  或 Windows: winget install ffmpeg"
    )


def _get_video_duration(video_path: str | Path) -> float:
    """使用 ffmpeg 获取视频时长（秒）。"""
    ffmpeg = _find_ffmpeg()
    # 尝试 ffprobe（同目录或 PATH 中）
    ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
    try:
        cmd = [
            ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (FileNotFoundError, ValueError):
        pass
    # 回退：用 ffmpeg 本身获取时长
    cmd = [
        ffmpeg, "-i", str(video_path),
        "-f", "null", "-",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    # 从 stderr 中解析 Duration: HH:MM:SS.xx
    for line in result.stderr.splitlines():
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", line)
        if m:
            h, mi, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
            return h * 3600 + mi * 60 + s
    raise RuntimeError(f"无法获取视频时长: {video_path}")


def _compress_video_segment(
    video_path: str | Path,
    output_path: str | Path,
    start_sec: float,
    duration_sec: float,
    scale: int = VIDEO_SCALE,
    crf: int = VIDEO_CRF,
    max_bitrate: str = VIDEO_BITRATE,
    burn_timestamp: bool = True,
) -> Path:
    """使用 ffmpeg 截取并压缩视频片段，可选叠加绝对时间水印。"""
    ffmpeg = _find_ffmpeg()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 构建 vf 滤镜链
    vf_parts = [f"scale=-2:{scale}"]
    if burn_timestamp:
        offset = int(start_sec)
        # drawtext 用 t（片段内秒数）+ offset 计算绝对时间
        dt_filter = (
            "drawtext="
            "text='%{eif\\:floor((t+" + str(offset) + ")/3600)\\:d\\:2}"
            "\\:%{eif\\:mod(floor((t+" + str(offset) + ")/60)\\,60)\\:d\\:2}"
            "\\:%{eif\\:mod(floor(t+" + str(offset) + ")\\,60)\\:d\\:2}':"
            "x=10:y=10:"
            "fontsize=28:fontcolor=white:"
            "box=1:boxcolor=black@0.6:boxborderw=5"
        )
        vf_parts.append(dt_filter)

    vf_str = ",".join(vf_parts)

    cmd = [
        ffmpeg, "-y",
        "-ss", str(start_sec),
        "-i", str(video_path),
        "-t", str(duration_sec),
        "-vf", vf_str,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-maxrate", max_bitrate,
        "-bufsize", "600k",
        "-preset", "fast",
        "-an",
        "-movflags", "+faststart",
        str(output_path),
    ]

    subprocess.run(
        cmd, capture_output=True, timeout=300,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg 压缩视频失败: {output_path}")

    return output_path


def _video_to_data_url(video_path: Path) -> str:
    """将视频文件编码为 base64 data URL。"""
    data = video_path.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f"data:video/mp4;base64,{b64}"


# ──────────────────────────────────────────────
# LLM 调用（支持视频输入）
# ──────────────────────────────────────────────

def _gemini_generate_video(
    system_prompt: str,
    user_content: list[dict],
    max_retries: int = 5,
) -> str:
    """调用 Gemini API（通过 nextrouter），支持视频输入。"""
    import requests

    api_key = os.getenv("NEXTROUTER_API_KEY")
    base_url = os.getenv("NEXTROUTER_BASE_URL", "https://nextrouter.cc")
    model = os.getenv("GEMINI_VIDEO_MODEL") or os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")

    if not api_key:
        raise EnvironmentError("未设置 NEXTROUTER_API_KEY")

    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    url = f"{base_url}/chat/completions"

    vid_count = sum(1 for c in user_content if c.get("type") == "video_url")
    img_count = sum(1 for c in user_content if c.get("type") == "image_url")
    tprint(f"  → LLM 请求: model={model}, {vid_count} 视频, {img_count} 图片")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 32768,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
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
                tprint(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time_module.sleep(wait)
                continue
        if not resp.ok:
            tprint(f"  [HTTP {resp.status_code}] {resp.text[:300]}")
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        finish = data["choices"][0].get("finish_reason", "")
        if not content:
            tprint(f"  [警告] 空响应! finish_reason={finish!r}")
        return content or ""

    raise RuntimeError("超过最大重试次数")


# ──────────────────────────────────────────────
# Phase 1：视频窗口切分 + 粗区间识别
# ──────────────────────────────────────────────

def _split_video_windows(
    video_path: Path,
    total_dur: float,
    window_sec: int = WINDOW_SEC,
    overlap_sec: int = WINDOW_OVERLAP_SEC,
) -> list[dict]:
    """计算视频窗口的起止时间。"""
    windows = []
    start = 0.0
    idx = 0
    while start < total_dur:
        end = min(start + window_sec, total_dur)
        windows.append({
            "index": idx,
            "start_sec": start,
            "end_sec": end,
            "duration": end - start,
        })
        idx += 1
        next_start = start + window_sec - overlap_sec
        if next_start >= total_dur:
            break
        if end >= total_dur:
            break
        start = next_start
    return windows


def run_phase1_video(
    video_path: Path,
    total_dur: float,
    flow_data: list[dict],
    prompt: PromptConfig,
    output_dir: Path,
    work_dir: Path,
    imu_records: list[ImuRecord] | None = None,
    overwrite: bool = False,
) -> tuple[list[dict], list[dict]]:
    """
    Phase 1：将视频切分为窗口，逐个发送给 LLM 识别。

    Returns:
        (segments, equipment_timeline)
    """
    tprint(f"\n{'=' * 60}")
    tprint(f"Phase 1 (Video): 阶段划分")
    tprint(f"{'=' * 60}")

    windows = _split_video_windows(video_path, total_dur)
    tprint(f"  视频时长: {total_dur:.0f}s ({sec_to_hhmmss(total_dur)})")
    tprint(f"  窗口: {len(windows)} 个 (每窗 {WINDOW_SEC}s, 重叠 {WINDOW_OVERLAP_SEC}s)")

    # 压缩视频目录
    clips_dir = work_dir / "video_clips" / "phase1"
    clips_dir.mkdir(parents=True, exist_ok=True)

    all_window_segments: list[list[dict]] = []
    all_equipment_timelines: list[list[dict]] = []
    all_raw_responses: list[str] = []

    for win in windows:
        win_idx = win["index"]
        win_start = win["start_sec"]
        win_end = win["end_sec"]
        win_dur = win["duration"]

        tprint(f"\n  ── 窗口 {win_idx + 1}/{len(windows)}: "
               f"{sec_to_hhmmss(win_start)} ~ {sec_to_hhmmss(win_end)} ({win_dur:.0f}s)")

        # 压缩视频片段
        clip_path = clips_dir / f"window_{win_idx + 1:03d}.mp4"
        if not overwrite and clip_path.exists() and clip_path.stat().st_size > 0:
            tprint(f"    使用缓存: {clip_path}")
        else:
            tprint(f"    压缩视频片段...")
            _compress_video_segment(
                video_path, clip_path,
                start_sec=win_start,
                duration_sec=win_dur,
            )
        clip_size_kb = clip_path.stat().st_size / 1024
        tprint(f"    视频大小: {clip_size_kb:.0f} KB")

        # 光流摘要
        flow_text = summarize_window_flow(flow_data, win_start, win_end)

        # IMU 摘要
        imu_text = ""
        if imu_records:
            imu_text = format_imu_for_phase1(imu_records, win_end, window_sec=IMU_WINDOW_SEC)

        # 构造 user content
        intro = (
            f"以下是一段健身视频的第一人称胸前相机片段，"
            f"视频总时长 {total_dur:.0f}s ({sec_to_hhmmss(total_dur)})。\n\n"
            f"当前为第 {win_idx + 1}/{len(windows)} 个窗口，"
            f"时间范围 {sec_to_hhmmss(win_start)} ~ {sec_to_hhmmss(win_end)} ({win_dur:.0f}s)。\n"
            f"★ 视频画面左上角叠加了绝对时间水印（HH:MM:SS），请直接从画面读取时间。\n"
            f"★ 输出的 start_time / end_time 必须与画面水印时间一致，严禁自行推算。\n\n"
            f"请将本段时间范围内的视频划分为 EXERCISE / REST 两种状态，"
            f"并在每个时间段上标注用户当前最可能交互的器材名称。\n\n"
            f"关键规则：\n"
            f"- 第一人称胸前相机，用户本人不完整出现在画面中\n"
            f"- 画面中其他人、镜子中其他人均非分析对象\n"
            f"- 仅关注用户双手、正在接触的器械、视角运动变化\n"
            f"- 用户双手与器械持续交互 + 视频中显示周期性运动 → EXERCISE\n"
            f"- 不同器械上的运动必须拆分为不同 EXERCISE 段\n"
            f"- 器械切换、行走、调整位置、组间休息 → 全部归为 REST\n"
            f"- 每个 segment 都必须填写 equipment、equipment_reason、equipment_features、posture 字段\n"
        )

        if imu_text:
            intro += f"\n\n{imu_text}\n"

        intro += f"\n光流摘要:\n{flow_text}\n"

        user_content: list[dict] = [{"type": "text", "text": intro}]

        # 添加视频
        video_data_url = _video_to_data_url(clip_path)
        user_content.append({
            "type": "video_url",
            "video_url": {"url": video_data_url},
        })

        # 输出格式
        output_fmt = (
            f"\n\n请输出覆盖 {sec_to_hhmmss(win_start)} ~ {sec_to_hhmmss(win_end)} 的时间线，"
            f"严格按 JSON 格式，不要包含 Markdown 代码块或注释：\n"
            f'{{"segments": [{{"start_time": "HH:MM:SS", "end_time": "HH:MM:SS", '
            f'"state": "EXERCISE|REST", "confidence": 0.0~1.0, '
            f'"reason": "判断依据", '
            f'"equipment": "器材名或UNKNOWN", '
            f'"equipment_reason": "器材判断依据", '
            f'"equipment_features": ["视觉特征1", "视觉特征2"], '
            f'"posture": "standing|seated|supine|prone|bending|hanging", '
            f'"posture_reason": "姿态判断依据", '
            f'"global_motion": true|false'
            f'}}], '
            f'"equipment_timeline": [{{"time": "HH:MM:SS", "equipment": "器材名", "event": "开始使用|切换到新器材"}}]}}'
        )
        user_content.append({"type": "text", "text": output_fmt})

        # 调用 LLM
        raw = _gemini_generate_video(prompt.system, user_content)
        tprint(f"    响应长度: {len(raw)} 字符")
        all_raw_responses.append(raw)

        # 保存原始响应
        (output_dir / f"phase1_raw_window_{win_idx + 1:03d}.txt").write_text(raw, encoding="utf-8")

        # 解析 JSON
        try:
            result = _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            tprint(f"    [警告] JSON 解析失败: {e}")
            all_window_segments.append([])
            all_equipment_timelines.append([])
            continue

        segments = []
        eq_timeline = []
        if isinstance(result, dict):
            segments = result.get("segments", [])
            eq_timeline = result.get("equipment_timeline", [])
        elif isinstance(result, list):
            segments = result

        # 补充 start_sec / end_sec
        for seg in segments:
            if "start_time" in seg and "start_sec" not in seg:
                seg["start_sec"] = mmss_to_sec(str(seg["start_time"]))
            if "end_time" in seg and "end_sec" not in seg:
                seg["end_sec"] = mmss_to_sec(str(seg["end_time"]))

        all_window_segments.append(segments)
        all_equipment_timelines.append(eq_timeline)

        ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
        tprint(f"    → {len(segments)} 段, 其中 {ex_count} EXERCISE")

    # ── 合并所有窗口结果 ──
    merged_segments = _merge_window_segments(all_window_segments)
    merged_timeline = _merge_equipment_timelines(all_equipment_timelines)

    # 保存合并结果
    version_tag = "v_video"
    meta = {
        "version": version_tag,
        "pipeline": "video",
        "phase1_prompt": Path(prompt.source_file).name,
        "video_source": str(video_path),
        "total_duration_sec": total_dur,
        "num_windows": len(windows),
        "window_sec": WINDOW_SEC,
        "overlap_sec": WINDOW_OVERLAP_SEC,
        "video_crf": VIDEO_CRF,
        "video_scale": VIDEO_SCALE,
        "model": os.getenv("GEMINI_VIDEO_MODEL") or os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "segments": merged_segments,
        "equipment_timeline": merged_timeline,
    }
    _save_json(meta, output_dir / "period_result.json")

    # 保存所有原始响应
    (output_dir / "period_raw_response.txt").write_text(
        "\n\n===== WINDOW SEPARATOR =====\n\n".join(all_raw_responses),
        encoding="utf-8",
    )

    ex_count = sum(1 for s in merged_segments if s.get("state", "").upper() == "EXERCISE")
    tprint(f"\n  Phase 1 (Video) 完成: {len(merged_segments)} 段, 其中 {ex_count} EXERCISE")
    for seg in merged_segments:
        equip = seg.get("equipment", "")
        equip_str = f"  [{equip}]" if equip else ""
        tprint(f"    {seg.get('start_time', '?')} → {seg.get('end_time', '?')}  "
               f"{seg.get('state', '?')}  conf={seg.get('confidence', '?')}{equip_str}  "
               f"{seg.get('reason', '')}")

    return merged_segments, merged_timeline


def _merge_window_segments(all_window_segs: list[list[dict]]) -> list[dict]:
    """合并多个窗口的 segments，处理重叠区域去重。"""
    if not all_window_segs:
        return []

    merged = []
    for segs in all_window_segs:
        for seg in segs:
            start = seg.get("start_sec", 0)
            end = seg.get("end_sec", 0)
            duplicate = False
            for existing in merged:
                es = existing.get("start_sec", 0)
                ee = existing.get("end_sec", 0)
                overlap = min(end, ee) - max(start, es)
                duration = max(end - start, 1)
                if overlap / duration > 0.5:
                    # 保留置信度更高的
                    if seg.get("confidence", 0) > existing.get("confidence", 0):
                        existing.update(seg)
                    duplicate = True
                    break
            if not duplicate:
                merged.append(seg)

    merged.sort(key=lambda s: s.get("start_sec", 0))

    # 合并相邻同状态段
    consolidated = []
    for seg in merged:
        if (consolidated
                and consolidated[-1].get("state", "").upper() == seg.get("state", "").upper()
                and consolidated[-1].get("equipment", "") == seg.get("equipment", "")
                and seg.get("start_sec", 0) - consolidated[-1].get("end_sec", 0) <= 5):
            consolidated[-1]["end_sec"] = seg.get("end_sec", 0)
            consolidated[-1]["end_time"] = seg.get("end_time", "")
            consolidated[-1]["confidence"] = min(
                consolidated[-1].get("confidence", 0),
                seg.get("confidence", 0),
            )
        else:
            consolidated.append(dict(seg))

    # 修正相邻段的时间间隙
    for i in range(1, len(consolidated)):
        prev_end = consolidated[i - 1].get("end_sec", 0)
        curr_start = consolidated[i].get("start_sec", 0)
        if 0 < curr_start - prev_end <= 5:
            consolidated[i]["start_sec"] = prev_end
            consolidated[i]["start_time"] = sec_to_hhmmss(prev_end)

    return consolidated


def _merge_equipment_timelines(all_timelines: list[list[dict]]) -> list[dict]:
    """合并多个窗口的器材时间线，去重。"""
    merged = []
    seen = set()
    for timeline in all_timelines:
        for evt in timeline:
            key = (evt.get("time", ""), evt.get("equipment", ""))
            if key not in seen:
                seen.add(key)
                merged.append(evt)
    merged.sort(key=lambda e: mmss_to_sec(e.get("time", "00:00:00")))
    return merged


# ──────────────────────────────────────────────
# Phase 2：单个 EXERCISE 视频识别
# ──────────────────────────────────────────────

def _recognize_exercise_video(
    seg: dict,
    video_path: Path,
    total_dur: float,
    flow_data: list[dict],
    system_prompt: str,
    output_dir: Path,
    work_dir: Path,
    imu_records: list[ImuRecord] | None = None,
    equipment_timeline: list[dict] | None = None,
    user_prompt_template: str = "",
    overwrite: bool = False,
) -> dict | None:
    """识别单个 EXERCISE 区间（视频输入版本）。"""
    seg_id = seg.get("segmentId", "?")
    t_start = seg.get("start_sec", 0.0)
    t_end = seg.get("end_sec", 0.0)
    dur = t_end - t_start

    tprint(f"\n  ── {seg_id}: {sec_to_hhmmss(t_start)} ~ {sec_to_hhmmss(t_end)} ({dur:.0f}s)")

    # 前后扩展
    pad_start = max(0.0, t_start - EXERCISE_PAD_SEC)
    pad_end = min(total_dur, t_end + EXERCISE_PAD_SEC)
    clip_dur = pad_end - pad_start
    tprint(f"    [{seg_id}] 扩展范围: {sec_to_hhmmss(pad_start)} ~ {sec_to_hhmmss(pad_end)} ({clip_dur:.0f}s)")

    # 压缩视频片段
    clips_dir = work_dir / "video_clips" / "phase2"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_path = clips_dir / f"{seg_id}.mp4"

    if not overwrite and clip_path.exists() and clip_path.stat().st_size > 0:
        tprint(f"    [{seg_id}] 使用缓存视频")
    else:
        tprint(f"    [{seg_id}] 压缩视频片段...")
        _compress_video_segment(
            video_path, clip_path,
            start_sec=pad_start,
            duration_sec=clip_dur,
        )
    clip_size_kb = clip_path.stat().st_size / 1024
    tprint(f"    [{seg_id}] 视频大小: {clip_size_kb:.0f} KB")

    # 光流摘要
    flow_summary = format_flow_for_exercise(flow_data, t_start, t_end)

    # IMU 摘要
    imu_text = format_imu_for_exercise(imu_records or [], t_start, t_end) if imu_records else ""

    # Phase 1 上下文
    phase1_equipment = seg.get("equipment", "UNKNOWN")
    phase1_posture = seg.get("posture", "")
    phase1_reason = seg.get("reason", "")
    phase1_eq_reason = seg.get("equipment_reason", "")
    phase1_eq_features = seg.get("equipment_features", [])
    phase1_global_motion = seg.get("global_motion", None)

    phase1_lines = []
    if phase1_equipment and phase1_equipment != "UNKNOWN":
        phase1_lines.append(f"  器材: {phase1_equipment}")
    if phase1_eq_reason:
        phase1_lines.append(f"  器材判据: {phase1_eq_reason}")
    if phase1_eq_features:
        phase1_lines.append(f"  器材特征: {', '.join(phase1_eq_features)}")
    if phase1_posture:
        phase1_lines.append(f"  用户姿态: {phase1_posture}")
    if phase1_reason:
        phase1_lines.append(f"  描述: {phase1_reason}")
    if phase1_global_motion is not None:
        phase1_lines.append(f"  全局运动: {'身体整体运动' if phase1_global_motion else '仅局部肢体运动'}")

    phase1_context = ""
    if phase1_lines:
        phase1_context = "- Phase 1 参考信息（需独立验证）:\n" + "\n".join(phase1_lines) + "\n"

    if equipment_timeline:
        timeline_lines = ["- 器材切换时间线（Phase 1 全局识别结果）:"]
        for et in equipment_timeline:
            timeline_lines.append(f"  {et.get('time', '?')}  {et.get('equipment', '?')}  ({et.get('event', '')})")
        phase1_context += "\n".join(timeline_lines) + "\n"

    # 构造 user prompt
    user_text = (
        f"以下是 EXERCISE 段 [{seg_id}] 的低码率视频片段（第一人称胸前相机）：\n"
        f"- 时间范围: {sec_to_hhmmss(t_start)} ~ {sec_to_hhmmss(t_end)} (共 {dur:.0f}s)\n"
        f"- 视频覆盖: {sec_to_hhmmss(pad_start)} ~ {sec_to_hhmmss(pad_end)} (含前后各{EXERCISE_PAD_SEC}s缓冲)\n"
        f"- 视频开头约15s为进场/准备画面，可用于识别器械细节\n"
        f"★ 视频画面左上角叠加了绝对时间水印（HH:MM:SS），请直接从画面读取时间。\n"
        f"{phase1_context}\n"
        f"---\n\n"
        f"{flow_summary}\n\n"
        + (f"{imu_text}\n\n" if imu_text else "")
        + f"---\n\n"
        f"{_build_standard_names_prompt()}"
        f"请根据视频内容，识别用户的训练动作、器械、组数和次数。\n\n"
        f"关键约束：\n"
        f"- 第一人称胸前相机 → 用户自身不会完整出现在画面中\n"
        f"- 画面中其他人、镜子中其他人均非分析对象\n"
        f"- 必须看到用户双手或器械的运动证据才能判定动作\n"
        f"- 如果器械无法确定，equipment 填 \"UNKNOWN_EQUIPMENT\"\n"
        f"- 如果动作无法确定，exercise 填 \"UNKNOWN_ACTION\"\n\n"
        f"严格输出 JSON，不要包含 Markdown 代码块。\n\n"
        + (_extract_output_format(user_prompt_template) if user_prompt_template else
           f'{{"equipment": "器械名称", "exercise": "标准动作名称", "exercise_id": "对应ID", '
           f'"exercise_reason": "判断依据", "confidence": 0.0~1.0, '
           f'"phase1_equipment_match": true, "motion_direction": "UP/DOWN", '
           f'"top_candidates": [{{"exercise": "候选", "confidence": 0.9, "support": "证据"}}], '
           f'"action_disambiguation": {{"equipment_verification": "", "selected_evidence": "", '
           f'"posture_flow_norm": "", "flow_alignment": "", "imu_alignment": null, '
           f'"phase1_alignment": "", "rejected_candidates": []}}, '
           f'"consistency_check": {{"same_exercise_across_interval": true, "consistency_key": "", "notes": ""}}, '
           f'"sets": [{{"set_number": 1, "start_time": "HH:MM:SS", "end_time": "HH:MM:SS", '
           f'"reps": 12, "imu_rep_hint": null, "rep_source": "video"}}], '
           f'"rest_periods": [], '
           f'"phase1_adjustment": {{"expand_before_sec": 0, "expand_after_sec": 0, "reason": ""}}}}')
    )

    user_content: list[dict] = [{"type": "text", "text": user_text}]

    # 添加视频
    video_data_url = _video_to_data_url(clip_path)
    user_content.append({
        "type": "video_url",
        "video_url": {"url": video_data_url},
    })

    # 调用 LLM（含重试）
    MAX_VALIDATE_RETRIES = 3
    seg_result = None

    for v_attempt in range(MAX_VALIDATE_RETRIES):
        raw = _gemini_generate_video(system_prompt, user_content)
        tprint(f"    [{seg_id}] 响应长度: {len(raw)} 字符")

        raw_path = output_dir / f"exercise_raw_{seg_id}.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(raw, encoding="utf-8")

        try:
            seg_result = _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            tprint(f"    [{seg_id}] [警告] JSON 解析失败: {e}")
            if v_attempt < MAX_VALIDATE_RETRIES - 1:
                tprint(f"    [{seg_id}] 重试 ({v_attempt + 1}/{MAX_VALIDATE_RETRIES})...")
                continue
            seg_result = {"raw_response": raw}
            break

        validation_errors = _validate_exercise_result(seg_result)
        if validation_errors and v_attempt < MAX_VALIDATE_RETRIES - 1:
            tprint(f"    [{seg_id}] 数据校验失败:")
            for err in validation_errors[:3]:
                tprint(f"      - {err}")
            tprint(f"    [{seg_id}] 重试 ({v_attempt + 1}/{MAX_VALIDATE_RETRIES})...")
            continue

        # UNKNOWN 自检
        exercise_val = seg_result.get("exercise") or ""
        if _is_unknown_exercise(exercise_val) and v_attempt < MAX_VALIDATE_RETRIES - 1:
            tprint(f"    [{seg_id}] 识别结果为未知动作({exercise_val!r})，重试...")
            retry_hint = {
                "type": "text",
                "text": (
                    "\n\n⚠️ 上一次你返回了未知动作，请重新仔细分析视频：\n"
                    "1. 禁止输出 UNKNOWN_ACTION 等。必须给出最可能的判断。\n"
                    "2. 重点关注：器械外观、手部运动方向、运动周期模式。\n"
                    "3. confidence 可以设低，但必须给出具体名称。\n"
                ),
            }
            if retry_hint not in user_content:
                user_content.append(retry_hint)
            continue

        seg_result = _sanitize_exercise_result(seg_result)
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
        "startTimeStr": sec_to_hhmmss(t_start),
        "endTimeStr": sec_to_hhmmss(t_end),
        "duration": dur,
        "result": seg_result,
    }


# ──────────────────────────────────────────────
# Phase 2：运动识别（并发）
# ──────────────────────────────────────────────

def run_phase2_video(
    video_path: Path,
    total_dur: float,
    flow_data: list[dict],
    segments: list[dict],
    prompt: PromptConfig,
    output_dir: Path,
    work_dir: Path,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
    imu_records: list[ImuRecord] | None = None,
    equipment_timeline: list[dict] | None = None,
    overwrite: bool = False,
) -> list[dict]:
    """Phase 2：对每个 EXERCISE 区间并发识别（视频版本）。"""
    tprint(f"\n{'=' * 60}")
    tprint(f"Phase 2 (Video): 运动识别")
    tprint(f"{'=' * 60}")

    system_prompt = prompt.system

    # 筛出 EXERCISE 段并编号
    exercise_segs = [
        s for s in segments if s.get("state", "").upper() == "EXERCISE"
    ]
    for i, s in enumerate(exercise_segs, 1):
        s.setdefault("segmentId", f"exercise_{i:03d}")

    tprint(f"  共 {len(exercise_segs)} 个 EXERCISE 段待识别（并发: {exercise_workers}）")

    if not exercise_segs:
        _save_json(
            {"version": "v_video", "pipeline": "video", "message": "no exercise segments", "results": []},
            output_dir / "exercise_result.json",
        )
        return []

    all_results: list[dict] = []
    workers = min(exercise_workers, len(exercise_segs))

    if workers <= 1:
        for seg in exercise_segs:
            result = _recognize_exercise_video(
                seg, video_path, total_dur, flow_data, system_prompt,
                output_dir, work_dir,
                imu_records=imu_records,
                equipment_timeline=equipment_timeline,
                user_prompt_template=prompt.user,
                overwrite=overwrite,
            )
            if result:
                all_results.append(result)
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for seg in exercise_segs:
                fut = executor.submit(
                    _recognize_exercise_video,
                    seg, video_path, total_dur, flow_data, system_prompt,
                    output_dir, work_dir,
                    imu_records, equipment_timeline, prompt.user, overwrite,
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
    result_payload = {
        "version": "v_video",
        "pipeline": "video",
        "phase2_prompt": Path(prompt.source_file).name,
        "model": os.getenv("GEMINI_VIDEO_MODEL") or os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "results": all_results,
    }
    _save_json(result_payload, output_dir / "exercise_result.json")

    # 应用 Phase 1 区间修正
    adjusted_segments, applied = apply_phase1_adjustments(segments, all_results, total_dur)
    _save_json(
        {
            "version": "v_video",
            "pipeline": "video",
            "model": os.getenv("GEMINI_VIDEO_MODEL") or os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
            "created_at": datetime.now().isoformat(),
            "adjustments_applied": applied,
            "segments": adjusted_segments,
        },
        output_dir / "period_result_adjusted.json",
    )

    tprint(f"\n  Phase 2 (Video) 完成: {len(all_results)} 个 EXERCISE, 区间修正 {applied} 处")
    return all_results


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def run_pipeline_video(
    video_path: str | Path,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
) -> None:
    """
    视频版完整识别流水线。

    Args:
        video_path:       原始视频文件路径（.mp4 等）
        output_dir:       结果输出目录（默认 recognize/visualize/result/v_video/<视频名>）
        overwrite:        是否忽略缓存重新执行
        exercise_workers: Phase 2 并发数
    """
    t0 = time_module.time()
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    video_name = video_path.stem

    # 工作目录（存放中间文件）
    work_dir = video_path.parent / video_name
    work_dir.mkdir(parents=True, exist_ok=True)

    # 输出目录
    if output_dir is None:
        out_dir = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "v_video" / video_name
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 加载环境变量
    for env_candidate in [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env",
    ]:
        if env_candidate.exists():
            load_dotenv(env_candidate)
            break

    # 加载 prompts
    prompts_dir = Path(__file__).parent / "prompts"
    phase1_prompt = load_prompt(prompts_dir / "phase1_period_recognize_v7_video.yaml")
    phase2_prompt = load_prompt(prompts_dir / "phase2_exercise_recognize_v10_video.yaml")

    # 获取视频时长
    total_dur = _get_video_duration(video_path)

    print(f"\n{'=' * 60}")
    print(f"视频版识别流水线")
    print(f"{'=' * 60}")
    print(f"视频文件：{video_path}")
    print(f"视频时长：{total_dur:.0f}s ({sec_to_hhmmss(total_dur)})")
    print(f"工作目录：{work_dir}")
    print(f"输出目录：{out_dir}")
    print(f"Phase 2 并发数：{exercise_workers}")
    print(f"{'=' * 60}\n")

    # ── Step 1：加载帧元数据（用于光流计算）──
    meta_path = work_dir / "frames_meta.json"
    frame_metas = []
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        frame_metas = [FrameMeta(**m) for m in raw]
        print(f"[Step 1] 帧元数据已加载: {len(frame_metas)} 帧")
    else:
        print(f"[Step 1] 未找到帧元数据，需要先抽帧（用于光流计算）")
        print(f"  请运行: python -m gym_analyzer.extractor {video_path}")
        print(f"  或者视频已抽帧的目录名需要与视频名一致")
        # 尝试查找同名目录下的帧
        for candidate_dir in [work_dir, video_path.parent / video_name]:
            candidate_meta = candidate_dir / "frames_meta.json"
            if candidate_meta.exists():
                with open(candidate_meta, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                frame_metas = [FrameMeta(**m) for m in raw]
                work_dir = candidate_dir
                print(f"  找到帧数据: {candidate_meta} ({len(frame_metas)} 帧)")
                break

    if not frame_metas:
        print("[警告] 没有帧数据，跳过光流计算，仅依赖视频内容分析")

    # ── Step 2：光流（如有帧数据）──
    flow_data = []
    if frame_metas:
        shared_base = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "shared"
        shared_flow = shared_base / work_dir.name / "optical_flow.json"
        flow_path = work_dir / "optical_flow.json"

        cached = load_flow(shared_flow) if shared_flow.exists() else None
        if cached:
            print(f"[Step 2] 光流使用 shared 缓存: {shared_flow}")
        else:
            cached = None if overwrite else load_flow(flow_path)

        if cached:
            flow_data, _ = cached
        else:
            print("[Step 2] 计算光流")
            frames_dir = work_dir / "frames"
            flow_data = compute_optical_flow(frame_metas, work_dir)
            periodicity = analyze_periodicity(flow_data)
            save_flow(flow_data, periodicity, len(frame_metas), flow_path)
    else:
        print("[Step 2] 无帧数据，跳过光流计算")

    # ── Step 2.5：加载 IMU 数据（如有）──
    shared_base = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "shared"
    shared_imu = shared_base / work_dir.name / "IMU.txt"
    imu_path = work_dir / "IMU_data.txt"
    imu_records = None
    if shared_imu.exists():
        imu_records = load_imu_data(shared_imu)
        if imu_records:
            print(f"[IMU] 已从 shared 加载 {len(imu_records)} 条记录: {shared_imu}")
    if not imu_records:
        imu_records = load_imu_data(imu_path)
        if imu_records:
            print(f"[IMU] 已加载 {len(imu_records)} 条记录: {imu_path}")
    if not imu_records:
        print(f"[IMU] 未找到 IMU 数据，跳过传感器辅助")

    # ── Step 3：Phase 1（视频版）──
    period_result_path = out_dir / "period_result.json"
    equipment_timeline = []

    if not overwrite and period_result_path.exists():
        print(f"[Step 3] Phase 1 使用缓存: {period_result_path}")
        with open(period_result_path, "r", encoding="utf-8") as f:
            cached_result = json.load(f)
        segments = cached_result.get("segments", [])
        equipment_timeline = cached_result.get("equipment_timeline", [])
    else:
        print("[Step 3] Phase 1 (Video)：视频窗口切分 + 粗区间识别")
        segments, equipment_timeline = run_phase1_video(
            video_path=video_path,
            total_dur=total_dur,
            flow_data=flow_data,
            prompt=phase1_prompt,
            output_dir=out_dir,
            work_dir=work_dir,
            imu_records=imu_records,
            overwrite=overwrite,
        )

    ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
    print(f"  → {len(segments)} 个区间，其中 {ex_count} 个 EXERCISE")

    # ── Phase 1 自检 ──
    if ex_count == 0:
        print("  [WARN] Phase 1 未识别出任何 EXERCISE 区间，重新识别...")
        segments, equipment_timeline = run_phase1_video(
            video_path=video_path,
            total_dur=total_dur,
            flow_data=flow_data,
            prompt=phase1_prompt,
            output_dir=out_dir,
            work_dir=work_dir,
            imu_records=imu_records,
            overwrite=True,
        )
        ex_count = sum(1 for s in segments if s.get("state", "").upper() == "EXERCISE")
        print(f"  → 重试结果: {len(segments)} 个区间，其中 {ex_count} 个 EXERCISE")

    print()

    # ── Step 4：Phase 2（视频版）──
    print("[Step 4] Phase 2 (Video)：逐 EXERCISE 视频精细识别")
    exercise_results = run_phase2_video(
        video_path=video_path,
        total_dur=total_dur,
        flow_data=flow_data,
        segments=segments,
        prompt=phase2_prompt,
        output_dir=out_dir,
        work_dir=work_dir,
        exercise_workers=exercise_workers,
        imu_records=imu_records,
        equipment_timeline=equipment_timeline,
        overwrite=overwrite,
    )

    # ── 汇总 ──
    elapsed = time_module.time() - t0
    print(f"\n{'=' * 60}")
    print(f"完成！耗时 {elapsed:.1f}s")
    print(f"结果文件：")
    print(f"  {out_dir / 'period_result.json'}")
    print(f"  {out_dir / 'exercise_result.json'}")
    print(f"  {out_dir / 'period_result_adjusted.json'}")
    print(f"EXERCISE 识别结果：")
    for r in exercise_results:
        res = r.get("result", {})
        equip = res.get("equipment", "?")
        exer = res.get("exercise", "?")
        eid = res.get("exercise_id", "")
        conf = res.get("confidence", "?")
        sets = res.get("sets", [])
        eid_str = f"  [{eid}]" if eid else ""
        print(f"  {r['startTimeStr']}→{r['endTimeStr']}  "
              f"{equip} / {exer}{eid_str}  {len(sets)} 组  conf={conf}")
    print(f"{'=' * 60}\n")


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="健身视频运动识别（视频片段版，直接发送低码率视频给LLM）")
    parser.add_argument(
        "video_path",
        help="原始视频文件路径（如 video/3.mp4）")
    parser.add_argument(
        "--output", "-o", default=None,
        help="结果输出目录（默认 recognize/visualize/result/v_video/<视频名>）")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="忽略缓存，重新执行所有步骤")
    parser.add_argument(
        "--workers", "-w", type=int, default=MAX_EXERCISE_WORKERS,
        help=f"Phase 2 并发数（默认 {MAX_EXERCISE_WORKERS}）")
    args = parser.parse_args()

    run_pipeline_video(
        video_path=args.video_path,
        output_dir=args.output,
        overwrite=args.overwrite,
        exercise_workers=args.workers,
    )


if __name__ == "__main__":
    main()
