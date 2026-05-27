"""组数与次数检测。

对每个 exercise 段，内部寻找"短暂静止"作为组间休息的标记：
  - 段内的 KeyframeLabel 中，连续 ≥ SET_BREAK_MIN_FRAMES（默认 2，即 ≥6s）个 rest 标签
    → 视为一次组间休息
  - 组数 = 1 + 段内符合条件的休息子区间数
  - 每组的 startTime / endTime 落在该组对应的关键帧上
  - 次数 = round(运动时长 / 该动作的 tempo)（向下兜底为 1）

注：由于段合并阶段已经把 ≤180s 的 rest 吸收进 exercise 段，
组间休息检测可以基于"段内的关键帧本身的 status"——
吸收前是 rest 的关键帧依然标记着 status=rest，正好用来切组。
"""

from __future__ import annotations

from . import config
from .heart_rate_loader import (
    HeartRateData,
    average_bpm,
    peak_bpm,
    slice_by_time,
)
from .models import KeyframeLabel, SetDetail, VideoSegment


# ---------------------------------------------------------------------------
# 内部：把一组段内关键帧切成"运动子区间"列表
# ---------------------------------------------------------------------------

def _split_into_active_runs(
    seg_frames: list[KeyframeLabel],
) -> list[tuple[float, float]]:
    """把一段内的关键帧切成多个"运动子区间"，每个对应一组训练。

    切分规则：连续 ≥ SET_BREAK_MIN_FRAMES 个 status=rest 的帧 → 当作组间休息切断。

    返回每段子区间 (start_s, end_s)，end_s 为最后一帧 + SAMPLING_INTERVAL_S。
    """
    runs: list[tuple[float, float]] = []
    interval = config.SAMPLING_INTERVAL_S
    min_rest = config.SET_BREAK_MIN_FRAMES

    cur_active: list[KeyframeLabel] = []
    rest_buf: list[KeyframeLabel] = []

    def _flush_active():
        if cur_active:
            runs.append((cur_active[0].timestamp, cur_active[-1].timestamp + interval))

    for f in seg_frames:
        if f.status == "rest":
            rest_buf.append(f)
            if len(rest_buf) >= min_rest:
                # 真休息，提交当前活动段
                _flush_active()
                cur_active = []
        else:
            # 一旦遇到非 rest，rest_buf 清空（视为"中间没真断"）
            # 但如果之前 rest_buf 长度足够，已经切断；这里只重置
            if rest_buf and len(rest_buf) < min_rest:
                # 这些 rest 算"短暂停顿"，归入当前活动段
                cur_active.extend(rest_buf)
            rest_buf = []
            cur_active.append(f)

    _flush_active()
    return runs


# ---------------------------------------------------------------------------
# 内部：tempo 估算次数
# ---------------------------------------------------------------------------

def _estimate_reps(movement_name: str, duration_s: float) -> int:
    """根据动作 tempo 估算次数。

    平板支撑等等长动作的 tempo 定义为"该姿势的常规持续时间"，估算结果代表"完成度"
    （比如 60s 平板 / 30s tempo = 2 次"组"），实际报告里会标 isEstimated=True 提示。
    """
    tempo = config.MOVEMENT_TEMPOS.get(movement_name, config.DEFAULT_TEMPO)
    if tempo <= 0:
        return 1
    return max(1, round(duration_s / tempo))


# ---------------------------------------------------------------------------
# 单段填组数
# ---------------------------------------------------------------------------

def detect_sets_for_segment(
    segment: VideoSegment,
    keyframes_in_segment: list[KeyframeLabel],
    heart_rate_data: list[HeartRateData] | None = None,
) -> None:
    """给一个 exercise 段填 sets 列表（原地修改 segment.exercise.sets）。"""
    if segment.type != "exercise" or segment.exercise is None:
        return

    movement_name = segment.exercise.movementName
    runs = _split_into_active_runs(keyframes_in_segment)
    if not runs:
        # 整段都没识别出活动子区间（不太可能，兜底）
        return

    sets: list[SetDetail] = []
    for i, (start, end) in enumerate(runs, start=1):
        duration = end - start
        reps = _estimate_reps(movement_name, duration)

        avg_hr = None
        peak_hr = None
        if heart_rate_data:
            slc = slice_by_time(heart_rate_data, start, end)
            avg = average_bpm(slc)
            avg_hr = int(round(avg)) if avg is not None else None
            peak_hr = peak_bpm(slc)

        sets.append(SetDetail(
            setIndex=i,
            startTime=round(start, 2),
            endTime=round(end, 2),
            repCount=reps,
            avgHeartRate=avg_hr,
            peakHeartRate=peak_hr,
            isEstimated=True,
        ))
    segment.exercise.sets = sets


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------

def detect_all_sets(
    segments: list[VideoSegment],
    keyframe_labels: list[KeyframeLabel],
    heart_rate_data: list[HeartRateData] | None = None,
) -> None:
    """遍历所有 exercise 段填 sets（原地修改）。"""
    # 按段切关键帧
    for seg in segments:
        if seg.type != "exercise":
            continue
        seg_frames = [
            lbl for lbl in keyframe_labels
            if seg.startTime <= lbl.timestamp < seg.endTime
        ]
        detect_sets_for_segment(seg, seg_frames, heart_rate_data)
