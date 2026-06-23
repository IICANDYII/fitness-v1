# IMU 数据融合识别技术方案

## 1. 数据现状

### 1.1 IMU 可用字段

| 字段 | 单位 | 采样率 | 状态 |
|------|------|--------|------|
| 加速度 X/Y/Z | g | ~10Hz | ✅ 可用 |
| 角速度 X/Y/Z | °/s | ~10Hz | ✅ 可用 |
| 欧拉角 X/Y/Z | ° | ~10Hz | ✅ 可用 |
| 磁场 X/Y/Z | uT | - | ❌ null |
| 四元数 0/1/2/3 | - | - | ❌ null |
| 温度 | °C | - | ❌ null |
| 高度 / 气压 | m / kPa | - | ❌ null |

**结论：可用信号为三轴加速度、三轴角速度、三轴欧拉角，共 9 通道。**

### 1.2 当前视觉识别管线

```
视频 → 1fps关键帧 + 光流
        ↓
  Phase 1（LLM）→ EXERCISE / REST / TRANSITION 区间划分
        ↓
  Phase 2（LLM）→ 器械识别 + 动作分类 + 组数/次数统计
```

### 1.3 视觉方案已知痛点

| 痛点 | 原因 |
|------|------|
| 运动/休息边界不精确 | 光流受光照变化、相机微抖影响，信噪比低 |
| rep 计数不准 | 1fps 采样丢失动作细节，光流周期性难以精确量化 |
| 站姿/坐姿/仰卧判断困难 | 第一人称视角无法直接看到自身姿态 |
| 推/拉方向模糊 | 光流方向受相机安装角度和画面内容干扰 |

---

## 2. IMU 可提取的特征

### 2.1 加速度特征（运动强度 & 动作方向）

| 特征名 | 计算方式 | 用途 |
|--------|---------|------|
| `acc_magnitude` | `sqrt(ax² + ay² + az²)` | 整体运动强度 |
| `acc_std` | 滑动窗口内 `acc_magnitude` 的标准差 | 区分运动/静止 |
| `acc_dominant_axis` | 窗口内方差最大的轴 | 判断动作主方向 |
| `acc_peak_count` | `acc_magnitude` 的峰值检测计数 | rep 计数 |
| `acc_peak_interval` | 相邻峰值的平均间隔（秒） | 动作节奏/速度 |

### 2.2 角速度特征（旋转运动）

| 特征名 | 计算方式 | 用途 |
|--------|---------|------|
| `gyro_magnitude` | `sqrt(gx² + gy² + gz²)` | 旋转运动强度 |
| `gyro_std` | 滑动窗口内 `gyro_magnitude` 的标准差 | 辅助区分运动/静止 |
| `gyro_dominant_axis` | 窗口内方差最大的轴 | 旋转方向（翻腕、摆臂等） |

### 2.3 欧拉角特征（身体姿态）

| 特征名 | 计算方式 | 用途 |
|--------|---------|------|
| `angle_x_mean` | 窗口内角度X均值 | 身体前后倾斜程度 |
| `angle_y_mean` | 窗口内角度Y均值 | 身体左右倾斜程度 |
| `angle_x_range` | 窗口内角度X的 max-min | 动作幅度（如深蹲的弯腰幅度） |
| `angle_y_range` | 窗口内角度Y的 max-min | 侧向动作幅度 |
| `posture_class` | 基于角度X/Y均值的阈值分类 | 站姿 / 坐姿 / 仰卧 / 俯身 |

**姿态分类规则（需根据 IMU 佩戴位置标定）：**

```
if angle_x ≈ 180° and angle_y ≈ 0°  → 直立站姿
if angle_x 偏离 180° 约 20°~40°     → 坐姿（略前倾）
if angle_x 偏离 180° 约 60°~90°     → 俯身 / 仰卧
```

> 注：具体阈值取决于 IMU 的佩戴位置（胸前/手腕/腰部），需用实际数据标定。

