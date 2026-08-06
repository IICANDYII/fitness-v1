# Fitness Agent 产品交接整理

> 角色视角：产品经理接手文档  
> 模块关系：Relty 下属 Fitness Agent，和此前推进的 Diet Agent 为平级 Agent  
> 资料来源：本地交接包内产品文档、动作库、IMU 脚本说明、Fitness Balance v4 文档与图示  
> 外链状态：飞书链接当前在命令行侧返回 404，需后续通过有权限账号补充校验

---

## 1. 一句话结论

Fitness Agent 当前不是一个成熟的“专业健身教练替代品”，而是 Relty 第一人称记录设备上的健身房训练记录与总结模块。

现阶段最重要的产品目标不是继续扩复杂 Agent 能力，而是跑稳：

```text
训练数据采集
→ 模型生成训练 timeline 草稿
→ 用户/人工轻反馈确认
→ 形成标准答案
→ 每日评测优化
→ 生成稳定训练报告
```

产品应优先服务于“低成本记录训练过程、识别训练内容、生成可理解报告、积累可回流数据”。

---

## 2. 模块定位

### 2.1 产品定位

Fitness Agent 是 Relty 的健身场景 Agent，基于胸前第一人称设备采集到的图片序列、视频素材和 IMU 数据，识别用户是否在健身、做了什么动作、练到了哪些肌群，并生成训练总结与后续建议。

### 2.2 与 Diet Agent 的关系

Fitness Agent 与 Diet Agent 是平级关系：

| 维度 | Diet Agent | Fitness Agent |
|---|---|---|
| 场景 | 饮食记录、识别、分析 | 健身房训练记录、识别、总结 |
| 输入 | 餐食图片、时间、上下文 | 第一人称图片/视频、IMU、训练计划 |
| 核心输出 | 饮食记录、营养结构、建议 | 训练 timeline、动作/肌群、报告、Balance |
| 用户负担 | 尽量少手动录入 | 轻确认训练 timeline 和动作 |
| 难点 | 食物识别、份量估计 | 第一人称动作识别、组数/次数、遮挡和相似动作 |

两者共用的产品原则是：先让用户低成本记录，再用轻反馈修正，最后把确认数据回流到模型和规则优化。

---

## 3. 当前进展判断

### 3.1 已经具备的基础

1. 训练素材到训练总结已经初步跑通  
   当前可以基于员工录制的视频/图片素材生成训练总结，内容包括训练内容、肌群覆盖、完成情况、表现反馈、恢复建议等。

2. 员工数据采集流程已有雏形  
   当前方式是员工录制完整健身过程，从进入健身房到训练结束。已发现视频文件大、NAS 上传慢等问题，临时方案是通过飞书压缩后上传至 NAS。

3. 动作库已完成初筛  
   本地动作库共 75 行、49 个标准动作，全部标记为 include_in_mvp。  
   其中 A 级第一人称可识别动作 50 行，B 级 25 行。

4. 模型评估方向已明确  
   当前模型方向为 Gemini 3 Flash，优化重点不是换模型，而是提示词、输入结构、数据组织与评测体系。

5. IMU 辅助脚本已有第一版  
   脚本可将 WT901 类 IMU 数据转为秒级特征、active/rest 段、set/rep 候选、动作大类候补 JSON。

6. Fitness Balance v4 公式已有候选版本  
   已有计算文档、流程图、函数曲线、3D 曲面、瀑布图和测试器，但该公式不应直接视为最终定稿。后续需要预留 PM 主导的公式 review 与修正窗口。

### 3.2 尚未跑稳的部分

1. 数据量不足  
   目前主要依赖内部员工素材，无法支撑稳定评测和动作覆盖。

2. 标准答案体系不足  
   还没有稳定的标注规范和评测集，模型效果容易停留在单次 demo 判断。

3. 用户轻反馈流程未产品化  
   文档建议采用轻反馈，但具体 UI、确认字段、回流链路尚未定义。

