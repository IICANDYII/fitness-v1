"""日报 MD 生成。

对应技术方案 3.3.1 的 6 模块版面：
  1. 标题栏（日期 + 周几）
  2. 核心指标表（时长 / 卡路里 / 动作数 / 总组数）
  3. 时间线图（嵌入 timeline.png）
  4. 动作明细表（每个动作的组数 / 次数 / 时长 / 卡路里）
  5. 心率分布（嵌入 pie.png + 心率区间表）
  6. 最佳表现（训练量最高的动作）
  7. 时间分配条（嵌入 time_breakdown.png）

输出：output/{视频名}/report.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .models import WorkoutSession, VideoSegment


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: float) -> str:
    """秒数 → "X 分 Y 秒" 或 "X 小时 Y 分"。"""
    s = int(round(seconds))
    if s < 60:
        return f"{s} 秒"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m} 分 {sec} 秒" if sec else f"{m} 分钟"
    h, m = divmod(m, 60)
    return f"{h} 小时 {m} 分" if m else f"{h} 小时"


def _fmt_time_range(start_s: float, end_s: float) -> str:
    """秒数 → "MM:SS – MM:SS"。"""
    def _t(s):
        s = int(round(s))
        return f"{s // 60:02d}:{s % 60:02d}"
    return f"{_t(start_s)} – {_t(end_s)}"


_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _weekday_cn(date_iso: str) -> str:
    dt = datetime.fromisoformat(date_iso)
    return _WEEKDAY_CN[dt.weekday()]


# ---------------------------------------------------------------------------
# 子模块渲染
# ---------------------------------------------------------------------------

def _render_title(session: WorkoutSession) -> str:
    dt = datetime.fromisoformat(session.date)
    weekday = _weekday_cn(session.date)
    return f"# 训练日报 · {dt.year}-{dt.month:02d}-{dt.day:02d}（{weekday}）"


def _render_core_metrics(session: WorkoutSession) -> str:
    total_dur = session.videoFile.durationSeconds
    total_cal = session.caloriesSummary.totalCalories if session.caloriesSummary else 0
    ex_segs = [s for s in session.timeline if s.type == "exercise"]
    exercise_count = len({s.exercise.movementName for s in ex_segs if s.exercise})
    total_sets = sum(len(s.exercise.sets) for s in ex_segs if s.exercise)

    return (
        "## 核心指标\n\n"
        "| 训练时长 | 总卡路里 | 动作种类 | 总组数 |\n"
        "|----------|----------|----------|--------|\n"
        f"| {_fmt_duration(total_dur)} | {total_cal:.0f} kcal | {exercise_count} | {total_sets} |"
    )


def _render_timeline_image(suffix: str = "") -> str:
    return f"## 时间线\n\n![训练时间线](timeline{suffix}.png)"


def _render_exercise_table(session: WorkoutSession) -> str:
    """动作明细：每个 exercise 段一行，列出器械、组数、次数、时长、kcal。"""
    cal_map: dict[str, float] = {}
    if session.caloriesSummary:
        for p in session.caloriesSummary.perSegment:
            cal_map[p.segmentId] = p.calories

    ex_segs = [s for s in session.timeline if s.type == "exercise"]
    if not ex_segs:
        return "## 动作明细\n\n_本次训练未识别出有效训练段。_"

    lines = [
        "## 动作明细",
        "",
        "| # | 器械 · 动作 | 组数 | 总次数 | 时间段 | 时长 | 卡路里 |",
        "|---|------|------|--------|--------|------|--------|",
    ]
    for i, seg in enumerate(ex_segs, start=1):
        ex = seg.exercise
        if not ex:
            continue
        sets = ex.sets
        total_reps = sum(s.repCount for s in sets)
        reps_str = f"~{total_reps}" if any(s.isEstimated for s in sets) else str(total_reps)
        kcal = cal_map.get(seg.id, 0.0)
        lines.append(
            f"| {i} | {ex.equipmentName} · {ex.movementName} | "
            f"{len(sets)} | {reps_str} | "
            f"{_fmt_time_range(seg.startTime, seg.endTime)} | "
            f"{_fmt_duration(seg.duration)} | {kcal:.0f} kcal |"
        )
    return "\n".join(lines)


def _render_set_detail(session: WorkoutSession) -> str:
    """每个动作展开：列出每一组的开始/结束时间、次数、心率（如果有）。"""
    ex_segs = [s for s in session.timeline if s.type == "exercise" and s.exercise]
    if not ex_segs:
        return ""

    lines = ["## 分组明细", ""]
    for i, seg in enumerate(ex_segs, start=1):
        ex = seg.exercise
        lines.append(f"### {i}. {ex.equipmentName} · {ex.movementName}")
        lines.append("")
        if not ex.sets:
            lines.append("_未检测到分组（可能是连续动作）_")
            lines.append("")
            continue
        has_hr = any(s.avgHeartRate is not None for s in ex.sets)
        if has_hr:
            lines.append("| 组 | 时间段 | 次数 | 平均心率 | 峰值心率 |")
            lines.append("|----|--------|------|----------|----------|")
            for s in ex.sets:
                avg = f"{s.avgHeartRate} bpm" if s.avgHeartRate else "-"
                peak = f"{s.peakHeartRate} bpm" if s.peakHeartRate else "-"
                reps = f"~{s.repCount}" if s.isEstimated else str(s.repCount)
                lines.append(
                    f"| {s.setIndex} | {_fmt_time_range(s.startTime, s.endTime)} | "
                    f"{reps} | {avg} | {peak} |"
                )
        else:
            lines.append("| 组 | 时间段 | 次数 |")
            lines.append("|----|--------|------|")
            for s in ex.sets:
                reps = f"~{s.repCount}" if s.isEstimated else str(s.repCount)
                lines.append(
                    f"| {s.setIndex} | {_fmt_time_range(s.startTime, s.endTime)} | {reps} |"
                )
        lines.append("")
    return "\n".join(lines)


def _render_hr_zones(session: WorkoutSession, suffix: str = "") -> str:
    if not session.heartRateData:
        return "## 心率\n\n_未上传心率数据。_"
    avg_hr = session.caloriesSummary.inputParams.avgHeartRate if session.caloriesSummary and session.caloriesSummary.inputParams else None
    max_hr = session.caloriesSummary.inputParams.maxHeartRate if session.caloriesSummary and session.caloriesSummary.inputParams else None

    lines = ["## 心率曲线", ""]
    lines.append(f"![心率曲线](hr_curve{suffix}.png)")
    lines.append("")
    lines.append("## 动作占比")
    lines.append("")
    lines.append(f"![动作占比饼图](pie{suffix}.png)")
    lines.append("")
    if avg_hr and max_hr:
        lines.append(f"- 平均心率：**{avg_hr:.0f} bpm** | 最大心率参考：{max_hr} bpm")
        lines.append("")
    if session.heartRateZones:
        lines.append("| 区间 | 心率范围 | 时长 | 占比 |")
        lines.append("|------|----------|------|------|")
        for z in session.heartRateZones:
            m, s = divmod(z.durationSeconds, 60)
            lines.append(
                f"| {z.displayName} | {z.rangeBpm[0]}-{z.rangeBpm[1]} bpm | "
                f"{m}:{s:02d} | {z.percentage}% |"
            )
    return "\n".join(lines)


def _render_highlight(session: WorkoutSession) -> str:
    """挑训练量（组数 × 次数 × 时长）最高的动作。"""
    ex_segs = [s for s in session.timeline if s.type == "exercise" and s.exercise]
    if not ex_segs:
        return ""

    def _volume(seg: VideoSegment) -> float:
        ex = seg.exercise
        reps = sum(s.repCount for s in ex.sets) if ex.sets else 0
        return reps * seg.duration

    best = max(ex_segs, key=_volume)
    ex = best.exercise
    total_reps = sum(s.repCount for s in ex.sets)
    sets_count = len(ex.sets)
    return (
        "## 最佳表现\n\n"
        f"🏆 **{ex.equipmentName} · {ex.movementName}** — "
        f"{sets_count} 组 × ~{total_reps // sets_count if sets_count else total_reps} 次 · "
        f"持续 {_fmt_duration(best.duration)}"
    )


def _render_time_breakdown_image(suffix: str = "") -> str:
    return f"## 时间分配\n\n![时间分配](time_breakdown{suffix}.png)"


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def generate_report(session: WorkoutSession, out_path: Path, image_suffix: str = "") -> None:
    """生成完整 MD 报告并写盘。

    image_suffix：嵌入图片文件名的后缀（如 "_full_context"），
    用于区分默认/全量上下文两种模式的输出，避免互相覆盖。
    """
    parts = [
        _render_title(session),
        "",
        _render_core_metrics(session),
        "",
        _render_timeline_image(image_suffix),
        "",
        _render_exercise_table(session),
        "",
        _render_set_detail(session),
        _render_hr_zones(session, image_suffix),
        "",
        _render_highlight(session),
        "",
        _render_time_breakdown_image(image_suffix),
        "",
        "---",
        f"_报告生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}_",
    ]
    content = "\n".join(p for p in parts if p is not None)
    out_path.write_text(content, encoding="utf-8")
