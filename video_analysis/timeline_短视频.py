"""生成短视频训练时间线图，风格参照 dashboard 样式。"""

import json
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from pathlib import Path

# ── 字体（支持中文）─────────────────────────────────────────────
def _find_cjk_font():
    candidates = [
        "Microsoft YaHei", "SimHei", "PingFang SC",
        "Noto Sans CJK SC", "WenQuanYi Micro Hei",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None

cjk = _find_cjk_font()
if cjk:
    matplotlib.rcParams["font.family"] = cjk
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 数据路径 ────────────────────────────────────────────────────
BASE   = Path(r"D:\WorkPath\fitness\video_analysis\短视频_results")
OUTPUT = BASE / "timeline_短视频.png"

# ── 颜色映射（关键词子串匹配，顺序即优先级）────────────────────
COLOR_RULES = [
    # status
    ("transition", "#AAAAAA"),
    ("rest",       "#F4AABB"),
    # 有氧
    ("跑步",       "#E53935"),
    ("慢跑",       "#E53935"),
    ("快走",       "#FF7043"),
    ("椭圆",       "#FF8F00"),
    # 腿部
    ("深蹲",       "#9C27B0"),
    ("腿屈伸",     "#FF9800"),
    ("腿弯举",     "#FB8C00"),
    # 背部
    ("引体向上",   "#1E88E5"),
    ("划船",       "#00ACC1"),
    ("悬垂",       "#1565C0"),
    # 胸部
    ("卧推",       "#00897B"),
    # 肩部
    ("推举",       "#F4511E"),
    # 核心
    ("核心",       "#8BC34A"),
    ("举腿",       "#558B2F"),
    # 默认运动
    ("exercise",   "#4CAF50"),
]

def get_color(label: str, status: str) -> str:
    """子串匹配：label 优先，status 兜底。"""
    for keyword, color in COLOR_RULES:
        if keyword in label or keyword in status:
            return color
    return "#777777"

LABEL_MAP = {
    "transition": "过渡",
    "rest":       "休息",
}


def _status(seg):
    return (seg.get("status") or seg.get("event")
            or seg.get("state") or seg.get("type") or "transition")


def load_data():
    with open(BASE / "period_result_v2.json", encoding="utf-8") as f:
        period = json.load(f)
    with open(BASE / "pose_result_v2.json", encoding="utf-8") as f:
        pose = json.load(f)

    # 构建 exercise 段 → 动作名映射（兼容 v2 字段结构）
    exercise_map = {}
    for seg in pose.get("results", []):
        pd = seg.get("pose_data", {})
        # v2: pose_data 是 dict
        if isinstance(pd, dict):
            movement = (pd.get("exercise") or pd.get("movementName")
                        or pd.get("exerciseName") or "未知动作")
        elif isinstance(pd, list) and pd:
            movement = (pd[0].get("movementName") or pd[0].get("exercise") or "未知动作")
        else:
            movement = "未知动作"
        exercise_map[(seg["startTime"], seg["endTime"])] = movement

    # period_result_v2: result 字段内有 segments
    raw_result = period.get("result", period)
    raw_segs   = raw_result.get("segments", []) if isinstance(raw_result, dict) else raw_result

    segments = []
    for raw_seg in raw_segs:
        t_start = raw_seg.get("startTime", 0)
        t_end   = raw_seg.get("endTime",   0)
        status  = _status(raw_seg)

        if status == "exercise":
            # 优先：period 段本身携带的 exerciseName（有训练计划上下文）
            label = (raw_seg.get("exerciseName") or raw_seg.get("movementName") or None)
            # 备用：pose 识别结果
            if not label:
                for (s, e), mv in exercise_map.items():
                    if abs(s - t_start) < 3 and abs(e - t_end) < 3:
                        label = mv
                        break
            label = label or "运动"
        else:
            label = LABEL_MAP.get(status, status)

        color = get_color(label, status)
        segments.append({
            "start":  t_start,
            "end":    t_end,
            "dur":    t_end - t_start,
            "label":  label,
            "color":  color,
            "status": status,
        })
    return segments, period.get("total_frames", 582)


def fmt_time(sec):
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def draw(segments, total_frames):
    total_dur = segments[-1]["end"] if segments else 300
    fig, ax = plt.subplots(figsize=(14, 1.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    BAR_H = 0.55

    # ── 视觉宽度分配策略 ──────────────────────────────────────
    # 过渡/休息：每段固定占总视觉宽度的 8%
    # 运动段：按实际时长比例分配剩余 (1 - n_bg*8%) 空间
    TOTAL_VIS   = 100.0   # 归一化为 100 个单位
    BG_VIS_EACH = 8.0     # 每个过渡/休息段固定 8 个单位

    n_bg  = sum(1 for s in segments if s["status"] in ("transition", "rest"))
    n_ex  = len(segments) - n_bg
    ex_total_real = sum(s["dur"] for s in segments
                        if s["status"] not in ("transition", "rest"))
    ex_pool = max(TOTAL_VIS - n_bg * BG_VIS_EACH, n_ex * 10)  # 运动段至少各占 10

    def visual_w(seg):
        if seg["status"] in ("transition", "rest"):
            return BG_VIS_EACH
        # 运动段按真实时长比例分配 ex_pool
        frac = seg["dur"] / ex_total_real if ex_total_real else 1.0 / n_ex
        return max(frac * ex_pool, 5.0)

    # ── 绘制色块 ───────────────────────────────────────────────
    cursor = 0.0
    for seg in segments:
        vw = visual_w(seg)
        ax.barh(0, vw, left=cursor,
                height=BAR_H, color=seg["color"],
                edgecolor="white", linewidth=1.0)
        seg["_x0"]   = cursor
        seg["_vdur"] = vw
        cursor += vw
    total_visual = cursor

    # ── 文字标签 ──────────────────────────────────────────────
    MIN_LABEL_W = total_visual * 0.06
    for seg in segments:
        cx = seg["_x0"] + seg["_vdur"] / 2
        if seg["_vdur"] >= MIN_LABEL_W:
            ax.text(cx, 0, seg["label"],
                    ha="center", va="center",
                    fontsize=11, color="white", fontweight="bold")
        else:
            # 窄段：文字标在上方，带箭头
            ax.annotate(
                seg["label"],
                xy=(cx, BAR_H / 2 + 0.02), xytext=(cx, 0.6),
                ha="center", va="bottom",
                fontsize=9, color=seg["color"], fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color=seg["color"], lw=1.2),
            )

    ax.set_xlim(0, total_visual)

    # ── X 轴刻度：等间距真实时间，映射到视觉坐标 ──────────────
    total_dur = segments[-1]["end"]
    tick_step = 30 if total_dur <= 300 else 60
    real_ticks = list(range(0, int(total_dur) + 1, tick_step))
    if real_ticks[-1] < total_dur:
        real_ticks.append(int(total_dur))

    # real_time → visual_x（分段线性插值）
    r_bounds = [0.0] + [s["end"]           for s in segments]
    v_bounds = [0.0] + [s["_x0"]+s["_vdur"] for s in segments]

    def r2v(t):
        for i in range(1, len(r_bounds)):
            if t <= r_bounds[i]:
                r0, r1 = r_bounds[i-1], r_bounds[i]
                v0, v1 = v_bounds[i-1], v_bounds[i]
                return v0 + (t - r0) / (r1 - r0) * (v1 - v0) if r1 > r0 else v0
        return v_bounds[-1]

    vis_ticks = [r2v(t) for t in real_ticks]
    ax.set_xticks(vis_ticks)
    ax.set_xticklabels([fmt_time(t) for t in real_ticks], fontsize=9)

    # ── 样式 ──────────────────────────────────────────────────
    ax.set_ylim(-0.55, 0.75)
    ax.set_yticks([])
    ax.spines[["top", "left", "right"]].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(axis="x", colors="#555555", labelsize=9, pad=4)
    ax.set_title("训练时间线", fontsize=14, fontweight="bold", pad=10)

    # ── 图例：横排居中，放在 x 轴刻度下方 ────────────────────
    seen = {}
    for seg in segments:
        if seg["label"] not in seen:
            seen[seg["label"]] = seg["color"]
    patches = [mpatches.Patch(color=c, label=l) for l, c in seen.items()]
    ax.legend(
        handles=patches,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.35),
        ncol=len(patches),
        frameon=False,
        fontsize=10,
    )

    plt.tight_layout()
    fig.savefig(OUTPUT, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"已保存: {OUTPUT}")
    plt.show()


if __name__ == "__main__":
    segs, total_frames = load_data()
    print(f"共 {len(segs)} 个时间段:")
    for s in segs:
        print(f"  {fmt_time(s['start'])} ~ {fmt_time(s['end'])}  {s['label']}  ({s['dur']:.1f}s)")
    draw(segs, total_frames)