4. 动作到肌群权重表未完全落地  
   Fitness Balance v4 需要 exercise-to-muscle taxonomy，但当前本地动作库和 Balance 权重表还未完全对齐。

5. 核心/腹部动作覆盖不足  
   Balance v4 使用 7 大肌群：legs、hips、back、abdomen、chest、shoulders、arms。  
   但当前动作库中核心/腹部动作明显不足，可能导致 Balance 经常提示 abdomen 缺失。

6. Fitness Balance 公式需要修正窗口  
   公式当前是 v4 候选稿。由于它会影响用户报告、周分析和下一次训练建议，不能只由研发照公式实现。需要先通过真实样本、极端样本和用户解释文案共同 review，再决定冻结版本。

---

## 4. MVP 产品范围

### 4.1 MVP 不做什么

MVP 阶段不要承诺：

1. 完全自动、无需用户确认的动作识别。
2. 高精度组数/次数识别。
3. 替代专业健身教练。
4. 基于重量的训练负荷分析。
5. 复杂增肌/减脂/塑形目标体系。
6. 医学或康复级恢复判断。

### 4.2 MVP 应做什么

MVP 应聚焦 5 个能力：

1. 识别用户是否处于健身房训练场景。
2. 生成训练 timeline 草稿。
3. 识别动作候选、器械候选和肌群覆盖。
4. 让用户以低成本确认/修正训练记录。
5. 基于确认后的训练记录生成训练报告与 Fitness Balance。

### 4.3 首页信息架构建议

Fitness Agent 首页不应优先让用户制定计划，而应优先展示上一次训练结果。

推荐结构：

1. 首页：上一次训练总结
2. 训练记录：训练时间线、动作、肌群、完成情况
3. 计划：根据目标和可用器械生成下一次训练建议
4. 对话：用户追问表现、调整计划、解释报告

---

## 5. 核心用户流程

### 5.1 训练前

用户可以选择或生成当天训练计划。

计划不应在 MVP 中做得过重，它主要作为模型识别的先验信息：

```text
当天计划包含深蹲
视觉候选：深蹲 / 硬拉 / 俯身划船
IMU：torso_flexion_extension，rep_count_candidate = 10
最终更倾向：深蹲，约 10 次
```

### 5.2 训练中

设备采集：

1. 第一人称图片序列或视频片段。
2. IMU 加速度、角速度、姿态角。
3. 时间戳。
4. 可选：训练计划 ID、健身房/器械上下文。

### 5.3 训练后

系统生成 timeline 草稿：

| 字段 | 说明 |
|---|---|
| start_s / end_s | 动作片段起止时间 |
| action_candidate | 候选动作 |
| equipment_candidate | 候选器械 |
| muscle_groups | 覆盖肌群 |
| set_candidate | 组候选 |
| rep_count_candidate | 次数候选 |
| confidence | 识别置信度 |
| needs_user_confirmation | 是否需要用户确认 |

### 5.4 用户轻反馈

用户不应被要求完整标注训练过程，只需要做轻量确认：

1. 这个时间段是不是训练动作？
2. 动作是否正确？
3. 如果不正确，在 2-3 个候选动作中选择。
4. 组数/次数是否大致正确？
5. 是否忽略这个片段？

### 5.5 报告生成

确认后生成训练报告：

1. 本次训练做了什么。
2. 覆盖了哪些肌群。
3. 哪些动作识别置信度较高/较低。
4. 本次训练是否偏向某些肌群。
5. 下次建议补充哪些部位。
6. Fitness Balance 是否更新。

---

## 6. 识别优先级

当前识别优先级应为：

1. 用户是否在健身。
2. 当前是有氧还是力量训练。
3. 当前使用什么器械/场景。
4. 当前做的动作是什么。
5. 练到什么肌群。
6. 做了几组、每组几次。

组数/次数不要作为第一优先级，因为仅靠第一人称画面很难稳定判断，需要 IMU、节奏特征和用户轻反馈共同辅助。

---

## 7. 动作库现状

### 7.1 总体统计

