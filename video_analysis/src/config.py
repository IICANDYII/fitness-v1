"""全局配置：常量、器械库、动作-tempo 表、MET 表、心率区间、月历分类。

所有可调参数都集中在这里，方便后续调优。
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = PROJECT_ROOT / "video"
OUTPUT_DIR = PROJECT_ROOT / "output"
USER_PROFILE_PATH = PROJECT_ROOT / "user_profile.json"


# ---------------------------------------------------------------------------
# AI 模型
# ---------------------------------------------------------------------------

VISION_MODEL = "gpt-5"
TEXT_MODEL = "gpt-5"
BATCH_SIZE = 8                           # 单次 GPT 调用喂入的关键帧张数
IMAGE_DETAIL = "low"                     # 节省 token


# ---------------------------------------------------------------------------
# 抽帧 / 分段算法参数
# ---------------------------------------------------------------------------

SAMPLING_INTERVAL_S = 0.5                # 抽帧间隔（秒）；0.5 = 2 fps
KEYFRAME_MAX_DIM = 400                   # 关键帧缩放后最大边长（像素）
KEYFRAME_JPEG_QUALITY = 50               # JPEG 编码质量（0-100），与 MAX_DIM 一起把单张控制在 ~10KB

# 段内 ≥SET_BREAK_MIN_FRAMES 个连续 rest 帧 → 一次组间休息
# 目标语义"≥6 秒静止"，根据当前 SAMPLING_INTERVAL_S 自动换算
SET_BREAK_MIN_FRAMES = max(2, int(round(6.0 / SAMPLING_INTERVAL_S)))
INTRA_EXERCISE_REST_MAX_S = 180          # ≤180s 的 rest 段被合并入相邻 exercise（v2.1 放宽）

LOW_CONFIDENCE_THRESHOLD = 0.5           # 低于此值标为 unknown
HR_MIN_POINTS_FOR_HR_METHOD = 5          # 心率法所需最少数据点


# ---------------------------------------------------------------------------
# 器械库（17 个标签，对应技术方案 2.4 节）
#
# 每个器械绑定：
#   id            内部 ID
#   name          中文名
#   category      free_weight / machine / cable / bodyweight / cardio / other
#   movements     该器械可能的具体动作（用于 AI prompt 约束）
#   metFactor     MET 系数（用于 MET 法卡路里估算）
# ---------------------------------------------------------------------------

EQUIPMENT_LIBRARY: dict[str, dict] = {
    # ── 有氧 ──
    "跑步": {
        "id": "equip_treadmill",
        "category": "cardio",
        "movements": ["跑步", "快走"],
        "metFactor": 8.3,
    },
    "椭圆机": {
        "id": "equip_elliptical",
        "category": "cardio",
        "movements": ["椭圆机"],
        "metFactor": 5.0,
    },
    "动感单车": {
        "id": "equip_spin_bike",
        "category": "cardio",
        "movements": ["动感单车"],
        "metFactor": 6.8,
    },
    "划船机": {
        "id": "equip_rower",
        "category": "cardio",
        "movements": ["划船机"],
        "metFactor": 7.0,
    },

    # ── 自由重量 ──
    "杠铃": {
        "id": "equip_barbell",
        "category": "free_weight",
        "movements": [
            "平板卧推", "上斜卧推", "下斜卧推",
            "深蹲", "硬拉", "划船", "推举", "弯举",
        ],
        "metFactor": 6.0,
    },
    "哑铃": {
        "id": "equip_dumbbell",
        "category": "free_weight",
        "movements": [
            "哑铃卧推", "哑铃上斜卧推", "哑铃飞鸟",
            "哑铃弯举", "哑铃侧平举", "哑铃划船", "哑铃推举",
        ],
        "metFactor": 5.0,
    },
    "史密斯架": {
        "id": "equip_smith",
        "category": "free_weight",
        "movements": [
            "史密斯卧推", "史密斯深蹲", "史密斯划船", "史密斯推举",
        ],
        "metFactor": 5.5,
    },

    # ── 自重 / 悬挂 ──
    "引体向上": {
        "id": "equip_pullup_bar",
        "category": "bodyweight",
        "movements": ["引体向上"],
        "metFactor": 8.0,
    },
    "自重训练": {
        "id": "equip_bodyweight",
        "category": "bodyweight",
        "movements": ["俯卧撑", "平板支撑", "卷腹", "深蹲跳", "箭步蹲"],
        "metFactor": 3.8,
    },

    # ── 固定器械 ──
    "高位下拉": {
        "id": "equip_lat_pulldown",
        "category": "machine",
        "movements": ["高位下拉"],
        "metFactor": 5.0,
    },
    "坐姿划船": {
        "id": "equip_seated_row",
        "category": "machine",
        "movements": ["坐姿划船"],
        "metFactor": 4.5,
    },
    "腿举机": {
        "id": "equip_leg_press",
        "category": "machine",
        "movements": ["腿举"],
        "metFactor": 5.5,
    },
    "蝴蝶机": {
        "id": "equip_pec_deck",
        "category": "machine",
        "movements": ["夹胸", "反向夹胸"],
        "metFactor": 4.5,
    },
    "推肩机": {
        "id": "equip_shoulder_press",
        "category": "machine",
        "movements": ["推肩"],
        "metFactor": 5.0,
    },

    # ── 绳索 ──
    "龙门架": {
        "id": "equip_cable_crossover",
        "category": "cable",
        "movements": [
            "绳索夹胸", "绳索下拉", "绳索划船", "绳索三头下压", "绳索弯举",
        ],
        "metFactor": 4.5,
    },

    # ── 非训练 ──
    "拉伸": {
        "id": "equip_stretch",
        "category": "other",
        "movements": ["拉伸"],
        "metFactor": 2.3,
    },
    "其他": {
        "id": "equip_other",
        "category": "other",
        "movements": [],
        "metFactor": 3.0,
    },
}

# 反查：equipmentName 列表（供 AI prompt 用）
EQUIPMENT_NAMES = list(EQUIPMENT_LIBRARY.keys())


# ---------------------------------------------------------------------------
# 动作 tempo 表（秒/次），用于次数估算
#
# 取值参考：常见健身教学视频里"标准节奏"的中位数。
# 估算公式：reps = max(1, round(运动时长 / tempo))
# 没有 tempo 的动作默认 3.0
# ---------------------------------------------------------------------------

MOVEMENT_TEMPOS: dict[str, float] = {
    # 卧推系
    "平板卧推": 3.5, "上斜卧推": 3.5, "下斜卧推": 3.5,
    "哑铃卧推": 3.5, "哑铃上斜卧推": 3.5,
    "史密斯卧推": 3.5,

    # 下肢
    "深蹲": 4.0, "硬拉": 4.0, "腿举": 3.5,
    "史密斯深蹲": 4.0, "箭步蹲": 3.0, "深蹲跳": 1.5,

    # 推举
    "推举": 3.0, "哑铃推举": 3.0, "史密斯推举": 3.0, "推肩": 3.0,

    # 拉
    "划船": 3.0, "哑铃划船": 3.0, "史密斯划船": 3.0,
    "坐姿划船": 3.0, "高位下拉": 3.0, "引体向上": 3.0,
    "绳索划船": 3.0, "绳索下拉": 3.0,

    # 单关节
    "弯举": 2.5, "哑铃弯举": 2.5, "绳索弯举": 2.5,
    "哑铃侧平举": 2.5,
    "飞鸟": 3.5, "哑铃飞鸟": 3.5,
    "夹胸": 3.5, "反向夹胸": 3.5, "绳索夹胸": 3.5,
    "绳索三头下压": 2.5,

    # 自重
    "俯卧撑": 2.5, "卷腹": 2.0,
    # 等长动作（无 rep 概念，存一个值方便统一处理）
    "平板支撑": 30.0,

    # 有氧（连续动作，下面的 tempo 不会真正用到）
    "跑步": 1.0, "快走": 1.0, "椭圆机": 1.0,
    "动感单车": 1.0, "划船机": 1.0,

    # 默认
    "拉伸": 30.0,
}

DEFAULT_TEMPO = 3.0


# ---------------------------------------------------------------------------
# 心率区间
# ---------------------------------------------------------------------------

HR_ZONES = [
    ("warmup",  "热身",   0.50, 0.60, "#94A3B8"),  # 灰蓝
    ("fatburn", "燃脂",   0.60, 0.70, "#FCD34D"),  # 黄
    ("cardio",  "有氧",   0.70, 0.80, "#34D399"),  # 绿
    ("peak",    "峰值",   0.80, 0.90, "#FB923C"),  # 橙
    ("max",     "极限",   0.90, 1.10, "#EF4444"),  # 红（上限给 1.10 兜底）
]


# ---------------------------------------------------------------------------
# 月历分类：动作 → 类别（推 / 拉 / 腿 / 有氧 / 混合）
#
# 用 movementName 关键词匹配。匹配优先级：
#   1) leg（深蹲/硬拉/腿举/箭步蹲）
#   2) cardio（跑步/快走/椭圆/单车/划船机）
#   3) push（卧推/推举/推肩/夹胸/三头）
#   4) pull（下拉/划船/引体/弯举）
#   5) 不在任何关键词命中 → "other"
#
# 一天里若出现 ≥2 个大类（且不含"other"），归为 "mixed"。
# ---------------------------------------------------------------------------

CATEGORY_COLORS = {
    "push":   "#3B82F6",   # 蓝
    "pull":   "#10B981",   # 绿
    "leg":    "#F97316",   # 橙
    "cardio": "#EF4444",   # 红
    "mixed":  "#8B5CF6",   # 紫
    "other":  "#9CA3AF",   # 灰
    "rest":   "#E5E7EB",   # 浅灰（休息日）
}

CATEGORY_DISPLAY_NAMES = {
    "push": "推",
    "pull": "拉",
    "leg":  "腿",
    "cardio": "有氧",
    "mixed": "混合",
    "other": "其他",
    "rest":  "休息",
}

# 关键词匹配规则（按优先级从上到下匹配，匹中即停）
CATEGORY_KEYWORDS = [
    ("leg",    ["深蹲", "硬拉", "腿举", "箭步蹲", "腿"]),
    ("cardio", ["跑步", "快走", "椭圆", "单车", "划船机"]),
    ("push",   ["卧推", "推举", "推肩", "夹胸", "三头", "俯卧撑"]),
    ("pull",   ["下拉", "划船", "引体", "弯举"]),
]


def categorize_movement(movement_name: str) -> str:
    """根据 movementName 推断动作大类（push/pull/leg/cardio/other）。"""
    if not movement_name:
        return "other"
    for cat, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in movement_name:
                return cat
    return "other"


def categorize_session(movements: list[str]) -> str:
    """根据一次训练的所有动作名，推断整次训练的大类。

    规则：
      - 全部 other → "other"
      - 单一类别 → 该类别
      - ≥2 个非 other 类别 → "mixed"
    """
    if not movements:
        return "other"
    cats = {categorize_movement(m) for m in movements}
    cats.discard("other")
    if not cats:
        return "other"
    if len(cats) == 1:
        return next(iter(cats))
    return "mixed"


# 月历显示时使用的类别排序（统一展示顺序：推 → 拉 → 腿 → 有氧 → 其他）
_CATEGORY_DISPLAY_ORDER = ["push", "pull", "leg", "cardio", "other"]


def session_categories(movements: list[str]) -> list[str]:
    """返回一次训练涉及的所有大类（去重 + 按统一顺序排序）。

    用于月历显示：一天里有"推"和"拉"两类动作时，返回 ["push", "pull"]，
    而不是粗暴聚合成"mixed"。
    """
    if not movements:
        return ["other"]
    found = {categorize_movement(m) for m in movements}
    out = [c for c in _CATEGORY_DISPLAY_ORDER if c in found]
    return out or ["other"]


# ---------------------------------------------------------------------------
# 训练部位（细粒度）：胸 / 背 / 肩 / 臂 / 腿 / 腹 / 心肺
#
# 月历单元格用这套粒度而不是粗大类（推/拉/腿）。
# 一个动作通常映射到一个主要部位；多关节动作取主练肌群。
# ---------------------------------------------------------------------------

BODYPART_COLORS = {
    "chest":     "#EF4444",   # 红
    "back":      "#10B981",   # 绿
    "shoulder":  "#8B5CF6",   # 紫
    "arm":       "#F59E0B",   # 琥珀
    "leg":       "#F97316",   # 橙
    "abs":       "#EC4899",   # 粉
    "cardio":    "#DC2626",   # 深红
    "other":     "#9CA3AF",   # 灰
}

BODYPART_DISPLAY_NAMES = {
    "chest":    "胸",
    "back":     "背",
    "shoulder": "肩",
    "arm":      "臂",
    "leg":      "腿",
    "abs":      "腹",
    "cardio":   "心肺",
    "other":    "其他",
}

# 动作名关键词 → 部位映射（按优先级匹配，匹中即停）
BODYPART_KEYWORDS = [
    # 腹（先于胸，因俯卧撑会被胸先抓走，但俯卧撑通常算胸）
    ("abs",      ["卷腹", "平板支撑"]),
    # 腿（先于其他，深蹲/硬拉是复合动作但主部位是腿）
    ("leg",      ["深蹲", "硬拉", "腿举", "箭步蹲"]),
    # 心肺
    ("cardio",   ["跑步", "快走", "椭圆", "单车", "划船机"]),
    # 胸（卧推、飞鸟、夹胸、俯卧撑）
    ("chest",    ["卧推", "飞鸟", "夹胸", "俯卧撑"]),
    # 肩（推肩、推举、侧平举）
    ("shoulder", ["推肩", "推举", "侧平举"]),
    # 背（下拉、划船、引体）
    ("back",     ["下拉", "划船", "引体"]),
    # 臂（弯举、三头下压）
    ("arm",      ["弯举", "三头", "下压"]),
]


def bodypart_of_movement(movement_name: str) -> str:
    """根据 movementName 推断主练部位。"""
    if not movement_name:
        return "other"
    for code, keywords in BODYPART_KEYWORDS:
        for kw in keywords:
            if kw in movement_name:
                return code
    return "other"


# 月历显示时部位的排序（统一展示顺序）
_BODYPART_DISPLAY_ORDER = ["chest", "back", "shoulder", "arm", "leg", "abs", "cardio", "other"]


def session_bodyparts(movements: list[str]) -> list[str]:
    """返回一次训练涉及的所有部位（去重 + 按统一顺序排序）。

    例：[卧推, 高位下拉, 推肩] → ["chest", "back", "shoulder"]
    """
    if not movements:
        return ["other"]
    found = {bodypart_of_movement(m) for m in movements}
    out = [bp for bp in _BODYPART_DISPLAY_ORDER if bp in found]
    return out or ["other"]


# ---------------------------------------------------------------------------
# 时间线 / 图表配色
# ---------------------------------------------------------------------------

SEGMENT_COLORS = {
    "exercise":   "#3B82F6",  # 蓝
    "transition": "#9CA3AF",  # 灰
    "rest":       "#FCA5A5",  # 浅红
}


# ---------------------------------------------------------------------------
# 月历训练强度（5 级，0=休息）
#
# 强度计算逻辑（按优先级）：
#   1. 有心率数据 → 用"占主导的心率区间"映射等级：
#        warmup→1  fatburn→2  cardio→3  peak→4  max→4
#      "占主导"= durationSeconds 最大的那个区间
#   2. 无心率数据 → 用 kcal/分钟 这个粗略指标：
#        <3 kcal/min → 1   3-5 → 2   5-8 → 3   ≥8 → 4
#
# 每级对应一组背景色（淡到浓），用于月历格子的 tint。
# ---------------------------------------------------------------------------

INTENSITY_LEVELS = [
    ("rest",       "休息",   "#F9FAFB"),   # 0: 几乎白
    ("low",        "低强度", "#FEF3C7"),   # 1: 浅奶黄
    ("moderate",   "中强度", "#FDE68A"),   # 2: 浅黄
    ("high",       "高强度", "#FB923C"),   # 3: 橙
    ("very_high",  "极强度", "#DC2626"),   # 4: 深红
]


def _intensity_from_hr_zones(zones: list[dict]) -> int:
    """根据 heartRateZones 找占主导（时长最大）的区间，返回 1-4。"""
    if not zones:
        return 0
    dominant = max(zones, key=lambda z: z.get("durationSeconds", 0))
    code = dominant.get("zone", "warmup")
    return {"warmup": 1, "fatburn": 2, "cardio": 3, "peak": 4, "max": 4}.get(code, 1)


def _intensity_from_kcal_rate(total_calories: float, duration_min: float) -> int:
    """没有心率数据时的兜底：用 kcal/min。"""
    if duration_min <= 0:
        return 0
    rate = total_calories / duration_min
    if rate < 3:
        return 1
    if rate < 5:
        return 2
    if rate < 8:
        return 3
    return 4


def calculate_day_intensity(
    has_workout: bool,
    heart_rate_zones: list[dict] | None,
    total_calories: float,
    duration_minutes: float,
) -> tuple[int, str]:
    """返回 (intensity_level, label)，其中 level ∈ {0,1,2,3,4}。"""
    if not has_workout or duration_minutes <= 0:
        return 0, "rest"
    if heart_rate_zones:
        level = _intensity_from_hr_zones(heart_rate_zones)
    else:
        level = _intensity_from_kcal_rate(total_calories, duration_minutes)
    return level, INTENSITY_LEVELS[level][0]


def intensity_background_color(level: int) -> str:
    """根据强度等级返回格子背景色。"""
    level = max(0, min(4, level))
    return INTENSITY_LEVELS[level][2]


# ---------------------------------------------------------------------------
# Matplotlib 中文字体回退
# ---------------------------------------------------------------------------

CHINESE_FONTS = ["Microsoft YaHei", "SimHei", "DengXian", "Arial Unicode MS"]
