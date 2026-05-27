"""一次性把所有关键帧给 LLM，让它先划分时间线段，再做识别。

与默认的 frame_classifier.py 区别：
  默认版：8 张/批，AI 在每批内独立判断，跨批容易丢上下文
  本版：所有 N 张一次性丢给 LLM，AI 看到完整时间线再分段

提示流程：
  1. 让 AI 把连续帧划成"段"（status + 起止 frameIndex）
  2. 对每个 exercise 段，识别 equipmentName + movementName

输出仍是 list[KeyframeLabel]，与默认版兼容，下游 segment_merger / set_detector 不变。
"""

from __future__ import annotations

import base64
import json
import math
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from openai import OpenAI

from . import config
from .frame_classifier import _make_openai_client, _encode_image_b64
from .keyframe_extractor import FrameMeta, _imread_unicode
from .models import KeyframeLabel


# ---------------------------------------------------------------------------
# 网格合成：把 N 张关键帧拼成一张大图，每个 cell 标 frame index
# ---------------------------------------------------------------------------

def _compute_grid_layout(n: int, min_cell_w: int = 110, max_canvas_w: int = 4400) -> tuple[int, int, int, int]:
    """计算 (cols, rows, cell_w, cell_h)。

    目标：单个 cell 至少 min_cell_w × min_cell_w*9/16 像素（保证 AI 能看清动作细节）；
    网格 ≈ 16:9 宽高比；整张画布宽度允许放大到 max_canvas_w 以容纳更多帧。

    对大批量帧（如 600+），网格会变得很大。GPT-5 视觉对 4000+px 宽的图像处理良好。
    """
    # 优先满足 cell 大小，列数据由 cell 决定
    ratio = (16 / 9) * (16 / 9) / 2  # ≈ 1.58
    cols = max(1, round(math.sqrt(n * ratio)))
    # 在不超过画布上限的前提下，cell 尽量大
    cell_w = min(220, max(min_cell_w, max_canvas_w // cols))
    rows = math.ceil(n / cols)
    cell_h = int(cell_w * 9 / 16)
    return cols, rows, cell_w, cell_h


def _create_grid_composite(
    frames: list[FrameMeta],
    frames_dir: Path,
) -> tuple[bytes, int, int, int, int]:
    """合成网格大图。返回 (JPEG bytes, cols, rows, cell_w, cell_h)。

    每个 cell 在左上角用绿色文字标注 frame index，方便 AI 引用。
    """
    n = len(frames)
    cols, rows, cell_w, cell_h = _compute_grid_layout(n)

    canvas_w = cols * cell_w
    canvas_h = rows * cell_h
    canvas = np.full((canvas_h, canvas_w, 3), 240, dtype=np.uint8)  # 浅灰底

    for i, f in enumerate(frames):
        img = _imread_unicode(frames_dir / f.filename, cv2.IMREAD_COLOR)
        if img is None:
            continue
        # 等比缩放 + 居中放入 cell
        h, w = img.shape[:2]
        scale = min(cell_w / w, cell_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        # 居中
        r, c = divmod(i, cols)
        y0 = r * cell_h + (cell_h - new_h) // 2
        x0 = c * cell_w + (cell_w - new_w) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = resized

        # 帧索引标签（绿底白字，左上角）
        label = f"{f.frameIndex}"
        lbl_w = max(22, 8 * len(label) + 6)
        lbl_h = 14
        ly0 = r * cell_h
        lx0 = c * cell_w
        cv2.rectangle(canvas, (lx0, ly0), (lx0 + lbl_w, ly0 + lbl_h),
                      (40, 180, 40), thickness=-1)
        cv2.putText(canvas, label, (lx0 + 3, ly0 + 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

    ok, buf = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not ok:
        raise RuntimeError("网格图编码失败")
    return buf.tobytes(), cols, rows, cell_w, cell_h


# ---------------------------------------------------------------------------
# Prompt 构造
# ---------------------------------------------------------------------------

def _build_movements_block() -> str:
    lines = []
    for name in config.EQUIPMENT_NAMES:
        spec = config.EQUIPMENT_LIBRARY[name]
        if spec["movements"]:
            lines.append(f"  - {name}: {' / '.join(spec['movements'])}")
    return "\n".join(lines)


def _format_training_plan(training_plan: dict | None) -> tuple[str, int]:
    """把训练计划 JSON 格式化成 prompt 友好的文本。

    返回 (人类可读的计划文本, 动作总数)。
    """
    if not training_plan:
        return "（本次训练未提供训练计划）", 0

    lines = []
    name = training_plan.get("name") or training_plan.get("planName") or "未命名"
    lines.append(f"计划名称：{name}")
    date = training_plan.get("date") or training_plan.get("targetDate")
    if date:
        lines.append(f"计划日期：{date}")

    n_exercises = 0
    phases = training_plan.get("phases", [])
    if phases:
        for phase in phases:
            phase_name = phase.get("phaseName", "")
            phase_lines = []
            for ex in phase.get("exercises", []):
                n_exercises += 1
                order = ex.get("order", n_exercises)
                ex_name = ex.get("exerciseName") or ex.get("movementName") or "未命名动作"
                eq = ex.get("equipmentId") or ex.get("equipmentName") or ""
                tail = f"（{eq}）" if eq else ""
                phase_lines.append(f"  动作 {order}. {ex_name}{tail}")
            if phase_lines:
                lines.append(f"\n【{phase_name} 阶段】")
                lines.extend(phase_lines)
    else:
        # 兼容 v2.1 规格中扁平的 plannedExercises 数组
        for ex in training_plan.get("plannedExercises", []):
            n_exercises += 1
            order = ex.get("order", n_exercises)
            ex_name = ex.get("movementName") or ex.get("exerciseName") or "未命名动作"
            eq = ex.get("equipmentId") or ex.get("equipmentName") or ""
            tail = f"（{eq}）" if eq else ""
            lines.append(f"  动作 {order}. {ex_name}{tail}")

    return "\n".join(lines), n_exercises


def _build_full_context_prompt(
    n_frames: int,
    interval_s: float,
    total_duration_s: float,
    training_plan: dict | None = None,
) -> str:
    equipment_names = "、".join(f'"{nm}"' for nm in config.EQUIPMENT_NAMES)
    movements_block = _build_movements_block()
    n_equipment = len(config.EQUIPMENT_NAMES)
    plan_text, n_planned = _format_training_plan(training_plan)
    # 期望段数：考虑动作之间会有 transition / rest，2-3 倍是合理估计
    min_expected = max(3, n_planned + 2) if n_planned else 3
    max_expected = max(8, n_planned * 4 + 2) if n_planned else 20

    # 注意：JSON 示例里的 {} 用 {{}} 转义，避免 f-string 解释
    return f"""你是一名专业的健身视频时间线标注员。你的任务是分析一组按时间顺序排列的关键帧截图，将它们划分成多个连续的时间段。

## 输入说明

你收到的是一段健身房训练视频的 {n_frames} 张关键帧，按时间顺序排列，编号从 0 到 {n_frames - 1}。
相邻两帧间隔 {interval_s} 秒。视频总时长约 {total_duration_s:.1f} 秒。
视频为训练者**第一人称视角**（可穿戴相机），画面中**通常看不到训练者本人**，主要看到器械、健身房环境、显示屏等。

## ⚠️ 核心要求：根据训练计划对照视频，识别每个动作段

你会同时收到一份**本次训练计划**（见下方）。计划告诉你用户今天打算做哪些动作、用什么器械、做几组。
你的任务是在关键帧中找到每个计划动作对应的视频片段，并识别出动作之间的休息和移动。

### 本次训练计划

{plan_text}

### 你应该怎么用这份计划

- 计划是**参考**，不是硬约束。用户可能跳过某个动作、调换顺序、或临时加了计划外的动作。
- 计划告诉你「大概会出现哪些器械和动作」→ 帮你缩小识别范围，而不是直接抄答案。
- 你必须**用画面证据判断**，不能因为计划里写了"杠铃卧推"就把看到龙门架的帧也标成卧推。
- 如果视频中出现了计划里没有的器械/动作 → 正常标注，在 note 中注明「计划外」。
- 如果计划里的某个动作在视频中完全找不到 → 不要硬凑，该动作可能被跳过了。

### 期望的分段结构

根据计划，本次训练有 {n_planned} 个动作。加上每个动作之间的休息和移动，你的分段结果**大约**在 {min_expected} 到 {max_expected} 段之间。
这只是参考范围，实际多一些少一些都正常——关键是你的分段要有画面证据支撑。

## 你的工作流程（必须严格按此执行）

### 第一步：逐帧扫描，写出每一帧的状态标签

从第 0 帧开始，逐帧检查，为每一帧写出一个临时标签。你必须关注：
- 画面中主体是什么？（器械？走廊？地面？天花板？手机屏幕？水杯？）
- 画面是否在运动中？（模糊程度、前后帧的场景变化）
- 和前一帧相比，场景是否发生了变化？（器械换了？位置变了？视角突变？）

标签只有三种：
- **E**（exercise）：画面中可见用户**正在操作**某台器械（不是仅仅路过看到器械）
- **T**（transition）：画面在移动中——场景在变化、在走动、在换位置
- **R**（rest）：画面静止或接近静止——用户在坐着/站着/看手机/喝水/等待

### 第二步：重点检查——找出所有「状态切换点」

回顾你第一步写的标签序列，找出所有相邻帧标签不同的位置——这些就是切换点。
例如：帧 15 是 E，帧 16 是 R → 第 15-16 帧之间有一个切换点。

特别注意以下容易遗漏的切换信号：
- **器械变了**：前几帧是一台器械的特写，后几帧变成另一台器械 → 中间一定经过了 transition
- **视角突变**：前一帧看着器械，下一帧突然看到走廊/天花板/地面 → 状态切换了
- **画面从动到静**：前几帧画面有运动模糊，后几帧变清晰静止 → 从 exercise 进入 rest
- **画面从静到动**：反过来 → 从 rest 进入 exercise 或 transition

### 第三步：合并连续相同标签，生成分段

将连续的相同标签合并为一个段。合并规则：
- 连续的 E 帧且器械相同 → 合并为一个 exercise 段
- 连续的 E 帧但器械不同 → 必须拆成不同的 exercise 段（中间插入 transition）
- 连续的 T 帧 → 合并为一个 transition 段
- 连续的 R 帧 → 合并为一个 rest 段

**去噪规则**：如果某个段只有 1 帧（仅 {interval_s} 秒），且前后段类型相同 → 将这 1 帧归入前一段（视为噪声）。

### 第四步：对每个 exercise 段识别器械和动作

**equipmentName** 从以下 {n_equipment} 个标签中选一个：
{equipment_names}

**movementName** 从对应器械的候选动作中选一个：
{movements_block}

## 器械判断规则

### 🔴 核心原则：看到器械 ≠ 正在用器械

第一人称视角下，用户走过任何器械都会拍到它。你必须看到**操作证据**才能标记为 exercise：

| 器械 | 必须看到的操作证据 |
|------|------------------|
| 跑步机 | 履带在转动 + 控制面板亮着 + 画面有节奏性上下晃动 |
| 椭圆机 | 踏板在做椭圆运动 + 长动臂在前后摆 |
| 动感单车 | 腿部蹬踏动作 + 飞轮在转 |
| 划船机 | 滑座在前后滑动 + 拉绳/拉柄被拉动 |
| 杠铃 | 杠铃杆在移动（上下推/拉）或在用户身上（肩/胸前） |
| 史密斯架 | 双立柱内的杠铃在上下移动 + 卡扣可见 |
| 哑铃 | 用户手持哑铃在做动作（非仅放在架上） |
| 龙门架 | 绳索被拉紧 + 配重在升降（**双立柱**结构） |
| 高位下拉 | 用户坐在座椅上 + 从头顶拉下拉杆（**单立柱** + 大腿挡板） |
| 坐姿划船 | 坐在座垫上 + 横向拉杆被拉动 |
| 蝴蝶机 | 坐着 + 两侧扇形挡板在合拢/张开 |
| 腿举机 | 45°斜板 + 脚蹬踏板在推动 |
| 推肩机 | 坐着 + 双手握把向上推 |
| 自重训练 | 镜头低角度看地面/墙面 + 无器械被操作 |
| 引体向上 | 用户身体悬挂 + 脚离地 + 向上拉 |

### 🔴 易混淆场景

- **引体向上 vs 高位下拉**：脚离地悬挂 → 引体向上；坐在椅子上 → 高位下拉
- **龙门架 vs 高位下拉**：龙门架是**双立柱**独立结构；高位下拉是**单立柱** + 座椅 + 大腿挡板
- **路过器械 vs 使用器械**：画面快速扫过器械（1-2帧）→ transition；画面持续停留在同一器械（3帧以上）+ 有操作动作 → exercise
- **看手机/喝水**：即使坐在器械上，只要没在做动作 → rest（不是 exercise）

### 动作识别要点

- 杠铃：躺着向上推 → 卧推；站着从地面拉起 → 硬拉；杠铃在肩上蹲下 → 深蹲；屈臂向上 → 弯举
- 哑铃：双臂水平展开合拢 → 飞鸟；屈肘上举 → 弯举；过头推 → 推举
- 龙门架：高位双手向中合 → 绳索夹胸；屈肘下压 → 三头下压；低位水平拉 → 绳索划船
- 自重：躺地上抬头脚 → 卷腹；撑地推身体 → 俯卧撑；身体平直撑住不动 → 平板支撑

如果看不清具体动作，movementName 直接填 equipmentName（兜底）。

## 输出格式

严格输出 JSON，不要输出任何其他文字：

```json
{{
  "frame_labels": "EEEEERRRTTTEEEEEERRREEEE...",
  "segments": [
    {{
      "startFrameIndex": 0,
      "endFrameIndex": 5,
      "status": "exercise",
      "equipmentName": "杠铃",
      "movementName": "平板卧推",
      "confidence": 0.85,
      "plannedOrder": 1,
      "note": "可见杠铃杆在上下推动，配重片可见，对应计划第1个动作"
    }},
    {{
      "startFrameIndex": 6,
      "endFrameIndex": 8,
      "status": "rest",
      "note": "画面静止，坐在卧推凳上调息"
    }},
    {{
      "startFrameIndex": 9,
      "endFrameIndex": 11,
      "status": "transition",
      "note": "画面在移动，从卧推区走向龙门架"
    }},
    {{
      "startFrameIndex": 12,
      "endFrameIndex": 20,
      "status": "exercise",
      "equipmentName": "龙门架",
      "movementName": "绳索夹胸",
      "confidence": 0.78,
      "plannedOrder": null,
      "note": "绳索被拉紧配重在动，计划中未包含此动作（计划外）"
    }}
  ],
  "planCoverage": {{
    "matched": [1, 2, 3],
    "missed": [4],
    "unplanned": ["绳索夹胸"]
  }}
}}
```

### 输出规则

1. **frame_labels**：长度恰好 {n_frames} 个字符的字符串，每个字符是 E / T / R，对应每一帧的标签。这是你逐帧分析的中间结果，必须输出，用于验证你的分段是否正确。
2. **segments** 按时间顺序排列
3. 首段 startFrameIndex = 0，末段 endFrameIndex = {n_frames - 1}
4. 相邻段连续：segments[i+1].startFrameIndex == segments[i].endFrameIndex + 1
5. exercise 段必须填 equipmentName / movementName / confidence
6. exercise 段必须填 **plannedOrder**：如果该动作对应训练计划中的第 N 个动作则填 N，如果是计划外的动作则填 null
7. transition / rest 段只填 status 和 note
8. 每个段的 note 用一句话描述你看到了什么（这能帮助你自己验证判断是否合理）
9. **planCoverage** 对象：matched 列出在视频中找到的计划动作序号数组，missed 列出在视频中找不到的计划动作序号数组，unplanned 列出计划外动作的名称数组

### 自检清单（输出前必须检查）

- [ ] frame_labels 长度是否等于 {n_frames}？
- [ ] segments 是否覆盖了从 0 到 {n_frames - 1} 的所有帧？
- [ ] 对照训练计划，每个计划中的动作是否都尝试在视频中找到了对应段？找不到的是否确认为"跳过"？
- [ ] 每个 exercise 段的 note 里是否描述了你看到的操作证据？（不能仅因为计划里有这个动作就标注）
- [ ] 是否有 exercise 段超过 40 帧？如果有，请检查中间是否包含了组间休息——真实训练中一组通常 20-60 秒，之后会有 30-120 秒的休息
- [ ] 两个不同器械的 exercise 段之间，是否有 transition 或 rest 段隔开？（用户不可能瞬间从一台器械跳到另一台）
"""


# ---------------------------------------------------------------------------
# 单次大调用
# ---------------------------------------------------------------------------

def _classify_all_frames(
    client: OpenAI,
    frames: list[FrameMeta],
    motions: list[float],
    frames_dir: Path,
    training_plan: dict | None = None,
    max_retries: int = 3,
) -> tuple[list[dict[str, Any]], bytes, tuple[int, int, int, int]]:
    """一次性把所有帧丢给 LLM。

    实现：把 N 帧合成为一张大网格图（每个 cell 标 frame index），作为单张图发给 API
    （网关限制每次最多 20 个文件，单张大图能绕过这限制并保持"全量上下文"语义）。

    training_plan：可选的训练计划 JSON dict，会被格式化进 prompt 帮 AI 缩小识别范围。

    返回 (segments 列表, 网格图 bytes, 网格元数据 (cols, rows, cell_w, cell_h))。
    """
    n = len(frames)
    total_duration_s = (n - 1) * config.SAMPLING_INTERVAL_S if n > 0 else 0.0
    system_prompt = _build_full_context_prompt(
        n_frames=n,
        interval_s=config.SAMPLING_INTERVAL_S,
        total_duration_s=total_duration_s,
        training_plan=training_plan,
    )

    # 合成网格大图
    composite_bytes, cols, rows, cell_w, cell_h = _create_grid_composite(frames, frames_dir)
    composite_b64 = base64.b64encode(composite_bytes).decode("ascii")

    intro = (
        f"以下是整段训练视频的全部 {n} 张关键帧，已**合成为一张大网格图**：\n"
        f"  - 网格布局：{cols} 列 × {rows} 行（共 {cols * rows} 个 cell，最后 {cols * rows - n} 个 cell 留空）\n"
        f"  - 每个 cell 左上角的**绿底白字数字**就是 frame index（0-based，从左到右、从上到下）\n"
        f"  - 每张关键帧相隔 {config.SAMPLING_INTERVAL_S} 秒，所以 frameIndex × {config.SAMPLING_INTERVAL_S} = 该帧在视频中的秒数\n\n"
        f"附加每帧的运动强度 motion（相对前一帧灰度 absdiff 均值，0-50，"
        f"≥6 表示画面在动，<2 表示静止）：\n"
        f"motion = {motions}\n\n"
        f"请按系统提示中的两步法分析整张网格图，输出 segments 列表。"
    )
    content: list[dict[str, Any]] = [
        {"type": "text", "text": intro},
        {"type": "image_url", "image_url": {
            "url": f"data:image/jpeg;base64,{composite_b64}",
            "detail": "high",  # 网格图需要高细节才能看清每个 cell
        }},
    ]

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=config.VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                response_format={"type": "json_object"},
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise ValueError("空响应")
            parsed = json.loads(raw)
            segs = parsed.get("segments") if isinstance(parsed, dict) else None
            if not segs:
                raise ValueError("响应中缺少 segments 字段")
            return segs, composite_bytes, (cols, rows, cell_w, cell_h)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"    [重试 {attempt+1}/{max_retries}] 解析失败: {e}", flush=True)
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"    [重试 {attempt+1}/{max_retries}] API 错误: {e}", flush=True)
                time.sleep(3.0 * (attempt + 1))
                continue
            raise


# ---------------------------------------------------------------------------
# 段 → 每帧 KeyframeLabel
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"exercise", "transition", "rest"}


def _segments_to_keyframe_labels(
    segments: list[dict[str, Any]],
    frames: list[FrameMeta],
    motions: list[float],
    frames_subpath: str,
) -> list[KeyframeLabel]:
    """把 LLM 输出的段展开成与帧一一对应的 KeyframeLabel 列表。

    展开规则：段内每一帧都继承该段的 status / equipment / movement / confidence；
    note 同步到每一帧便于追溯。
    """
    labels: list[KeyframeLabel] = []
    n = len(frames)

    # 用一个 frameIndex → segment 的映射
    seg_for_frame: list[dict[str, Any] | None] = [None] * n
    for seg in segments:
        try:
            s_start = int(seg.get("startFrameIndex"))
            s_end = int(seg.get("endFrameIndex"))
        except (TypeError, ValueError):
            continue
        s_start = max(0, s_start)
        s_end = min(n - 1, s_end)
        for i in range(s_start, s_end + 1):
            seg_for_frame[i] = seg

    for f, m in zip(frames, motions):
        seg = seg_for_frame[f.frameIndex]
        if seg is None:
            # AI 输出有空隙，补占位
            labels.append(KeyframeLabel(
                frameIndex=f.frameIndex,
                timestamp=f.timestamp,
                status="rest",
                confidence=0.0,
                imageUrl=f"{frames_subpath}/{f.filename}",
                note="未覆盖段（AI 输出空隙）",
                motion=m,
            ))
            continue

        status = seg.get("status")
        if status not in _VALID_STATUSES:
            status = "rest"
        confidence = float(seg.get("confidence", 0.0) or 0.0)
        note = str(seg.get("note", ""))[:80]

        equipment_id = None
        equipment_name = None
        movement_name = None

        if status == "exercise":
            eq_name = seg.get("equipmentName")
            mv_name = seg.get("movementName")
            if eq_name not in config.EQUIPMENT_LIBRARY:
                eq_name = "其他"
            spec = config.EQUIPMENT_LIBRARY[eq_name]
            if confidence < config.LOW_CONFIDENCE_THRESHOLD:
                equipment_id = "unknown"
                equipment_name = "未识别"
                movement_name = None
            else:
                equipment_id = spec["id"]
                equipment_name = eq_name
                allowed = set(spec["movements"])
                if not mv_name or (allowed and mv_name not in allowed):
                    movement_name = eq_name
                else:
                    movement_name = mv_name

        labels.append(KeyframeLabel(
            frameIndex=f.frameIndex,
            timestamp=f.timestamp,
            status=status,
            equipmentId=equipment_id,
            equipmentName=equipment_name,
            movementName=movement_name,
            confidence=round(confidence, 3),
            imageUrl=f"{frames_subpath}/{f.filename}",
            note=note,
            motion=m,
        ))

    return labels


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------

def classify_keyframes_full_context(
    frames: list[FrameMeta],
    motions: list[float],
    frames_dir: Path,
    frames_subpath: str = "frames",
    composite_out_path: Path | None = None,
    training_plan: dict | None = None,
    progress: bool = True,
) -> tuple[list[KeyframeLabel], list[dict[str, Any]]]:
    """全量上下文版分类。

    把所有帧合成一张网格图发给 LLM，返回 (KeyframeLabel 列表, 原始段列表)。
    training_plan：可选的训练计划 dict，会被纳入 prompt 帮 AI 对照识别。
    composite_out_path：可选的网格图存盘位置，便于人工核对 AI 看到的输入。
    """
    if progress:
        print(f"  [full-context] 合成 {len(frames)} 帧为单张网格图 ...", flush=True)
    client = _make_openai_client()
    segments_raw, composite_bytes, grid_meta = _classify_all_frames(
        client, frames, motions, frames_dir,
        training_plan=training_plan,
    )
    if composite_out_path is not None:
        composite_out_path.write_bytes(composite_bytes)
        if progress:
            cols, rows, cw, ch = grid_meta
            print(f"  [full-context] 网格图 {cols}×{rows} (cell {cw}×{ch}) → {composite_out_path.name}", flush=True)
    if progress:
        print(f"  [full-context] AI 划分出 {len(segments_raw)} 个段", flush=True)
    labels = _segments_to_keyframe_labels(segments_raw, frames, motions, frames_subpath)
    return labels, segments_raw
