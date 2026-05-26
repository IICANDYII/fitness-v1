"""
健身报告生成
============
输入：Extract_keyframes.py 抽出的关键帧 + frames_meta.json
处理：
  1) 调用 GPT-5识别每张关键帧的动作类型（批量、缓存）
  2) matplotlib 画动作时间轴 + 动作占比饼图
  3) 调用 GPT 写一段训练总评
输出：output/action_timeline.png, output/action_pie.png, output/report.md
依赖：openai>=1.0, python-dotenv, matplotlib
"""

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")  # 必须在 import pyplot 之前，避免 Qt/PySide 后端在无显示环境下 native crash
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import Ellipse, FancyBboxPatch, Patch, Polygon
from dotenv import load_dotenv
from openai import OpenAI


# -------------------- 配置 --------------------

ACTION_LABELS = [
    # 有氧
    "跑步", "椭圆机", "动感单车", "划船机",
    # 自由重量
    "杠铃", "哑铃", "史密斯架",
    # 悬挂 / 自重
    "引体向上", "自重训练",
    # 固定力量器械
    "高位下拉", "坐姿划船", "腿举机", "龙门架", "蝴蝶机", "推肩机",
    # 非训练
    "拉伸", "休息", "其他",
]

# 给每个标签分配固定颜色，时间轴/饼图保持一致
ACTION_COLORS = {
    # 有氧 —— 红/橙色系
    "跑步":       "#E63946",
    "椭圆机":     "#F4A261",
    "动感单车":   "#E76F51",
    "划船机":     "#2A9D8F",
    # 自由重量 —— 黄/棕色系
    "杠铃":       "#F77F00",
    "哑铃":       "#FCBF49",
    "史密斯架":   "#B85C00",
    # 悬挂 / 自重 —— 绿色系
    "引体向上":   "#06A77D",
    "自重训练":   "#52B788",
    # 固定器械 —— 蓝/紫色系
    "高位下拉":   "#118AB2",
    "坐姿划船":   "#7209B7",
    "腿举机":     "#3A0CA3",
    "龙门架":     "#90BE6D",
    "蝴蝶机":     "#FF006E",
    "推肩机":     "#C77DFF",
    # 非训练 —— 灰/浅色系
    "拉伸":       "#B8E0D2",
    "休息":       "#9D9D9D",
    "其他":       "#C0C0C0",
}

BATCH_SIZE = 8         # GPT-V 每次喂几张图
DEFAULT_VISION_MODEL = "gpt-5.5"
DEFAULT_TEXT_MODEL = "gpt-5.5"
DEFAULT_WEIGHT_KG = 70.0

# 肌肉群映射：动作 → {部位: 权重}（1.0 主练，0.5 辅助/协同）
# 仅在动作明确时贡献部位强度；杠铃/哑铃等多动作器械给"综合"标记
MUSCLE_GROUPS: dict[str, dict[str, float]] = {
    "跑步":       {"心肺": 1.0, "股四头肌": 0.6, "腘绳肌": 0.6, "小腿": 0.6, "臀部": 0.4},
    "椭圆机":     {"心肺": 1.0, "腿部综合": 0.6, "臀部": 0.4},
    "动感单车":   {"心肺": 1.0, "股四头肌": 0.8, "臀部": 0.5},
    "划船机":     {"心肺": 1.0, "背部": 0.7, "二头肌": 0.4, "腿部综合": 0.5},
    "杠铃":       {"全身综合": 1.0},  # 不知具体动作，作为通用标记
    "哑铃":       {"全身综合": 1.0},
    "史密斯架":   {"全身综合": 1.0},
    "引体向上":   {"背阔肌": 1.0, "二头肌": 0.7, "前臂": 0.5, "核心": 0.3},
    "自重训练":   {"核心": 0.8, "全身综合": 0.5},
    "高位下拉":   {"背阔肌": 1.0, "二头肌": 0.5},
    "坐姿划船":   {"背部": 1.0, "二头肌": 0.5, "后束三角肌": 0.4},
    "腿举机":     {"股四头肌": 1.0, "臀部": 0.7, "腘绳肌": 0.4},
    "龙门架":     {"全身综合": 1.0},
    "蝴蝶机":     {"胸部": 1.0, "前束三角肌": 0.3},
    "推肩机":     {"三角肌": 1.0, "三头肌": 0.6},
    "拉伸":       {"柔韧": 1.0},
    "休息":       {},
    "其他":       {},
}


# MET（代谢当量）表 —— 估算 kcal = MET × 体重kg × 时长h
# 数据来源：2011 Compendium of Physical Activities，取健身房常见动作中等强度值
MET_TABLE = {
    # 有氧
    "跑步":       9.0,   # 中速跑步机
    "椭圆机":     5.0,
    "动感单车":   6.8,   # 中等阻力
    "划船机":     7.0,
    # 自由重量
    "杠铃":       6.0,   # 力量训练，中高强度
    "哑铃":       5.0,
    "史密斯架":   5.5,
    # 悬挂 / 自重
    "引体向上":   8.0,
    "自重训练":   3.8,   # 俯卧撑/卷腹/平板平均
    # 固定器械
    "高位下拉":   5.0,
    "坐姿划船":   4.5,
    "腿举机":     5.5,
    "龙门架":     4.5,
    "蝴蝶机":     4.5,
    "推肩机":     5.0,
    # 非训练
    "拉伸":       2.3,
    "休息":       1.3,
    "其他":       3.0,
}


@dataclass
class Paths:
    """所有产物都放在帧目录里（= video.parent / video.stem）。"""
    video: Path
    frames_dir: Path

    @property
    def actions_json(self) -> Path:
        return self.frames_dir / "actions.json"

    @property
    def timeline_png(self) -> Path:
        return self.frames_dir / "action_timeline.png"

    @property
    def pie_png(self) -> Path:
        return self.frames_dir / "action_pie.png"

    @property
    def muscle_body_png(self) -> Path:
        return self.frames_dir / "muscle_body.png"

    @property
    def report_md(self) -> Path:
        return self.frames_dir / "report.md"


# -------------------- 输入扫描 --------------------

FRAME_NAME_RE = re.compile(r"^state(\d+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.png$")


def discover_frames(video_path: Path) -> tuple[Path, list[dict], dict]:
    """从视频路径反推帧目录，扫描 state*.png，返回 (frames_dir, frames, meta)。

    每个 frame: {n, filename, timestamp_s}
    timestamp_s 用 (n-1) × interval 计算，interval 自相邻两帧 datetime 差推断。
    meta 兼容旧版 frames_meta.json 结构：{video_path, video_info: {...}}
    """
    frames_dir = video_path.parent / video_path.stem
    if not frames_dir.is_dir():
        raise FileNotFoundError(
            f"找不到帧目录：{frames_dir}\n请先跑：python extract_keyframes.py {video_path.name}"
        )

    parsed: list[tuple[int, datetime, str]] = []
    for p in frames_dir.glob("state*.png"):
        m = FRAME_NAME_RE.match(p.name)
        if not m:
            continue
        parsed.append((
            int(m.group(1)),
            datetime.strptime(m.group(2), "%Y-%m-%d_%H-%M-%S"),
            p.name,
        ))
    if not parsed:
        raise FileNotFoundError(f"{frames_dir} 下没有 state*.png")

    parsed.sort(key=lambda x: x[0])

    # 推抽帧间隔：用相邻两帧 datetime 差；只 1 帧时回退到 1 秒
    if len(parsed) >= 2:
        interval = (parsed[1][1] - parsed[0][1]).total_seconds() or 1.0
    else:
        interval = 1.0

    frames = [
        {"n": n, "filename": fname, "timestamp_s": round((n - 1) * interval, 2)}
        for n, _ts, fname in parsed
    ]

    # 视频信息（cv2 直接读）
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video_path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    duration_s = total_frames / src_fps if src_fps > 0 else frames[-1]["timestamp_s"] + interval

    meta = {
        "video_path": str(video_path),
        "video_info": {
            "width": width,
            "height": height,
            "src_fps": round(src_fps, 2),
            "duration_s": round(duration_s, 2),
            "total_frames": total_frames,
            "frame_interval_s": interval,
            "frame_count_extracted": len(frames),
        },
    }
    return frames_dir, frames, meta


def compute_motion(frames: list[dict], frames_dir: Path) -> None:
    """给每个 frame 注入 motion 字段：相对前一帧的灰度 absdiff 均值（0-255）。

    用途：作为 GPT-V 的辅助信号 —— motion 高 → 拍摄者/器械正在动；
         motion 低 → 静止画面（看屏幕、对着墙、休息）。

    缩到 160x90 计算，避免分辨率影响。第一帧 motion = 0.0。
    """
    prev_small = None
    for f in frames:
        img = cv2.imread(str(frames_dir / f["filename"]), cv2.IMREAD_GRAYSCALE)
        if img is None:
            f["motion"] = 0.0
            prev_small = None
            continue
        small = cv2.resize(img, (160, 90), interpolation=cv2.INTER_AREA)
        if prev_small is None:
            f["motion"] = 0.0
        else:
            diff = cv2.absdiff(small, prev_small)
            f["motion"] = round(float(diff.mean()), 2)
        prev_small = small


# -------------------- 中文字体（matplotlib 默认不支持中文） --------------------

