"""
visualize_experiments.py
------------------------
读取 9 组实验结果，渲染训练时间线对比图。

布局：3 行（fps 设置）× 3 列（模型）
每个色块：【过渡】灰 / 【休息】粉 / 【具体锻炼动作】各自颜色

输出：
  output/timeline_comparison.png   — 3×3 对比大图
  output/{exp_id}/timeline.png     — 各实验单独小图
"""

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec

# ── CJK 字体 ─────────────────────────────────────────────────────────────
def _find_cjk():
    avail = {f.name for f in fm.fontManager.ttflist}
    for name in ("Microsoft YaHei", "SimHei", "PingFang SC",
                 "Noto Sans CJK SC", "WenQuanYi Micro Hei"):
        if name in avail:
            return name
    return None

_cjk = _find_cjk()
if _cjk:
    matplotlib.rcParams["font.family"] = _cjk
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 路径 / 实验矩阵 ────────────────────────────────────────────────────────
OUTPUT_BASE = Path(r"D:\WorkPath\fitness\perception_service\pose\output")

FPS_LABELS   = ["2fps", "1fps", "0.33fps"]
MODEL_NAMES  = ["flash", "lite", "g3flash", "claude"]
MODEL_DISPLAY = {
    "flash":   "Gemini 3.5 Flash",
    "lite":    "Gemini 3.1 Flash Lite",
    "g3flash": "Gemini 3 Flash Preview",
    "claude":  "Claude Sonnet 4.5",
}

# ── 颜色规则（子串匹配，顺序即优先级）────────────────────────────────────
STATUS_COLORS = {
    "transition": "#AAAAAA",
    "rest":       "#F4AABB",
}

MOVEMENT_RULES = [
    # 有氧
    ("跑步",   "#E53935"),
    ("慢跑",   "#E53935"),
    ("快走",   "#FF7043"),
    ("椭圆",   "#FF8F00"),
    # 腿部
    ("深蹲",   "#9C27B0"),
    ("腿屈伸", "#FF9800"),
    ("腿弯举", "#FB8C00"),
    ("硬拉",   "#6D4C41"),
    # 背部
    ("引体",   "#1E88E5"),
    ("划船",   "#00ACC1"),
    ("悬垂",   "#1565C0"),
    # 胸部
    ("卧推",   "#00897B"),
    # 肩部
    ("推举",   "#F4511E"),
    # 核心
    ("核心",   "#8BC34A"),
    ("举腿",   "#558B2F"),
    # 史密斯（无具体动作时）
    ("史密斯", "#9C27B0"),
]
DEFAULT_EX_COLOR = "#4CAF50"


def _movement_color(name: str) -> str:
    for kw, color in MOVEMENT_RULES:
        if kw in name:
            return color
    return DEFAULT_EX_COLOR


# ── 数据读取 ──────────────────────────────────────────────────────────────

def _seg_status(seg: dict) -> str:
    """兼容 status / phase 字段名。"""
    return seg.get("status") or seg.get("phase") or "transition"


def _movement_name(pose_data: dict) -> str:
    """
    从不一致的 pose_data 字段名中提取动作名称。
    支持顶层及嵌套结构（Claude: recognition.exerciseName；
    Lite: exercise_analysis.identifiedExercise 等）。
    """
    _EXERCISE_KEYS = (
        "movementName", "exerciseName", "exercise_name", "exercise",
        "movement", "actionName",
        "identifiedExercise", "recognizedExercise",
    )

    def _search(obj: dict, depth: int = 0) -> str | None:
        if not isinstance(obj, dict) or depth > 4:
            return None
        # 先检查当前层的直接字段
        for key in _EXERCISE_KEYS:
            val = obj.get(key)
            if val and isinstance(val, str) and val not in ("unknown", "Unknown", ""):
                return val
        # 再递归进入嵌套 dict 值
        for v in obj.values():
            if isinstance(v, dict):
                result = _search(v, depth + 1)
                if result:
                    return result
        return None

    return _search(pose_data) or "运动"


def load_experiment(exp_id: str) -> tuple[list[dict], list[dict]]:
    """返回 (period_segments, pose_results)，文件缺失时返回空列表。"""
    exp_dir = OUTPUT_BASE / exp_id
    segments: list[dict] = []
    pose_results: list[dict] = []

    p = exp_dir / "period_result.json"
    if p.exists():
        try:
            segments = json.loads(p.read_text(encoding="utf-8")).get("segments", [])
        except Exception:
            pass

    p = exp_dir / "pose_result.json"
    if p.exists():
        try:
            pose_results = json.loads(p.read_text(encoding="utf-8")).get("results", [])
        except Exception:
            pass

    return segments, pose_results


