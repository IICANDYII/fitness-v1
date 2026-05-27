"""关键帧序列 → VideoSegment 时间线。

合并规则（对应技术方案 3.1 步骤三）：
  1. 基本合并：相邻 KeyframeLabel 的 (status, equipmentId) 相同 → 同段
     - exercise 段额外要求 equipmentId 一致
     - transition / rest 只看 status
  2. 去噪：孤立的 3 秒短段（仅 1 帧）若前后段是同类型则被吸收
  3. exercise 段内部的 rest 子段：若 ≤180s 且前后 exercise 段使用相同器械 → 吸收为组间休息

输入：KeyframeLabel 列表（已按时间排序）
输出：VideoSegment 列表
"""

from __future__ import annotations

from . import config
from .models import (
    ExerciseDetail,
    KeyframeLabel,
    TransitionDetail,
    VideoSegment,
)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _frame_key(label: KeyframeLabel) -> tuple:
    """合并键：决定相邻两帧是否被视为"同段"。

    - exercise 段：(status, equipmentId) 一起决定
    - 非 exercise 段：只看 status
    """
    if label.status == "exercise":
        return (label.status, label.equipmentId)
    return (label.status,)


def _next_seg_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"seg_{counter[0]:03d}"


def _dominant_movement(frames: list[KeyframeLabel]) -> tuple[str, str, str]:
    """对一组同器械 exercise 帧，统计主导 (equipmentId, equipmentName, movementName)。

    - equipmentId / equipmentName：取出现次数最多的
    - movementName：取出现次数最多的（None 不计）
    """
    from collections import Counter

    eq_id = Counter(f.equipmentId for f in frames if f.equipmentId).most_common(1)
    eq_name = Counter(f.equipmentName for f in frames if f.equipmentName).most_common(1)
    mv_name = Counter(f.movementName for f in frames if f.movementName).most_common(1)

    return (
        eq_id[0][0] if eq_id else "unknown",
        eq_name[0][0] if eq_name else "未识别",
        mv_name[0][0] if mv_name else (eq_name[0][0] if eq_name else "未识别"),
    )


def _build_segment(
    seg_id: str,
    frames: list[KeyframeLabel],
    seg_type: str,
) -> VideoSegment:
    """从一组连续同类型帧构造 VideoSegment。"""
    start = frames[0].timestamp
    end = frames[-1].timestamp + config.SAMPLING_INTERVAL_S
    avg_conf = sum(f.confidence for f in frames) / len(frames)

    seg = VideoSegment(
        id=seg_id,
        type=seg_type,
        startTime=round(start, 2),
        endTime=round(end, 2),
        duration=round(end - start, 2),
        confidence=round(avg_conf, 3),
        keyframeTimestamps=[f.timestamp for f in frames],
    )

    if seg_type == "exercise":
        eq_id, eq_name, mv_name = _dominant_movement(frames)
        seg.exercise = ExerciseDetail(
            equipmentId=eq_id,
            equipmentName=eq_name,
            movementName=mv_name,
        )
    elif seg_type == "transition":
        seg.transition = TransitionDetail()  # from/to 在后处理中填

    return seg


# ---------------------------------------------------------------------------
# 主合并流程
# ---------------------------------------------------------------------------

def merge_keyframes(labels: list[KeyframeLabel]) -> list[VideoSegment]:
    """关键帧序列 → 初始 VideoSegment 时间线（未做 rest 吸收）。"""
    if not labels:
        return []

    segments: list[VideoSegment] = []
    counter = [0]

    cur_key = _frame_key(labels[0])
    buf: list[KeyframeLabel] = [labels[0]]

    for lbl in labels[1:]:
        key = _frame_key(lbl)
        if key == cur_key:
            buf.append(lbl)
        else:
            seg = _build_segment(_next_seg_id(counter), buf, buf[0].status)
            segments.append(seg)
            buf = [lbl]
            cur_key = key

    segments.append(_build_segment(_next_seg_id(counter), buf, buf[0].status))
    return segments