| 指标 | 数量 |
|---|---:|
| 动作库行数 | 75 |
| 标准动作数 | 49 |
| A 级第一人称可识别动作 | 50 |
| B 级动作 | 25 |
| include_in_mvp | 75 |

### 7.2 肌群分布

| 分类 | 数量 |
|---|---:|
| 胸 | 14 |
| 腿 | 14 |
| 背 | 13 |
| 手臂 | 11 |
| 肩 | 11 |
| 有氧 | 6 |
| 腿/臀 | 3 |
| 胸/手臂 | 3 |

### 7.3 器械分布

| 器械 | 数量 |
|---|---:|
| cable | 14 |
| dumbbell | 14 |
| fixed_machine | 12 |
| barbell | 10 |
| smith_machine | 8 |
| no_equipment | 7 |
| assisted_machine | 4 |
| cardio_bike | 3 |
| cardio_elliptical | 1 |
| cardio_stepmill | 1 |
| cardio_treadmill | 1 |

### 7.4 MVP 采集建议

不要一上来覆盖全部 49 个标准动作。建议先选 15-20 个 A 级高频动作作为第一批采集闭环。

建议优先动作：

1. machine_chest_press
2. cable_lat_pulldown
3. cable_seated_row
4. machine_leg_press
5. machine_shoulder_press
6. dumbbell_shoulder_press
7. dumbbell_squat
8. barbell_squat
9. smith_squat
10. barbell_bent_over_row
11. cable_triceps_pushdown
12. cable_biceps_curl
13. dumbbell_biceps_curl
14. cable_lateral_raise
15. treadmill_walk_run
16. stationary_bike
17. elliptical

补充建议：需要增加核心/腹部动作，否则 Fitness Balance 的 abdomen 维度会长期缺数据。

---

## 8. IMU 的产品定位

### 8.1 IMU 做什么

IMU 不直接识别具体动作名。它适合辅助回答：

1. 用户什么时候在运动。
2. 哪些运动段可能是一组训练。
3. 每组大概有多少次动作候选。
4. 当前运动更像哪类动作形态。
5. 哪些动作大类可以排除。
6. 哪些片段需要结合视频确认。

### 8.2 IMU 输出动作大类

当前脚本输出 6 类：

| 动作大类 | 含义 |
|---|---|
| rest_or_static_hold | 静止、休息、站立、坐着或静态支撑候选 |
| large_transition_or_device_rotation | 转身、走动、换器械、调整设备 |
| cardio_rhythmic | 连续有氧周期运动 |
| torso_flexion_extension | 躯干俯仰/屈伸类，如深蹲、硬拉、划船 |
| upper_limb_isolation | 上肢孤立类，如弯举、下压、侧平举 |
| ambiguous_motion | 有运动但规则无法稳定分类 |

### 8.3 IMU 与视觉模型的融合

推荐融合方式：

```text
视觉模型：识别器械、手部方向、身体姿态、候选动作
IMU 脚本：识别 active/rest、set 候选、rep 候选、动作大类
训练计划：提供当天可能动作先验
大模型：融合三者，输出最终 timeline
```

### 8.4 IMU 边界

1. 不能单独识别具体动作。
2. 不能替代视觉模型。
3. 对上肢孤立动作的具体动作名识别弱。
4. 对佩戴位置变化敏感。
5. 转身、设备调整、走路可能产生 rep 误报。
6. 阈值需要真实健身房数据持续校准。

---

## 9. Fitness Balance v4 候选公式

### 9.1 指标定位

Fitness Balance 是 Fitness Agent 中用于解释用户近期力量训练结构状态的 Balance 指标。

当前公式应被视为 `v4_candidate`，不是最终冻结版。后续需要专门 review，并保留公式修正窗口。

它用于回答：

1. 最近 7 天力量训练是否真实有效。
2. 训练结构是否相对合理。
3. 训练频率和剂量是否足够。
4. 是否存在同一肌群恢复间隔不足。

Fitness Balance 不等于：

1. 训练计划完成度。
2. 增肌效果。
3. 力量水平。
4. 减脂效果。
5. 热量消耗。
6. 训练后酸痛程度。
7. 用户目标完成度。