def setup_chinese_font():
    # Windows 上常见的中文字体回退顺序
    candidates = ["Microsoft YaHei", "SimHei", "DengXian", "Arial Unicode MS"]
    rcParams["font.sans-serif"] = candidates + rcParams.get("font.sans-serif", [])
    rcParams["axes.unicode_minus"] = False


# -------------------- 数据加载 --------------------

def encode_image_b64(img_path: Path) -> str:
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# -------------------- GPT-V 动作识别 --------------------

# 每个器械的视觉线索（供 prompt 引用）
_EQUIPMENT_HINTS = {
    "跑步":       "跑步机扶手 / 跑步机控制面板 / 履带 / 速度心率显示屏",
    "椭圆机":     "椭圆形踏板 + 两侧动臂 + 中控显示屏",
    "动感单车":   "座垫 + 把手 + 大飞轮（小或无显示屏，常带阻力旋钮）",
    "划船机":     "滑轨 + 拉绳 / 拉柄 + 风轮 / 水箱 + 数显",
    "杠铃":       "杠铃杆 + 杠铃片 / 卧推架 / 深蹲架 / 杠铃架立柱",
    "哑铃":       "成对或单只哑铃 / 哑铃架（一排短把手配重）",
    "史密斯架":   "垂直双立柱 + 横杠 + 钩位卡扣（杠铃在固定轨道上）",
    "引体向上":   "引体杆 / 单杠 / 双手悬挂的画面",
    "自重训练":   "地垫 / 自重姿势（俯卧撑 / 平板支撑 / 卷腹 / 箭步蹲，无器械）",
    "高位下拉":   "座椅 + 头顶长拉杆 + 配重片",
    "坐姿划船":   "座垫 + 横向拉杆 + 滑轨",
    "腿举机":     "45° 斜板 / 踏板 / 配重",
    "龙门架":     "双立柱 + 绳索 + 滑轮 + 可调高度",
    "蝴蝶机":     "座椅 + 两侧大型扇形挡板（夹胸 / 反向夹胸）",
    "推肩机":     "座椅 + 头部两侧握把（垂直向上推）",
    "拉伸":       "地垫 / 静态拉伸姿势 / 泡沫轴 / 拉伸区",
}


def build_recognize_prompt(labels: list[str]) -> str:
    """根据"允许的标签集合"动态构造识别 prompt。

    标签集越窄，模型越倾向把可疑画面归到"其他"，避免"短时间内做了一堆不同器械"的过度切换。
    "休息" 和 "其他" 必须在 labels 里。
    """
    train_labels = [x for x in labels if x not in ("休息", "其他")]
    hints_block = "\n".join(
        f"   - {_EQUIPMENT_HINTS.get(x, x)} → \"{x}\""
        for x in train_labels
    )
    return f"""你是一名健身房动作识别助手。视频是健身者**第一视角**录制（戴在身上或手持），
画面里**通常看不到训练者本人**，主要看到的是健身房环境、器械、显示屏、对方训练者。
"画面里没人"是常态，**不要因为没人就判"其他"**。

## 本次可用的标签集（必须只从中选，不要编造、不要扩展）

{labels}

**重要**：本次训练只可能出现上面这些动作。即使你在画面中看到列表外的器械（例如哑铃、龙门架、腿举机等），
也**绝对不要标这些列表外的标签**——这些大概率是"路过看到"或"背景里的别人器械"，应当：
   - 归到列表中视觉最接近的训练标签（例如哑铃架和杠铃片接近，可归为"杠铃"附近的过渡）
   - 或者标"其他"

## 判断规则（按优先级）

1. **优先识别画面里出现的器械特征**，即使没有人也算"正在使用该器械"。允许的器械特征：
{hints_block}

2. **视觉相似器械的关键区分**（容易误判，要严格按下面判断）：
   - **杠铃 vs 史密斯架**：两者都有立柱 + 杠铃片。判史密斯架**必须看到**横杠在垂直轨道上滑动 / 锁扣 / 卡钩位置；
     只看到立柱 + 杠铃片但**没有固定轨道证据** → 标 "杠铃"（深蹲架/卧推架/普通杠铃架）。**默认偏向杠铃**。
   - **跑步机 vs 椭圆机 vs 动感单车**：
     · 跑步机：水平履带 + 控制面板（屏幕字样常含 SPEED/PACE/距离/坡度），扶手向前伸
     · 椭圆机：两侧长动臂（人手抓的把手随踩踏前后摆动），脚下是椭圆轨迹的踏板
     · 动感单车：座垫 + 把手 + 显眼飞轮，屏幕较小或无
     · 只看到"控制屏幕"分不清是哪种 → 选"跑步"（最常见）或"其他"
   - **龙门架 vs 高位下拉/坐姿划船**：龙门架是**双立柱**之间用绳索/滑轮连接；高位下拉是**单立柱**带头顶拉杆 + 座椅；
     坐姿划船是低位水平拉杆 + 座垫。只看到"绳索/拉杆"无法明确双立柱结构 → 不要随便标龙门架。
   - **引体向上的第一视角特征（非常重要，容易被错判成龙门架/椭圆机）**：
     · 画面**剧烈上下/前后晃动**（motion 通常 ≥ 40），因为身体在悬挂摆动
     · 头顶能看到**横向横杆/单杠**，可能仰视
     · 偶尔在画面里看到**镜中自己**悬挂在杆上的姿势
     · 看到上述特征 → 优先标 "引体向上"，**不要**标龙门架或椭圆机
     · 龙门架是**安静**对着双立柱看；椭圆机是**看着控制屏 + 前后摆动**；都不会镜头大幅上下颠
     · 引体杆架本身就是双立柱 + 横杆，但**身体在动而不是站着看 → 引体向上**

3. **结合 motion（帧间运动强度 0-50）辅助**：
   - motion ≥ 6 且画面有上述器械特征 → 正在使用该器械（不是"其他"）
   - motion < 2 且画面静止（对着屏幕、墙面、空场地）→ "休息"
   - motion 高但器械特征不清（走动、晃动、过渡画面）→ "其他"

4. **走廊 / 入口 / 未进入训练区 / 完全看不出场景 → "其他"**

5. **时间连续性约束（最重要）**：
   - 本批图是**连续时间线**，每张图相隔 2 秒，按顺序构成一段时间。
   - **段稳定性优先于单帧判断**：如果连续多张是同一器械，中间出现 1-2 张看起来像另一器械的图，
     **大概率是镜头扫过旁边器械（背景）**，应当**延续主导标签**，而不是切换。
   - 真实训练通常持续 10 秒以上（5+ 关键帧）。**避免**在 1-2 帧间频繁切换器械。
   - 只有看到**明显的位置切换信号**（走廊画面 / 长时间无关画面 / 完全不同的器械区）才切换标签。

6. 注意第一视角的典型画面：盯着跑步机控制屏在跑步、扛着杠铃低头看片、做引体时画面剧烈晃动 + 看到杠子，
   这些都应该标对应器械，**不要判"其他"**。

## 输出格式

输出严格的 JSON 对象 `{{"results": [...]}}`，results 数组长度等于输入图片数，顺序与输入一致。
每个元素结构：
  `{{"index": <0-based 整数>, "action": <标签>, "confidence": <0-1 浮点>, "note": <一句中文简短描述, 不超过 20 字, 说明你识别到的器械或画面要素>}}`

不要输出 JSON 之外的任何文字。"""


def recognize_batch(
    client: OpenAI,
    model: str,
    frames: list[dict],
    frames_dir: Path,
    system_prompt: str,
    labels: list[str],
) -> list[dict]:
    """对一批帧调一次 GPT-V，返回与 frames 等长的标注 list。"""
    motion_list = [f.get("motion", 0.0) for f in frames]
    intro = (
        f"这是 {len(frames)} 张关键帧（第一视角健身视频），按顺序识别每一张的动作。\n"
        f"附加：每张图的帧间运动强度 motion（相对前一帧灰度 absdiff 均值，范围 0-50，"
        f"motion ≥ 6 表示画面在动，motion < 2 表示画面静止）：\n"
        f"motion = {motion_list}\n"
        f"请结合 motion 和画面里的器械特征做判断。"
    )
    content = [{"type": "text", "text": intro}]
    for f in frames:
        b64 = encode_image_b64(frames_dir / f["filename"])
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "low",  # 降低 token 成本
            },
        })

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content
    parsed = json.loads(raw)
    # 兼容三种返回形态：
    #   1) 顶层是 list（最常见，模型偷懒）→ 直接用
    #   2) 顶层是 dict 且有 results/data 字段 → 取出
    #   3) 顶层是单个 dict → 包成单元素 list
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("results") or parsed.get("data")
        if items is None:
            items = [parsed]
    else:
        items = []

    # 按 index 排序，补齐缺失项
    out = []
    by_idx = {item.get("index", i): item for i, item in enumerate(items)}
    for i, f in enumerate(frames):
        item = by_idx.get(i, {"action": "其他", "confidence": 0.0, "note": "解析缺失"})
        action = item.get("action", "其他")
        if action not in labels:
            action = "其他"
        out.append({
            "n": f["n"],
            "timestamp_s": f["timestamp_s"],
            "filename": f["filename"],
            "motion": f.get("motion", 0.0),
            "action": action,
            "confidence": float(item.get("confidence", 0.0) or 0.0),
            "note": str(item.get("note", ""))[:40],
        })
    return out