# ---------------------------------------------------------------------------
# 后处理：组间休息吸收
# ---------------------------------------------------------------------------

def absorb_intra_exercise_rest(segments: list[VideoSegment]) -> list[VideoSegment]:
    """把"夹在两个相同 exercise 段之间、≤180s 的 rest 或 transition 段"吸收为组间休息。

    规则：
      seg[i-1].type == "exercise" 且
      seg[i  ].type in {"rest", "transition"} 且 seg[i].duration <= 180 且
      seg[i+1].type == "exercise" 且 seg[i-1].exercise.equipmentId == seg[i+1].exercise.equipmentId
      → 把三段合并为一段大 exercise（seg[i-1].endTime = seg[i+1].endTime）

    被吸收的 rest/transition 段会被丢弃，但它的 keyframeTimestamps 合并到大段里。
    """
    if not segments:
        return segments

    out: list[VideoSegment] = []
    i = 0
    counter = [0]

    while i < len(segments):
        cur = segments[i]

        if (
            cur.type == "exercise"
            and i + 2 < len(segments)
            and segments[i + 1].type in ("rest", "transition")
            and segments[i + 1].duration <= config.INTRA_EXERCISE_REST_MAX_S
            and segments[i + 2].type == "exercise"
            and cur.exercise is not None
            and segments[i + 2].exercise is not None
            and cur.exercise.equipmentId == segments[i + 2].exercise.equipmentId
            and cur.exercise.equipmentId != "unknown"
        ):
            # 三段融合
            mid = segments[i + 1]
            nxt = segments[i + 2]
            merged_timestamps = sorted(
                cur.keyframeTimestamps + mid.keyframeTimestamps + nxt.keyframeTimestamps
            )
            # confidence 取加权平均（按段时长）
            tot_dur = cur.duration + mid.duration + nxt.duration
            avg_conf = (
                cur.confidence * cur.duration
                + mid.confidence * mid.duration
                + nxt.confidence * nxt.duration
            ) / tot_dur if tot_dur > 0 else cur.confidence

            counter[0] += 1
            merged = VideoSegment(
                id=f"seg_{counter[0]:03d}",
                type="exercise",
                startTime=cur.startTime,
                endTime=nxt.endTime,
                duration=round(nxt.endTime - cur.startTime, 2),
                confidence=round(avg_conf, 3),
                keyframeTimestamps=merged_timestamps,
                exercise=ExerciseDetail(
                    equipmentId=cur.exercise.equipmentId,
                    equipmentName=cur.exercise.equipmentName,
                    movementName=cur.exercise.movementName,
                ),
            )
            out.append(merged)
            i += 3  # 跳过被吸收的三段
        else:
            counter[0] += 1
            cur.id = f"seg_{counter[0]:03d}"
            out.append(cur)
            i += 1

    return out


# ---------------------------------------------------------------------------
# 后处理：填 transition 段的 from / to 字段
# ---------------------------------------------------------------------------

def fill_transition_endpoints(segments: list[VideoSegment]) -> None:
    """给 transition 段填 fromEquipmentId / toEquipmentId（原地修改）。"""
    for i, seg in enumerate(segments):
        if seg.type != "transition" or seg.transition is None:
            continue
        prev_eq = None
        next_eq = None
        # 向前找最近的 exercise
        for j in range(i - 1, -1, -1):
            if segments[j].type == "exercise" and segments[j].exercise:
                prev_eq = segments[j].exercise.equipmentId
                break
        for j in range(i + 1, len(segments)):
            if segments[j].type == "exercise" and segments[j].exercise:
                next_eq = segments[j].exercise.equipmentId
                break
        seg.transition.fromEquipmentId = prev_eq
        seg.transition.toEquipmentId = next_eq


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------

def build_timeline(labels: list[KeyframeLabel]) -> list[VideoSegment]:
    """完整流程：合并 → 吸收组间休息 → 填 transition 端点。"""
    segments = merge_keyframes(labels)
    segments = absorb_intra_exercise_rest(segments)
    fill_transition_endpoints(segments)
    return segments