这些应进入 Fitness Finish、Training Volume、Training Load、Progressive Overload、Recovery Flag 或 Coach Insight。

### 9.2 计算窗口

```text
rolling_window = 最近 7 天
```

每天计算时，回看最近 7 天内的有效力量训练事件。

### 9.3 有氧处理

健身房有氧训练在 Fitness Agent 中展示，但不进入 Fitness Balance，而是进入 Activity Balance。

例如：

| 训练事件 | 归属 |
|---|---|
| 跑步机 30 分钟 | Activity Balance |
| 椭圆机 15 分钟 | Activity Balance |
| 固定器械推胸 | Fitness Balance |
| 高位下拉 | Fitness Balance |

如果用户最近 7 天只有健身房有氧，没有有效力量训练：

```json
{
  "status": "cardio_only_session",
  "fitness_balance": null,
  "reason": "This gym session was cardio-focused and contributes to Activity Balance instead of Fitness Balance."
}
```

### 9.4 有效力量动作判断

一个动作只有满足以下条件，才进入 Fitness Balance：

```text
valid_strength_exercise = true 当且仅当：
1. event_type = muscle_strengthening
2. exercise_confidence >= 0.70
3. repetition_pattern_score >= 0.50
4. active_repetition_duration_seconds >= 30
5. major_muscle_groups 非空
```

不计入的情况：

1. 坐上器械但没有训练。
2. 调节器械。
3. 只试动两下。
4. 模型低置信度识别。
5. 路过器械被误判。

### 9.5 exercise_unit

由于当前无法稳定识别重量，组数也不稳定，因此不用：

```text
sets × reps × weight
```

改用 exercise_unit 作为训练剂量代理：

```text
if detected_sets_confident:
    exercise_unit = detected_sets
else:
    exercise_unit = active_repetition_duration_seconds / 45

exercise_unit = clamp(exercise_unit, 0, 4)
```

### 9.6 总公式

```text
FitnessBalance_base =
0.15 × G + 0.40 × S + 0.20 × E + 0.25 × C

FitnessBalance_final =
clamp(FitnessBalance_base + RecoverySpacingAdjustment, 0, 100)
```

其中：

| 符号 | 名称 | 权重 | 作用 |
|---|---|---:|---|
| G | Guideline Reference Score | 15% | 成人肌肉强化活动指南参考 |
| S | Preference-Adjusted Structure Score | 40% | 肌群分布是否符合用户偏好 |
| E | Effective Training Evidence Score | 20% | 识别到的训练是否真实有效 |
| C | Strength Consistency & Dose Score | 25% | 最近 7 天训练持续性和剂量 |
| RecoverySpacingAdjustment | 恢复间隔修正项 | -5 到 +3 | 同一肌群训练间隔是否过密 |

### 9.7 G：指南参考分

主要肌群集合：

```text
MAJOR_MUSCLE_GROUPS = {
  legs,
  hips,
  back,
  abdomen,
  chest,
  shoulders,
  arms
}
```

公式：

```text
valid_strength_days_7d = 最近 7 天有效力量训练天数
covered_official_major_groups_7d = 最近 7 天覆盖到的主要肌群集合

frequency_ratio = min(valid_strength_days_7d / 2, 1)
coverage_ratio = count(covered_official_major_groups_7d) / 7

G = 100 × min(frequency_ratio, coverage_ratio)
```

### 9.8 S：偏好调整结构分

默认目标肌群分布：

```json
{
  "legs": 0.16,
  "hips": 0.14,
  "back": 0.16,
  "abdomen": 0.14,
  "chest": 0.14,
  "shoulders": 0.14,
  "arms": 0.12
}
```

用户只问一个偏好问题：

```text
有没有不想明显增肌的部位？
```

可选项：

1. 手臂
2. 腿部
3. 胸部
4. 肩部
5. 没有特别避开的部位

避开增肌部位调整：

