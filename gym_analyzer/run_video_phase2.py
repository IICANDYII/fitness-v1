"""
run_video_phase2.py - 基于视频的 Phase 2 运动识别

使用低帧率视频（而非网格图）作为 LLM 输入进行动作识别。

用法：
  python -m gym_analyzer.run_video_phase2 \
    --work-dir gym_analyzer/input/1 \
    --period-result recognize/visualize/result/v10/1/period_result.json \
    --fps 1 \
    --output-dir recognize/visualize/result/v10-1fps/1
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .extractor import FrameMeta
from .optical_flow import (
    format_flow_for_exercise,
    load_flow,
)
from .recognizer import (
    EXERCISE_BOUNDARY_PAD,
    MAX_EXERCISE_WORKERS,
    ImuRecord,
    _build_standard_names_prompt,
    _extract_json,
    _extract_output_format,
    _is_unknown_exercise,
    _normalize_exercise_name,
    _sanitize_exercise_result,
    _validate_exercise_result,
    apply_phase1_adjustments,
    format_imu_for_exercise,
    load_imu_data,
    tprint,
)
from .stitcher import sec_to_hhmmss, mmss_to_sec
from .video_stitcher import stitch_exercise_video, load_period_result
from .yaml_loader import load_prompt


def _video_to_data_url(video_path: Path) -> str:
    raw = video_path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    return f"data:video/mp4;base64,{b64}"


def _gemini_generate_video(
    system_prompt: str,
    user_content: list[dict],
    max_retries: int = 3,
) -> str:
    """调用 Gemini API，支持视频输入。"""
    import requests

    api_key = os.getenv("NEXTROUTER_API_KEY")
    base_url = os.getenv("NEXTROUTER_BASE_URL", "https://nextrouter.cc")
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")

    if not api_key:
        raise EnvironmentError("未设置 NEXTROUTER_API_KEY")

    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    url = f"{base_url}/chat/completions"

    vid_count = sum(1 for c in user_content if c.get("type") == "video_url")
    img_count = sum(1 for c in user_content if c.get("type") == "image_url")
    tprint(f"  → LLM 请求: model={model}, {vid_count} 个视频, {img_count} 张图片")

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
            resp = session.post(url, headers=headers, json=payload, timeout=120)
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
            wait = min(15 * attempt, 60)
            tprint(f"  [HTTP {resp.status_code}] 服务端错误")
            if attempt < max_retries:
                tprint(f"  等待 {wait}s 后重试（{attempt}/{max_retries}）...")
                time_module.sleep(wait)
                continue
        if not resp.ok:
            tprint(f"  [HTTP {resp.status_code}] {resp.text[:500]}")
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        finish = data["choices"][0].get("finish_reason", "")
        if not content:
            tprint(f"  [警告] 空响应! finish_reason={finish!r}")
        return content or ""

    raise RuntimeError("超过最大重试次数")


def _recognize_one_exercise_video(
    seg: dict,
    frame_metas: list[dict],
    frames_dir: Path,
    output_dir: Path,
    flow_data: list[dict],
    system_prompt: str,
    target_fps: int,
    imu_records: list[ImuRecord] | None = None,
    equipment_timeline: list[dict] | None = None,
    user_prompt_template: str = "",
    video_cache_dir: Path | None = None,
) -> dict | None:
    """识别单个 EXERCISE 区间（视频模式）。"""
    seg_id = seg.get("segmentId", "?")
    t_start = seg.get("start_sec", 0.0)
    t_end = seg.get("end_sec", 0.0)
    dur = t_end - t_start

    tprint(f"\n  ── {seg_id}: {sec_to_hhmmss(t_start)} ~ {sec_to_hhmmss(t_end)} ({dur:.0f}s)")

    total_dur = frame_metas[-1]["timestamp"] if frame_metas else 0
    pad_start = max(0.0, t_start - EXERCISE_BOUNDARY_PAD)
    pad_end = min(total_dur, t_end + EXERCISE_BOUNDARY_PAD)
    tprint(f"    [{seg_id}] 扩充范围: {sec_to_hhmmss(pad_start)} ~ {sec_to_hhmmss(pad_end)}")

    # 生成或复用视频
    if video_cache_dir is None:
        video_cache_dir = output_dir / "exercise_videos"
    video_cache_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_cache_dir / f"{seg_id}_{target_fps}fps.mp4"

    if not video_path.exists():
        video_meta = stitch_exercise_video(
            frame_metas=frame_metas,
            frames_dir=frames_dir,
            start_sec=pad_start,
            end_sec=pad_end,
            output_path=video_path,
            target_fps=target_fps,
        )
        if video_meta is None:
            tprint(f"    [{seg_id}] [警告] 视频生成失败，跳过")
            return None
    else:
        tprint(f"    [{seg_id}] 复用已有视频: {video_path.name}")

    video_size_kb = video_path.stat().st_size / 1024
    tprint(f"    [{seg_id}] 视频: {video_path.name} ({video_size_kb:.0f}KB)")

    # 光流摘要
    flow_summary = format_flow_for_exercise(flow_data, t_start, t_end)

    # IMU 摘要
    imu_exercise_text = format_imu_for_exercise(imu_records or [], t_start, t_end) if imu_records else ""

    # Phase 1 上下文
    phase1_reason = seg.get("reason", "")
    phase1_equipment = seg.get("equipment", "UNKNOWN")
    phase1_posture = seg.get("posture", "")
    phase1_context = ""
    if phase1_reason or phase1_equipment != "UNKNOWN":
        phase1_lines = []
        if phase1_reason:
            phase1_lines.append(f"  描述: {phase1_reason}")
        if phase1_equipment and phase1_equipment != "UNKNOWN":
            phase1_lines.append(f"  器材预识别: {phase1_equipment}（请根据视频独立验证）")
        if phase1_posture:
            phase1_lines.append(f"  用户姿态: {phase1_posture}")
        phase1_context = (
            f"- Phase 1 参考信息（器材名需独立验证）:\n" + "\n".join(phase1_lines) + "\n"
        )

    if equipment_timeline:
        timeline_lines = [f"- 器材切换时间线（Phase 1 全局识别结果）:"]
        for et in equipment_timeline:
            timeline_lines.append(f"  {et.get('time', '?')}  {et.get('equipment', '?')}  ({et.get('event', '')})")
        phase1_context += "\n".join(timeline_lines) + "\n"

    user_text = (
        f"以下是 EXERCISE 段 [{seg_id}] 的**低帧率视频**（第一人称胸前相机，{target_fps}fps 采样）：\n"
        f"- 时间范围: {sec_to_hhmmss(t_start)} ~ {sec_to_hhmmss(t_end)} (共 {dur:.0f}s)\n"
        f"- 视频覆盖: {sec_to_hhmmss(pad_start)} ~ {sec_to_hhmmss(pad_end)} (前后扩充 {EXERCISE_BOUNDARY_PAD}s)\n"
        f"- 采样率: {target_fps}fps\n"
        f"- 视频前约 15 秒为进场画面，可用于观察器械全貌\n"
        f"{phase1_context}\n"
        f"---\n\n"
        f"{flow_summary}\n\n"
        + (f"{imu_exercise_text}\n\n" if imu_exercise_text else "")
        + f"---\n\n"
        f"{_build_standard_names_prompt()}"
        f"请根据视频内容，严格按以下步骤分析，然后输出 JSON：\n\n"
        f"Step 1 — 进场画面分析: 描述视频开头看到的器械外观\n"
        f"Step 2 — 器械识别: 结合进场画面和训练画面判断器械\n"
        f"Step 3 — 光流验证: 结合光流方向验证或修正器械判断\n"
        f"Step 4 — 动作判定: 综合器械 + 光流 + 视频画面判定具体动作名称\n"
        f"Step 5 — 组次统计: 利用视频运动周期统计组数和每组次数\n\n"
        f"关键约束：\n"
        f"- 第一人称胸前相机 → 用户自身不会完整出现在画面中\n"
        f"- 画面中其他人均非分析对象\n"
        f"- 必须看到用户双手或器械的运动证据才能判定动作\n"
        f"- 如果器械无法确定，equipment 填 \"UNKNOWN_EQUIPMENT\"\n"
        f"- 如果动作无法确定，exercise 填 \"UNKNOWN_ACTION\"\n\n"
        f"输出格式：先写分析过程（每个 Step 1~2 句话），最后输出完整 JSON（不要包含 Markdown 代码块）。\n\n"
        + (_extract_output_format(user_prompt_template) if user_prompt_template else "")
    )

    # 构造 user content：文字 + 视频
    user_content = [
        {"type": "text", "text": user_text},
        {
            "type": "video_url",
            "video_url": {"url": _video_to_data_url(video_path)},
        },
    ]

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

        exercise_val = seg_result.get("exercise") or ""
        if _is_unknown_exercise(exercise_val) and v_attempt < MAX_VALIDATE_RETRIES - 1:
            tprint(f"    [{seg_id}] 识别为未知动作({exercise_val!r})，重试...")
            retry_hint = {
                "type": "text",
                "text": (
                    "\n\n⚠️ 上一次你返回了未知动作。请重新仔细分析视频：\n"
                    "1. 必须给出最可能的判断，禁止输出 UNKNOWN。\n"
                    "2. confidence 可以设低，但必须给出具体的 exercise 名称。\n"
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
        "video_file": str(video_path.name),
        "video_fps": target_fps,
        "result": seg_result,
    }


def run_video_phase2(
    work_dir: str | Path,
    period_result_path: str | Path,
    target_fps: int = 1,
    output_dir: str | Path | None = None,
    exercise_workers: int = MAX_EXERCISE_WORKERS,
) -> list[dict]:
    """
    基于视频的 Phase 2 运动识别主函数。

    Args:
        work_dir:             帧数据目录
        period_result_path:   period_result.json 路径
        target_fps:           视频帧率（1 或 2）
        output_dir:           结果输出目录
        exercise_workers:     并发数
    """
    t0 = time_module.time()
    work_dir = Path(work_dir)
    period_result_path = Path(period_result_path)

    if output_dir is None:
        output_dir = work_dir
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载环境变量
    for env_candidate in [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env",
    ]:
        if env_candidate.exists():
            load_dotenv(env_candidate)
            break

    # 加载 prompt
    prompt_path = Path(__file__).parent / "prompts" / "phase2_exercise_recognize_v4_video.yaml"
    prompt = load_prompt(prompt_path)
    tprint(f"[prompt] {prompt.name} v{prompt.version} ({Path(prompt.source_file).name})")

    # 加载帧元数据
    meta_path = work_dir / "frames_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"找不到 frames_meta.json: {meta_path}")
    with open(meta_path, "r", encoding="utf-8") as f:
        frame_metas = json.load(f)

    frames_dir = work_dir / "frames"
    total_dur = frame_metas[-1]["timestamp"] if frame_metas else 0

    # 加载 period_result
    with open(period_result_path, "r", encoding="utf-8") as f:
        period_data = json.load(f)
    segments = period_data.get("segments", [])
    equipment_timeline = period_data.get("equipment_timeline", [])

    exercise_segs = [s for s in segments if s.get("state", "").upper() == "EXERCISE"]
    for i, s in enumerate(exercise_segs, 1):
        s.setdefault("segmentId", f"exercise_{i:03d}")

    # 加载光流
    _shared_base = Path(__file__).parent.parent / "recognize" / "visualize" / "result" / "shared"
    _shared_flow = _shared_base / work_dir.name / "optical_flow.json"
    flow_path = work_dir / "optical_flow.json"

    cached = load_flow(_shared_flow) if _shared_flow.exists() else None
    if not cached:
        cached = load_flow(flow_path)
    if cached:
        flow_data, periodicity = cached
    else:
        flow_data = []
        tprint("[警告] 未找到光流数据")

    # 加载 IMU
    _shared_imu = _shared_base / work_dir.name / "IMU.txt"
    imu_path = work_dir / "IMU_data.txt"
    imu_records = None
    if _shared_imu.exists():
        imu_records = load_imu_data(_shared_imu)
    if not imu_records:
        imu_records = load_imu_data(imu_path)

    # 视频缓存目录
    video_cache_dir = output_dir / "exercise_videos"

    print(f"\n{'=' * 60}")
    print(f"Video Phase 2: 基于视频的运动识别")
    print(f"帧目录：{work_dir}")
    print(f"输出目录：{output_dir}")
    print(f"帧数：{len(frame_metas)}  时长：{sec_to_hhmmss(total_dur)}")
    print(f"EXERCISE 区间数：{len(exercise_segs)}")
    print(f"目标帧率：{target_fps}fps")
    print(f"并发数：{exercise_workers}")
    print(f"{'=' * 60}\n")

    # 复制 period_result.json 到输出目录
    import shutil
    dst_period = output_dir / "period_result.json"
    if not dst_period.exists():
        shutil.copy2(period_result_path, dst_period)
        tprint(f"  已复制 period_result.json → {dst_period}")

    # 逐个识别
    all_results: list[dict] = []
    workers = min(exercise_workers, len(exercise_segs))

    if workers <= 1:
        for seg in exercise_segs:
            try:
                result = _recognize_one_exercise_video(
                    seg, frame_metas, frames_dir, output_dir, flow_data,
                    prompt.system, target_fps,
                    imu_records=imu_records,
                    equipment_timeline=equipment_timeline,
                    user_prompt_template=prompt.user,
                    video_cache_dir=video_cache_dir,
                )
                if result:
                    all_results.append(result)
            except Exception as e:
                tprint(f"    [{seg.get('segmentId', '?')}] [错误] {e}")
                tprint(f"    [{seg.get('segmentId', '?')}] 跳过此区间，继续下一个")
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for seg in exercise_segs:
                fut = executor.submit(
                    _recognize_one_exercise_video,
                    seg, frame_metas, frames_dir, output_dir, flow_data,
                    prompt.system, target_fps,
                    imu_records, equipment_timeline, prompt.user,
                    video_cache_dir,
                )
                futures[fut] = seg.get("segmentId", "?")

            for fut in as_completed(futures):
                seg_id = futures[fut]
                try:
                    result = fut.result()
                    if result:
                        all_results.append(result)
                except Exception as e:
                    tprint(f"    [{seg_id}] [错误] {e}")

        all_results.sort(key=lambda r: r["startTime"])

    # 保存 exercise_result.json
    result_payload = {
        "version": f"v4-video-{target_fps}fps",
        "phase2_prompt": Path(prompt.source_file).name,
        "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "target_fps": target_fps,
        "input_mode": "video",
        "results": all_results,
    }
    result_path = output_dir / "exercise_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, ensure_ascii=False, indent=2)
    tprint(f"  [OK] 已保存: {result_path}")

    # 应用 Phase 1 区间修正
    fm_objects = [type('FM', (), {"timestamp": m["timestamp"]})() for m in frame_metas]
    adjusted_segments, applied = apply_phase1_adjustments(
        segments, all_results, total_dur)
    adj_payload = {
        "version": f"v4-video-{target_fps}fps",
        "model": os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview"),
        "created_at": datetime.now().isoformat(),
        "adjustments_applied": applied,
        "segments": adjusted_segments,
    }
    adj_path = output_dir / "period_result_adjusted.json"
    with open(adj_path, "w", encoding="utf-8") as f:
        json.dump(adj_payload, f, ensure_ascii=False, indent=2)
    tprint(f"  [OK] 已保存: {adj_path}")

    # 汇总
    elapsed = time_module.time() - t0
    print(f"\n{'=' * 60}")
    print(f"完成！耗时 {elapsed:.1f}s")
    print(f"结果文件：")
    print(f"  {result_path}")
    print(f"  {adj_path}")
    print(f"EXERCISE 识别结果：")
    for r in all_results:
        res = r.get("result", {})
        equip = res.get("equipment", "?")
        exer = res.get("exercise", "?")
        eid = res.get("exercise_id", "")
        conf = res.get("confidence", "?")
        sets_list = res.get("sets", [])
        eid_str = f"  [{eid}]" if eid else ""
        print(f"  {r['startTimeStr']}→{r['endTimeStr']}  "
              f"{equip} / {exer}{eid_str}  {len(sets_list)} 组  conf={conf}")
    print(f"{'=' * 60}\n")

    return all_results


def main():
    parser = argparse.ArgumentParser(
        description="基于视频的 Phase 2 运动识别")
    parser.add_argument(
        "--work-dir", required=True,
        help="帧数据目录（包含 frames_meta.json 和 frames/）")
    parser.add_argument(
        "--period-result", required=True,
        help="period_result.json 路径")
    parser.add_argument(
        "--fps", type=int, default=1, choices=[1, 2],
        help="目标帧率（默认 1）")
    parser.add_argument(
        "--output-dir", "-o", required=True,
        help="结果输出目录")
    parser.add_argument(
        "--workers", "-w", type=int, default=2,
        help="并发数（默认 2）")

    args = parser.parse_args()

    run_video_phase2(
        work_dir=args.work_dir,
        period_result_path=args.period_result,
        target_fps=args.fps,
        output_dir=args.output_dir,
        exercise_workers=args.workers,
    )


if __name__ == "__main__":
    main()
