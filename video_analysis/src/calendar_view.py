"""月历汇总：扫描 output/*/workout_session.json，按月聚合，生成月历 PNG + MD。

对应技术方案 3.3.3 节。彩点按动作部位归类（推/拉/腿/有氧/混合），
规则定义在 config.py 的 categorize_movement / categorize_session。

输出：
  output/calendar/{年}-{月}/calendar.png    月历网格图
  output/calendar/{年}-{月}/calendar.md     详细列表
"""

from __future__ import annotations

import calendar as _cal
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle

from . import config
from .models import (
    CalendarDay,
    MonthCalendarData,
    MonthStats,
)


# ---------------------------------------------------------------------------
# 扫描所有 session 文件
# ---------------------------------------------------------------------------

def _setup_chinese_font():
    rcParams["font.sans-serif"] = config.CHINESE_FONTS + rcParams.get("font.sans-serif", [])
    rcParams["axes.unicode_minus"] = False


def scan_sessions(output_root: Path = None) -> list[dict]:
    """扫描 output/*/workout_session.json，返回会话字典列表（精简字段）。"""
    output_root = output_root or config.OUTPUT_DIR
    sessions = []
    if not output_root.exists():
        return sessions

    for session_file in output_root.glob("*/workout_session.json"):
        try:
            with open(session_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # 抽取每个动作的 movementName
        movements = []
        exercise_summaries = []
        for seg in data.get("timeline", []):
            if seg.get("type") != "exercise":
                continue
            ex = seg.get("exercise")
            if not ex:
                continue
            mv = ex.get("movementName")
            if mv:
                movements.append(mv)
            sets = ex.get("sets", [])
            total_reps = sum(s.get("repCount", 0) for s in sets)
            if sets:
                avg_reps = total_reps // len(sets) if total_reps else 0
                exercise_summaries.append(
                    f"{ex.get('equipmentName', '')} · {mv}  "
                    f"{len(sets)}×~{avg_reps}"
                )
            else:
                exercise_summaries.append(f"{ex.get('equipmentName', '')} · {mv}")

        cal_summary = data.get("caloriesSummary") or {}
        sessions.append({
            "id": data.get("id"),
            "date": data.get("date"),
            "totalCalories": cal_summary.get("totalCalories", 0),
            "durationSeconds": data.get("videoFile", {}).get("durationSeconds", 0),
            "movements": movements,
            "exerciseSummaries": exercise_summaries,
            "heartRateZones": data.get("heartRateZones", []),
        })
    return sessions


# ---------------------------------------------------------------------------
# 按月聚合
# ---------------------------------------------------------------------------

def build_month_data(year: int, month: int, sessions: list[dict]) -> MonthCalendarData:
    """组装某一个月的 MonthCalendarData。"""
    # 按日期分组（一天可能多次训练，本 MVP 取第一次）
    by_date: dict[str, list[dict]] = defaultdict(list)
    for s in sessions:
        if not s["date"]:
            continue
        try:
            dt = date.fromisoformat(s["date"])
        except ValueError:
            continue
        if dt.year != year or dt.month != month:
            continue
        by_date[s["date"]].append(s)

    days_in_month = _cal.monthrange(year, month)[1]
    days: list[CalendarDay] = []
    for d in range(1, days_in_month + 1):
        iso = date(year, month, d).isoformat()
        same_day_sessions = by_date.get(iso, [])
        if not same_day_sessions:
            days.append(CalendarDay(
                date=iso, hasWorkout=False,
                categories=["rest"],
                categoryColors=[config.CATEGORY_COLORS["rest"]],
                intensity=0,
                intensityLabel="rest",
            ))
            continue

        # 合并当天所有 sessions
        all_movements: list[str] = []
        all_summaries: list[str] = []
        total_cal = 0.0
        total_dur = 0.0
        # 多次训练时心率区间按时长加权合并
        merged_zones: dict[str, dict] = {}
        for s in same_day_sessions:
            all_movements.extend(s["movements"])
            all_summaries.extend(s["exerciseSummaries"])
            total_cal += s["totalCalories"]
            total_dur += s["durationSeconds"]
            for z in s.get("heartRateZones", []):
                key = z.get("zone")
                if not key:
                    continue
                cur = merged_zones.get(key)
                if cur is None:
                    merged_zones[key] = dict(z)
                else:
                    cur["durationSeconds"] = cur.get("durationSeconds", 0) + z.get("durationSeconds", 0)

        bodyparts = config.session_bodyparts(all_movements)
        duration_min = total_dur / 60.0
        level, label = config.calculate_day_intensity(
            has_workout=True,
            heart_rate_zones=list(merged_zones.values()),
            total_calories=total_cal,
            duration_minutes=duration_min,
        )
        days.append(CalendarDay(
            date=iso,
            hasWorkout=True,
            sessionId=same_day_sessions[0]["id"],
            categories=bodyparts,
            categoryColors=[config.BODYPART_COLORS.get(c, "#9CA3AF") for c in bodyparts],
            totalCalories=round(total_cal),
            durationMinutes=int(round(duration_min)),
            exerciseSummaries=all_summaries,
            intensity=level,
            intensityLabel=label,
        ))

    stats = _compute_month_stats(days)
    return MonthCalendarData(year=year, month=month, days=days, monthStats=stats)


def _compute_month_stats(days: list[CalendarDay]) -> MonthStats:
    total_sessions = sum(1 for d in days if d.hasWorkout)
    total_cal = sum(d.totalCalories for d in days)
    total_dur_min = sum(d.durationMinutes for d in days)
    rest_days = sum(1 for d in days if not d.hasWorkout)

    # 连续训练统计
    best_streak = 0
    cur_streak = 0
    current_streak_at_today = 0
    today = date.today().isoformat()

    for d in days:
        if d.hasWorkout:
            cur_streak += 1
            best_streak = max(best_streak, cur_streak)
        else:
            cur_streak = 0

    # currentStreak：从当月最后一个训练日（不晚于今天）向前数
    for d in reversed(days):
        if d.date > today:
            continue
        if d.hasWorkout:
            current_streak_at_today += 1
        else:
            break

    h, m = divmod(total_dur_min, 60)
    duration_display = f"{h} 小时 {m} 分" if h else f"{m} 分钟"

    return MonthStats(
        totalSessions=total_sessions,
        totalCalories=total_cal,
        totalDurationDisplay=duration_display,
        currentStreak=current_streak_at_today,
        bestStreak=best_streak,
        restDays=rest_days,
    )


# ---------------------------------------------------------------------------
# 渲染月历 PNG
# ---------------------------------------------------------------------------

def plot_calendar_grid(data: MonthCalendarData, out_path: Path) -> None:
    """渲染月历网格 PNG。

    布局：7 列（周一到周日）× 5-6 行（周）。
    每个训练日：底色 = categoryColor，格子里写日期数字 + 类别名 + 卡路里。
    休息日：浅灰底色 + 日期数字。
    本月外的格子：白底空白。
    """
    _setup_chinese_font()

    days_in_month = _cal.monthrange(data.year, data.month)[1]
    first_weekday = date(data.year, data.month, 1).weekday()  # 周一=0

    # 计算需要多少行
    total_cells = first_weekday + days_in_month
    rows = (total_cells + 6) // 7

    # 纵向拉长：保持横向宽度，给每格更多垂直空间，让多个色条（胸/背/肩/臂）能舒展显示
    fig_w = 14
    fig_h = 2 + rows * 2.8     # 之前 1.8，现在 2.8 → 每格纵向高度近 60% 增加
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, 7)
    ax.set_ylim(-1.7, rows + 1.5)  # 顶部留空间给表头，底部留单排强度图例
    # 不再强制 aspect=equal，让格子变成纵向更高的矩形
    ax.axis("off")

    # 标题
    title = f"{data.year} 年 {data.month} 月 训练月历"
    ax.text(3.5, rows + 1.15, title, ha="center", va="center",
            fontsize=18, fontweight="bold", color="#1F2937")

    # 周次表头
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    for i, wd in enumerate(weekdays):
        ax.text(i + 0.5, rows + 0.4, wd, ha="center", va="center",
                fontsize=12, fontweight="bold", color="#4B5563")

    # 各格子
    day_idx = 0
    for d in range(1, days_in_month + 1):
        cell_idx = first_weekday + d - 1
        col = cell_idx % 7
        row = rows - 1 - (cell_idx // 7)

        day_info = data.days[d - 1]
        _draw_day_cell(ax, col, row, d, day_info)
        day_idx += 1

    # 底部图例
    _draw_legend(ax, rows)

    # 月份汇总信息（顶部右上角）
    stats = data.monthStats
    stats_text = (
        f"训练 {stats.totalSessions} 天 · "
        f"{stats.totalCalories} kcal · "
        f"{stats.totalDurationDisplay} · "
        f"最长连续 {stats.bestStreak} 天"
    )
    ax.text(3.5, -0.6, stats_text, ha="center", va="center",
            fontsize=11, color="#6B7280")

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _draw_day_cell(ax, col: int, row: int, day_num: int, info: CalendarDay) -> None:
    """画单个日期格子。

    背景颜色根据当天训练强度（0-4 级）着色：从浅奶黄 → 浅黄 → 橙 → 深红。
    内部仍然显示当天的训练类别小色条（保持类别一目了然）。
    """
    padding = 0.05
    x = col + padding
    y = row + padding
    w = 1 - 2 * padding
    h = 1 - 2 * padding

    # ── 背景：按强度着色 ──
    bg_color = config.intensity_background_color(info.intensity)
    # 强度越高，边框越深以增强层次
    edge_color = "#E5E7EB" if info.intensity <= 1 else "#D1D5DB"
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=bg_color, edgecolor=edge_color, linewidth=1.0,
    ))

    # 强度高时文字用白色（对比度），否则用深灰
    if info.intensity >= 3:
        primary_text = "white"
        muted_text = "#F3F4F6"
    else:
        primary_text = "#1F2937"
        muted_text = "#6B7280"

    # 日期数字（左上）
    date_color = primary_text if info.hasWorkout else "#9CA3AF"
    ax.text(x + 0.1, y + h - 0.15, str(day_num),
            ha="left", va="top", fontsize=13,
            fontweight="bold" if info.hasWorkout else "normal",
            color=date_color)

    if not info.hasWorkout:
        return

    cats = info.categories or ["other"]
    colors = info.categoryColors or [config.CATEGORY_COLORS["other"]]
    n = len(cats)

    # ── 类别色条：纵向堆叠，每条内部写类别名 ──
    # 布局区域：日期行下方到底部信息行上方
    # 日期数字在 y+h-0.15，字号 13，约占 0.18 高度，所以 stack_top 要在 y+h-0.33 以下
    stack_top = y + h - 0.35           # 留足空间给顶部日期数字
    stack_bottom = y + 0.20            # 略高于底部 kcal/分钟
    stack_h_avail = stack_top - stack_bottom

    bar_w = w * 0.78
    bar_x = x + (w - bar_w) / 2

    gap_v = 0.015
    # 每条高度：可用空间 / 数量，给出合理上限避免单类别时太胖
    raw_bar_h = (stack_h_avail - gap_v * (n - 1)) / n
    bar_h_each = min(raw_bar_h, 0.20)

    # 居中布局：实际占用高度 < 可用高度时，把它们整体居中
    actual_total = n * bar_h_each + (n - 1) * gap_v
    top_padding = (stack_h_avail - actual_total) / 2
    cur_y = stack_top - top_padding - bar_h_each

    for bp, color in zip(cats, colors):
        # 色条背景 = 部位颜色（红=胸 / 绿=背 / 紫=肩 / 琥珀=臂 / 橙=腿 / 粉=腹 / 深红=心肺）
        ax.add_patch(FancyBboxPatch(
            (bar_x, cur_y), bar_w, bar_h_each,
            boxstyle="round,pad=0.005,rounding_size=0.04",
            facecolor=color, edgecolor="white", linewidth=0.6,
        ))
        # 部位文字：白色，直接写在彩色色条上
        label = config.BODYPART_DISPLAY_NAMES.get(bp, "")
        ax.text(bar_x + bar_w / 2, cur_y + bar_h_each / 2, label,
                ha="center", va="center",
                fontsize=10 if len(label) <= 1 else 9,
                color="white", fontweight="bold")
        cur_y -= bar_h_each + gap_v

    # 卡路里 + 时长（底部，一行内显示）
    bottom_y = y + 0.10
    parts = []
    if info.totalCalories > 0:
        parts.append(f"{int(info.totalCalories)} kcal")
    if info.durationMinutes > 0:
        parts.append(f"{info.durationMinutes} 分钟")
    if parts:
        ax.text(x + w / 2, bottom_y, " · ".join(parts),
                ha="center", va="center", fontsize=8, color=muted_text)