```text
avoid_bulk_group_target_weight =
max(default_weight × 0.4, 0.05)
```

动作到肌群曝光：

```text
muscle_exposure_m =
Σ exercise_unit_i × muscle_weight_i,m × exercise_confidence_i
```

实际肌群占比：

```text
actual_share_m =
muscle_exposure_m / total_muscle_exposure
```

S 公式：

```text
S = 100 × [1 - 0.5 × Σ |actual_share_m - target_share_m|]
```

### 9.9 E：有效训练证据分

单个动作证据分：

```text
exercise_evidence_i =
0.35 × action_confidence
+ 0.25 × repetition_pattern_score
+ 0.25 × unit_sufficiency_score
+ 0.15 × user_or_plan_support
```

字段说明：

```text
action_confidence = exercise_confidence
repetition_pattern_score = 1.0 明确重复动作节律，0.5 疑似重复，0 无证据
unit_sufficiency_score = min(exercise_unit / 2, 1)
user_or_plan_support = 1.0 用户确认，0.7 在当天计划中，0 无确认且不在计划
```

汇总公式：

```text
E =
100 × Σ(exercise_evidence_i × exercise_unit_i) / Σ(exercise_unit_i)
```

### 9.10 C：训练持续性与剂量分

```text
day_consistency = min(valid_strength_days_7d / 4, 1)
unit_dose = min(total_exercise_units_7d / 8, 1)

C = 100 × (
  0.6 × day_consistency
  + 0.4 × unit_dose
)
```

解释：

1. 4 天是最近 7 天内较高频但仍合理的力量训练频率上限。
2. 8 units 约等于 4 次训练 × 每次至少 2 个有效训练单位。
3. C 用于解决用户持续训练但结构分不再变化的问题。

### 9.11 Recovery Spacing Adjustment

同一肌群当天有效训练判断：

```text
muscle_exposure_day_m >= 1.0 unit
```

相邻训练间隔评分：

```text
if rest_gap_hours >= 48:
    spacing_pair_score = 1.0
elif 24 <= rest_gap_hours < 48:
    spacing_pair_score = 0.7
else:
    spacing_pair_score = 0.3
```

恢复间隔分：

```text
R = 100 × weighted_average(spacing_pair_score, weight = muscle_exposure_pair)
```

修正项：

```text
if R is null:
    RecoverySpacingAdjustment = 0
elif R >= 85:
    RecoverySpacingAdjustment = +3
elif 70 <= R < 85:
    RecoverySpacingAdjustment = 0
elif 50 <= R < 70:
    RecoverySpacingAdjustment = -2
else:
    RecoverySpacingAdjustment = -5
```

### 9.12 输出状态

| status | 含义 |
|---|---|
| active | 存在有效力量训练，输出 Fitness Balance |
| insufficient_strength_data | 最近 7 天无有效力量训练或肌群曝光为 0 |
| low_confidence | 有疑似力量训练但置信度不足 |
| cardio_only_session | 有健身房 session，但只有有氧 |
| not_in_overall_balance | 不参与当前 Overall Balance 聚合，不按 0 分处理 |

---

## 10. Fitness Balance 公式修正窗口

### 10.1 为什么需要修正窗口

Fitness Balance 是 Fitness Agent 里最容易影响用户信任的指标。它不仅输出一个分数，还会解释用户“练得是否均衡”“哪里被忽略”“下次该练什么”。

因此，公式不能只看数学上是否能算通，还要看：

1. 分数是否符合用户直觉。
2. 扣分原因是否能解释。
3. 下一次训练建议是否和扣分原因一致。
4. 有氧、低置信度、轻量试动是否被正确排除。
5. 不同用户偏好下是否会给出违背目标的建议。

### 10.2 修正窗口定义

建议设置一个明确的公式修正窗口：

```text
阶段名称：Fitness Balance v4 Formula Review Window
建议时长：1-2 周
Owner：产品经理
参与方：算法、研发、数据标注、教练顾问/健身知识 reviewer
输出物：v4_final 公式说明、字段表、样本测试结果、解释文案、边界状态
```