---

## 3. 融合方案设计

### 3.1 总体架构

```
视频 → 1fps关键帧 + 光流 ─────────────────┐
                                           ├→ Phase 1（LLM）→ 区间划分
IMU  → 运动强度时间线 + 姿态摘要 ──────────┘
                                           ├→ Phase 2（LLM）→ 动作识别
IMU  → 区间内姿态 + 周期特征 + rep计数 ────┘
```

### 3.2 Phase 1 融合：区间划分增强

**目标：提高 EXERCISE / REST / TRANSITION 边界精度。**

#### 输入给 LLM 的 IMU 摘要格式

按与光流摘要相同的时间窗口，生成如下文本：

```
IMU 运动摘要（窗口 00:01:00 ~ 00:02:00）:
  00:01:00~00:01:10  运动强度: 高(acc_std=0.45) 姿态: 坐姿  → 可能在做力量训练
  00:01:10~00:01:20  运动强度: 高(acc_std=0.38) 姿态: 坐姿  → 持续运动中
  00:01:20~00:01:30  运动强度: 低(acc_std=0.03) 姿态: 坐姿  → 组间休息
  00:01:30~00:01:40  运动强度: 高(acc_std=0.41) 姿态: 坐姿  → 运动恢复
  00:01:40~00:01:55  运动强度: 低(acc_std=0.05) 姿态: 直立  → 休息/行走
  00:01:55~00:02:00  运动强度: 中(acc_std=0.15) 姿态: 直立  → 行走/转场
```

#### 融合规则

- 光流显示运动 + IMU `acc_std` 高 → **高置信度 EXERCISE**
- 光流不明确 + IMU `acc_std` 低 → **倾向 REST**
- 光流显示运动 + IMU `acc_std` 低 → 可能是相机抖动导致的光流噪声，**降低 EXERCISE 置信度**
- IMU 姿态突变（如直立→坐姿） → **TRANSITION 边界标志**

### 3.3 Phase 2 融合：动作识别增强

**目标：辅助器械判断、动作分类、rep 计数。**

#### 输入给 LLM 的 IMU 特征摘要格式

```
IMU 动作特征（EXERCISE 段 exercise_001, 00:05:30 ~ 00:07:15）:
  姿态: 坐姿（angle_x 均值=155°, angle_y 均值=-8°）
  主运动方向: Y轴为主（上下运动，acc_y 方差占比 62%）
  运动幅度: angle_x 波动范围 18°（中等幅度）
  周期性: 检测到 12 个加速度峰值，平均间隔 2.3s
  推测 rep 数: 12 次
  节奏稳定性: 高（间隔标准差 0.3s）
```

#### 融合规则

| 视觉信号 | IMU 信号 | 融合判断 |
|----------|---------|---------|
| 画面看到横杆上下 | 姿态=仰卧, 主方向=Z轴(上下) | → 卧推（高置信度）|
| 画面看到绳索 | 姿态=坐姿, 主方向=Z轴(上下) | → 高位下拉（非绳索下压，因为是坐姿）|
| 画面看到绳索 | 姿态=站姿, 主方向=Z轴(上下) | → 绳索下压（站姿+从上往下）|
| 光流=左右为主 | 加速度主方向=X轴(左右) | → 夹胸类动作（双重确认）|
| 光流=前后为主 | 加速度主方向=Y轴(前后) | → 推胸类动作（双重确认）|
| LLM 判断 10 reps | IMU 峰值检测 12 reps | → 采信 IMU（更精确），输出 12 reps |

### 3.4 Phase 2 增强：组间休息检测

利用 IMU 在一个 EXERCISE 区间内进一步细分组（set）：

```
EXERCISE 段内 IMU 强度时间线:
  ████░░████░░████░░████        （█=高强度运动  ░=短暂静止）
  set1    set2    set3    set4
       rest  rest  rest
```

**检测逻辑：**