def recognize_all(
    client: OpenAI,
    model: str,
    frames: list[dict],
    frames_dir: Path,
    system_prompt: str,
    labels: list[str],
) -> list[dict]:
    results = []
    total_batches = (len(frames) + BATCH_SIZE - 1) // BATCH_SIZE
    for bi in range(total_batches):
        batch = frames[bi * BATCH_SIZE : (bi + 1) * BATCH_SIZE]
        print(f"  [GPT-V] batch {bi+1}/{total_batches}  ({len(batch)} 张) ...", flush=True)
        annotated = recognize_batch(client, model, batch, frames_dir, system_prompt, labels)
        results.extend(annotated)
    return results


# -------------------- 可视化 --------------------

def plot_timeline(actions: list[dict], duration_s: float, out_path: Path):
    """动作时间轴：横轴时间，每个关键帧画一个垂直色块。"""
    fig, ax = plt.subplots(figsize=(12, 2.5))

    # 估计每帧覆盖的时间宽度 = 抽帧间隔
    if len(actions) >= 2:
        bar_w = actions[1]["timestamp_s"] - actions[0]["timestamp_s"]
    else:
        bar_w = 1.0

    for a in actions:
        ax.barh(
            y=0,
            width=bar_w,
            left=a["timestamp_s"],
            height=1.0,
            color=ACTION_COLORS.get(a["action"], "#CCCCCC"),
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xlim(0, max(duration_s, actions[-1]["timestamp_s"] + bar_w))
    ax.set_ylim(-0.6, 0.6)
    ax.set_yticks([])
    ax.set_xlabel("时间 (秒)")
    ax.set_title("动作时间轴")

    # 图例只显示实际出现过的标签
    present = []
    seen = set()
    for a in actions:
        if a["action"] not in seen:
            seen.add(a["action"])
            present.append(a["action"])
    legend_handles = [
        Patch(facecolor=ACTION_COLORS.get(lbl, "#CCC"), label=lbl)
        for lbl in present
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.35),
        ncol=min(len(present), 6),
        frameon=False,
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  时间轴 → {out_path}")


# 视觉相似器械组：组内标签经常被 GPT-V 在相邻帧间互换，应合并为主导标签
VISUAL_GROUPS: list[set[str]] = [
    {"杠铃", "史密斯架"},                                       # 都有立柱 + 杠铃片
    {"跑步", "椭圆机", "动感单车", "划船机"},                   # 都有"带屏幕的有氧器械"特征
    {"龙门架", "高位下拉", "坐姿划船", "引体向上"},             # 第一视角易混：双立柱 + 横杆/拉杆/绳索
]

_LABEL_TO_GROUP: dict[str, frozenset[str]] = {
    lbl: frozenset(g) for g in VISUAL_GROUPS for lbl in g
}


def consolidate_visual_groups(
    actions: list[dict],
    min_total_frames: int = 5,
    prefer_weights: dict[str, float] | None = None,
) -> tuple[list[dict], list[dict]]:
    """对相邻同视觉组的标签段做合并。

    算法：
      1) 找连续非'其他'段 [i, j)
      2) 在 [i, j) 内，按"视觉组归属"再细分为子序列（每个子序列内所有标签都属于同一视觉组）
      3) 每个子序列若帧数 >= min_total_frames 且含多标签 → 按帧数投票统一为主导标签

    这样能处理"史密斯架 → 龙门架 → 引体向上"这种跨组序列：
    史密斯架(杠铃组) 单独，龙门架+引体向上(拉力组) 合并为主导标签。

    被合并的帧 note 加 `[合并:<原>→<新>]`，置信度降到原值 × 0.8。
    """
    from collections import Counter
    out = [dict(a) for a in actions]
    n = len(out)
    log: list[dict] = []
    i = 0
    while i < n:
        if out[i]["action"] == "其他":
            i += 1
            continue
        # 连续非"其他"段 [i, j)
        j = i
        while j < n and out[j]["action"] != "其他":
            j += 1
        # 在 [i, j) 里按视觉组细分子序列
        sub_start = i
        while sub_start < j:
            sub_group = _LABEL_TO_GROUP.get(out[sub_start]["action"])
            sub_end = sub_start
            while sub_end < j and _LABEL_TO_GROUP.get(out[sub_end]["action"]) == sub_group:
                sub_end += 1
            # 子序列 [sub_start, sub_end)
            n_frames = sub_end - sub_start
            if sub_group is not None and n_frames >= min_total_frames:
                cnt = Counter(out[k]["action"] for k in range(sub_start, sub_end))
                if len(cnt) >= 2:
                    # 加权投票：prefer_weights 里的标签得到加权
                    weighted = {
                        lbl: c * (prefer_weights.get(lbl, 1.0) if prefer_weights else 1.0)
                        for lbl, c in cnt.items()
                    }
                    # 平局规则：(加权票数, 是否在 prefer 列表, 原始票数) 字典序最大获胜
                    # 这样 prefer 标签在平局时优先，仍未决时按原始票数决
                    def _vote_key(lbl: str) -> tuple:
                        return (
                            weighted[lbl],
                            1 if (prefer_weights and lbl in prefer_weights) else 0,
                            cnt[lbl],
                        )
                    dominant = max(weighted, key=_vote_key)
                    changed = 0
                    for k in range(sub_start, sub_end):
                        if out[k]["action"] != dominant:
                            orig = out[k]["action"]
                            out[k]["note"] = f"[合并:{orig}→{dominant}] {out[k]['note']}"
                            out[k]["action"] = dominant
                            out[k]["confidence"] = round(out[k].get("confidence", 0.5) * 0.8, 2)
                            changed += 1
                    if changed > 0:
                        log.append({
                            "dominant": dominant,
                            "start_s": out[sub_start]["timestamp_s"],
                            "end_s": out[sub_end - 1]["timestamp_s"],
                            "n_changed": changed,
                            "labels": dict(cnt),
                            "weighted": {k: round(v, 1) for k, v in weighted.items()} if prefer_weights else None,
                        })
            sub_start = sub_end
        i = j
    return out, log


def remove_isolated_runs(
    actions: list[dict],
    min_run: int,
    support_window: int = 3,
) -> tuple[list[dict], list[dict]]:
    """把"真正孤立"的短非'其他'段回退为'其他'。

    一个段被视为孤立 ⇔
      - 段长 < min_run（默认 3 帧 = 6 秒）
      - 且左侧 support_window 帧内、右侧 support_window 帧内都**没有相同标签的支持**
        （即没有其他帧也被判为该标签）

    这能区分两种短段：
      - "路过扫到"型：前后窗口都没该标签 → 回退到"其他"
      - "训练开头/中断"型：前/后窗口里有该标签的同伴 → 保留（后续平滑会合并）

    回退的帧 note 加 `[回退:<原标签>]` 前缀，置信度降到 min(原值, 0.4)。

    返回 (new_actions, isolated_log)。
    """
    out = [dict(a) for a in actions]
    n = len(out)
    log: list[dict] = []
    i = 0
    while i < n:
        if out[i]["action"] == "其他":
            i += 1
            continue
        cur = out[i]["action"]
        j = i
        while j < n and out[j]["action"] == cur:
            j += 1
        run_len = j - i
        if run_len < min_run:
            # 邻域支持检查：基于原始 actions（避免被本轮已回退段影响判断）
            left_start = max(0, i - support_window)
            right_end = min(n, j + support_window)
            left_supported = any(actions[k]["action"] == cur for k in range(left_start, i))
            right_supported = any(actions[k]["action"] == cur for k in range(j, right_end))
            if not (left_supported or right_supported):
                for k in range(i, j):
                    out[k]["note"] = f"[回退:{cur}] {out[k]['note']}"
                    out[k]["action"] = "其他"
                    out[k]["confidence"] = round(min(out[k].get("confidence", 0.5), 0.4), 2)
                log.append({
                    "action": cur,
                    "start_s": out[i]["timestamp_s"],
                    "end_s": out[j - 1]["timestamp_s"],
                    "n_frames": run_len,
                })
        i = j
    return out, log


# 基于 Wikimedia "1105 Anterior and Posterior Views of Muscles.jpg" (1304x3033, CC BY 4.0) 描点的肌肉群多边形。
# 每个肌肉群对应一个 list[Polygon]，每个 Polygon 是 [(x, y), ...] 像素坐标。
# 用多边形贴合肌肉外形，而不是规则椭圆覆盖。
_TEMPLATE_POLYGONS: dict[str, list[list[tuple[int, int]]]] = {
    # ============ 前面观 (y ≈ 100..1500) ============

    # 三角肌前束（双肩半月形）
    "三角肌前束": [
        [(380, 250), (470, 220), (570, 235), (610, 290), (590, 340), (510, 350), (420, 320), (385, 290)],
        [(920, 250), (830, 220), (730, 235), (690, 290), (710, 340), (790, 350), (880, 320), (915, 290)],
    ],
    "三角肌": [
        [(380, 250), (470, 220), (570, 235), (610, 290), (590, 340), (510, 350), (420, 320), (385, 290)],
        [(920, 250), (830, 220), (730, 235), (690, 290), (710, 340), (790, 350), (880, 320), (915, 290)],
    ],

    # 胸大肌（扇形：从锁骨往胸骨收）
    "胸部": [
        # 左侧
        [(640, 270), (530, 280), (440, 320), (410, 380), (440, 430), (550, 440), (610, 420), (640, 380)],
        # 右侧
        [(660, 270), (770, 280), (860, 320), (890, 380), (860, 430), (750, 440), (690, 420), (660, 380)],
    ],

    # 二头肌（上臂前侧梭形）
    "二头肌": [
        [(260, 380), (320, 365), (350, 410), (355, 510), (335, 580), (280, 600), (240, 540), (235, 450)],
        [(1044, 380), (984, 365), (954, 410), (949, 510), (969, 580), (1024, 600), (1064, 540), (1069, 450)],
    ],

    # 前臂（屈肌群，前面观双前臂）
    "前臂": [
        # 前面观左
        [(220, 620), (290, 615), (320, 680), (320, 800), (290, 850), (235, 840), (205, 740), (200, 660)],
        # 前面观右
        [(1084, 620), (1014, 615), (984, 680), (984, 800), (1014, 850), (1069, 840), (1099, 740), (1104, 660)],
        # 背面观左
        [(220, 2130), (290, 2125), (320, 2190), (320, 2310), (290, 2360), (235, 2350), (205, 2250), (200, 2170)],
        # 背面观右
        [(1084, 2130), (1014, 2125), (984, 2190), (984, 2310), (1014, 2360), (1069, 2350), (1099, 2250), (1104, 2170)],
    ],

    # 腹直肌（六块腹肌：3 行 × 2 列）
    "核心": [
        [(615, 410), (685, 410), (685, 460), (615, 460)],
        [(615, 470), (685, 470), (685, 525), (615, 525)],
        [(615, 535), (685, 535), (685, 595), (615, 595)],
        [(615, 605), (685, 605), (685, 665), (615, 665)],
        [(620, 675), (680, 675), (680, 720), (620, 720)],
        [(625, 730), (675, 730), (675, 770), (625, 770)],
    ],

    # 股四头肌（大腿前侧梭形，从髋到膝）
    "股四头肌": [
        [(560, 730), (640, 720), (660, 830), (660, 950), (635, 1050), (580, 1080), (530, 1000), (515, 870), (530, 790)],
        [(740, 730), (660, 720), (640, 830), (640, 950), (665, 1050), (720, 1080), (770, 1000), (785, 870), (770, 790)],
    ],
    "腿部综合": [
        [(560, 730), (640, 720), (660, 830), (660, 950), (635, 1050), (580, 1080), (530, 1000), (515, 870), (530, 790)],
        [(740, 730), (660, 720), (640, 830), (640, 950), (665, 1050), (720, 1080), (770, 1000), (785, 870), (770, 790)],
    ],

    # 小腿（前面：胫骨前肌；背面：腓肠肌）
    "小腿": [
        # 前面观左
        [(545, 1150), (620, 1145), (635, 1230), (625, 1340), (590, 1400), (555, 1390), (530, 1290), (530, 1200)],
        # 前面观右
        [(755, 1150), (680, 1145), (665, 1230), (675, 1340), (710, 1400), (745, 1390), (770, 1290), (770, 1200)],
        # 背面观左
        [(545, 2650), (620, 2645), (635, 2730), (625, 2840), (590, 2900), (555, 2890), (530, 2790), (530, 2700)],
        # 背面观右
        [(755, 2650), (680, 2645), (665, 2730), (675, 2840), (710, 2900), (745, 2890), (770, 2790), (770, 2700)],
    ],

    # ============ 背面观 (y ≈ 1620..3030) ============

    # 三角肌后束
    "三角肌后束": [
        [(380, 1900), (470, 1875), (570, 1890), (610, 1940), (590, 1990), (510, 2000), (420, 1975), (385, 1945)],
        [(920, 1900), (830, 1875), (730, 1890), (690, 1940), (710, 1990), (790, 2000), (880, 1975), (915, 1945)],
    ],

    # 背阔肌（V 形：上宽下窄）
    "背阔肌": [
        [(640, 2000), (480, 2050), (400, 2200), (450, 2330), (550, 2360), (635, 2330), (640, 2200)],
        [(660, 2000), (820, 2050), (900, 2200), (850, 2330), (750, 2360), (665, 2330), (660, 2200)],
    ],
    "背部": [
        [(640, 2000), (480, 2050), (400, 2200), (450, 2330), (550, 2360), (635, 2330), (640, 2200)],
        [(660, 2000), (820, 2050), (900, 2200), (850, 2330), (750, 2360), (665, 2330), (660, 2200)],
    ],

    # 三头肌（上臂后侧）
    "三头肌": [
        [(260, 1990), (320, 1975), (350, 2020), (355, 2120), (335, 2190), (280, 2210), (240, 2150), (235, 2060)],
        [(1044, 1990), (984, 1975), (954, 2020), (949, 2120), (969, 2190), (1024, 2210), (1064, 2150), (1069, 2060)],
    ],

    # 臀大肌（左右两块圆形）
    "臀部": [
        [(640, 2390), (510, 2410), (445, 2490), (470, 2580), (570, 2620), (640, 2580)],
        [(660, 2390), (790, 2410), (855, 2490), (830, 2580), (730, 2620), (660, 2580)],
    ],

    # 腘绳肌（大腿后侧梭形）
    "腘绳肌": [
        [(560, 2580), (640, 2570), (660, 2680), (660, 2800), (635, 2900), (580, 2920), (530, 2850), (515, 2730), (530, 2640)],
        [(740, 2580), (660, 2570), (640, 2680), (640, 2800), (665, 2900), (720, 2920), (770, 2850), (785, 2730), (770, 2640)],
    ],
}


def plot_muscle_body_template(muscles: dict, template_path: Path, out_path: Path) -> None:
    """用真实解剖图模板（CC BY 4.0）作底图，叠加半透明色块标注训练强度。

    叠加在原图上，保留原图英文标签（双语对照），按 _TEMPLATE_OVERLAYS 的预标定像素坐标
    画半透明椭圆。alpha=0.55 让原图肌肉纹理仍可见。
    """
    import matplotlib.image as mpimg
    import numpy as np

    muscle_level: dict[str, str] = {m["muscle"]: m["level"] for m in muscles.get("per_muscle", [])}

    LEVEL_COLOR = {
        "高": "#1F3A6E",
        "中": "#4D6FA7",
        "低": "#7E9BC4",
    }
    LABEL_COLOR = "#1A1A1A"

    img = mpimg.imread(str(template_path))
    W = img.shape[1]

    # 把上下排列的前/后视图拼成左右排列，输出图横向友好
    SPLIT_Y = 1516  # 原图大约的中间分割线（前面观结束 / 背面观开始）
    front_img = img[:SPLIT_Y, :, :]
    back_img = img[SPLIT_Y:, :, :]
    # pad 到等高再水平拼接
    h_front, h_back = front_img.shape[0], back_img.shape[0]
    target_h = max(h_front, h_back)
    if h_front < target_h:
        pad = np.ones((target_h - h_front, W, img.shape[2]), dtype=img.dtype) * 255
        front_img = np.vstack([front_img, pad])
    if h_back < target_h:
        pad = np.ones((target_h - h_back, W, img.shape[2]), dtype=img.dtype) * 255
        back_img = np.vstack([back_img, pad])
    combined = np.hstack([front_img, back_img])
    NEW_W = combined.shape[1]   # 2 * W
    NEW_H = combined.shape[0]   # target_h
    BACK_X_OFFSET = W           # 背面观 polygon x 坐标要 +W；y 坐标 -SPLIT_Y

    fig, ax = plt.subplots(figsize=(15, 9))
    ax.imshow(combined)

    def remap(pt: tuple[int, int]) -> tuple[int, int]:
        """把原图坐标 (x, y) 映射到新拼接图坐标。
        前面观 (y < SPLIT_Y)：(x, y) 不变；
        背面观 (y >= SPLIT_Y)：(x + W, y - SPLIT_Y)。"""
        x, y = pt
        if y >= SPLIT_Y:
            return (x + BACK_X_OFFSET, y - SPLIT_Y)
        return (x, y)

    # "核心" 由 6 块腹肌组成，标签合并写一个，避免重复 6 次拥挤
    GRID_LIKE = {"核心"}

    def split_front_back(polys):
        """按 y 中位数把多边形分到前/后视图。"""
        front, back = [], []
        for p in polys:
            cy = sum(pt[1] for pt in p) / len(p)
            (front if cy < SPLIT_Y else back).append(p)
        return front, back

    for muscle, lvl in muscle_level.items():
        if muscle not in _TEMPLATE_POLYGONS or lvl not in LEVEL_COLOR:
            continue
        color = LEVEL_COLOR[lvl]
        polys = _TEMPLATE_POLYGONS[muscle]
        # 画所有 polygon（remap 到新坐标系）
        for poly_pts in polys:
            remapped = [remap(p) for p in poly_pts]
            ax.add_patch(Polygon(remapped, closed=True, facecolor=color, edgecolor="white",
                                 linewidth=1.5, alpha=0.78, zorder=3))
        # 标签策略
        if muscle in GRID_LIKE:
            # 网格肌肉只写一个总标签，前后视图各一个
            front_p, back_p = split_front_back(polys)
            for group in (front_p, back_p):
                if not group:
                    continue
                all_pts = [remap(pt) for poly in group for pt in poly]
                cx = sum(p[0] for p in all_pts) / len(all_pts)
                cy = sum(p[1] for p in all_pts) / len(all_pts)
                ax.text(cx, cy, f"{muscle}·{lvl}", ha="center", va="center",
                        fontsize=11, color="white", fontweight="bold", zorder=4)
        else:
            # 每个 polygon 一个标签
            for poly_pts in polys:
                remapped = [remap(p) for p in poly_pts]
                cx = sum(p[0] for p in remapped) / len(remapped)
                cy = sum(p[1] for p in remapped) / len(remapped)
                ax.text(cx, cy, f"{muscle}\n{lvl}", ha="center", va="center",
                        fontsize=10, color="white", fontweight="bold", zorder=4)

    ax.set_xlim(0, NEW_W)
    ax.set_ylim(NEW_H, 0)
    ax.axis("off")
    ax.set_title("训练部位刺激图", fontsize=18, fontweight="bold", pad=10, color=LABEL_COLOR)
    # 在两半下方添加"前面观/背面观"中文标识
    label_y = NEW_H * 0.97
    ax.text(W / 2, label_y, "前面观", ha="center", va="top", fontsize=14,
            color=LABEL_COLOR, fontweight="bold")
    ax.text(W + W / 2, label_y, "背面观", ha="center", va="top", fontsize=14,
            color=LABEL_COLOR, fontweight="bold")

    # 顶部 badge（心肺 / 全身综合 / 柔韧）
    BADGE_LABELS = ["心肺", "全身综合", "柔韧"]
    badges = [(m, muscle_level[m]) for m in BADGE_LABELS if m in muscle_level]
    if badges:
        badge_text = "    ".join(f"{m} · {lvl}" for m, lvl in badges)
        fig.text(0.5, 0.965, badge_text, ha="center", fontsize=11, color=LABEL_COLOR,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#E8F0FE",
                           edgecolor="#4D6FA7", linewidth=1.0))

    # 图例（叠加在图内右上角，半透明背景）
    legend_handles = [
        Patch(facecolor=LEVEL_COLOR["高"], label="高 (≥60s)", alpha=0.7),
        Patch(facecolor=LEVEL_COLOR["中"], label="中 (≥30s)", alpha=0.7),
        Patch(facecolor=LEVEL_COLOR["低"], label="低 (<30s)", alpha=0.7),
    ]
    ax.legend(handles=legend_handles, loc="upper right", fontsize=10,
              framealpha=0.92, bbox_to_anchor=(0.99, 0.99))

    # CC-BY 4.0 attribution（图底部小字）
    fig.text(0.5, 0.003,
             "底图：OpenStax College / Wikimedia Commons - "
             "File:1105 Anterior and Posterior Views of Muscles.jpg (CC BY 4.0)",
             ha="center", fontsize=7, color="#666", style="italic")

    plt.tight_layout(rect=(0, 0.015, 1, 0.955))
    plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  人体图(模板版) → {out_path}")