在修正窗口结束前，研发可以做原型和测试器，但不应将该公式作为正式线上口径。

### 10.3 修正窗口内要 review 的内容

| 模块 | 需要 review 的问题 |
|---|---|
| G 指南参考分 | 2 天力量训练、7 大肌群覆盖是否符合产品目标 |
| S 结构分 | 默认目标肌群分布是否合理，避开增肌部位如何降权 |
| E 证据分 | 置信度、重复节律、训练剂量、计划/用户支持的权重是否合理 |
| C 持续性与剂量分 | 4 天、8 units 的上限是否符合 MVP 用户训练频率 |
| Recovery 修正 | 同一肌群 24h/48h 间隔规则是否过严或过松 |
| exercise_unit | 45 秒 = 1 unit 的代理值是否符合真实训练样本 |
| 有氧处理 | 健身房有氧是否完全转入 Activity Balance |
| 输出状态 | low_confidence、cardio_only、insufficient_strength_data 是否互斥清楚 |
| 文案解释 | 每种扣分原因用户是否能理解 |

### 10.4 必须准备的测试样本

公式 review 不能只用理想样本。至少要准备以下样本：

| 样本类型 | 目的 |
|---|---|
| 只做有氧 | 验证不更新 Fitness Balance，进入 Activity Balance |
| 只练一个肌群 | 验证结构分是否下降，解释是否清楚 |
| 连续两天练同一肌群 | 验证 Recovery 是否扣分合理 |
| 一周 2 次全身力量 | 验证 G 是否合理上升 |
| 一周 4 次但偏科 | 验证 C 上升但 S 不盲目上升 |
| 低置信度动作 | 验证不应强行计算 |
| 试动/调器械 | 验证 active 但不计入有效力量训练 |
| 用户选择不想手臂明显增肌 | 验证 arms target 降权后建议是否变化 |
| 核心动作缺失 | 验证 abdomen 缺失是否会导致不合理扣分 |
| 上肢孤立动作较多 | 验证 arms/shoulders/chest 的归因是否稳定 |

### 10.5 修正窗口验收标准

公式冻结前需要满足：

1. 至少 20 个真实或半真实 session 样本跑通。
2. 每个样本都能输出分数、组件分、原因解释和建议。
3. PM review 后，80% 以上样本的分数方向符合直觉。
4. 每个低分样本都能解释“为什么低”。
5. 每个建议都能追溯到 G/S/E/C/Recovery 的具体原因。
6. 有氧 session 不误伤 Fitness Balance。
7. low_confidence 不被当作 0 分惩罚用户。
8. 动作到肌群映射表有明确 owner 和版本号。

### 10.6 公式冻结条件

修正窗口结束后，输出：

```text
Fitness Balance formula_version = v4_final
```

冻结内容包括：

1. 公式权重。
2. 7 大肌群集合。
3. 默认 target profile。
4. avoid_bulk_group 调整规则。
5. exercise_unit 计算方式。
6. 有效力量动作门槛。
7. Recovery 修正规则。
8. 输出状态枚举。
9. 用户侧解释文案模板。

冻结后，如需调整，应进入下一版本：

```text
v4_final → v4.1 / v5_candidate
```

不要在线上静默修改公式，否则历史分数会失去可解释性。

---

## 11. 模型评测体系

### 11.1 不要只看单次输出

当前最大的产品风险是“看起来某个视频识别得不错”，但没有可量化评测。

需要建立 daily eval 表，持续比较：

```text
模型输出 vs 人工标准答案
```

### 11.2 建议评测指标

| 指标 | 说明 |
|---|---|
| 是否健身识别准确率 | 判断是否为健身场景 |
| 有氧/力量分类准确率 | 判断训练类型 |
| 器械识别准确率 | 当前器械/场景是否正确 |
| 动作识别准确率 | final_action 是否正确 |
| 时间段 IoU | 预测片段与标准片段重叠程度 |
| 边界误差 | start/end 与人工标注差异 |
| 组数误差 | set count 偏差 |
| 次数误差 | rep count 偏差 |
| 低置信度召回 | 不确定片段是否正确要求用户确认 |
| 用户确认率 | 用户是否愿意完成轻反馈 |