1. 在 EXERCISE 区间内，找 `acc_std` 低于阈值且持续 > 5秒 的片段 → 组间休息
2. 两个休息之间的高强度区间 → 一组（set）
3. 每组内的加速度峰值数 → 该组的 reps

---

## 4. 时间对齐

IMU 和视频必须在同一时间轴上才能融合。

### 4.1 方案 A：绝对时间戳对齐（推荐）

- 视频文件名或元数据包含录制开始时间
- IMU 数据自带绝对时间戳（如 `2026-06-18T17:21:54.843`）
- 两者通过系统时钟对齐，误差通常在 1 秒内

### 4.2 方案 B：事件对齐（备选）

如果时钟不同步，利用"击掌"或"跺脚"等大幅度动作：
- 视频中找到该动作的帧时间
- IMU 中找到对应的加速度脉冲时间
- 两个时间差作为偏移量

---

## 5. 实现计划

### 5.1 模块结构

```
gym_analyzer/
  imu_processor.py        # IMU 数据解析 + 特征提取
  recognizer.py            # 修改：在 Phase 1/2 中注入 IMU 摘要
```

### 5.2 `imu_processor.py` 核心接口

```python
class IMUData:
    """解析 IMU 原始数据文件"""
    def __init__(self, filepath: str): ...

    # 基础查询
    def get_time_range(self) -> tuple[datetime, datetime]: ...
    def get_sample_rate(self) -> float: ...

    # Phase 1 用：运动强度时间线
    def summarize_motion_intensity(
        self, start_sec: float, end_sec: float, bin_sec: float = 10
    ) -> str: ...

    # Phase 2 用：区间内动作特征
    def extract_exercise_features(
        self, start_sec: float, end_sec: float
    ) -> dict: ...
    # 返回: {posture, dominant_axis, angle_range, peak_count, peak_interval, ...}

    # Phase 2 用：组间休息检测
    def detect_sets(
        self, start_sec: float, end_sec: float,
        rest_threshold: float = 0.08, min_rest_sec: float = 5
    ) -> list[dict]: ...
    # 返回: [{set_start, set_end, reps, rest_after_sec}, ...]

    # 格式化输出（直接嵌入 LLM prompt）
    def format_for_phase1(self, start_sec: float, end_sec: float) -> str: ...
    def format_for_phase2(self, start_sec: float, end_sec: float) -> str: ...
```

### 5.3 开发步骤

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | 实现 `IMUData` 数据解析和基础特征计算 | 无 |
| 2 | 实现 `format_for_phase1()`，生成运动强度时间线文本 | 步骤 1 |
| 3 | 修改 `run_phase1()`，在 user_content 中插入 IMU 摘要 | 步骤 2 |
| 4 | 实现 `extract_exercise_features()` 和 `detect_sets()` | 步骤 1 |
| 5 | 实现 `format_for_phase2()`，生成动作特征文本 | 步骤 4 |
| 6 | 修改 `run_phase2()`，在 user prompt 中插入 IMU 特征 | 步骤 5 |
| 7 | 用 618 数据端到端验证，调整阈值和 prompt | 步骤 3+6 |

### 5.4 降级策略

IMU 数据为可选输入。当 IMU 文件不存在或时间无法对齐时，系统回退到纯视觉方案，不影响现有功能。

---

## 6. 预期收益

| 维度 | 纯视觉方案 | 视觉 + IMU 融合 |
|------|-----------|-----------------|
| 区间边界精度 | ±5~10s | ±1~2s |
| rep 计数 | 依赖光流周期性，误差较大 | IMU 峰值检测，误差 ±1 |
| 站姿/坐姿判断 | 靠画面推断，常出错 | 欧拉角直接判定 |
| 组间休息识别 | Phase 2 LLM 推测 | IMU 强度阈值精确切分 |
| 推/拉方向 | 光流方向（受干扰大） | 加速度主轴 + 光流双重验证 |
