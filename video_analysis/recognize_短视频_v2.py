"""
recognize_短视频_v2.py
---------------------
两阶段 LLM 识别（v2）：
  Step 1: period_recognize_v2 → 阶段划分（exercise / transition / rest 三分类）
  Step 2: pose_recognize_v2   → exercise 段精细识别 + 组次估算 + 计划匹配偏差

输入变化（v2 vs v1）：
  - 不再逐帧传图，改为将采样关键帧拼成网格图（单张）作为输入
  - 子图保持原始像素尺寸（568×320），不缩放
  - 注入训练计划 JSON

输出（保存在 OUTPUT_DIR）：
  period_result_v2.json
  pose_result_v2.json
"""

import base64
import io
import json
import math
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ── 配置 ───────────────────────────────────────────────────────
FRAMES_DIR  = Path(r"D:\WorkPath\fitness\video\frames\短视频")
OUTPUT_DIR  = Path(r"D:\WorkPath\fitness\video_analysis\短视频_results")
INTERVAL    = 0.5

PERIOD_SAMPLE_STEP = 5   # period 识别：每 5 帧取 1 帧 → ~117 帧
POSE_SAMPLE_STEP   = 2   # exercise 段：每 2 帧取 1 帧（段较短，多保留细节）
GRID_COLS_PERIOD   = 10  # period 网格列数
GRID_JPEG_QUALITY  = 88  # 网格图 JPEG 质量（不影响子图内容，仅影响拼图文件大小）

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://nextrouter.cc/v1")
MODEL           = "gemini-3-flash-preview"

TRAINING_PLAN = {
    "planId": "plan_demo_001",
    "userId": "user_test_001",
    "date": "2026-05-27",
    "name": "全身基础训练",
    "phases": [
        {
            "phaseName": "warmup",
            "order": 1,
            "exercises": [
                {"order": 1, "equipmentId": "equip_treadmill_01", "exerciseName": "跑步机慢跑"}
            ]
        },
        {
            "phaseName": "strength",
            "order": 2,
            "exercises": [
                {"order": 2, "equipmentId": "equip_smith_machine_01", "exerciseName": "史密斯机深蹲"}
            ]
        },
        {
            "phaseName": "core",
            "order": 3,
            "exercises": [
                {"order": 3, "equipmentId": "equip_pull_up_bar_01", "exerciseName": "悬垂举腿"}
            ]
        }
    ]
}
# ─────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════
# Prompts（来自 period_recognize_v2.yaml / pose_recognize_v2.yaml）
# ═══════════════════════════════════════════════════════════════

PERIOD_SYSTEM = """\
你是一个专业的第一人称健身视频分析 AI。

你将收到：
- 一张由多个视频关键帧按时间顺序拼接而成的网格图
- 读取顺序：从左到右、从上到下，即第 1 帧在左上角

你的任务：
将视频切分为 exercise / transition / rest 三类时间段。
不需要识别具体动作名称或器材，只需判断用户当前处于哪个阶段。

======================
【时间计算方法】
======================

- 第 N 帧（从 1 开始）的时间 = (N - 1) × frame_interval（秒）
- startFrame / endFrame 均指帧序号（从 1 开始）
- startTime = (startFrame - 1) × frame_interval
- endTime   = endFrame × frame_interval
- duration  = endTime - startTime

======================
【阶段分类】
======================

exercise（正在训练）：重复性动作，固定在器材附近，规律视角节奏变化
transition（移动/准备）：行走、大范围视角变化、接近/离开器材、调整设备参数
rest（休息）：长时间静止、坐下、玩手机、喝水

======================
【第一人称视频特点】
======================

- 存在头部抖动、转头、手部遮挡、短暂模糊
- 网格中每格分辨率为原始帧大小，重点看整体行为模式
- 不要因单帧异常而误判阶段切换

======================
【输出要求】
======================

严格输出 JSON 数组，不允许 Markdown 包裹、注释、解释性文字。\
"""