### 11.3 标注分层

不要一开始全部做精标注。

| 标注层级 | 内容 | 用途 |
|---|---|---|
| 轻标注 | 是否在健身、动作大类、开始结束时间 | 大规模数据管理 |
| 中标注 | 具体动作、器械、训练阶段、是否完成 | 模型主要评测 |
| 精标注 | 组数、次数、每组起止、动作质量 | 小规模评测样本 |

---

## 12. 数据采集要求

### 12.1 每条素材必须绑定

1. 员工/用户 ID
2. 录制日期
3. 训练计划 ID
4. 动作清单
5. 视频/图片素材路径
6. IMU 数据路径
7. 人工标注状态
8. 模型输出版本
9. 提示词版本
10. 是否进入评测集

### 12.2 每个核心动作采集目标

每个核心动作至少采集：

```text
5-10 条不同员工素材
```

每条素材尽量包含：

1. 完整一组或多组动作。
2. 组间休息。
3. 真实转场。
4. 器械调整。
5. 训练计划绑定。

### 12.3 数据命名建议

```text
fitness_{date}_{user_id}_{plan_id}_{session_id}_{source_type}
```

示例：

```text
fitness_20260624_u003_planA_s01_video.mp4
fitness_20260624_u003_planA_s01_imu.txt
fitness_20260624_u003_planA_s01_label.csv
```

---

## 13. 产品需求拆解

### 13.1 P0

1. 训练 session 识别与创建。
2. 训练 timeline 草稿生成。
3. 动作候选、器械候选、肌群候选。
4. 用户轻反馈确认。
5. 训练报告生成。
6. 数据回流到评测表。

### 13.2 P1

1. IMU 特征摘要接入 timeline 融合。
2. Fitness Balance v4_candidate 计算与测试器。
3. 训练周报。
4. 下一次训练建议。
5. 低置信度片段主动询问。

### 13.3 P2

1. 健身房器械记忆。
2. 个性化计划调整。
3. 更细肌群拆分。
4. Training Load / Volume / Progressive Overload。
5. 更强 Coach Insight。

---

## 14. 研发输入输出建议

### 14.1 模型输入格式

```json
{
  "session": {
    "session_id": "fitness_20260624_u003_s01",
    "start_time": "2026-06-24T19:00:00+08:00",
    "end_time": "2026-06-24T20:05:00+08:00"
  },
  "plan": {
    "plan_id": "planA",
    "planned_actions": ["machine_chest_press", "cable_lat_pulldown", "machine_leg_press"]
  },
  "visual_candidates": [],
  "imu_summary": {},
  "known_action_candidates": []
}
```

### 14.2 模型输出格式

```json
{
  "timeline": [
    {
      "start_s": 51.09,
      "end_s": 69.90,
      "final_action": "machine_leg_press",
      "equipment": "fixed_machine",
      "set_index": 1,
      "rep_count": 10,
      "confidence": "medium",
      "major_muscle_groups": ["legs", "hips"],
      "evidence": {
        "visual": "画面中出现腿举器械和周期性蹬伸",
        "imu": "torso_flexion_extension，存在周期性",
        "plan": "当天计划包含腿举"
      },
      "needs_user_confirmation": true
    }
  ]
}
```

### 14.3 Fitness Balance 输入

```json
{
  "event_type": "muscle_strengthening",
  "exercise": "machine_leg_press",
  "exercise_confidence": 0.86,
  "repetition_pattern_score": 1.0,
  "active_repetition_duration_seconds": 90,
  "detected_sets": 3,
  "detected_sets_confident": true,
  "major_muscle_groups": ["legs", "hips"],
  "user_or_plan_support": 0.7
}
```

---

## 15. 风险清单

