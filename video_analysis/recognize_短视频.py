"""
recognize_短视频.py
-----------------
两阶段 LLM 识别短视频内容：
  Step 1: period_recognize_v1  → 阶段划分（exercise / transition / rest）
  Step 2: pose_recognize_v1    → 【exercise 段】具体运动识别

输出（保存在 OUTPUT_DIR）：
  period_result.json  — 阶段划分结果
  pose_result.json    — 运动识别结果

用法：
    python recognize_短视频.py
"""

import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── 配置 ───────────────────────────────────────────────────────
FRAMES_DIR  = Path(r"D:\WorkPath\fitness\video\frames\短视频")
OUTPUT_DIR  = Path(r"D:\WorkPath\fitness\video_analysis\短视频_results")
INTERVAL    = 0.5           # 帧间隔（秒），与 extract_keyframes 保持一致

# 采样步长：period 识别每 N 帧取 1 帧，降低请求体积
PERIOD_SAMPLE_STEP = 1      # 全部帧
POSE_SAMPLE_STEP   = 3      # exercise 段每 3 帧取 1 帧

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://nextrouter.cc/v1")
MODEL           = "gemini-3-flash-preview"
# ─────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════
# Prompts（来自 period_recognize_v1.yaml / pose_recognize_v1.yaml）
# ═══════════════════════════════════════════════════════════════

PERIOD_SYSTEM_PROMPT = """\
你是一个专业的第一人称健身行为事件切分 AI。

你将收到：
- 按时间顺序排列的视频关键帧
- 每张图对应时间戳
- 每张图对应 motion 值（画面运动幅度）

你的任务：
对整个视频进行行为阶段切分。

======================
【事件分类】
======================

仅允许以下三种状态：

1. exercise
   用户正在进行明确训练动作。

   特征：
   - 重复性动作
   - 固定器材附近
   - 持续运动节奏
   - 规律视角变化
   - 长时间停留在训练区域

2. transition
   用户正在移动或切换区域。

   特征：
   - 行走
   - 大范围视角变化
   - 场景快速变化
   - 接近器材
   - 离开器材
   - 调整位置

3. rest
   用户正在休息。

   特征：
   - 长时间静止
   - 无明显重复动作
   - motion 较低
   - 坐下/站立不动
   - 玩手机/喝水

======================
【重要规则】
======================

你的核心目标：
是划分时间段，而不是识别具体动作。

不需要详细判断：
- 深蹲
- 引体向上
- 卧推

只需要判断：
当前是否属于：
- exercise
- rest
- transition

======================
【事件切分规则】
======================

出现以下情况必须切换事件：

- 用户停止训练
- 用户开始移动
- 用户开始休息
- 用户开始训练
- 场景明显变化
- 器材区域变化

注意：
短时间镜头晃动不能直接切分事件。

必须综合考虑：
- 连续关键帧
- 场景连续性
- motion 连续性
- 行为连续性

======================
【第一人称视频特点】
======================

第一人称视频存在：
- 头部抖动
- 转头
- 手部遮挡
- 短暂模糊

不要因为这些情况误判。

======================
【时间规则】
======================

startTime:
  当前事件开始时间（秒）

endTime:
  当前事件结束时间（秒）

duration:
  endTime - startTime

======================
【输出要求】
======================

必须严格输出 JSON 数组。

不允许：
- Markdown
- 注释
- 解释
- 多余文本\
"""

PERIOD_USER_SUFFIX = """\

请对视频进行时间段划分。

输出：
- 状态类型
- 开始时间
- 结束时间
- 持续时间
- 状态说明

严格输出 JSON。\
"""

POSE_SYSTEM_PROMPT = """\
你是一个专业的第一人称健身动作识别 AI。

输入：
- 某一段 exercise 时间段中的关键帧
- 时间戳
- motion 数值

你的任务：
识别用户正在进行的具体训练动作。

======================
【识别目标】
======================

需要识别：

- 器材类型
- 动作名称
- 当前训练状态
- 动作连续性
- 是否属于有效训练

======================
【器材识别范围】
======================

常见器材包括：

- 跑步机
- 引体向上杆
- 史密斯机
- 哑铃
- 杠铃
- 龙门架
- 绳索器械
- 划船机
- 椭圆机
- 卧推椅
- 深蹲架

======================
【动作识别范围】
======================

常见动作包括：

- 引体向上
- 深蹲
- 卧推
- 划船
- 推举
- 慢跑
- 快走
- 悬垂举腿
- 核心训练

======================
【第一人称视角分析重点】
======================

重点结合：

- 手部位置
- 镜中反射
- 运动节奏
- 视角上下变化
- 器材结构
- 运动重复性

不要仅凭单帧判断。

必须结合：
- 连续关键帧
- motion 变化
- 场景一致性

======================
【状态定义】
======================

status 仅允许：

- exercise
- rest
- unknown

如果：
- 无法确定动作
- 画面模糊
- 器材不可见

则：
- equipmentId = "unknown"
- equipmentName = "unknown"
- movementName = "unknown"

======================
【置信度】
======================

confidence 范围：
0~1

confidence 含义：
- 0.9+ : 非常确定
- 0.7+ : 较确定
- 0.5 以下 : 不可靠

======================
【输出要求】
======================

必须严格输出 JSON 数组。

不允许：
- Markdown
- 注释
- 解释
- 多余文本\
"""