POSE_SYSTEM = """\
你是一个专业的第一人称健身动作识别与评估 AI。

你将收到：
- 某一段 exercise 时间段的关键帧网格图（单张图片）
- 网格读取顺序：从左到右、从上到下
- 本段的起止时间与总时长
- 用户当日训练计划（JSON）

你的任务：
1. 识别器材与动作
2. 估算本段的组数与每组次数
3. 将识别结果与训练计划进行匹配，说明偏差

======================
【时长与组次估算】
======================

- totalDuration：本段总时长（秒），由输入直接给出
- estimatedSets：根据动作停顿、重新抓握、明显休息判断组数
- estimatedRepsPerSet：根据运动周期频率推断每组次数
- avgSetDuration：平均每组持续时长（秒）
- 如果无法估算，填 null 并在 note 中说明原因

======================
【计划匹配规则】
======================

匹配状态（status）：
- matched：器材 + 动作与计划完全吻合
- partial：器材一致，动作不同，需说明计划动作和实际动作的差异
- unplanned：计划中没有该动作/器材
- unknown：无法判断器材

======================
【置信度】
======================

confidence 范围 0~1：
- 0.9+ : 非常确定
- 0.7+ : 较确定
- < 0.5 : 不可靠，填 "unknown"

======================
【输出要求】
======================

严格输出 JSON 对象，不允许 Markdown 包裹、注释、解释性文字。\
"""


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def parse_frames(frames_dir: Path) -> list[dict]:
    pattern = re.compile(r"state(\d+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.jpg")
    frames = []
    for f in frames_dir.iterdir():
        m = pattern.match(f.name)
        if m:
            idx = int(m.group(1))
            ts  = datetime.strptime(m.group(2), "%Y-%m-%d_%H-%M-%S")
            frames.append({"index": idx, "timestamp": ts, "path": f})
    return sorted(frames, key=lambda x: x["index"])


def frame_time_sec(all_frames: list[dict], frame: dict) -> float:
    return (frame["index"] - all_frames[0]["index"]) * INTERVAL


def build_grid_image(frames: list[dict], cols: int, jpeg_quality: int = GRID_JPEG_QUALITY) -> tuple[bytes, int, int]:
    """
    将帧列表拼成网格图（子图保持原始像素尺寸，不缩放）。
    返回 (jpeg_bytes, grid_cols, grid_rows)。
    """
    if not frames:
        raise ValueError("frames 为空")

    # 读取第一帧确定单帧尺寸
    sample = Image.open(frames[0]["path"])
    fw, fh = sample.size
    sample.close()

    rows = math.ceil(len(frames) / cols)
    grid_w = cols * fw
    grid_h = rows * fh

    print(f"    子图尺寸: {fw}×{fh}px，网格: {cols}列×{rows}行 → {grid_w}×{grid_h}px，共 {len(frames)} 帧")

    canvas = Image.new("RGB", (grid_w, grid_h), color=(30, 30, 30))

    for i, frame in enumerate(frames):
        img = Image.open(frame["path"])
        # 不做任何缩放，直接粘贴
        x = (i % cols) * fw
        y = (i // cols) * fh
        canvas.paste(img, (x, y))
        img.close()

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=jpeg_quality)
    jpeg_bytes = buf.getvalue()
    print(f"    网格图大小: {len(jpeg_bytes)/1024:.0f} KB")
    return jpeg_bytes, cols, rows


def image_to_data_url(jpeg_bytes: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()


def gemini_generate(system_prompt: str, user_content: list[dict]) -> str:
    url = f"{GEMINI_BASE_URL}/chat/completions"
    img_count = sum(1 for c in user_content if c.get("type") == "image_url")
    print(f"  → 请求: {img_count} 张图片（网格拼图）")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 8192,
    }
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(1, 4):
        resp = requests.post(url, headers=headers, json=payload, timeout=600)
        if resp.status_code == 429:
            wait = 60 * attempt
            print(f"  [429] 等待 {wait}s 后重试（{attempt}/3）...")
            time.sleep(wait)
            continue
        if not resp.ok:
            print(f"  [HTTP {resp.status_code}] {resp.text[:300]}")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    raise RuntimeError("超过最大重试次数")


def extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = [l for l in lines if not l.startswith("```")]
        text = "\n".join(inner).strip()
    return json.loads(text)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 已保存: {path}")


def is_exercise(seg: dict) -> bool:
    return any(seg.get(k) == "exercise" for k in ("status", "event", "state", "type"))


# ═══════════════════════════════════════════════════════════════
# Step 1: 阶段划分（period_recognize_v2）
# ═══════════════════════════════════════════════════════════════

def run_period_recognize(all_frames: list[dict]) -> list[dict]:
    print("\n=== Step 1: 阶段划分 (period_recognize_v2) ===")
    sampled = all_frames[::PERIOD_SAMPLE_STEP]
    print(f"  总帧数: {len(all_frames)}, 采样帧数: {len(sampled)} (每 {PERIOD_SAMPLE_STEP} 帧取 1)")

    # 拼网格图（子图不缩放）
    jpeg_bytes, g_cols, g_rows = build_grid_image(sampled, cols=GRID_COLS_PERIOD)

    user_content = [
        {
            "type": "text",
            "text": (
                f"以下是视频关键帧网格图：\n"
                f"- 列数：{g_cols}，行数：{g_rows}\n"
                f"- 有效帧数：{len(sampled)} 帧，帧间隔：{INTERVAL * PERIOD_SAMPLE_STEP}s\n"
                f"- 读取顺序：从左到右、从上到下\n\n"
                f"请将视频切分为 exercise / transition / rest 时间段，严格输出 JSON 数组。"
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": image_to_data_url(jpeg_bytes)},
        },
    ]

    raw = gemini_generate(PERIOD_SYSTEM, user_content)
    print(f"  原始响应长度: {len(raw)} 字符")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "period_raw_response_v2.txt").write_text(raw, encoding="utf-8")

    try:
        result = extract_json(raw)
    except json.JSONDecodeError as e:
        print(f"  [警告] JSON 解析失败: {e}")
        result = {"raw_response": raw}

    meta = {
        "source": str(FRAMES_DIR),
        "total_frames": len(all_frames),
        "sampled_frames": len(sampled),
        "sample_step": PERIOD_SAMPLE_STEP,
        "effective_interval_sec": INTERVAL * PERIOD_SAMPLE_STEP,
        "grid": {"cols": g_cols, "rows": g_rows},
        "model": MODEL,
        "created_at": datetime.now().isoformat(),
        "result": result,
    }
    save_json(meta, OUTPUT_DIR / "period_result_v2.json")

    # 取出 segments 列表
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        return result.get("segments", [])
    return []


# ═══════════════════════════════════════════════════════════════
# Step 2: 运动识别（pose_recognize_v2）
# ═══════════════════════════════════════════════════════════════