def plot_muscle_body(muscles: dict, out_path: Path) -> None:
    """画前/背面观人体肌肉图，按训练强度着色。

    设计：用 Polygon 多点描出曲线人体轮廓（更像解剖图），肌肉群细分（六块腹肌、
    背阔 V 形等），标签用引导线引到人体外侧避免遮挡，蓝色调专业配色。
    """
    muscle_level: dict[str, str] = {m["muscle"]: m["level"] for m in muscles.get("per_muscle", [])}

    # 蓝色调配色（参考训记 App 风格）
    LEVEL_COLOR = {
        "高": "#1F3A6E",   # 深蓝
        "中": "#4D6FA7",   # 中蓝
        "低": "#7E9BC4",   # 浅蓝
    }
    BASE_COLOR = "#D8DEE6"     # 未训练 浅灰蓝
    BODY_COLOR = "#EEF1F5"     # 身体底色
    OUTLINE = "#A8B0BD"
    LABEL_COLOR = "#2E3440"

    fig, axes = plt.subplots(1, 2, figsize=(13, 11))

    def color_for(muscle: str) -> tuple[str, str | None]:
        lvl = muscle_level.get(muscle)
        return LEVEL_COLOR.get(lvl, BASE_COLOR), lvl

    def alpha_for(lvl: str | None) -> float:
        return 0.92 if lvl else 0.55

    # 半边轮廓顶点（右半，y 轴向上）；用于构造对称 Polygon
    HALF_OUTLINE = [
        (0.0, 14.5),       # 头顶
        (0.55, 14.4),
        (0.85, 13.9),
        (0.95, 13.1),
        (0.85, 12.5),      # 头底
        (0.55, 12.25),
        (0.55, 11.95),     # 颈侧
        (1.35, 11.55),     # 锁骨
        (2.15, 11.0),      # 三角肌外
        (2.4, 10.4),
        (2.45, 9.8),
        (2.4, 8.8),        # 二头肌外
        (2.3, 7.8),        # 肘
        (2.3, 6.9),        # 前臂外
        (2.2, 5.6),
        (2.0, 4.7),        # 手腕
        (2.1, 4.3),
        (1.85, 4.1),       # 手
        (1.6, 4.3),
        (1.7, 4.7),        # 回躯干
        (1.55, 4.45),      # 髋外
        (1.55, 3.95),
        (1.4, 2.85),       # 大腿外
        (1.15, 1.5),       # 膝外
        (1.0, 0.6),        # 小腿外
        (0.9, 0.05),
        (0.55, -0.05),
        (0.1, -0.05),
        (0.1, 0.8),        # 内小腿
        (0.05, 2.3),
        (0.0, 4.0),        # 档底
    ]

    def draw_silhouette(ax):
        full = HALF_OUTLINE + [(-x, y) for x, y in reversed(HALF_OUTLINE) if x > 0.001]
        ax.add_patch(Polygon(full, closed=True, facecolor=BODY_COLOR, edgecolor=OUTLINE,
                             linewidth=1.4, alpha=0.7, zorder=1))

    def setup_axis(ax, title: str):
        ax.set_xlim(-4.5, 4.5)
        ax.set_ylim(-0.5, 15.2)
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=15, fontweight="bold", pad=10, color=LABEL_COLOR)
        ax.axis("off")

    def add_muscle(ax, muscle: str, shape: str, x: float, y: float, w: float, h: float,
                   mirror: bool = False, rot: float = 0):
        color, lvl = color_for(muscle)
        alpha = alpha_for(lvl)
        positions = [(-abs(x), y), (abs(x), y)] if mirror else [(x, y)]
        for cx, cy in positions:
            if shape == "ellipse":
                ax.add_patch(Ellipse((cx, cy), w, h, angle=rot, facecolor=color, edgecolor="white",
                                     linewidth=1.2, alpha=alpha, zorder=2))
            elif shape == "rect":
                ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                            boxstyle="round,pad=0.01,rounding_size=0.15",
                                            facecolor=color, edgecolor="white",
                                            linewidth=1.2, alpha=alpha, zorder=2))

    def label_outside(ax, muscle: str, anchor_x: float, anchor_y: float,
                      label_x: float, label_y: float, ha: str = "left"):
        """从肌肉块用引导线引出标签到人体外侧。未训练的部位不画标签。"""
        lvl = muscle_level.get(muscle)
        if not lvl:
            return
        line_color = LEVEL_COLOR[lvl]
        ax.annotate(
            f"{muscle} · {lvl}",
            xy=(anchor_x, anchor_y),
            xytext=(label_x, label_y),
            fontsize=9, ha=ha, va="center",
            color=LABEL_COLOR, fontweight="bold" if lvl == "高" else "normal",
            arrowprops=dict(arrowstyle="-", color=line_color, lw=1.1, alpha=0.7,
                            connectionstyle="arc3,rad=0.0"),
            zorder=4,
        )

    # ============== 前面观 ==============
    ax = axes[0]
    setup_axis(ax, "前面观")
    draw_silhouette(ax)

    # 三角肌前束（双肩）
    delt_front = "前束三角肌" if "前束三角肌" in muscle_level else "三角肌"
    add_muscle(ax, delt_front, "ellipse", 1.7, 10.95, 0.95, 0.7, mirror=True)
    # 胸大肌上胸（视觉细分，按"胸部"着色）
    add_muscle(ax, "胸部", "ellipse", 0.55, 10.25, 0.95, 0.55, mirror=True)
    # 胸大肌中下胸
    add_muscle(ax, "胸部", "ellipse", 0.6, 9.35, 1.15, 0.85, mirror=True)
    # 二头肌
    add_muscle(ax, "二头肌", "ellipse", 2.15, 8.5, 0.55, 1.15, mirror=True, rot=-5)
    # 前臂（前面）
    add_muscle(ax, "前臂", "ellipse", 2.1, 6.4, 0.5, 1.35, mirror=True, rot=8)
    # 六块腹肌（按"核心"整体着色）
    abs_color, abs_lvl = color_for("核心")
    abs_alpha = alpha_for(abs_lvl)
    for row_y in (8.5, 7.85, 7.2, 6.55, 5.95, 5.4):
        for cx in (-0.3, 0.3):
            ax.add_patch(FancyBboxPatch((cx - 0.22, row_y - 0.25), 0.44, 0.5,
                                        boxstyle="round,pad=0.01,rounding_size=0.08",
                                        facecolor=abs_color, edgecolor="white",
                                        linewidth=1.0, alpha=abs_alpha, zorder=2))
    # 股四头肌
    quad_label = "股四头肌" if "股四头肌" in muscle_level else ("腿部综合" if "腿部综合" in muscle_level else "股四头肌")
    add_muscle(ax, quad_label, "rect", 0.7, 2.9, 0.8, 1.95, mirror=True)
    # 小腿前（胫骨/腓肠肌前侧）
    add_muscle(ax, "小腿", "ellipse", 0.6, 0.95, 0.6, 1.1, mirror=True)

    # 引导线标签（前面观）
    label_outside(ax, delt_front, 2.15, 10.95, 3.8, 11.5, ha="left")
    label_outside(ax, "胸部", -1.1, 9.5, -3.8, 10.0, ha="right")
    label_outside(ax, "二头肌", -2.15, 8.5, -3.8, 8.5, ha="right")
    label_outside(ax, "前臂", 2.1, 6.4, 3.8, 6.4, ha="left")
    label_outside(ax, "核心", -0.3, 7.0, -3.8, 7.0, ha="right")
    label_outside(ax, quad_label, 0.7, 2.9, 3.8, 2.9, ha="left")
    label_outside(ax, "小腿", -0.6, 0.95, -3.8, 0.95, ha="right")

    # ============== 背面观 ==============
    ax = axes[1]
    setup_axis(ax, "背面观")
    draw_silhouette(ax)

    # 三角肌后束
    delt_back = "后束三角肌" if "后束三角肌" in muscle_level else "三角肌"
    add_muscle(ax, delt_back, "ellipse", 1.7, 10.95, 0.95, 0.7, mirror=True)
    # 背阔肌（V 形：两个三角形从上背向下收）
    back_label = "背阔肌" if "背阔肌" in muscle_level else "背部"
    bcolor, blvl = color_for(back_label)
    balpha = alpha_for(blvl)
    back_left = [(-0.05, 10.4), (-1.55, 9.7), (-1.1, 7.0), (-0.05, 7.2)]
    back_right = [(0.05, 10.4), (1.55, 9.7), (1.1, 7.0), (0.05, 7.2)]
    ax.add_patch(Polygon(back_left, closed=True, facecolor=bcolor, edgecolor="white",
                         linewidth=1.2, alpha=balpha, zorder=2))
    ax.add_patch(Polygon(back_right, closed=True, facecolor=bcolor, edgecolor="white",
                         linewidth=1.2, alpha=balpha, zorder=2))
    # 三头肌
    add_muscle(ax, "三头肌", "ellipse", 2.15, 8.5, 0.55, 1.15, mirror=True, rot=-5)
    # 前臂背侧
    add_muscle(ax, "前臂", "ellipse", 2.1, 6.4, 0.5, 1.35, mirror=True, rot=8)
    # 臀部
    add_muscle(ax, "臀部", "ellipse", 0.55, 4.25, 0.95, 0.85, mirror=True)
    # 腘绳肌
    add_muscle(ax, "腘绳肌", "rect", 0.7, 2.9, 0.8, 1.95, mirror=True)
    # 小腿（腓肠肌）
    add_muscle(ax, "小腿", "ellipse", 0.6, 0.95, 0.6, 1.1, mirror=True)

    # 引导线标签（背面观）
    label_outside(ax, delt_back, 2.15, 10.95, 3.8, 11.5, ha="left")
    label_outside(ax, back_label, -1.2, 8.4, -3.8, 8.4, ha="right")
    label_outside(ax, "三头肌", 2.15, 8.5, 3.8, 8.5, ha="left")
    label_outside(ax, "前臂", -2.1, 6.4, -3.8, 6.4, ha="right")
    label_outside(ax, "臀部", 0.55, 4.25, 3.8, 4.25, ha="left")
    label_outside(ax, "腘绳肌", -0.7, 2.9, -3.8, 2.9, ha="right")
    label_outside(ax, "小腿", 0.6, 0.95, 3.8, 0.95, ha="left")

    # 顶部 badge：心肺 / 全身综合 / 柔韧（画不到身体上的）
    BADGE_LABELS = ["心肺", "全身综合", "柔韧"]
    badges = [(m, muscle_level[m]) for m in BADGE_LABELS if m in muscle_level]
    if badges:
        badge_text = "    ".join(f"{m} · {lvl}" for m, lvl in badges)
        fig.text(0.5, 0.945, badge_text, ha="center", fontsize=12, color=LABEL_COLOR,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#E8F0FE",
                           edgecolor="#4D6FA7", linewidth=1.0))

    # 底部图例
    legend_handles = [
        Patch(facecolor=LEVEL_COLOR["高"], label="高强度 (≥60s)"),
        Patch(facecolor=LEVEL_COLOR["中"], label="中强度 (≥30s)"),
        Patch(facecolor=LEVEL_COLOR["低"], label="低强度 (<30s)"),
        Patch(facecolor=BASE_COLOR, label="本次未训练", alpha=0.6),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=4, frameon=False, fontsize=10)

    fig.suptitle("训练部位刺激图", fontsize=17, fontweight="bold", y=0.99, color=LABEL_COLOR)
    plt.tight_layout(rect=(0, 0.04, 1, 0.91))
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  人体图 → {out_path}")


