"""GPT 视觉模型批量识别关键帧。

每帧输出 4 个字段：
  status         exercise / transition / rest
  equipmentName  17 个标签之一（当 status=exercise 时有效）
  movementName   该器械下的具体动作名（约束在 EQUIPMENT_LIBRARY[器械].movements 内）
  confidence     0-1

如果置信度 < LOW_CONFIDENCE_THRESHOLD，对应字段会被回退到 unknown / 通用名。
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from . import config
from .keyframe_extractor import FrameMeta
from .models import KeyframeLabel


# ---------------------------------------------------------------------------
# OpenAI 客户端初始化
#
# 兼容两套环境变量：
#   - API_KEY / BASE_URL          自建网关（如 zchat.tech）
#   - OPENAI_API_KEY / OPENAI_BASE_URL   官方 / 通用回退
# ---------------------------------------------------------------------------

def _make_openai_client() -> OpenAI:
    """根据 .env 配置创建 OpenAI 客户端。"""
    load_dotenv()
    api_key = os.environ.get("API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未找到 API key（请在 .env 中设置 API_KEY 或 OPENAI_API_KEY）"
        )
    base_url = os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL") or None
    timeout_ms = os.environ.get("API_TIMEOUT_MS")
    timeout = float(timeout_ms) / 1000.0 if timeout_ms else 600.0
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


# ---------------------------------------------------------------------------
# Prompt 构造
# ---------------------------------------------------------------------------

def _build_movements_block() -> str:
    """生成"每个器械可能的动作"列表块，写进 system prompt。"""
    lines = []
    for name in config.EQUIPMENT_NAMES:
        spec = config.EQUIPMENT_LIBRARY[name]
        movements = spec["movements"]
        if not movements:
            continue
        lines.append(f"  - {name}: {' / '.join(movements)}")
    return "\n".join(lines)


def _build_system_prompt() -> str:
    equipment_names = "、".join(f'"{n}"' for n in config.EQUIPMENT_NAMES)
    movements_block = _build_movements_block()

    return f"""你是一名健身房动作识别助手。视频是健身者**第一视角**录制（戴在身上或手持），
画面里**通常看不到训练者本人**，主要看到的是健身房环境、器械、显示屏。
"画面里没人"是常态——**不要因为没人就直接判 rest**。

## 任务

对每张关键帧输出 4 个字段：

1. **status**（必填）：用户此刻的状态
   - `"exercise"` —— 正在用某个器械做动作（画面里有器械特征、画面在动、姿态符合训练）
   - `"transition"` —— 在器械之间移动 / 调整器械 / 在走廊或更衣区 / 拿水拿毛巾 / 走动中
   - `"rest"` —— 站或坐在某个器械旁静止 / 看手机 / 调呼吸 / 等待器械可用

2. **equipmentName**：器械中文名，**必须**从下面 17 个标签中选一个；当 status≠"exercise" 时也可标"其他"
   {equipment_names}

3. **movementName**：当 status="exercise" 时，**必须**从下面对应器械的候选动作里选一个；
   如果看不清细节，可以**直接复用 equipmentName**作为兜底（例如不确定是哪个杠铃动作时填"杠铃"）。
   候选清单：
{movements_block}

4. **confidence**：你对本帧整体判断的置信度，0-1 浮点。
   - 看到清晰的器械 + 明确动作姿态 → 0.8+
   - 看到器械但姿态不确定 → 0.5-0.7
   - 完全看不清场景 → < 0.5

## 关键判断规则

**status 判断要点：**
- 看到器械特征 + motion 高（≥ 6）→ `exercise`
- motion 高但画面是走廊 / 在器械间穿行 / 看不到正在用的器械 → `transition`
- motion 低（< 3）+ 画面静止在某器械旁 → `rest`
- 完全黑屏 / 强烈晃动看不清 → `rest`，confidence 给低值

**🔴 极其重要的"看到器械 ≠ 正在用器械"原则：**

仅仅看到健身器械的轮廓不等于用户在用它。要标某个器械（不是 自重训练）必须看到**操作证据**：
- **杠铃/史密斯架**：看到杠铃在动 / 杠铃在用户肩上或胸前 / 用户握住横杆 / 配重片明显在升降
- **龙门架**：看到绳索被拉紧 / 滑轮带着配重在上下移动 / 用户手里抓着绳索手柄
- **椭圆机/动感单车/划船机**：看到踏板/座垫/拉绳被人操作
- **高位下拉/坐姿划船**：看到用户坐在座椅上 + 拉杆在动
- **引体向上**：看到用户身体悬挂