def run_pose_recognize(all_frames: list[dict], segments: list[dict]) -> list[dict]:
    print("\n=== Step 2: 运动识别 (pose_recognize_v2) ===")

    exercise_segs = [s for s in segments if is_exercise(s)]
    # 补全缺失 segmentId
    for i, s in enumerate(exercise_segs, 1):
        if not s.get("segmentId"):
            s["segmentId"] = f"exercise_{i:03d}"

    print(f"  共 {len(exercise_segs)} 个 exercise 段")
    if not exercise_segs:
        save_json({"message": "no exercise segments found"}, OUTPUT_DIR / "pose_result_v2.json")
        return []

    plan_json  = json.dumps(TRAINING_PLAN, ensure_ascii=False, indent=2)
    all_results = []

    for seg in exercise_segs:
        seg_id  = seg.get("segmentId", "?")
        t_start = seg.get("startTime", 0.0)
        t_end   = seg.get("endTime",   0.0)
        fi_s    = seg.get("startFrame")
        fi_e    = seg.get("endFrame")

        print(f"\n  处理 {seg_id}: {t_start:.1f}s ~ {t_end:.1f}s")

        # 取该段帧（优先用 startFrame/endFrame，否则按时间过滤）
        if fi_s is not None and fi_e is not None:
            seg_frames = [f for f in all_frames if fi_s <= f["index"] <= fi_e]
        else:
            seg_frames = [
                f for f in all_frames
                if t_start - 0.1 <= frame_time_sec(all_frames, f) <= t_end + 0.1
            ]

        if not seg_frames:
            print(f"    [警告] 无匹配帧，跳过")
            continue

        sampled_seg = seg_frames[::POSE_SAMPLE_STEP]
        print(f"    段内帧数: {len(seg_frames)}, 采样: {len(sampled_seg)} 帧")

        # 自动决定列数（尽量接近正方形）
        g_cols = max(1, round(math.sqrt(len(sampled_seg))))
        jpeg_bytes, g_cols, g_rows = build_grid_image(sampled_seg, cols=g_cols)

        dur = t_end - t_start
        user_content = [
            {
                "type": "text",
                "text": (
                    f"以下是 exercise 段 {seg_id} 的关键帧网格图：\n"
                    f"- 列数：{g_cols}，行数：{g_rows}\n"
                    f"- 有效帧数：{len(sampled_seg)} 帧，帧间隔：{INTERVAL * POSE_SAMPLE_STEP}s\n"
                    f"- 本段时间：{t_start:.1f}s ~ {t_end:.1f}s（共 {dur:.1f}s）\n\n"
                    f"用户当天的训练计划：\n{plan_json}\n\n"
                    f"请识别：\n"
                    f"1. 使用器材与动作名称\n"
                    f"2. 组数与每组次数估算\n"
                    f"3. 与训练计划的匹配情况及偏差说明\n\n"
                    f"严格输出 JSON。"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": image_to_data_url(jpeg_bytes)},
            },
        ]

        raw = gemini_generate(POSE_SYSTEM, user_content)
        print(f"    原始响应长度: {len(raw)} 字符")

        raw_path = OUTPUT_DIR / f"pose_raw_{seg_id}_v2.txt"
        raw_path.write_text(raw, encoding="utf-8")
        print(f"    [OK] 原始响应: {raw_path}")

        try:
            seg_result = extract_json(raw)
        except json.JSONDecodeError as e:
            print(f"    [警告] JSON 解析失败: {e}")
            seg_result = {"raw_response": raw}

        all_results.append({
            "segmentId":      seg_id,
            "startTime":      t_start,
            "endTime":        t_end,
            "duration":       dur,
            "frames_analyzed": len(sampled_seg),
            "grid":           {"cols": g_cols, "rows": g_rows},
            "pose_data":      seg_result,
        })

    save_json(
        {
            "source":    str(FRAMES_DIR),
            "model":     MODEL,
            "created_at": datetime.now().isoformat(),
            "results":   all_results,
        },
        OUTPUT_DIR / "pose_result_v2.json",
    )
    return all_results


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    if not GEMINI_API_KEY:
        print("[错误] GEMINI_API_KEY 未设置")
        sys.exit(1)

    try:
        from PIL import Image  # noqa
    except ImportError:
        print("[错误] 需要 Pillow: pip install Pillow")
        sys.exit(1)

    all_frames = parse_frames(FRAMES_DIR)
    if not all_frames:
        print("[错误] 未找到关键帧")
        sys.exit(1)

    total_dur = frame_time_sec(all_frames, all_frames[-1])
    print(f"帧数: {len(all_frames)}, 时长约 {total_dur:.1f}s")

    segments = run_period_recognize(all_frames)
    run_pose_recognize(all_frames, segments)
    print("\n全部完成！")


if __name__ == "__main__":
    main()