def build_labeled_segments(segments: list[dict],
                            pose_results: list[dict]) -> list[dict]:
    """
    给每个 period 段附加显示标签和颜色。
    exercise 段：按时间重叠从 pose_results 查找动作名。
    """
    labeled = []
    for seg in segments:
        status = _seg_status(seg)
        t_s    = float(seg.get("startTime", 0))
        t_e    = float(seg.get("endTime",   0))

        if status == "transition":
            label, color = "过渡", STATUS_COLORS["transition"]
        elif status == "rest":
            label, color = "休息", STATUS_COLORS["rest"]
        else:
            # exercise：找最大重叠的 pose 结果
            best_name, best_overlap = "运动", 0.0
            for pr in pose_results:
                p_s = float(pr.get("startTime", 0))
                p_e = float(pr.get("endTime",   0))
                overlap = min(t_e, p_e) - max(t_s, p_s)
                if overlap > best_overlap:
                    mv = _movement_name(pr.get("pose_data", {}))
                    best_name, best_overlap = mv, overlap
            label = best_name
            color = _movement_color(label)

        labeled.append({
            "startTime": t_s,
            "endTime":   t_e,
            "duration":  t_e - t_s,
            "status":    status,
            "label":     label,
            "color":     color,
        })
    return labeled


def fmt_time(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


# ── 单行时间线绘制 ────────────────────────────────────────────────────────

def draw_row(ax, labeled_segs: list[dict], total_dur: float,
             show_xaxis: bool = False, row_title: str = "") -> dict[str, str]:
    """
    在 ax 上绘制一行时间线（线性比例）。
    返回 {label: color} 用于汇总图例。
    """
    ax.set_facecolor("white")
    ax.set_xlim(0, total_dur)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.spines[["top", "left", "right"]].set_visible(False)
    ax.spines["bottom"].set_color("#DDDDDD")

    if not labeled_segs:
        ax.text(total_dur / 2, 0, "无数据", ha="center", va="center",
                fontsize=9, color="#AAAAAA")
        ax.set_xticks([])
        return {}

    BAR_H = 0.55
    seen: dict[str, str] = {}

    for seg in labeled_segs:
        dur   = seg["duration"]
        x0    = seg["startTime"]
        color = seg["color"]
        label = seg["label"]

        ax.barh(0, dur, left=x0, height=BAR_H,
                color=color, edgecolor="white", linewidth=0.8)
        seen[label] = color

        # 文字标签（宽度占比 ≥ 6% 时显示在块内）
        rel_w = dur / total_dur if total_dur > 0 else 0
        if rel_w >= 0.06:
            fontsize = 9 if rel_w >= 0.12 else 7
            ax.text(x0 + dur / 2, 0, label,
                    ha="center", va="center",
                    fontsize=fontsize, color="white", fontweight="bold",
                    clip_on=True)

    # X 轴刻度
    if show_xaxis:
        step = 30 if total_dur <= 300 else 60
        ticks = list(range(0, int(total_dur) + 1, step))
        if ticks and ticks[-1] < total_dur:
            ticks.append(int(total_dur))
        ax.set_xticks(ticks)
        ax.set_xticklabels([fmt_time(t) for t in ticks], fontsize=8)
        ax.tick_params(axis="x", colors="#666666", pad=2, length=3)
    else:
        ax.set_xticks([])

    return seen


# ── 单实验独立图 ──────────────────────────────────────────────────────────

def save_individual(exp_id: str, labeled_segs: list[dict], total_dur: float,
                    model_display: str, fps_label: str) -> None:
    fig, ax = plt.subplots(figsize=(14, 1.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    seen = draw_row(ax, labeled_segs, total_dur, show_xaxis=True)

    ax.set_title(f"训练时间线  [{exp_id}]  {model_display} / {fps_label}",
                 fontsize=12, fontweight="bold", pad=8)
    ax.set_xlabel("时间", fontsize=9, color="#555555")

    if seen:
        patches = [mpatches.Patch(color=c, label=l) for l, c in seen.items()]
        ax.legend(handles=patches, loc="upper center",
                  bbox_to_anchor=(0.5, -0.55),
                  ncol=min(len(patches), 8),
                  frameon=False, fontsize=9)

    plt.tight_layout()
    out = OUTPUT_BASE / exp_id / "timeline.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] {out}")


# ── 3×3 对比大图 ──────────────────────────────────────────────────────────

def save_comparison(all_data: dict) -> None:
    """
    all_data: {exp_id: {"labeled": [...], "total": float}}
    """
    n_rows = len(FPS_LABELS)
    n_cols = len(MODEL_NAMES)

    # 每组实验统一用同一个 total_dur（取全局最大，保持 x 轴对齐）
    global_dur = max(
        (v["total"] for v in all_data.values() if v["total"] > 0),
        default=300.0,
    )

    ROW_H    = 1.5   # 每行高度（英寸）
    HEADER_H = 0.5   # 列标题预留
    LEGEND_H = 0.7   # 底部图例预留
    FIG_W    = 16

    fig_h = ROW_H * n_rows + HEADER_H + LEGEND_H
    fig = plt.figure(figsize=(FIG_W, fig_h), facecolor="white")

    # GridSpec: 留出顶部 header 行和底部 legend 区域
    gs = GridSpec(
        n_rows, n_cols,
        figure=fig,
        top=1 - HEADER_H / fig_h,
        bottom=LEGEND_H / fig_h,
        left=0.07, right=0.99,
        hspace=0.10, wspace=0.03,
    )

    all_seen: dict[str, str] = {}

    for row, fps_label in enumerate(FPS_LABELS):
        for col, model_name in enumerate(MODEL_NAMES):
            exp_id = f"30K_{fps_label}_{model_name}"
            ax = fig.add_subplot(gs[row, col])
            data = all_data.get(exp_id, {"labeled": [], "total": global_dur})

            is_bottom = (row == n_rows - 1)
            seen = draw_row(ax, data["labeled"], global_dur, show_xaxis=is_bottom)
            all_seen.update(seen)

            # 列标题（第一行）
            if row == 0:
                ax.set_title(MODEL_DISPLAY[model_name],
                             fontsize=10, fontweight="bold", pad=6)

            # 行标签（最左列）
            if col == 0:
                ax.set_ylabel(fps_label, fontsize=10, fontweight="bold",
                              rotation=0, ha="right", va="center",
                              labelpad=8)

            # 无数据时显示灰底提示
            if not data["labeled"]:
                ax.set_facecolor("#F5F5F5")

    # 主标题
    fig.text(0.5, 1 - 0.12 / fig_h,
             "训练时间线  ·  实验结果对比",
             ha="center", va="top",
             fontsize=14, fontweight="bold")

    # 图例（底部居中）
    # 固定顺序：先 status 类，再按 MOVEMENT_RULES 顺序
    legend_order = ["过渡", "休息"] + [
        l for _, _ in MOVEMENT_RULES
        for l, c in all_seen.items()
        if _ in l          # 宽松匹配
    ]
    # 简单去重保序
    seen_set: set[str] = set()
    ordered_patches = []
    for label in ["过渡", "休息"] + list(all_seen.keys()):
        if label in all_seen and label not in seen_set:
            ordered_patches.append(
                mpatches.Patch(color=all_seen[label], label=label)
            )
            seen_set.add(label)

    fig.legend(
        handles=ordered_patches,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.0),
        ncol=min(len(ordered_patches), 9),
        frameon=False,
        fontsize=9,
        columnspacing=1.2,
    )

    out = OUTPUT_BASE / "timeline_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"\n[OK] 对比图已保存: {out}")


# ── 入口 ──────────────────────────────────────────────────────────────────

def main() -> None:
    print("读取实验数据...")
    all_data: dict[str, dict] = {}

    for fps_label in FPS_LABELS:
        for model_name in MODEL_NAMES:
            exp_id = f"30K_{fps_label}_{model_name}"
            segs, pose = load_experiment(exp_id)
            labeled    = build_labeled_segments(segs, pose)
            total      = max((s["endTime"] for s in segs), default=0.0)

            n_ex  = sum(1 for s in labeled if s["status"] not in ("transition", "rest"))
            n_tr  = sum(1 for s in labeled if s["status"] == "transition")
            n_rs  = sum(1 for s in labeled if s["status"] == "rest")
            print(f"  {exp_id:<28}  total={total:.0f}s  "
                  f"exercise={n_ex} transition={n_tr} rest={n_rs}")

            all_data[exp_id] = {"labeled": labeled, "total": total}

            if labeled:
                save_individual(
                    exp_id, labeled, total,
                    MODEL_DISPLAY.get(model_name, model_name),
                    fps_label,
                )

    print("\n生成对比图...")
    save_comparison(all_data)
    print("完成！")


if __name__ == "__main__":
    main()