**如果画面里只是远远看到某个器械的立柱/外壳/部件，但没有任何"被使用"的证据：**
- 用户**很可能根本不在用这个器械**
- 优先考虑：自重训练（用户在器械间的空地做卷腹/俯卧撑/拉伸）或 transition / rest
- **不要因为"画面里有立柱"就标 史密斯架/龙门架**——这是最常见的错判

**器械视觉特征：**
- 跑步机：水平履带 + 控制面板（屏幕含 SPEED/PACE/距离/坡度），扶手向前伸
- 椭圆机：两侧长动臂 + 椭圆轨迹踏板
- 动感单车：座垫 + 把手 + 显眼飞轮
- 划船机：滑轨 + 拉绳 / 拉柄 + 风轮 / 水箱
- 杠铃：杠铃杆 + 杠铃片 / 卧推架 / 深蹲架（无固定轨道）
- 史密斯架：垂直双立柱 + 横杠 + 卡扣 
- 哑铃：成对或单只哑铃 / 哑铃架
- 龙门架：**双立柱**（两根独立柱子，中间有距离）+ 绳索 + 滑轮
- 高位下拉：**单立柱**机器 + 头顶长拉杆 + **座椅 + 大腿挡板**（用户坐在椅子上）+ 配重片
- 坐姿划船：座垫 + 横向拉杆 + 滑轨
- 腿举机：45° 斜板 + 踏板 + 配重
- 蝴蝶机：座椅 + 两侧大型扇形挡板
- 推肩机：座椅 + 头部两侧握把（垂直向上推）

**🔴 引体向上 vs 高位下拉（最容易混淆，按以下规则严格区分）：**

**引体向上**的决定性证据（任一命中就标 引体向上，不要标高位下拉）：
- 画面中或镜面反射中能看到**用户整个身体悬挂在空中**（脚离地、身体被双手吊着）
- 画面**剧烈上下晃动**（motion ≥ 30），因为身体在悬挂荡动
- 头顶有**横向横杆/单杠/拉环**且画面下方**看不到任何座椅或大腿垫**（用户站着或悬挂）
- 双立柱之间架着横杆（功能性训练器/Functional Trainer/Rack 顶部的引体杆）
- 镜头视角**朝上看**（仰角拍摄），能看到天花板和头顶横杆

**高位下拉**的决定性证据（同时满足这两条才标 高位下拉）：
- 画面下半部清晰可见**座椅 + 大腿挡板**（用户坐着）
- 头顶单根长拉杆从机器顶部垂下来，**配重片**通常在侧面可见
- 用户身体姿态是**坐姿**（不会悬空），motion 通常 10-25（中等）

**一句话区分：用户脚是否离地。脚离地→引体向上；坐着→高位下拉。**
如果看不清是站是坐，但**画面剧烈晃动 + 头顶有横杆 + 没看到座椅**→倾向 引体向上。

**🔴 自重训练（卷腹/俯卧撑/平板支撑/箭步蹲）—— 容易被误判为各种机器，仔细看：**

**决定性证据（任一命中就标 自重训练）：**
- **镜头视角非常低**（贴近地面 / 仰角很大 / 主体是墙面或天花板而不是器械操作面）
- 画面**主体是地面、瑜伽垫、木地板**或装饰墙；周边可能有器械框架，但**没有任何器械被操作**
- 用户**躺在地上**做动作（卷腹画面随头部上下小幅起伏；motion 10-30，不像跑步/引体那么剧烈）
- 在双立柱训练架中间但**镜头朝下/朝上**而不是对着拉杆/绳索 → 用户没在用机器，而是在地上做自重

**绝对不要**把这种情况标成：
- ❌ 椭圆机（只是背景里有椭圆机不代表在用）
- ❌ 史密斯架 / 龙门架（镜头扫过立柱不代表在用，除非看到杠铃在动 / 用户在拉绳索）
- ❌ 高位下拉（用户没坐着 + 头顶没拉杆 → 不是）

