"""卡路里计算与心率区间统计。

对应技术方案 3.2.2 节。三种计算方法按优先级：
  1. 心率法（hr_based）：段内有 ≥ HR_MIN_POINTS_FOR_HR_METHOD 个心率数据点
  2. MET 法（met_based）：段内完全无心率数据
  3. 混合法（hybrid）：段内部分时间有心率（极少见，按段切分子区间分别用前两种）

心率法公式（Keytel et al. 2005）：
  男：kcal/min = (-55.0969 + 0.6309 × HR + 0.1988 × W + 0.2017 × A) / 4.184
  女：kcal/min = (-20.4022 + 0.4472 × HR - 0.1263 × W + 0.0740 × A) / 4.184
  其中 HR=平均心率，W=体重kg，A=年龄。
  注：原公式系数针对中等强度训练，低心率时会算出负值，此时回退到 MET 法保底。

MET 法公式：
  kcal = MET × W × 时长h
  exercise 段：MET 取自该段对应器械的 metFactor
  transition 段：固定 2.5
  rest 段：固定 1.2
"""

from __future__ import annotations

from . import config
from .heart_rate_loader import (
    HeartRateData,
    average_bpm,
    slice_by_time,
)
from .models import (
    CalorieInputParams,
    CaloriesSummary,
    HeartRateZone,
    PerSegmentCalorie,
    UserProfile,
    VideoSegment,
)


# ---------------------------------------------------------------------------
# 心率法 / MET 法（单段）
# ---------------------------------------------------------------------------

def _kcal_hr_based(
    avg_hr: float,
    duration_s: float,
    weight: float,
    age: int,
    sex: str,
) -> float:
    """心率法。负值兜底为 0（外层会回退到 MET 法）。"""
    minutes = duration_s / 60.0
    if sex == "female":
        per_min = (-20.4022 + 0.4472 * avg_hr - 0.1263 * weight + 0.0740 * age) / 4.184
    else:
        per_min = (-55.0969 + 0.6309 * avg_hr + 0.1988 * weight + 0.2017 * age) / 4.184
    return max(0.0, per_min * minutes)


def _met_for_segment(segment: VideoSegment) -> float:
    """根据段类型 + 器械取 MET 系数。"""
    if segment.type == "exercise" and segment.exercise:
        spec = config.EQUIPMENT_LIBRARY.get(segment.exercise.equipmentName)
        if spec:
            return spec["metFactor"]
        return 4.0  # 兜底
    if segment.type == "transition":
        return 2.5
    return 1.2   # rest


def _kcal_met_based(segment: VideoSegment, weight: float) -> float:
    """MET 法：kcal = MET × 体重 × 小时。"""
    met = _met_for_segment(segment)
    hours = segment.duration / 3600.0
    return met * weight * hours


# ---------------------------------------------------------------------------
# 单段卡路里（自动选择方法）
# ---------------------------------------------------------------------------

def calculate_segment_calories(
    segment: VideoSegment,
    profile: UserProfile,
    heart_rate_data: list[HeartRateData],
) -> tuple[float, str]:
    """返回 (kcal, method)。method ∈ {hr_based, met_based, hybrid}。

    本 MVP 暂不实现 hybrid（实际场景极少）；段内只要有足够心率点就用心率法，否则 MET 法。
    """
    hr_points = slice_by_time(heart_rate_data, segment.startTime, segment.endTime)

    if len(hr_points) >= config.HR_MIN_POINTS_FOR_HR_METHOD:
        avg = average_bpm(hr_points)
        kcal = _kcal_hr_based(
            avg_hr=avg,
            duration_s=segment.duration,
            weight=profile.weightKg,
            age=profile.age,
            sex=profile.sex,
        )
        if kcal > 0:
            return kcal, "hr_based"
        # 心率法算出负数（低强度场景），回退 MET 法
        return _kcal_met_based(segment, profile.weightKg), "met_based"

    return _kcal_met_based(segment, profile.weightKg), "met_based"


# ---------------------------------------------------------------------------
# 整次训练汇总
# ---------------------------------------------------------------------------

def calculate_session_calories(
    segments: list[VideoSegment],
    profile: UserProfile,
    heart_rate_data: list[HeartRateData],
) -> CaloriesSummary:
    """对整次训练计算 CaloriesSummary。"""
    per_segment: list[PerSegmentCalorie] = []
    exercise_sum = 0.0
    transition_sum = 0.0
    rest_sum = 0.0

    for seg in segments:
        kcal, method = calculate_segment_calories(seg, profile, heart_rate_data)
        per_segment.append(PerSegmentCalorie(
            segmentId=seg.id,
            calories=round(kcal, 2),
            method=method,
        ))
        if seg.type == "exercise":
            exercise_sum += kcal
        elif seg.type == "transition":
            transition_sum += kcal
        else:
            rest_sum += kcal

    total = exercise_sum + transition_sum + rest_sum
    avg_hr = average_bpm(heart_rate_data) if heart_rate_data else None

    input_params = CalorieInputParams(
        userWeightKg=profile.weightKg,
        userAge=profile.age,
        userSex=profile.sex,
        maxHeartRate=profile.effective_max_hr,
        avgHeartRate=round(avg_hr, 1) if avg_hr is not None else None,
        vo2MaxEstimate=profile.vo2Max,
    )

    return CaloriesSummary(
        totalCalories=round(total),
        exerciseCalories=round(exercise_sum),
        transitionCalories=round(transition_sum),
        restCalories=round(rest_sum),
        perSegment=per_segment,
        inputParams=input_params,
    )


# ---------------------------------------------------------------------------
# 心率区间统计
# ---------------------------------------------------------------------------

def calculate_heart_rate_zones(
    heart_rate_data: list[HeartRateData],
    profile: UserProfile,
) -> list[HeartRateZone]:
    """统计心率在各区间的累计时长 + 占比。"""
    if not heart_rate_data:
        return []

    max_hr = profile.effective_max_hr
    interval = config.SAMPLING_INTERVAL_S
    # 这里 interval 用心率数据自身的间隔更准；
    # 但用户的 CSV 每点间隔 3 秒，正好与 SAMPLING_INTERVAL_S 一致
    # 严谨做法：用相邻两点差均值
    if len(heart_rate_data) >= 2:
        diffs = [
            heart_rate_data[i + 1].timestamp - heart_rate_data[i].timestamp
            for i in range(len(heart_rate_data) - 1)
        ]
        diffs = [d for d in diffs if d > 0]
        interval = sum(diffs) / len(diffs) if diffs else interval

    zone_seconds: dict[str, float] = {z[0]: 0.0 for z in config.HR_ZONES}

    for pt in heart_rate_data:
        pct = pt.bpm / max_hr
        for code, _name, lo, hi, _color in config.HR_ZONES:
            if lo <= pct < hi:
                zone_seconds[code] += interval
                break

    total = sum(zone_seconds.values()) or 1.0
    zones: list[HeartRateZone] = []
    for code, name, lo, hi, _color in config.HR_ZONES:
        secs = zone_seconds[code]
        zones.append(HeartRateZone(
            zone=code,
            displayName=name,
            rangeBpm=(int(round(max_hr * lo)), int(round(max_hr * hi))),
            durationSeconds=int(round(secs)),
            percentage=int(round(secs / total * 100)),
        ))
    return zones