def estimate_muscles(calories: dict) -> dict:
    """基于已分组的动作时长，按 MUSCLE_GROUPS 映射累加部位强度。

    返回：
      {
        "per_muscle": [{muscle, seconds_weighted, primary_actions: [...], level: 高/中/低}, ...],
        "total_actions_with_muscle": <参与统计的动作数>,
        "has_generic": <bool 是否有"全身综合"标记，提示数据粗略>,
      }

    部位强度等级阈值：
      - 高：weighted_seconds >= 60
      - 中：30 <= ... < 60
      - 低：0 < ... < 30
    """
    muscle_seconds: dict[str, float] = {}
    muscle_actions: dict[str, set[str]] = {}
    has_generic = False
    for p in calories.get("per_action", []):
        action = p["action"]
        seconds = p["seconds"]
        mapping = MUSCLE_GROUPS.get(action, {})
        if not mapping:
            continue
        if "全身综合" in mapping:
            has_generic = True
        for muscle, weight in mapping.items():
            muscle_seconds[muscle] = muscle_seconds.get(muscle, 0.0) + seconds * weight
            muscle_actions.setdefault(muscle, set()).add(action)

    def level(s: float) -> str:
        if s >= 60:
            return "高"
        if s >= 30:
            return "中"
        return "低"

    per_muscle = sorted(
        (
            {
                "muscle": m,
                "seconds_weighted": round(s, 1),
                "primary_actions": sorted(muscle_actions[m]),
                "level": level(s),
            }
            for m, s in muscle_seconds.items()
        ),
        key=lambda x: -x["seconds_weighted"],
    )
    return {
        "per_muscle": per_muscle,
        "total_actions_with_muscle": sum(1 for p in calories.get("per_action", []) if MUSCLE_GROUPS.get(p["action"], {})),
        "has_generic": has_generic,
    }