**自重动作 movementName 判断：**
- 镜头随头部上下小幅起伏，能瞥见自己的腿或胸 → 卷腹
- 镜头朝下，地面近 + 手部/上肢入画 → 俯卧撑
- 镜头一直平稳贴近地面，几乎不动（motion < 5） → 平板支撑
- 一步前一步后 + 镜头大幅上下起伏 → 箭步蹲

**🔴 第一视角里的双立柱训练架（Functional Trainer / Cable Crossover）经常同时具备多种用途：**
- 顶部横杆 → 用来做引体向上
- 两侧滑轮 + 配重 → 看起来像龙门架
- 中间地面空间 → 用来做卷腹 / 俯卧撑等自重训练

**看到双立柱时，必须额外判断"用户在做什么"，而不是被立柱本身蒙住：**
- 镜头朝上 + 镜中看到悬挂身体 → 引体向上
- 镜头水平 + 用户拉绳索 → 龙门架
- 镜头朝下/贴地 + 没人操作绳索 → 自重训练（很可能是卷腹/俯卧撑）

**其他器械的 movementName 判断要点：**
- 杠铃：躺着推→平板/上斜卧推；屈髋向上拉→硬拉；杠铃在肩上深屈膝→深蹲；屈臂向上→弯举
- 哑铃：水平展开→飞鸟；屈肘上举→弯举；过头推→推举；两手往身侧侧抬→侧平举
- 龙门架：滑轮在高位 + 双手向中合 → 绳索夹胸；高位下拉式 → 绳索下拉；低位水平拉 → 绳索划船；屈肘下压 → 三头下压
- 史密斯架 / 蝴蝶机 同理，按身体姿态决定

## 时间连续性

本批图按时间顺序排列，每张相隔 {config.SAMPLING_INTERVAL_S} 秒。
- **段稳定优先于单帧判断**：连续多张同一器械，中间 1-2 张看起来像别的器械，大概率是镜头扫过背景 → 延续主导标签
- 不要在 1-2 帧间频繁切换器械

## 输出格式

输出严格的 JSON 对象 `{{"results": [...]}}`，results 长度等于输入张数，顺序与输入一致。
每个元素：

```json
{{
  "index": 0,
  "status": "exercise",
  "equipmentName": "杠铃",
  "movementName": "平板卧推",
  "confidence": 0.85,
  "note": "镜中可见仰卧推杠铃"
}}
```

