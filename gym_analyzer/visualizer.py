"""Generate training timeline and summary charts from Gemini segments.

Outputs saved to gym_analyzer/results/<date>_timeline.png
                              gym_analyzer/results/<date>_summary.png
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from . import config

# ── Chinese font setup ────────────────────────────────────────────────────────
_CN_FONTS = ["Microsoft YaHei", "SimHei", "DengXian", "Arial Unicode MS",
             "PingFang SC", "Noto Sans CJK SC"]


def _setup_font():
    from matplotlib import rcParams
    rcParams["font.sans-serif"] = _CN_FONTS + list(rcParams.get("font.sans-serif", []))
    rcParams["axes.unicode_minus"] = False


# ── Segment coloring ──────────────────────────────────────────────────────────
_REST_COLOR       = "#FECACA"   # light red
_TRANSITION_COLOR = "#D1D5DB"   # gray

# exercise_name keyword → color
_EXERCISE_COLORS: list[tuple[str, str]] = [
    # cardio (red/orange)
    ("跑步",   "#EF4444"), ("椭圆",  "#F97316"), ("单车",  "#F59E0B"),
    ("划船机", "#14B8A6"),
    # legs (orange)
    ("深蹲",   "#EA580C"), ("腿举",  "#C2410C"), ("硬拉",  "#9A3412"),
    ("箭步",   "#FB923C"),
    # chest/push (blue)
    ("卧推",   "#3B82F6"), ("推举",  "#2563EB"), ("夹胸",  "#1D4ED8"),
    ("飞鸟",   "#60A5FA"), ("俯卧撑","#93C5FD"),
    # back/pull (green)
    ("下拉",   "#10B981"), ("划船",  "#059669"), ("引体",  "#047857"),
    ("硬拉",   "#065F46"),
    # shoulders
    ("侧平举", "#8B5CF6"), ("推肩",  "#7C3AED"),
    # arms
    ("弯举",   "#6366F1"), ("下压",  "#4338CA"), ("三头",  "#4F46E5"),
    # core
    ("卷腹",   "#EC4899"), ("支撑",  "#DB2777"), ("举腿",  "#BE185D"),
    # stretch/other
    ("拉伸",   "#94A3B8"),
]
_DEFAULT_EXERCISE_COLOR = "#64748B"


def _seg_color(seg: dict) -> str:
    t = seg.get("type", "")
    if t == "rest":
        return _REST_COLOR
    if t == "transition":
        return _TRANSITION_COLOR
    name = seg.get("exercise_name", "")
    for kw, color in _EXERCISE_COLORS:
        if kw in name:
            return color
    return _DEFAULT_EXERCISE_COLOR


def _fmt_mmss(value, _pos):
    v = max(0, int(round(value)))
    return f"{v // 60}:{v % 60:02d}"


# ── Main draw functions ───────────────────────────────────────────────────────

def plot_timeline(segments: list[dict], total_sec: float, out_path: Path) -> None:
    """Horizontal coloured-bar timeline — one bar per segment."""
    _setup_font()
    fig, ax = plt.subplots(figsize=(15, 2.8))

    min_label = total_sec * 0.04  # don't label very short segments

    for seg in segments:
        start = float(seg.get("start_sec", 0))
        end   = float(seg.get("end_sec", start))
        dur   = end - start
        if dur <= 0:
            continue
        color = _seg_color(seg)
        ax.barh(0, dur, left=start, height=1.0,
                color=color, edgecolor="white", linewidth=0.6)

        if dur >= min_label:
            t = seg.get("type", "")
            if t == "exercise":
                label = seg.get("exercise_name", "运动")
                sets  = seg.get("sets_count", "")
                reps  = seg.get("reps_estimate", "")
                if sets and reps:
                    label += f"\n{sets}组×{reps}次"
            elif t == "rest":
                label = f"休息\n{int(dur)}s"
            else:
                label = "过渡"
            ax.text(start + dur / 2, 0, label,
                    ha="center", va="center",
                    fontsize=7.5, color="white", fontweight="bold",
                    linespacing=1.3)

    ax.set_xlim(0, total_sec)
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xlabel("时间 (分:秒)", fontsize=10)
    ax.set_title("训练时间线", fontsize=13, fontweight="bold", pad=12)
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_mmss))

    # Legend
    seen: dict[str, str] = {}
    for seg in segments:
        t = seg.get("type", "")
        if t == "exercise":
            key = seg.get("exercise_name", "运动")
        elif t == "rest":
            key = "休息"
        else:
            key = "过渡"
        if key not in seen:
            seen[key] = _seg_color(seg)

    handles = [Patch(facecolor=c, label=n) for n, c in seen.items()]
    ax.legend(handles=handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.5),
              ncol=min(len(handles), 7),
              frameon=False, fontsize=8.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_summary(segments: list[dict], total_sec: float,
                 calories: float, out_path: Path) -> None:
    """Two-panel summary: time breakdown bar + exercise duration bars."""
    _setup_font()
    fig, axes = plt.subplots(1, 2, figsize=(14, 4))

    # ── Left: exercise / rest / transition time breakdown ────────────────────
    ax = axes[0]
    buckets = {"运动": 0.0, "休息": 0.0, "过渡": 0.0}
    for seg in segments:
        dur = float(seg.get("end_sec", 0)) - float(seg.get("start_sec", 0))
        t   = seg.get("type", "")
        if t == "exercise":
            buckets["运动"] += dur
        elif t == "rest":
            buckets["休息"] += dur
        else:
            buckets["过渡"] += dur

    colors = {"运动": "#3B82F6", "休息": _REST_COLOR, "过渡": _TRANSITION_COLOR}
    left = 0.0
    for label, dur in buckets.items():
        if dur <= 0:
            continue
        pct = dur / total_sec * 100
        ax.barh(0, dur, left=left, height=0.5, color=colors[label],
                edgecolor="white", linewidth=1)
        if pct >= 8:
            ax.text(left + dur / 2, 0, f"{label}\n{int(dur // 60)}m{int(dur % 60):02d}s",
                    ha="center", va="center", fontsize=8, color="white", fontweight="bold")
        left += dur

    ax.set_xlim(0, total_sec)
    ax.set_ylim(-0.4, 0.4)
    ax.set_yticks([])
    ax.set_xlabel("时间 (分:秒)", fontsize=9)
    ax.set_title("时间分布", fontsize=11, fontweight="bold")
    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_mmss))
    total_min = total_sec / 60
    ax.set_xlabel(
        f"总时长 {int(total_min)}分{int(total_sec % 60):02d}秒  |  "
        f"消耗 {int(calories)} kcal", fontsize=9)

    # ── Right: per-exercise duration bar chart ───────────────────────────────
    ax2 = axes[1]
    ex_dur: dict[str, float] = {}
    for seg in segments:
        if seg.get("type") != "exercise":
            continue
        name = seg.get("exercise_name", "未知")
        dur  = float(seg.get("end_sec", 0)) - float(seg.get("start_sec", 0))
        ex_dur[name] = ex_dur.get(name, 0) + dur

    if ex_dur:
        names  = list(ex_dur.keys())
        durs   = [ex_dur[n] for n in names]
        colors2 = [_seg_color({"type": "exercise", "exercise_name": n}) for n in names]
        y = range(len(names))
        bars = ax2.barh(list(y), durs, color=colors2, edgecolor="white", linewidth=0.5)
        ax2.set_yticks(list(y))
        ax2.set_yticklabels(names, fontsize=9)
        ax2.set_xlabel("时长 (秒)", fontsize=9)
        ax2.set_title("各动作时长", fontsize=11, fontweight="bold")
        for bar, dur in zip(bars, durs):
            ax2.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                     f"{int(dur)}s", va="center", fontsize=8, color="#374151")
    else:
        ax2.text(0.5, 0.5, "无运动段", ha="center", va="center",
                 transform=ax2.transAxes, fontsize=12, color="#9CA3AF")
        ax2.set_title("各动作时长", fontsize=11, fontweight="bold")

    plt.tight_layout(pad=2.0)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ── Tool function ─────────────────────────────────────────────────────────────

def generate_charts(segments_result: dict, dashboard: dict,
                    date_str: str | None = None) -> dict:
    """Generate timeline + summary PNG charts and save to results folder.

    Called as an agent tool after compute_dashboard.
    Returns paths of saved files.
    """
    from datetime import date as _date
    date_str   = date_str or dashboard.get("date") or _date.today().isoformat()
    segments   = segments_result.get("segments", [])
    total_sec  = float(segments_result.get("video_duration_sec", 0))
    calories   = float(dashboard.get("daily", {}).get("calories", 0))

    if not segments or total_sec <= 0:
        return {"error": "No segments or zero duration", "files": []}

    out_dir = config.RESULTS_DIR
    tl_path  = out_dir / f"{date_str}_timeline.png"
    sum_path = out_dir / f"{date_str}_summary.png"

    try:
        plot_timeline(segments, total_sec, tl_path)
        plot_summary(segments, total_sec, calories, sum_path)
        return {
            "timeline": str(tl_path),
            "summary":  str(sum_path),
            "status":   "ok",
        }
    except Exception as e:
        return {"error": str(e), "status": "failed"}
