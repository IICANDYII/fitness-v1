"""数据类定义。

对应技术方案 v2.1 第二节的数据结构。
所有数据类都支持 to_dict() 方法用于 JSON 序列化，方便后续接入 FastAPI。

注：MVP 阶段不实现肌群相关字段（保留字段名，留空值 / 空列表），
后续扩展时再填充。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 关键帧（视频分析中间产物）
# ---------------------------------------------------------------------------

@dataclass
class KeyframeLabel:
    """单个关键帧的 AI 分类结果。"""
    frameIndex: int
    timestamp: float                     # 秒，相对视频开头
    status: str                          # exercise / transition / rest
    equipmentId: Optional[str] = None
    equipmentName: Optional[str] = None
    movementName: Optional[str] = None
    confidence: float = 0.0
    imageUrl: Optional[str] = None       # 相对路径，例如 "frames/state1_xxx.png"
    note: str = ""                       # AI 备注（调试用）
    motion: float = 0.0                  # 帧间运动强度（调试用）

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 组数明细
# ---------------------------------------------------------------------------

@dataclass
class SetDetail:
    """单组训练详情。"""
    setIndex: int
    startTime: float
    endTime: float
    repCount: int                        # tempo 法估算
    weight: Optional[float] = None       # 3 秒采样无法识别，留空
    avgHeartRate: Optional[int] = None
    peakHeartRate: Optional[int] = None
    isEstimated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 时间段（exercise / transition / rest）
# ---------------------------------------------------------------------------

@dataclass
class ExerciseDetail:
    """exercise 段附带的运动详情。"""
    equipmentId: str
    equipmentName: str
    movementName: str
    sets: list[SetDetail] = field(default_factory=list)
    targetMuscleGroups: list[str] = field(default_factory=list)   # MVP 留空

    def to_dict(self) -> dict[str, Any]:
        return {
            "equipmentId": self.equipmentId,
            "equipmentName": self.equipmentName,
            "movementName": self.movementName,
            "sets": [s.to_dict() for s in self.sets],
            "targetMuscleGroups": self.targetMuscleGroups,
        }


@dataclass
class TransitionDetail:
    """transition 段附带的过渡详情。"""
    fromEquipmentId: Optional[str] = None
    toEquipmentId: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VideoSegment:
    """视频时间线上的一个段。"""
    id: str                              # "seg_001"、"seg_002" ...
    type: str                            # exercise / transition / rest
    startTime: float
    endTime: float
    duration: float
    confidence: float
    keyframeTimestamps: list[float] = field(default_factory=list)
    exercise: Optional[ExerciseDetail] = None
    transition: Optional[TransitionDetail] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "startTime": self.startTime,
            "endTime": self.endTime,
            "duration": self.duration,
            "confidence": self.confidence,
            "keyframeTimestamps": self.keyframeTimestamps,
        }
        if self.exercise is not None:
            out["exercise"] = self.exercise.to_dict()
        if self.transition is not None:
            out["transition"] = self.transition.to_dict()
        return out


# ---------------------------------------------------------------------------
# 心率数据
# ---------------------------------------------------------------------------

@dataclass
class HeartRateData:
    """单个心率数据点（标准化后，相对视频开头的秒数）。"""
    timestamp: float                     # 秒，相对视频开头
    bpm: int
    source: str                          # apple_watch / garmin / polar / simulated / ...

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 卡路里
# ---------------------------------------------------------------------------

@dataclass
class PerSegmentCalorie:
    """单段卡路里明细。"""
    segmentId: str
    calories: float
    method: str                          # hr_based / met_based / hybrid

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CalorieInputParams:
    """卡路里计算输入参数（用于审计 / 复算）。"""
    userWeightKg: float
    userAge: int
    userSex: str                         # male / female
    maxHeartRate: int
    avgHeartRate: Optional[float] = None
    vo2MaxEstimate: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaloriesSummary:
    """整次训练的卡路里汇总。"""
    totalCalories: float
    exerciseCalories: float
    transitionCalories: float
    restCalories: float
    perSegment: list[PerSegmentCalorie] = field(default_factory=list)
    inputParams: Optional[CalorieInputParams] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalCalories": self.totalCalories,
            "exerciseCalories": self.exerciseCalories,
            "transitionCalories": self.transitionCalories,
            "restCalories": self.restCalories,
            "perSegment": [p.to_dict() for p in self.perSegment],
            "inputParams": self.inputParams.to_dict() if self.inputParams else None,
        }


# ---------------------------------------------------------------------------
# 心率区间统计
# ---------------------------------------------------------------------------

@dataclass
class HeartRateZone:
    """单个心率区间的统计。"""
    zone: str                            # warmup / fatburn / cardio / peak / max
    displayName: str                     # 中文名
    rangeBpm: tuple[int, int]            # (min_bpm, max_bpm)
    durationSeconds: int
    percentage: int                      # 0-100 整数

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "displayName": self.displayName,
            "rangeBpm": list(self.rangeBpm),
            "durationSeconds": self.durationSeconds,
            "percentage": self.percentage,
        }


# ---------------------------------------------------------------------------
# 视频信息
# ---------------------------------------------------------------------------

@dataclass
class VideoFile:
    url: str
    durationSeconds: float
    resolution: str                      # 如 "1920x1080"
    fps: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 用户资料
# ---------------------------------------------------------------------------

@dataclass
class UserProfile:
    userId: str
    weightKg: float
    age: int
    sex: str                             # male / female
    maxHeartRate: Optional[int] = None   # 不填则用 220-年龄
    heightCm: Optional[float] = None
    vo2Max: Optional[float] = None

    @property
    def effective_max_hr(self) -> int:
        """实际使用的最大心率，未填则用 220 - 年龄。"""
        return self.maxHeartRate if self.maxHeartRate else (220 - self.age)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        return cls(
            userId=data.get("userId", "default_user"),
            weightKg=float(data["weightKg"]),
            age=int(data["age"]),
            sex=data["sex"],
            maxHeartRate=data.get("maxHeartRate"),
            heightCm=data.get("heightCm"),
            vo2Max=data.get("vo2Max"),
        )


# ---------------------------------------------------------------------------
# 训练会话（最终聚合对象）
# ---------------------------------------------------------------------------

@dataclass
class WorkoutSession:
    id: str
    userId: str
    date: str                            # ISO 日期，如 "2026-05-25"
    startTime: str                       # ISO 时间戳
    endTime: str
    videoFile: VideoFile
    timeline: list[VideoSegment] = field(default_factory=list)
    keyframeLabels: list[KeyframeLabel] = field(default_factory=list)
    heartRateData: list[HeartRateData] = field(default_factory=list)
    heartRateSyncOffset: float = 0.0
    trainingPlanId: Optional[str] = None
    caloriesSummary: Optional[CaloriesSummary] = None
    heartRateZones: list[HeartRateZone] = field(default_factory=list)
    muscleGroupVolume: dict[str, Any] = field(default_factory=dict)  # MVP 留空
    status: str = "review"               # processing / review / confirmed
    createdAt: str = ""
    updatedAt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "userId": self.userId,
            "date": self.date,
            "startTime": self.startTime,
            "endTime": self.endTime,
            "videoFile": self.videoFile.to_dict(),
            "timeline": [s.to_dict() for s in self.timeline],
            "keyframeLabels": [k.to_dict() for k in self.keyframeLabels],
            "heartRateData": [h.to_dict() for h in self.heartRateData],
            "heartRateSyncOffset": self.heartRateSyncOffset,
            "trainingPlanId": self.trainingPlanId,
            "caloriesSummary": self.caloriesSummary.to_dict() if self.caloriesSummary else None,
            "heartRateZones": [z.to_dict() for z in self.heartRateZones],
            "muscleGroupVolume": self.muscleGroupVolume,
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


# ---------------------------------------------------------------------------
# 月历数据
# ---------------------------------------------------------------------------

@dataclass
class CalendarDay:
    date: str                            # ISO 日期
    hasWorkout: bool
    sessionId: Optional[str] = None
    categories: list[str] = field(default_factory=list)         # 当天涵盖的所有大类：["push", "pull"]
    categoryColors: list[str] = field(default_factory=list)     # 与 categories 对齐的颜色
    totalCalories: float = 0.0
    durationMinutes: int = 0
    exerciseSummaries: list[str] = field(default_factory=list)  # ["杠铃·平板卧推 4×10", ...]
    intensity: int = 0                   # 强度等级 0-4（0=休息，1=低 .. 4=极高）
    intensityLabel: str = "rest"         # rest / low / moderate / high / very_high

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MonthStats:
    totalSessions: int
    totalCalories: float
    totalDurationDisplay: str
    currentStreak: int
    bestStreak: int
    restDays: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MonthCalendarData:
    year: int
    month: int
    days: list[CalendarDay]
    monthStats: MonthStats

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "month": self.month,
            "days": [d.to_dict() for d in self.days],
            "monthStats": self.monthStats.to_dict(),
        }