POSE_USER_SUFFIX = """\

请识别：
- 用户正在进行的训练动作
- 使用器材
- 动作状态
- 动作置信度

严格输出 JSON。\
"""


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def parse_frames(frames_dir: Path) -> list[dict]:
    """解析帧文件夹，返回按 index 排序的帧列表。"""
    pattern = re.compile(r"state(\d+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.jpg")
    frames = []
    for f in frames_dir.iterdir():
        m = pattern.match(f.name)
        if m:
            idx = int(m.group(1))
            ts  = datetime.strptime(m.group(2), "%Y-%m-%d_%H-%M-%S")
            frames.append({"index": idx, "timestamp": ts, "path": f})
    return sorted(frames, key=lambda x: x["index"])


def frame_time_sec(frames: list[dict], frame: dict) -> float:
    """计算帧相对于第一帧的时间（秒）。"""
    return (frame["index"] - frames[0]["index"]) * INTERVAL


def encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def build_openai_content(frames: list[dict], all_frames: list[dict], step: int = 1) -> list[dict]:
    """构建 OpenAI-compatible vision content，文本+图片交替排列。"""
    content = []
    selected = frames[::step]
    for frame in selected:
        t = frame_time_sec(all_frames, frame)
        label = f"[Frame {frame['index']} | Time: {t:.1f}s | {frame['timestamp']:%H:%M:%S} | motion: N/A]"
        content.append({"type": "text", "text": label})
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encode_image(frame['path'])}",
            },
        })
    return content


def gemini_generate(system_prompt: str, user_content: list[dict]) -> str:
    """调用 OpenAI-compatible API（nextrouter.cc 代理 Gemini），返回响应文本。"""
    url = f"{GEMINI_BASE_URL}/chat/completions"
    image_count = sum(1 for c in user_content if c.get("type") == "image_url")
    print(f"  → 发送请求（{len(user_content)} content items，含 {image_count} 帧图片）")
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
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        resp = requests.post(url, headers=headers, json=payload, timeout=600)
        if resp.status_code == 429:
            wait = 60 * attempt
            print(f"  [429] Rate limit，等待 {wait}s 后重试（{attempt}/{max_retries}）...")
            time.sleep(wait)
            continue
        if not resp.ok:
            print(f"  [HTTP {resp.status_code}] 错误响应: {resp.text[:500]}")
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    raise RuntimeError("超过最大重试次数，请求失败")


def extract_json(text: str) -> list | dict:
    """从响应文本中提取 JSON，兼容 Markdown 代码块包装。"""
    text = text.strip()
    # 去除 ```json ... ``` 包装
    if text.startswith("```"):
        lines = text.split("\n")
        inner = []
        in_block = False
        for line in lines:
            if line.startswith("```"):
                in_block = not in_block
                continue
            if in_block or (not text.startswith("```") and not line.startswith("```")):
                inner.append(line)
        text = "\n".join(inner).strip()
    return json.loads(text)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 已保存: {path}")


# ═══════════════════════════════════════════════════════════════
# Step 1: 阶段划分
# ═══════════════════════════════════════════════════════════════

def run_period_recognize(all_frames: list[dict]) -> list[dict]:
    print("\n=== Step 1: 阶段划分 (period_recognize_v1) ===")
    sampled = all_frames[::PERIOD_SAMPLE_STEP]
    print(f"  总帧数: {len(all_frames)}, 采样帧数: {len(sampled)} (每 {PERIOD_SAMPLE_STEP} 帧取 1)")

    # 构建 user content（OpenAI-compatible vision 格式）
    user_content = [{"type": "text", "text": "以下是按时间顺序排列的视频关键帧：\n"}]
    user_content += build_openai_content(sampled, all_frames, step=1)
    user_content.append({"type": "text", "text": PERIOD_USER_SUFFIX})

    raw = gemini_generate(PERIOD_SYSTEM_PROMPT, user_content)
    print(f"  原始响应长度: {len(raw)} 字符")

    # 立即保存原始响应，防止后续失败导致丢失
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = OUTPUT_DIR / "period_raw_response.txt"
    raw_path.write_text(raw, encoding="utf-8")
    print(f"  [OK] 原始响应已保存: {raw_path}")

    try:
        result = extract_json(raw)
    except json.JSONDecodeError as e:
        print(f"  [警告] JSON 解析失败: {e}")
        result = {"raw_response": raw}

    # 保存解析结果
    out_path = OUTPUT_DIR / "period_result.json"
    meta = {
        "source": str(FRAMES_DIR),
        "total_frames": len(all_frames),
        "sampled_frames": len(sampled),
        "sample_step": PERIOD_SAMPLE_STEP,
        "model": MODEL,
        "created_at": datetime.now().isoformat(),
        "segments": result,
    }
    save_json(meta, out_path)
    return result if isinstance(result, list) else []