def smooth_actions(
    actions: list[dict],
    max_other_gap: int,
) -> tuple[list[dict], list[dict]]:
    """把被夹在相同非'其他'标签之间的'其他'段合并到该标签。

    规则：
    - 找连续被判为"其他"的段 [i, j)
    - 若前一帧标签 prev 与后一帧标签 nxt 相同且都非"其他"
    - 且段长 (j - i) <= max_other_gap
    - 则把该段所有帧改成 prev，note 前加 [平滑]，置信度 = 参考帧最低值 × 0.8

    超过 max_other_gap 的"其他"段视为真实过渡（如走廊行走），保留原标签。

    返回 (smoothed_actions, merge_log)。
    smoothed_actions 是深拷贝。merge_log 是每次合并的记录：
      [{"target": <标签>, "start_s": ..., "end_s": ..., "n_frames": ...}, ...]
    """
    out = [dict(a) for a in actions]
    n = len(out)
    merge_log: list[dict] = []
    i = 0
    while i < n:
        if out[i]["action"] != "其他":
            i += 1
            continue
        # 连续"其他"段 [i, j)
        j = i
        while j < n and out[j]["action"] == "其他":
            j += 1
        gap = j - i
        prev = out[i - 1]["action"] if i > 0 else None
        nxt = out[j]["action"] if j < n else None
        if (
            prev is not None and prev == nxt and prev != "其他"
            and gap <= max_other_gap
        ):
            ref_conf = min(
                out[i - 1].get("confidence", 0.5),
                out[j].get("confidence", 0.5),
            )
            new_conf = round(ref_conf * 0.8, 2)
            for k in range(i, j):
                out[k]["action"] = prev
                out[k]["note"] = f"[平滑] {out[k]['note']}"
                out[k]["confidence"] = new_conf
            merge_log.append({
                "target": prev,
                "start_s": out[i]["timestamp_s"],
                "end_s": out[j - 1]["timestamp_s"],
                "n_frames": gap,
            })
        i = j
    return out, merge_log