不要输出 JSON 之外的任何文字。"""


SYSTEM_PROMPT = _build_system_prompt()


# ---------------------------------------------------------------------------
# 单批调用
# ---------------------------------------------------------------------------

def _encode_image_b64(img_path: Path) -> str:
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _classify_batch(
    client: OpenAI,
    frames: list[FrameMeta],
    motions: list[float],
    frames_dir: Path,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """对一批帧调一次 GPT，返回原始 JSON 数组（顺序对齐）。

    遇到空响应或 JSON 解析失败会自动重试 max_retries 次；最终失败时
    返回占位结果（每帧默认 rest），让流程能跑完而不是整条 pipeline 崩。
    """
    intro = (
        f"这是 {len(frames)} 张连续关键帧（第一视角健身视频），每张间隔 {config.SAMPLING_INTERVAL_S} 秒。\n"
        f"附加帧间运动强度 motion（0-50，≥6 表示画面在动，<2 表示静止）：\n"
        f"motion = {motions}\n"
        f"请按时间顺序识别每张的 status / equipmentName / movementName / confidence。"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": intro}]
    for f in frames:
        b64 = _encode_image_b64(frames_dir / f.filename)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": config.IMAGE_DETAIL,
            },
        })

    last_err: Exception | None = None
    raw = ""
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=config.VISION_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                response_format={"type": "json_object"},
            )
            raw = (resp.choices[0].message.content or "").strip()
            if not raw:
                raise ValueError("空响应")
            parsed = json.loads(raw)
            break
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"    [重试 {attempt+1}/{max_retries}] 解析失败: {e}", flush=True)
                time.sleep(1.5 * (attempt + 1))
                continue
            # 最终失败：返回占位
            print(f"    [跳过] 该批次连续 {max_retries} 次失败，使用占位: {last_err}", flush=True)
            return [{
                "status": "rest",
                "equipmentName": "其他",
                "movementName": None,
                "confidence": 0.0,
                "note": f"API 解析失败：{type(last_err).__name__}",
            } for _ in frames]
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"    [重试 {attempt+1}/{max_retries}] API 错误: {e}", flush=True)
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("results") or parsed.get("data") or [parsed]
    else:
        items = []

    # 按 index 对齐，缺失项用占位
    by_idx = {int(item.get("index", i)): item for i, item in enumerate(items)}
    out = []
    for i in range(len(frames)):
        out.append(by_idx.get(i, {
            "status": "rest",
            "equipmentName": "其他",
            "movementName": None,
            "confidence": 0.0,
            "note": "解析缺失",
        }))
    return out


# ---------------------------------------------------------------------------
# 字段规整：把 AI 输出规整成 KeyframeLabel
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"exercise", "transition", "rest"}


def _normalize_one(
    raw: dict[str, Any],
    frame: FrameMeta,
    motion: float,
    frames_subpath: str,
) -> KeyframeLabel:
    """把单帧 AI 输出规整成 KeyframeLabel。

    规整规则：
      - status 不在白名单 → rest
      - confidence < LOW_CONFIDENCE_THRESHOLD → equipmentId 设为 unknown
      - equipmentName 不在 17 标签内 → "其他"
      - movementName 不在该器械的候选清单内 → 回退到 equipmentName 本身
      - status != exercise → equipmentName/movementName 置空（rest/transition 不带器械信息）
    """
    status = raw.get("status")
    if status not in _VALID_STATUSES:
        status = "rest"
    confidence = float(raw.get("confidence", 0.0) or 0.0)

    equipment_name = raw.get("equipmentName")
    movement_name = raw.get("movementName")
    note = str(raw.get("note", ""))[:60]

    equipment_id: str | None = None

    if status == "exercise":
        # 器械规整
        if equipment_name not in config.EQUIPMENT_LIBRARY:
            equipment_name = "其他"
        spec = config.EQUIPMENT_LIBRARY[equipment_name]

        # 置信度低 → 标 unknown
        if confidence < config.LOW_CONFIDENCE_THRESHOLD:
            equipment_id = "unknown"
            equipment_name = "未识别"
            movement_name = None
        else:
            equipment_id = spec["id"]
            # movementName 规整
            allowed = set(spec["movements"])
            if not movement_name or (allowed and movement_name not in allowed):
                # 回退到 equipmentName 作为动作名
                movement_name = equipment_name
    else:
        # 非 exercise 段不带器械信息
        equipment_id = None
        equipment_name = None
        movement_name = None

    return KeyframeLabel(
        frameIndex=frame.frameIndex,
        timestamp=frame.timestamp,
        status=status,
        equipmentId=equipment_id,
        equipmentName=equipment_name,
        movementName=movement_name,
        confidence=round(confidence, 3),
        imageUrl=f"{frames_subpath}/{frame.filename}",
        note=note,
        motion=motion,
    )


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------

def classify_keyframes(
    frames: list[FrameMeta],
    motions: list[float],
    frames_dir: Path,
    frames_subpath: str = "frames",
    progress: bool = True,
) -> list[KeyframeLabel]:
    """对全部关键帧分类，返回 KeyframeLabel 列表。

    Args:
        frames: 帧元数据列表
        motions: 与 frames 等长的 motion 分数列表
        frames_dir: 帧文件所在物理目录
        frames_subpath: 写入 imageUrl 的相对前缀（默认 "frames"）
        progress: 是否打印进度
    """
    client = _make_openai_client()

    labels: list[KeyframeLabel] = []
    batch_size = config.BATCH_SIZE
    total_batches = (len(frames) + batch_size - 1) // batch_size

    for bi in range(total_batches):
        batch_frames = frames[bi * batch_size : (bi + 1) * batch_size]
        batch_motions = motions[bi * batch_size : (bi + 1) * batch_size]
        if progress:
            print(f"  [classify] batch {bi+1}/{total_batches} ({len(batch_frames)} 张) ...", flush=True)
        raw_items = _classify_batch(client, batch_frames, batch_motions, frames_dir)
        for f, m, raw in zip(batch_frames, batch_motions, raw_items):
            labels.append(_normalize_one(raw, f, m, frames_subpath))
    return labels