| 风险 | 影响 | 建议 |
|---|---|---|
| 数据量不足 | 模型优化不可持续 | 先建素材管理表和核心动作采集计划 |
| 没有标准答案 | 无法判断模型是否进步 | 建 daily eval |
| 第一人称遮挡/相似动作 | 动作识别不稳定 | 结合计划、IMU、器械上下文和用户确认 |
| 过早承诺组数/次数 | 用户预期过高 | 只展示“约 N 次”或要求确认 |
| 动作库覆盖与 Balance 肌群不一致 | Balance 解释失真 | 补核心动作，统一肌群 taxonomy |
| 有氧与 Fitness Balance 混算 | 指标解释混乱 | 有氧归 Activity Balance |
| 用户纠错成本过高 | 反馈链路断掉 | 只做轻反馈，不要求完整标注 |
| 飞书资料未同步到本地 | 接手信息不完整 | 统一导出关键飞书文档到本地或知识库 |
| Fitness Balance 未经过修正窗口 | 分数和建议可能误导用户 | 设置 v4_candidate review window，冻结后再进入正式实现 |

---

## 16. 近期推进计划

### Week 1：对齐与补齐基础

1. 确认 Fitness Agent MVP 范围。
2. 补齐飞书外链资料。
3. 建素材管理表。
4. 从动作库筛出第一批 15-20 个核心动作。
5. 定义标注规范和 daily eval 表。

### Week 2：数据闭环

1. 每个核心动作采集 5-10 条员工素材。
2. 每条素材绑定 plan_id 和动作清单。
3. 建立轻标注/中标注流程。
4. 跑第一版模型输出 vs 人工标准答案。

### Week 3：产品闭环

1. 设计训练后 timeline 确认 UI。
2. 设计训练报告结构。
3. 定义低置信度片段处理。
4. 接入 IMU 摘要作为辅助信息。

### Week 4：指标闭环

1. 将 Fitness Balance v4_candidate 转成研发字段表。
2. 对员工样本跑 Balance 测试。
3. 校验分数是否符合直觉。
4. 补充分数解释文案和异常状态文案。
5. 完成公式修正窗口并冻结 v4_final。

---

## 17. PM 待决策项

1. Fitness Agent 首页是否确认以“上一次训练报告”为首屏。
2. MVP 是否只覆盖健身房场景，不覆盖居家训练。
3. 第一批核心动作清单最终选哪些。
4. 是否在 MVP 中展示具体次数，还是展示“约 N 次/待确认”。
5. 用户轻反馈入口是在训练报告页、timeline 页，还是对话中。
6. Fitness Balance 是否进入 Overall Balance；如果暂不进入，状态为 not_in_overall_balance。
7. 核心/腹部动作如何补齐。
8. 动作到肌群权重表由谁审核，是否需要教练确认。
9. 员工素材采集由谁 owner，数据命名和上传规范由谁验收。
10. Fitness Balance v4_candidate 的修正窗口排期、参与人和冻结标准。

---

## 18. 需要补充校验的飞书资料

本地文档引用了以下飞书资料，但当前命令行侧访问返回 404，需要用有权限账号打开后补充：

1. 健身 MVP 功能规划
2. Activity 和 Fitness 产品结构图
3. 训练计划数据库
4. 健身计划排班表
5. 健身数据录制规范
6. 教练访谈问卷与总结
7. Fitness Balance 指标计算说明文档线上版

建议处理方式：

1. 将关键飞书文档导出为 Markdown/PDF 放入交接文件夹。
2. 或在飞书中给当前接手人开权限，并确认链接不是失效链接。
3. 外链内容补齐后，更新本文档的“公式修正窗口”“待决策项”和“研发字段表”。

---

## 19. PM 接手后的第一句话

Fitness Agent 现在最缺的不是更多想法，而是稳定闭环。

接手后应优先把团队拉回到三件事：

1. 数据能不能稳定采集和管理。
2. 模型输出能不能被标准答案量化评估。
3. 用户能不能用很低成本确认训练记录，并让确认结果回流。

这三件事跑稳后，再谈计划生成、个性化建议、长期趋势和更完整的 Coach 能力。