# ═══════════════════════════════════════════════════════════════
# Step 2: 运动识别（仅 exercise 段）
# ═══════════════════════════════════════════════════════════════

def run_pose_recognize(all_frames: list[dict], period_result: list[dict]) -> list[dict]:
    print("\n=== Step 2: 运动识别 (pose_recognize_v1) ===")

    # 取出 exercise 段（兼容 status / event / state 三种字段名）
    def is_exercise(seg):
        return any(
            seg.get(k) == "exercise"
            for k in ("status", "event", "state")
        )

    exercise_segments = [s for s in period_result if is_exercise(s)]
    # 补全缺失的 segmentId
    for i, seg in enumerate(exercise_segments, 1):
        if not seg.get("segmentId"):
            seg["segmentId"] = f"exercise_{i:03d}"
    print(f"  共 {len(exercise_segments)} 个 exercise 段")

    if not exercise_segments:
        print("  未找到 exercise 段，跳过。")
        out_path = OUTPUT_DIR / "pose_result.json"
        save_json({"message": "no exercise segments found", "segments": []}, out_path)
        return []

    all_pose_results = []

    for seg in exercise_segments:
        seg_id    = seg.get("segmentId", f"seg_{exercise_segments.index(seg)+1:03d}")
        t_start   = seg.get("startTime", 0)
        t_end     = seg.get("endTime", 0)
        fi_start  = seg.get("startFrameIndex")
        fi_end    = seg.get("endFrameIndex")

        print(f"\n  处理 {seg_id}: {t_start:.1f}s ~ {t_end:.1f}s")

        # 根据 startFrameIndex / endFrameIndex 取帧，若无则按时间过滤
        if fi_start is not None and fi_end is not None:
            seg_frames = [f for f in all_frames if fi_start <= f["index"] <= fi_end]
        else:
            seg_frames = [
                f for f in all_frames
                if t_start <= frame_time_sec(all_frames, f) <= t_end
            ]

        if not seg_frames:
            print(f"    [警告] 该段无匹配帧，跳过。")
            continue

        print(f"    帧数: {len(seg_frames)}, 采样步长: {POSE_SAMPLE_STEP}")

        # 构建 user content（OpenAI-compatible vision 格式）
        user_content = [{"type": "text", "text": f"以下是某段 exercise 时间段的关键帧（{seg_id}，{t_start:.1f}s ~ {t_end:.1f}s）：\n"}]
        user_content += build_openai_content(seg_frames, all_frames, step=POSE_SAMPLE_STEP)
        user_content.append({"type": "text", "text": POSE_USER_SUFFIX})

        raw = gemini_generate(POSE_SYSTEM_PROMPT, user_content)
        print(f"    原始响应长度: {len(raw)} 字符")

        # 立即保存原始响应
        raw_path = OUTPUT_DIR / f"pose_raw_{seg_id}.txt"
        raw_path.write_text(raw, encoding="utf-8")
        print(f"    [OK] 原始响应已保存: {raw_path}")

        try:
            seg_result = extract_json(raw)
        except json.JSONDecodeError as e:
            print(f"    [警告] JSON 解析失败: {e}")
            seg_result = {"raw_response": raw}

        all_pose_results.append({
            "segmentId": seg_id,
            "startTime": t_start,
            "endTime":   t_end,
            "frames_analyzed": len(seg_frames[::POSE_SAMPLE_STEP]),
            "pose_data": seg_result,
        })

    out_path = OUTPUT_DIR / "pose_result.json"
    meta = {
        "source": str(FRAMES_DIR),
        "model": MODEL,
        "created_at": datetime.now().isoformat(),
        "exercise_segments_count": len(exercise_segments),
        "results": all_pose_results,
    }
    save_json(meta, out_path)
    return all_pose_results


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    if not GEMINI_API_KEY:
        print("[错误] 环境变量 GEMINI_API_KEY 未设置")
        sys.exit(1)

    print(f"帧目录: {FRAMES_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")

    all_frames = parse_frames(FRAMES_DIR)
    if not all_frames:
        print("[错误] 未找到关键帧文件")
        sys.exit(1)

    total_dur = frame_time_sec(all_frames, all_frames[-1])
    print(f"帧数: {len(all_frames)}, 视频时长约 {total_dur:.1f}s")

    # Step 1
    period_result = run_period_recognize(all_frames)

    # Step 2
    run_pose_recognize(all_frames, period_result)

    print("\n全部完成！")


if __name__ == "__main__":
    main()