def estimate_calories(
    actions: list[dict],
    duration_s: float,
    weight_kg: float,
) -> dict:
    """按动作类型分摊时长，套 MET 表估算 kcal。

    返回结构：
        {
          "weight_kg": ...,
          "seconds_per_frame": ...,
          "per_action": [{action, seconds, met, kcal}, ...],   # 按 kcal 降序
          "total_seconds": ...,
          "total_kcal": ...,
        }
    """
    if not actions:
        return {"weight_kg": weight_kg, "per_action": [], "total_kcal": 0.0, "total_seconds": 0.0}

    # 每帧覆盖时长：用相邻帧间隔；只 1 帧时回退到总时长
    if len(actions) >= 2:
        seconds_per_frame = actions[1]["timestamp_s"] - actions[0]["timestamp_s"]
    else:
        seconds_per_frame = duration_s

    seconds_by_action: dict[str, float] = {}
    for a in actions:
        seconds_by_action[a["action"]] = seconds_by_action.get(a["action"], 0.0) + seconds_per_frame

    per_action = []
    for action, seconds in seconds_by_action.items():
        met = MET_TABLE.get(action, MET_TABLE["其他"])
        kcal = met * weight_kg * (seconds / 3600.0)
        per_action.append({
            "action": action,
            "seconds": round(seconds, 1),
            "met": met,
            "kcal": round(kcal, 2),
        })
    per_action.sort(key=lambda x: x["kcal"], reverse=True)

    return {
        "weight_kg": weight_kg,
        "seconds_per_frame": round(seconds_per_frame, 2),
        "per_action": per_action,
        "total_seconds": round(sum(p["seconds"] for p in per_action), 1),
        "total_kcal": round(sum(p["kcal"] for p in per_action), 2),
    }


def plot_pie(actions: list[dict], out_path: Path) -> dict:
    """动作占比饼图，返回 {action: count} 用于报告。"""
    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1

    labels = list(counts.keys())
    sizes = list(counts.values())
    colors = [ACTION_COLORS.get(l, "#CCC") for l in labels]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 11},
    )
    ax.set_title("动作占比")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  饼图 → {out_path}")
    return counts


# -------------------- 总评 --------------------

ANALYSIS_SYSTEM_PROMPT = """你是一名健身教练助理。我会给你一次健身房训练的动作分布、总时长、
能耗估算等结构化数据。请基于这些数据用中文输出一份训练分析。

严格按以下 JSON 结构输出，不要任何 JSON 之外的文字：
{
  "summary": "<150-250 字的整体点评，包含：训练性质（力量/有氧/混合）、强度与节奏判断、动作搭配是否合理。不使用 markdown 标题，直接出文本>",
  "next_plan": [
    {"item": "<下次训练的一条具体安排，例如 '加入卧推 4 组×8 次' 或 '把跑步延长到 15 分钟'>",
     "reason": "<一句话说明为什么这么安排，结合本次训练的不足或互补部位>"},
    ...共 3 到 5 条
  ],
  "recovery": "<2-3 句中文：本次训练后的拉伸/休息/补水建议，可指明部位>"
}

约束：
- next_plan 至少 3 条，至多 5 条，必须具体可执行（含动作、组数/时长），不要"加强核心"这种空话。
- summary 中要**结合提供的"部位刺激"数据**指明本次训练到的主要部位（如"主要刺激了背阔肌、二头肌、心肺"），
  以及**缺失的部位**（如"胸部、肩部、下肢力量缺失"）。
- 如果发现某个部位本次完全没练，在 next_plan 里主动补上对应动作。
- summary 用专业但易懂的中文，不要堆术语。
- 如果"部位刺激"里出现"全身综合"标签，说明杠铃/哑铃等多动作器械无法精确定位部位，summary 可提示用户后续补充具体动作信息。"""


def generate_analysis(
    client: OpenAI,
    model: str,
    counts: dict,
    duration_s: float,
    frame_count: int,
    calories: dict,
    muscles: dict,
) -> dict:
    """返回 {summary, next_plan, recovery}。next_plan 是 list[dict]。"""
    facts = {
        "总时长_秒": round(duration_s, 1),
        "关键帧数": frame_count,
        "动作分布_帧计数": counts,
        "动作时长_秒": {p["action"]: p["seconds"] for p in calories["per_action"]},
        "能耗估算": {
            "体重_kg": calories["weight_kg"],
            "总kcal": calories["total_kcal"],
            "按动作_kcal": {p["action"]: p["kcal"] for p in calories["per_action"]},
        },
        "部位刺激": {
            m["muscle"]: {"加权秒": m["seconds_weighted"], "强度": m["level"], "来源": m["primary_actions"]}
            for m in muscles.get("per_muscle", [])
        },
        "含多动作器械": muscles.get("has_generic", False),
    }
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": "训练数据：\n" + json.dumps(facts, ensure_ascii=False, indent=2)},
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 中转/模型偶尔返回 markdown 包裹或空串，捞一下花括号子串
        print(f"[warn] generate_analysis 返回非 JSON（len={len(raw)}）: {raw[:200]!r}", flush=True)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
    if not isinstance(data, dict):
        data = {}
    # 兜底字段
    return {
        "summary": (data.get("summary") or "").strip(),
        "next_plan": data.get("next_plan") or [],
        "recovery": (data.get("recovery") or "").strip(),
    }


# -------------------- Markdown 报告 --------------------

def build_report_md(
    paths: Paths,
    meta: dict,
    actions: list[dict],
    calories: dict,
    muscles: dict,
    analysis: dict,
) -> str:
    info = meta["video_info"]
    lines = []
    lines.append("# 健身训练报告")
    lines.append("")
    lines.append(f"- 视频：`{Path(meta['video_path']).name}`")
    lines.append(f"- 分辨率：{info['width']}×{info['height']}")
    lines.append(f"- 时长：{info['duration_s']} 秒")
    lines.append(f"- 关键帧数：{len(actions)}")
    lines.append(f"- 体重（用于能耗估算）：{calories['weight_kg']} kg")
    lines.append(f"- **估算总能耗：{calories['total_kcal']} kcal**")
    lines.append("")
    lines.append("## 动作时间轴")
    lines.append("")
    lines.append(f"![timeline]({paths.timeline_png.name})")
    lines.append("")
    lines.append("## 动作占比")
    lines.append("")
    lines.append(f"![pie]({paths.pie_png.name})")
    lines.append("")
    lines.append("## 训练点评")
    lines.append("")
    lines.append(analysis["summary"] or "（未生成）")
    lines.append("")
    lines.append("## 能耗估算")
    lines.append("")
    lines.append("> 公式：kcal = MET × 体重(kg) × 时长(小时)；MET 取自 2011 Compendium 中健身房动作中等强度值。")
    lines.append("")
    lines.append("| 动作 | 时长(s) | MET | kcal |")
    lines.append("| --- | ---: | ---: | ---: |")
    for p in calories["per_action"]:
        lines.append(f"| {p['action']} | {p['seconds']} | {p['met']} | {p['kcal']} |")
    lines.append(f"| **合计** | **{calories['total_seconds']}** | — | **{calories['total_kcal']}** |")
    lines.append("")
    lines.append("## 训练部位")
    lines.append("")
    if muscles["per_muscle"]:
        lines.append(f"![muscle_body]({paths.muscle_body_png.name})")
        lines.append("")
        lines.append("> 公式：部位强度 = Σ(动作时长 × 该动作对该部位的贡献权重)。"
                     "强度等级：高 ≥ 60s / 中 ≥ 30s / 低 < 30s。")
        lines.append("")
        lines.append("| 部位 | 加权时长(s) | 强度 | 主要来源 |")
        lines.append("| --- | ---: | :---: | --- |")
        for m in muscles["per_muscle"]:
            sources = "、".join(m["primary_actions"])
            lines.append(f"| {m['muscle']} | {m['seconds_weighted']} | {m['level']} | {sources} |")
        lines.append("")
        if muscles["has_generic"]:
            lines.append("> 注：本次训练含杠铃/哑铃/史密斯架/龙门架类**多动作器械**，无法仅凭画面判断具体动作（深蹲/卧推/硬拉/划船等），"
                         "因此被标记为「全身综合」。如需精确部位分析，需补充每段对应的具体动作信息。")
            lines.append("")
    else:
        lines.append("（本次未识别到具有明确部位映射的训练动作）")
        lines.append("")
    lines.append("## 下次训练计划")
    lines.append("")
    if analysis["next_plan"]:
        for i, p in enumerate(analysis["next_plan"], 1):
            item = p.get("item", "").strip()
            reason = p.get("reason", "").strip()
            if reason:
                lines.append(f"{i}. **{item}** —— {reason}")
            else:
                lines.append(f"{i}. {item}")
    else:
        lines.append("（未生成）")
    lines.append("")
    lines.append("## 恢复建议")
    lines.append("")
    lines.append(analysis["recovery"] or "（未生成）")
    lines.append("")
    lines.append("## 动作明细")
    lines.append("")
    lines.append("| 时间(s) | 动作 | 置信度 | 备注 |")
    lines.append("| --- | --- | --- | --- |")
    for a in actions:
        lines.append(
            f"| {a['timestamp_s']:.2f} | {a['action']} | {a['confidence']:.2f} | {a['note']} |"
        )
    lines.append("")
    return "\n".join(lines)


# -------------------- 入口 --------------------

def build_client() -> tuple[OpenAI, str]:
    """假定 load_dotenv() 已在 main 中调用。优先 API_KEY/BASE_URL，回退 OPENAI_*。"""
    api_key = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("错误：未读到 API_KEY，请在 .env 中配置。", file=sys.stderr)
        sys.exit(1)
    base_url = os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None
    timeout_ms = os.environ.get("API_TIMEOUT_MS")
    timeout = float(timeout_ms) / 1000.0 if timeout_ms else None
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return client, base_url or "https://api.openai.com/v1"


