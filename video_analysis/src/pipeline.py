"""CLI 入口：一键完成视频 → 日报全流程。

用法：
    python -m src.pipeline video/20260525-132917.mp4
    python -m src.pipeline video/20260525-132917.mp4 --skip-classify  # 跳过 GPT，复用 keyframes.json

约定：
    心率 CSV 自动按 "{视频名}_heart_rate_data.csv" 在视频同目录寻找
    用户资料读 user_profile.json
    所有产物输出到 output/{视频名}/
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from . import config
from .calorie_calculator import (
    calculate_heart_rate_zones,
    calculate_session_calories,
)
from .frame_classifier import classify_keyframes
from .frame_classifier_full_context import classify_keyframes_full_context
from .heart_rate_loader import load_heart_rate_csv
from .keyframe_extractor import (
    compute_motion_scores,
    extract_keyframes,
    probe_video,
)
from .models import (
    KeyframeLabel,
    UserProfile,
    VideoFile,
    WorkoutSession,
)
from .report_generator import generate_report
from .segment_merger import build_timeline
from .set_detector import detect_all_sets
from .visualizer import (
    plot_action_pie,
    plot_hr_curve,
    plot_hr_zones,
    plot_time_breakdown,
    plot_timeline,
)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _load_user_profile() -> UserProfile:
    if not config.USER_PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"用户资料文件不存在：{config.USER_PROFILE_PATH}\n"
            "请按 user_profile.json 模板创建后再运行。"
        )
    with open(config.USER_PROFILE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_note", None)
    return UserProfile.from_dict(data)


def _find_heart_rate_csv(video_path: Path) -> Path | None:
    """按 {视频名}_heart_rate_data.csv 在视频同目录寻找。找不到返回 None。"""
    candidate = video_path.parent / f"{video_path.stem}_heart_rate_data.csv"
    return candidate if candidate.exists() else None


def _save_json(data, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_keyframes_cache(path: Path) -> list[KeyframeLabel]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for item in payload["keyframes"]:
        out.append(KeyframeLabel(
            frameIndex=item["frameIndex"],
            timestamp=item["timestamp"],
            status=item["status"],
            equipmentId=item.get("equipmentId"),
            equipmentName=item.get("equipmentName"),
            movementName=item.get("movementName"),
            confidence=item["confidence"],
            imageUrl=item.get("imageUrl"),
            note=item.get("note", ""),
            motion=item.get("motion", 0.0),
        ))
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_pipeline(
    video_path: Path,
    skip_classify: bool = False,
    full_context: bool = False,
) -> Path:
    """运行完整管线，返回 report.md 路径。

    full_context=True 时使用 frame_classifier_full_context（所有帧一次性给 LLM），
    所有产物追加 _full_context 后缀，不覆盖默认模式的结果。
    """
    if not video_path.exists():
        raise FileNotFoundError(f"视频不存在：{video_path}")

    profile = _load_user_profile()
    suffix = "_full_context" if full_context else ""

    out_dir = config.OUTPUT_DIR / video_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    keyframes_json_path = out_dir / f"keyframes{suffix}.json"
    segments_raw_path = out_dir / f"segments_raw{suffix}.json"

    # ── 1. 抽帧
    print(f"\n[1/8] 抽帧 {video_path.name} ...")
    info, frames = extract_keyframes(video_path, frames_dir)
    print(f"  视频 {info.resolution} @ {info.fps}fps，时长 {info.durationSeconds}s，抽出 {len(frames)} 帧")

    # ── 2. motion 计算
    print(f"[2/8] 计算 motion 分数 ...")
    motions = compute_motion_scores(frames, frames_dir)

    # ── 3. GPT 分类
    if skip_classify and keyframes_json_path.exists():
        print(f"[3/8] 跳过 GPT 分类，加载 {keyframes_json_path.name} ...")
        labels = _load_keyframes_cache(keyframes_json_path)
        if len(labels) != len(frames):
            print(f"  警告：缓存帧数 {len(labels)} ≠ 抽帧数 {len(frames)}，建议重跑（去掉 --skip-classify）")
    elif full_context:
        print(f"[3/8] GPT 全量上下文分类（一次性提交 {len(frames)} 帧）...")
        composite_path = out_dir / "keyframes_grid_full_context.jpg"
        labels, segments_raw = classify_keyframes_full_context(
            frames, motions, frames_dir,
            frames_subpath="frames",
            composite_out_path=composite_path,
        )
        _save_json({
            "totalCount": len(labels),
            "keyframes": [lbl.to_dict() for lbl in labels],
        }, keyframes_json_path)
        _save_json({"segments": segments_raw}, segments_raw_path)
        print(f"  → {keyframes_json_path}")
        print(f"  → {segments_raw_path}（AI 原始段输出）")
    else:
        print(f"[3/8] GPT 分类 {len(frames)} 帧（每批 {config.BATCH_SIZE} 张）...")
        labels = classify_keyframes(frames, motions, frames_dir, frames_subpath="frames")
        _save_json({
            "totalCount": len(labels),
            "keyframes": [lbl.to_dict() for lbl in labels],
        }, keyframes_json_path)
        print(f"  → {keyframes_json_path}")

    # ── 4. 心率加载
    print(f"[4/8] 加载心率数据 ...")
    hr_csv = _find_heart_rate_csv(video_path)
    if hr_csv:
        hr_data, sync_offset = load_heart_rate_csv(hr_csv)
        print(f"  心率 {len(hr_data)} 个数据点，同步偏移 {sync_offset}s ← {hr_csv.name}")
    else:
        hr_data = []
        sync_offset = 0.0
        print(f"  未找到心率 CSV（约定路径：{video_path.stem}_heart_rate_data.csv）→ MET 法估算")

    # ── 5. 分段
    print(f"[5/8] 合并时间线 ...")
    segments = build_timeline(labels)
    print(f"  得到 {len(segments)} 个段（"
          f"exercise={sum(1 for s in segments if s.type=='exercise')}, "
          f"transition={sum(1 for s in segments if s.type=='transition')}, "
          f"rest={sum(1 for s in segments if s.type=='rest')})")

    # ── 6. 组数检测
    print(f"[6/8] 组数 + 次数估算 ...")
    detect_all_sets(segments, labels, hr_data)

    # ── 7. 卡路里 + 心率区间
    print(f"[7/8] 计算卡路里 + 心率区间 ...")
    cal_summary = calculate_session_calories(segments, profile, hr_data)
    hr_zones = calculate_heart_rate_zones(hr_data, profile)
    print(f"  总卡路里 {cal_summary.totalCalories:.0f} kcal")

    # ── 8. 组装 WorkoutSession + 出图 + 出报告
    print(f"[8/8] 渲染图表 + 报告 ...")
    now_iso = datetime.now().isoformat(timespec="seconds")
    mtime = datetime.fromtimestamp(video_path.stat().st_mtime)
    session = WorkoutSession(
        id=f"session_{uuid.uuid4().hex[:12]}",
        userId=profile.userId,
        date=mtime.date().isoformat(),
        startTime=mtime.isoformat(timespec="seconds"),
        endTime=(mtime.replace(microsecond=0).isoformat()),
        videoFile=VideoFile(
            url=str(video_path),
            durationSeconds=info.durationSeconds,
            resolution=info.resolution,
            fps=info.fps,
        ),
        timeline=segments,
        keyframeLabels=labels,
        heartRateData=hr_data,
        heartRateSyncOffset=sync_offset,
        caloriesSummary=cal_summary,
        heartRateZones=hr_zones,
        status="review",
        createdAt=now_iso,
        updatedAt=now_iso,
    )

    # 保存 session
    session_path = out_dir / f"workout_session{suffix}.json"
    _save_json(session.to_dict(), session_path)

    # 渲染图表
    plot_timeline(segments, info.durationSeconds, out_dir / f"timeline{suffix}.png")
    plot_action_pie(segments, out_dir / f"pie{suffix}.png")
    plot_time_breakdown(segments, out_dir / f"time_breakdown{suffix}.png")
    if hr_data:
        plot_hr_curve(hr_data, out_dir / f"hr_curve{suffix}.png")

    # 生成 MD
    report_path = out_dir / f"report{suffix}.md"
    generate_report(session, report_path, image_suffix=suffix)

    print(f"\n✓ 完成！")
    print(f"  报告: {report_path}")
    print(f"  数据: {session_path}")
    print(f"  关键帧: {keyframes_json_path}")
    return report_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="健身视频 → 日报 MD")
    parser.add_argument("video", type=Path, help="视频文件路径（相对或绝对）")
    parser.add_argument("--skip-classify", action="store_true",
                        help="跳过 GPT 分类，复用上次的 keyframes.json")
    parser.add_argument("--full-context", action="store_true",
                        help="把所有关键帧一次性给 LLM 做整体识别（替代默认的批次模式），"
                             "产物追加 _full_context 后缀")
    args = parser.parse_args()

    try:
        run_pipeline(
            args.video,
            skip_classify=args.skip_classify,
            full_context=args.full_context,
        )
    except Exception as e:
        print(f"\n✗ 出错：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
