# 项目 TODO

## 待办事项

<!-- 在此添加待办任务 -->

---

## 当前识别算法摘要

### 总体管线

```
视频 → 抽帧（1fps）+ 光流计算
          ↓
    Phase 1（LLM）→ EXERCISE / REST / TRANSITION 区间划分
          ↓
    Phase 2（LLM）→ 器械识别 + 动作分类 + 组数/次数统计
```

可选输入：IMU 数据（`IMU_data.txt`），缺失时自动降级为纯视觉方案。

---

### 1. 抽帧方式

- **采样率**：固定 1 FPS（`INTERVAL = 1.0` 秒），每秒取一帧
- **存储**：帧以 JPEG 格式保存到 `{work_dir}/frames/`，元数据写入 `frames_meta.json`（含时间戳和文件路径）
- **相机视角**：第一人称胸前摄像头，画面中无法直接看到完整身体，主要依赖手部动作、器械细节和画面整体运动趋势

---

### 2. 拼图模式（Grid / Mosaic）

两阶段使用不同策略生成拼图，均以左→右、上→下的阅读顺序排列帧：

#### Phase 1：时间窗口拼图（区间划分用）

- 将整段视频按固定时间窗口切分，每个窗口内的帧拼成一张网格图
- 图像以 JPEG quality=60 编码后送入 LLM，LLM 据此判断当前窗口属于 EXERCISE / REST / TRANSITION
- 大视频触发分块处理（`PHASE1_CHUNK_THRESHOLD=25` 个窗口），每块最多 20 个窗口

#### Phase 2：动作区间拼图（动作识别用）

- 以识别到的每段 EXERCISE 区间为单位生成拼图，首尾各扩展 **15 秒**（`EXERCISE_BOUNDARY_PAD`）以保留动作上下文
- 额外提取**入场帧**（区间开始前 5 秒 ～ 开始后 3 秒，最多 3 帧），单独发给 LLM，用于观察器械外观（座椅、踏板、把手、配重）
- 每段 EXERCISE 区间独立并发处理（最多 4 个并发，可配置）

---

### 3. 光流信息

**计算模块**：`optical_flow.py`，函数 `compute_optical_flow(frame_metas, video_dir)`

**数据结构**（每帧一条记录）：
```
{
  "time_sec": 0.0,
  "avg_flow": 2.5,
  "flow_direction": "UP|DOWN|LEFT|RIGHT|FORWARD|BACKWARD",
  "flow_details": { 各方向占比 }
}
```

**缓存策略**（三级优先）：
1. 共享缓存：`recognize/visualize/result/shared/{video_name}/optical_flow.json`
2. 本地缓存：`{video_dir}/optical_flow.json`
3. 两者均不存在或指定 `--overwrite` 时重新计算

**Phase 1 用途**：`summarize_window_flow()` 生成每个时间窗口的文本摘要（均值、主方向），附加在拼图提示词中，辅助判断运动/休息状态。

**Phase 2 用途**：`format_flow_for_exercise()` 生成方向分布文本，并触发**光流纠正机制**——若光流方向与 LLM 的器械推断矛盾，LLM 必须以光流为准（例：左右光流 → 夹胸，非推胸）。

---

### 4. IMU 摘要

> 详细方案见 [imu_integration_proposal.md](imu_integration_proposal.md)

**数据来源**：`{video_dir}/IMU_data.txt`（Tab 分隔，含时间戳和 9 通道信号）

**可用信号**：三轴加速度（acc_x/y/z）、三轴角速度（gyro_x/y/z）、三轴欧拉角，共 9 通道，采样率约 10Hz。

**当前实现（pipeline.py + recognizer.py）**：

加载时计算：
- `acc_magnitude = sqrt(ax² + ay² + az²)`
- `gyro_magnitude = sqrt(gx² + gy² + gz²)`

**Phase 1 IMU**：`format_imu_for_phase1()`，按 30 秒窗口统计 `gyro_mean/max`，映射为强度标签：
| gyro_max | 标签 |
|----------|------|
| > 30 °/s | 高强度运动 |
| > 10 °/s | 中等运动 |
| > 3 °/s  | 轻度运动 |
| ≤ 3 °/s  | 静止/休息 |

**Phase 2 IMU**：`format_imu_for_exercise()`，在区间 ±5 秒范围内计算 `gyro_mean/max`、`acc_mean/max`，并通过阈值过零点检测估算动作周期（≥4 次过零则估算 `est_period = duration / (transitions / 2)`）。

**待完善方向（来自提案）**：
- 加速度峰值计数（rep 计数）
- 欧拉角姿态分类（站姿 / 坐姿 / 仰卧 / 俯身）
- EXERCISE 区间内组间休息细分（基于 `acc_std` 阈值）
- 提取独立 `imu_processor.py` 模块，实现 `IMUData` 类统一接口
- 时间对齐：优先绝对时间戳，备选事件对齐（击掌/跺脚）