def main():
    parser = argparse.ArgumentParser(description="健身报告生成（基于关键帧 + GPT Vision）")
    parser.add_argument("--video", required=True,
                        help="视频文件路径，例如 video/20260525-132917.mp4。"
                             "帧目录自动定位到同级 video/<视频名>/，所有产物也写入该目录。")
    parser.add_argument("--vision-model", default=None,
                        help=f"多模态模型名（默认读 env MULTIMODAL_MODEL，否则 {DEFAULT_VISION_MODEL}）")
    parser.add_argument("--text-model", default=None,
                        help=f"文本分析模型名（默认读 env TEXT_MODEL，否则 {DEFAULT_TEXT_MODEL}）")
    parser.add_argument("--weight", type=float, default=DEFAULT_WEIGHT_KG,
                        help=f"体重 kg，用于能耗估算，默认 {DEFAULT_WEIGHT_KG}")
    parser.add_argument("--refresh", action="store_true", help="强制重新调用 GPT-V，忽略 actions.json 缓存")
    parser.add_argument("--exercises", default=None,
                        help="本次训练实际包含的运动（逗号分隔），收窄候选标签集，例如 '跑步,杠铃,引体向上'。"
                             "不指定则用全 10 标签。建议指定，能显著减少误识别。")
    parser.add_argument("--min-run", type=int, default=3,
                        help="孤立段过滤：连续相同非'其他'标签的段长 < 此值时回退为'其他'，1 关闭。默认 3（= 6 秒）")
    parser.add_argument("--min-run-support", type=int, default=3,
                        help="孤立段过滤的邻域支持窗口（前后各 N 帧）。前/后窗口内有相同标签的同伴 → 保留该短段。默认 3（= 6 秒）")
    parser.add_argument("--no-consolidate", action="store_true",
                        help="关闭视觉组合并（默认开启）。视觉组合并：相邻同视觉组的标签段按帧数投票统一，"
                             "解决杠铃/史密斯架、跑步/椭圆机等容易被混淆的相邻段问题")
    parser.add_argument("--prefer", default=None,
                        help="视觉组合并投票时给指定标签加权（逗号分隔），帮助纠正 GPT 的视觉相似系统性误判。"
                             "例如 --prefer 杠铃,引体向上 让 {杠铃,史密斯架} 组倾向杠铃、"
                             "{龙门架,...,引体向上} 组倾向引体向上。默认权重 2.0")
    parser.add_argument("--prefer-weight", type=float, default=2.0,
                        help="--prefer 标签的票数倍数，默认 2.0")
    parser.add_argument("--smooth-gap", type=int, default=20,
                        help="平滑：合并夹在相同标签之间的'其他'段，段长（关键帧数）<= 此值才合并，0 关闭。默认 20")
    args = parser.parse_args()

    # 提前加载 .env，让后续 env 读取都生效
    load_dotenv()

    vision_model = args.vision_model or os.environ.get("MULTIMODAL_MODEL") or DEFAULT_VISION_MODEL
    text_model = args.text_model or os.environ.get("TEXT_MODEL") or DEFAULT_TEXT_MODEL

    # 收窄标签集：如果用户用 --exercises 指定了运动，只让 GPT 在这些 + "休息" + "其他" 里选
    if args.exercises:
        user_labels = [x.strip() for x in args.exercises.split(",") if x.strip()]
        unknown = [x for x in user_labels if x not in ACTION_LABELS]
        if unknown:
            print(f"警告：忽略未知标签 {unknown}（可选：{ACTION_LABELS}）", file=sys.stderr)
        user_labels = [x for x in user_labels if x in ACTION_LABELS]
        labels = user_labels + [x for x in ["休息", "其他"] if x not in user_labels]
    else:
        labels = list(ACTION_LABELS)
    recognize_system_prompt = build_recognize_prompt(labels)
    print(f"识别标签集：{labels}")

    setup_chinese_font()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        print(f"错误：视频文件不存在：{video_path}", file=sys.stderr)
        sys.exit(1)

    frames_dir, frames, meta = discover_frames(video_path)
    paths = Paths(video=video_path, frames_dir=frames_dir)
    duration_s = meta["video_info"]["duration_s"]
    interval = meta["video_info"]["frame_interval_s"]
    print(f"视频：{video_path.name}")
    print(f"帧目录：{frames_dir}")
    print(f"载入 {len(frames)} 帧，视频时长 {duration_s}s，抽帧间隔 {interval}s")

    # 计算帧间运动强度（本地，无 API 消耗），作为 GPT-V 的辅助信号
    print("计算帧间运动强度 ...")
    compute_motion(frames, frames_dir)
    motion_vals = [f["motion"] for f in frames]
    if motion_vals:
        print(f"  motion: min={min(motion_vals):.2f}, max={max(motion_vals):.2f}, "
              f"avg={sum(motion_vals)/len(motion_vals):.2f}")

    client = None
    endpoint = None

    # 1) 动作识别（带缓存；缓存里始终是 raw GPT-V 结果）
    if paths.actions_json.exists() and not args.refresh:
        print(f"读取缓存：{paths.actions_json}")
        raw_actions = json.loads(paths.actions_json.read_text(encoding="utf-8"))
    else:
        client, endpoint = build_client()
        print(f"调用 GPT-V（endpoint={endpoint}, model={vision_model}）...")
        raw_actions = recognize_all(
            client, vision_model, frames, paths.frames_dir,
            recognize_system_prompt, labels,
        )
        paths.actions_json.write_text(
            json.dumps(raw_actions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  动作标注 → {paths.actions_json}")

    # 1b) 后处理：先去孤立短段（避免路过扫到被记为训练），再合并夹"其他"
    actions = raw_actions

    if args.min_run > 1:
        actions, iso_log = remove_isolated_runs(actions, args.min_run, args.min_run_support)
        iso_frames = sum(m["n_frames"] for m in iso_log)
        print(f"去孤立（min_run={args.min_run}, support={args.min_run_support}）："
              f"{len(iso_log)} 段共 {iso_frames} 帧短训练段 → 其他")
        for m in iso_log:
            print(f"  {m['start_s']:.0f}s–{m['end_s']:.0f}s ({m['n_frames']} 帧) 原[{m['action']}] → 其他")

    if not args.no_consolidate:
        prefer_weights = None
        if args.prefer:
            prefer_labels = [x.strip() for x in args.prefer.split(",") if x.strip()]
            prefer_weights = {lbl: args.prefer_weight for lbl in prefer_labels if lbl in ACTION_LABELS}
            unknown_prefer = [x for x in prefer_labels if x not in ACTION_LABELS]
            if unknown_prefer:
                print(f"警告：--prefer 中忽略未知标签 {unknown_prefer}", file=sys.stderr)
            if prefer_weights:
                print(f"投票加权：{prefer_weights}")
        actions, cons_log = consolidate_visual_groups(actions, min_total_frames=5, prefer_weights=prefer_weights)
        if cons_log:
            total_changed = sum(m["n_changed"] for m in cons_log)
            print(f"视觉组合并：{len(cons_log)} 段共改写 {total_changed} 帧")
            for m in cons_log:
                print(f"  {m['start_s']:.0f}s–{m['end_s']:.0f}s 主导→{m['dominant']}（原分布 {m['labels']}）")

    if args.smooth_gap > 0:
        actions, merge_log = smooth_actions(actions, args.smooth_gap)
        merged_frames = sum(m["n_frames"] for m in merge_log)
        print(f"时间平滑（max_gap={args.smooth_gap}）：合并 {len(merge_log)} 段共 {merged_frames} 帧'其他' → 邻近标签")
        for m in merge_log:
            print(f"  {m['start_s']:.0f}s–{m['end_s']:.0f}s ({m['n_frames']} 帧) → {m['target']}")

    # 2) 可视化
    print("生成可视化 ...")
    plot_timeline(actions, duration_s, paths.timeline_png)
    counts = plot_pie(actions, paths.pie_png)

    # 3a) 能耗估算（纯本地，先于 LLM 跑）
    calories = estimate_calories(actions, duration_s, weight_kg=args.weight)
    print(f"  能耗估算（体重 {args.weight}kg）：{calories['total_kcal']} kcal")

    # 3b) 部位刺激分析（纯本地，基于 MUSCLE_GROUPS 映射）
    muscles = estimate_muscles(calories)
    if muscles["per_muscle"]:
        preview = ", ".join(f"{m['muscle']}({m['level']})" for m in muscles["per_muscle"][:6])
        more = "" if len(muscles["per_muscle"]) <= 6 else f" 等 {len(muscles['per_muscle'])} 项"
        print(f"  部位刺激：{preview}{more}")
        # 优先用真实解剖图模板（如果存在），否则用 Polygon 版
        template_path = Path("templates/body_anatomy.jpg")
        if template_path.is_file():
            plot_muscle_body_template(muscles, template_path, paths.muscle_body_png)
        else:
            plot_muscle_body(muscles, paths.muscle_body_png)

    # 4) 训练分析（总评 + 下次计划 + 恢复建议，一次 JSON 返回）
    print(f"生成训练分析（model={text_model}）...")
    if client is None:
        client, endpoint = build_client()
    analysis = generate_analysis(client, text_model, counts, duration_s, len(actions), calories, muscles)

    # 5) Markdown
    md = build_report_md(paths, meta, actions, calories, muscles, analysis)
    paths.report_md.write_text(md, encoding="utf-8")
    print(f"  报告 → {paths.report_md}")

    print("\n完成。")


if __name__ == "__main__":
    main()
