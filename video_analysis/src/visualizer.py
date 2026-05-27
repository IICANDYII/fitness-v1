"""matplotlib 图表生成：

  timeline.png         水平时间线，每段一个色块（exercise 按器械着色）
  pie.png              动作占比饼图（按 equipmentName 聚合时长）
  time_breakdown.png   3 色紧凑时间条（exercise / transition / rest 占比）
  hr_zones.png         心率区间条形图

所有图都用 matplotlib 渲染，无 Qt 后端依赖（Agg）。
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from pathlib import Path

from . import config
from .models import HeartRateData, HeartRateZone, VideoSegment


# ---------------------------------------------------------------------------
# 字体配置
# ---------------------------------------------------------------------------

def _setup_chinese_font():
    rcParams["font.sans-serif"] = config.CHINESE_FONTS + rcParams.get("font.sans-serif", [])
    rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# 器械配色（exercise 段使用，每种器械一个色）
# ---------------------------------------------------------------------------

# 17 个器械的固定配色（饱和度适中、彼此区分度高）
_EQUIPMENT_COLORS: dict[str, str] = {
    # 有氧（红/橙系）
    "跑步":       "#EF4444",
    "椭圆机":     "#F97316",
    "动感单车":   "#F59E0B",
    "划船机":     "#14B8A6",
    # 自由重量（蓝系）
    "杠铃":       "#3B82F6",
    "哑铃":       "#60A5FA",
    "史密斯架":   "#1D4ED8",
    # 自重 / 悬挂（绿系）
    "引体向上":   "#10B981",
    "自重训练":   "#34D399",
    # 固定器械（紫系）
    "高位下拉":   "#8B5CF6",
    "坐姿划船":   "#A78BFA",
    "腿举机":     "#7C3AED",
    "蝴蝶机":     "#C084FC",
    "推肩机":     "#6366F1",
    # 绳索（粉/紫）
    "龙门架":     "#EC4899",
    # 非训练
    "拉伸":       "#94A3B8",
    "其他":       "#CBD5E1",
    "未识别":     "#FCA5A5",
}

_TRANSITION_COLOR = "#9CA3AF"
_REST_COLOR = "#FECACA"


def _segment_color(seg: VideoSegment) -> str:
    if seg.type == "transition":
        return _TRANSITION_COLOR
    if seg.type == "rest":
        return _REST_COLOR
    if seg.exercise:
        return _EQUIPMENT_COLORS.get(seg.exercise.equipmentName, "#9CA3AF")
    return "#9CA3AF"


def _segment_label(seg: VideoSegment) -> str:
    if seg.type == "exercise" and seg.exercise:
        return f"{seg.exercise.movementName}"
    if seg.type == "transition":
        return "过渡"
    return "休息"


# ---------------------------------------------------------------------------
# 1. 时间线（彩色横条）
# ---------------------------------------------------------------------------

def plot_timeline(
    segments: list[VideoSegment],
    total_duration: float,
    out_path: Path,
) -> None:
    """渲染水平时间线图。每段一个彩色矩形 + 段名+时长标注（只在足够宽的段上显示）。"""
    _setup_chinese_font()
    fig, ax = plt.subplots(figsize=(14, 2.6))

    min_label_duration = total_duration * 0.05  # 段宽 < 5% 总宽则不放文字

    for seg in segments:
        color = _segment_color(seg)
        ax.barh(y=0, width=seg.duration, left=seg.startTime, height=1.0,
                color=color, edgecolor="white", linewidth=0.8)

        if seg.duration >= min_label_duration:
            label = _segment_label(seg)
            ax.text(
                seg.startTime + seg.duration / 2, 0,
                label,
                ha="center", va="center",
                fontsize=8.5, color="white", fontweight="bold",
            )

    ax.set_xlim(0, max(total_duration, segments[-1].endTime if segments else 1))
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xlabel("时间")
    ax.set_title("训练时间线", fontsize=13, fontweight="bold", pad=10)

    # 横轴格式化为 MM:SS
    def _fmt_mmss(value, _pos):
        v = max(0, int(round(value)))
        return f"{v // 60:d}:{v % 60:02d}"

    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_mmss))

    # 图例：只显示实际出现过的类别
    seen: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for seg in segments:
        if seg.type == "exercise" and seg.exercise:
            key = seg.exercise.equipmentName
        elif seg.type == "transition":
            key = "过渡"
        else:
            key = "休息"
        if key in seen_keys:
            continue
        seen.append((key, _segment_color(seg)))
        seen_keys.add(key)

    handles = [Patch(facecolor=color, label=name) for name, color in seen]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.45),
              ncol=min(len(handles), 6), frameon=False, fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 2. 动作占比饼图
# ---------------------------------------------------------------------------

def plot_action_pie(
    segments: list[VideoSegment],
    out_path: Path,
) -> None:
    """按 equipmentName 聚合时长，画占比饼图。

    非 exercise 段聚合为"过渡 / 休息"两类。
    """
    _setup_chinese_font()

    buckets: dict[str, float] = {}
    for seg in segments:
        if seg.type == "exercise" and seg.exercise:
            key = seg.exercise.equipmentName or "未识别"
        elif seg.type == "transition":
            key = "过渡"
        else:
            key = "休息"
        buckets[key] = buckets.get(key, 0.0) + seg.duration

    # 排序：训练类放前面（按时长降序），过渡/休息放最后
    rest_items = []
    train_items = []
    for k, v in buckets.items():
        if k in ("过渡", "休息"):
            rest_items.append((k, v))
        else:
            train_items.append((k, v))
    train_items.sort(key=lambda x: -x[1])
    items = train_items + rest_items

    labels = [k for k, _ in items]
    sizes = [v for _, v in items]
    colors = [
        _TRANSITION_COLOR if k == "过渡"
        else _REST_COLOR if k == "休息"
        else _EQUIPMENT_COLORS.get(k, "#9CA3AF")
        for k in labels
    ]

    fig, ax = plt.subplots(figsize=(7, 6))

    def _autopct(pct):
        return f"{pct:.0f}%" if pct >= 4 else ""

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct=_autopct, startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 10},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title("动作占比", fontsize=13, fontweight="bold", pad=15)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 3. 时间分配 3 色条
# ---------------------------------------------------------------------------

def plot_time_breakdown(
    segments: list[VideoSegment],
    out_path: Path,
) -> None:
    """按运动 / 过渡 / 休息三大类聚合时长，画堆叠条形图。"""
    _setup_chinese_font()

    bucket: dict[str, float] = {"exercise": 0.0, "transition": 0.0, "rest": 0.0}
    for seg in segments:
        bucket[seg.type] = bucket.get(seg.type, 0.0) + seg.duration
    total = sum(bucket.values()) or 1.0

    cats = [
        ("exercise", "运动", "#3B82F6"),
        ("transition", "过渡", "#9CA3AF"),
        ("rest", "休息", "#FCA5A5"),
    ]

    fig, ax = plt.subplots(figsize=(12, 1.8))

    left = 0.0
    for code, name, color in cats:
        w = bucket[code]
        ax.barh(y=0, width=w, left=left, height=0.6, color=color, edgecolor="white", linewidth=1.5)
        pct = w / total * 100
        if pct >= 4:
            m, s = divmod(int(round(w)), 60)
            ax.text(left + w / 2, 0, f"{name}\n{pct:.0f}% · {m}:{s:02d}",
                    ha="center", va="center", color="white", fontsize=10, fontweight="bold")
        left += w

    ax.set_xlim(0, total)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines[:].set_visible(False)
    ax.set_title("时间分配", fontsize=13, fontweight="bold", pad=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4. 心率曲线（深色底 + 粉红渐变填充）
# ---------------------------------------------------------------------------

def plot_hr_curve(
    heart_rate_data: list[HeartRateData],
    out_path: Path,
    title: str = "训练心率曲线",
) -> None:
    """画训练时段的心率曲线。

    参考样式（运动 App 风格）：
      - 深色背景（近黑）
      - 粉红色折线（#FF6B7A）
      - 折线下渐变填充（从粉到透明）
      - 右侧 y 轴 bpm，横轴 MM:SS（相对训练开始）
      - 顶部显示心率范围 + 平均心率
    """
    if not heart_rate_data:
        return
    _setup_chinese_font()

    times = [d.timestamp for d in heart_rate_data]
    bpms = [d.bpm for d in heart_rate_data]
    bpm_min = min(bpms)
    bpm_max = max(bpms)
    bpm_avg = sum(bpms) / len(bpms)

    # ── 配色（深色主题）──
    bg_color = "#171922"
    grid_color = "#2A2D3A"
    line_color = "#FF6B7A"
    fill_color = "#FF6B7A"
    text_color_strong = "#FFFFFF"
    text_color_muted = "#9BA1AE"

    fig, ax = plt.subplots(figsize=(14, 4.5))
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    # ── 折线 + 渐变填充 ──
    ax.plot(times, bpms, color=line_color, linewidth=1.5, zorder=3)
    # 渐变填充：从底部到曲线的渐变，从 fill_color 渐变到透明
    # 用 fill_between + 多层 alpha 模拟渐变
    ax.fill_between(times, bpms, min(bpm_min - 5, 50), color=fill_color, alpha=0.12, zorder=2)
    ax.fill_between(times, bpms, min(bpm_min - 5, 50),
                    where=[True] * len(times),
                    color=fill_color, alpha=0.08, zorder=2)

    # ── 坐标轴样式 ──
    # y 轴范围：心率 20-220 比较通用
    y_low = max(20, bpm_min - 20)
    y_high = min(220, bpm_max + 20)
    ax.set_ylim(y_low, y_high)
    ax.set_xlim(times[0], times[-1])

    # y 轴刻度移到右侧
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    # 选 4-5 个均匀的 y 轴刻度
    y_ticks = [round(y_low / 10) * 10]
    step = max(20, int((y_high - y_low) / 4 / 10) * 10)
    while y_ticks[-1] + step <= y_high:
        y_ticks.append(y_ticks[-1] + step)
    ax.set_yticks(y_ticks)
    ax.tick_params(axis="y", colors=text_color_muted, labelsize=10, length=0)

    # x 轴显示 MM:SS
    def _fmt_mmss(value, _pos):
        v = max(0, int(round(value)))
        return f"{v // 60:d}:{v % 60:02d}"
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_mmss))
    ax.tick_params(axis="x", colors=text_color_muted, labelsize=10, length=0, pad=8)

    # 网格
    ax.grid(True, axis="y", color=grid_color, linewidth=0.8, alpha=0.6)
    ax.set_axisbelow(True)

    # 隐藏 spines
    for sp in ax.spines.values():
        sp.set_visible(False)

    # ── 顶部信息条：心率范围 + 平均 ──
    info_y = 1.18
    ax.text(0.0, info_y + 0.07, f"{bpm_min}–{bpm_max}",
            transform=ax.transAxes, fontsize=28, fontweight="bold",
            color=text_color_strong, ha="left", va="bottom")
    ax.text(0.13, info_y + 0.10, "次/分钟",
            transform=ax.transAxes, fontsize=11,
            color=text_color_muted, ha="left", va="bottom")
    ax.text(0.0, info_y, "心率范围",
            transform=ax.transAxes, fontsize=10,
            color=text_color_muted, ha="left", va="bottom")

    ax.text(0.48, info_y + 0.07, f"{bpm_avg:.0f}",
            transform=ax.transAxes, fontsize=28, fontweight="bold",
            color=text_color_strong, ha="left", va="bottom")
    ax.text(0.55, info_y + 0.10, "次/分钟",
            transform=ax.transAxes, fontsize=11,
            color=text_color_muted, ha="left", va="bottom")
    ax.text(0.48, info_y, "平均心率",
            transform=ax.transAxes, fontsize=10,
            color=text_color_muted, ha="left", va="bottom")

    plt.subplots_adjust(top=0.72, bottom=0.10, left=0.04, right=0.93)
    plt.savefig(out_path, dpi=120, facecolor=bg_color)
    plt.close(fig)


def plot_hr_zones(zones: list[HeartRateZone], out_path: Path) -> None:
    """画心率区间堆叠柱：横轴=占比%，每个区间一个色段。"""
    if not zones:
        return
    _setup_chinese_font()

    zone_colors = {z[0]: z[4] for z in config.HR_ZONES}

    fig, ax = plt.subplots(figsize=(12, 2.2))
    left = 0.0
    for z in zones:
        if z.percentage <= 0:
            continue
        color = zone_colors.get(z.zone, "#9CA3AF")
        ax.barh(y=0, width=z.percentage, left=left, height=0.6,
                color=color, edgecolor="white", linewidth=1.5)
        if z.percentage >= 5:
            m, s = divmod(z.durationSeconds, 60)
            ax.text(left + z.percentage / 2, 0,
                    f"{z.displayName}\n{z.percentage}% · {m}:{s:02d}",
                    ha="center", va="center", color="white",
                    fontsize=9.5, fontweight="bold")
        left += z.percentage

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines[:].set_visible(False)
    ax.set_title("心率区间分布", fontsize=13, fontweight="bold", pad=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