def _draw_legend(ax, rows: int) -> None:
    """绘制底部图例：只有强度等级（部位名直接写在色条上，不再需要类别图例）。"""

    intensity_items = config.INTENSITY_LEVELS  # [(code, label, color), ...]
    y_int = -1.2
    item_w_int = 0.85
    total_w_int = len(intensity_items) * item_w_int
    start_x_int = 3.5 - total_w_int / 2

    ax.text(start_x_int - 0.45, y_int + 0.09, "强度:",
            ha="right", va="center", fontsize=9, color="#6B7280")
    for i, (_code, name, color) in enumerate(intensity_items):
        cx = start_x_int + i * item_w_int
        ax.add_patch(Rectangle((cx, y_int), 0.22, 0.16,
                                facecolor=color, edgecolor="#D1D5DB", linewidth=0.6))
        ax.text(cx + 0.28, y_int + 0.08, name,
                ha="left", va="center", fontsize=9, color="#374151")


# ---------------------------------------------------------------------------
# 渲染月历 MD
# ---------------------------------------------------------------------------

_WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def generate_calendar_md(data: MonthCalendarData, out_path: Path) -> None:
    """生成月历 MD 文件。

    版面：
      1. 标题（{年} 年 {月} 月）
      2. 嵌入 calendar.png
      3. 本月统计（训练天数 / 总卡路里 / 最长连续等）
      4. 训练详情：按日期排序，每天列出动作清单
    """
    lines: list[str] = []
    lines.append(f"# {data.year} 年 {data.month} 月 训练月历")
    lines.append("")
    lines.append("![月历](calendar.png)")
    lines.append("")

    # 本月统计
    stats = data.monthStats
    lines.append("## 本月统计")
    lines.append("")
    lines.append(f"- 训练天数：**{stats.totalSessions}** 天")
    lines.append(f"- 总卡路里：**{stats.totalCalories:.0f}** kcal")
    lines.append(f"- 总时长：**{stats.totalDurationDisplay}**")
    lines.append(f"- 最长连续训练：**{stats.bestStreak}** 天")
    lines.append(f"- 当前连续：**{stats.currentStreak}** 天")
    lines.append(f"- 休息天数：**{stats.restDays}** 天")
    lines.append("")

    # 训练详情
    workout_days = [d for d in data.days if d.hasWorkout]
    lines.append("## 训练详情")
    lines.append("")

    if not workout_days:
        lines.append("_本月暂无训练记录。_")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return

    for d in workout_days:
        dt = date.fromisoformat(d.date)
        weekday = _WEEKDAY_CN[dt.weekday()]
        # 月历 MVP 现在用部位（胸/背/...）作为 d.categories 的内容
        cat_label = " · ".join(config.BODYPART_DISPLAY_NAMES.get(c, "") for c in d.categories)
        h, m = divmod(d.durationMinutes, 60)
        dur_str = f"{h} 小时 {m} 分" if h else f"{m} 分钟"

        lines.append(
            f"### {dt.year}-{dt.month:02d}-{dt.day:02d}（{weekday}）· {cat_label} · "
            f"{dur_str} · {int(d.totalCalories)} kcal"
        )
        lines.append("")
        for summary in d.exerciseSummaries:
            lines.append(f"- {summary}")
        lines.append("")

    lines.append("---")
    lines.append(f"_报告生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}_")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------

def generate_month_calendar(year: int, month: int, out_root: Path | None = None) -> Path:
    """生成某月的月历 PNG + MD。返回 MD 文件路径。"""
    out_root = out_root or config.OUTPUT_DIR
    month_dir = out_root / "calendar" / f"{year}-{month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)

    sessions = scan_sessions(out_root)
    data = build_month_data(year, month, sessions)

    plot_calendar_grid(data, month_dir / "calendar.png")
    md_path = month_dir / "calendar.md"
    generate_calendar_md(data, md_path)

    # 同时把 MonthCalendarData JSON 也存一份，方便后续接 FastAPI
    json_path = month_dir / "calendar_data.json"
    json_path.write_text(
        json.dumps(data.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return md_path


def main():
    """CLI：python -m src.calendar_view 2026 5"""
    import argparse
    parser = argparse.ArgumentParser(description="生成月历 PNG + MD")
    parser.add_argument("year", type=int)
    parser.add_argument("month", type=int)
    args = parser.parse_args()
    out = generate_month_calendar(args.year, args.month)
    print(f"✓ 月历生成完成：{out}")


if __name__ == "__main__":
    main()
