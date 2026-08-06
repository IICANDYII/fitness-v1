# Activity 主页设计方案

> 基于 `activity_algorithm_spec.md` 的最终 Activity 指标算法，以及现有 Fitness 页面 UI 风格。

## 1. 页面定位

Activity 是全天活动总览页，不是 Fitness 页面换皮。它回答的问题是：

> 今天/本周我的全天活动行为是否接近健康指南？短板是活动量、力量训练、久坐，还是分布不均？

Fitness 作为 Activity 下的一个活动板块存在：用户点击 Activity 主页里的 `Fitness` 卡片后，进入原 Fitness 详情页。

## 2. 信息架构

### 顶部区域

沿用原 Fitness 页面：

- 左侧：头像 + streak/fire 数字。
- 中间：日期切换胶囊 `TODAY`。
- 右侧：设备电量 + 设备状态 icon。
- 标题：`Activity`
- 副标题：`Daily Movement Overview`

### 第一屏核心双卡

#### 左卡：Activity Health

替代原 `Fitness Balance`。

展示：

- 总分：`82 /100`
- 状态：`Good`
- 一句解释：`Strong movement day. Sitting is slightly high.`
- 底部：小型 7-day trend 曲线。

对应算法：

```text
S_activity =
0.45 * S_MVPA
+ 0.20 * S_Strength
+ 0.20 * S_Sedentary
+ 0.15 * S_Consistency
```

交互：

- 点击卡片进入 Activity Health 解释页。
- info icon 解释“这是基于 MVPA、Strength、Sedentary、Consistency 的提示性分数，不是医疗诊断”。

#### 右卡：MVPA Progress

替代原 `Goal Progress`。

展示：

- 环形进度：`96 / 150 min`
- 状态：`On Track`
- 副文案：`Moderate + vigorous minutes this week`

设计理由：

- MVPA 是证据最强的 Activity 子项。
- AHA LE8 / WHO / PAG 都能支撑 150 分钟目标。

## 3. Today's Overview 小卡

沿用原来四张渐变小卡，但内容改为全天活动核心组成：

| 卡片 | 示例值 | 颜色 | 含义 |
|---|---:|---|---|
| Steps | 8.4k | 绿色 | 全天基础活动 |
| Active | 42 min | 蓝色 | 今日中高强度活动分钟 |
| Sitting | 7.6 h | 橙色 | 今日久坐时间 |
| Fitness | 38 min | 紫/粉色 | 今日力量/健身活动入口 |

`Fitness` 卡片可点击，进入原 Fitness 页面。

## 4. 行动提醒条

原页面是 `3 sets need action confirmation`，Activity 主页改成：

```text
2 activity events need confirmation
```

或：

```text
Long sitting block detected · Move for 2 min
```

原则：

- 有低置信度活动识别时，优先提醒确认。
- 无识别问题但久坐过长时，提醒打断久坐。

## 5. Activity Health Components 大卡

替代原 `Muscle Group Coverage (Last 7 Days)`。

标题：

```text
Activity Health Components (Last 7 Days)
```

内容四行：

| 组件 | 示例 | 状态 | 算法来源 |
|---|---|---|---|
| MVPA | 96 / 150 min | ↑ | `S_MVPA` |
| Strength | 1 / 2 days | ↓ | `S_Strength` |
| Sitting | 7.6 h / day | → | `S_Sedentary` |
| Consistency | 4 / 5 active days | ↑ | `S_Consistency` |

视觉：

- 左侧用 4 条进度条。
- 右侧显示数值和趋势箭头。
- 色彩沿用绿色/蓝色/橙色/粉色，但状态评价以绿色为主，避免制造焦虑。

## 6. Activity Mix / 板块入口

新增一张横向 session 卡：

```text
Activity Mix
Walking 32m · Running 10m · Fitness 38m · Commute 45m
```

下面放 4 个 pill：

- Walking
- Running
- Fitness
- Commute

点击 `Fitness` 进入 Fitness 详情页；点击其他活动进入对应 activity type 详情。

## 7. Daily Timeline

沿用原 Training Timeline，但改为全天时间轴：

- Sedentary：灰色
- Walking：绿色
- Cardio：蓝色
- Fitness：粉色
- Commute：橙色
- Sleep/Unknown：浅灰

标题：

```text
Daily Activity Timeline
```

横轴：

```text
00:00    12:00    24:00
```

## 8. 页面线框

```text
┌────────────────────────────────────┐
│ avatar 🔥181       TODAY       65% │
│                                    │
│ Activity                           │
│ Daily Movement Overview            │
│                                    │
│ ┌────────────────┐ ┌─────────────┐ │
│ │ Activity Health│ │ MVPA        │ │
│ │ 82 /100 Good   │ │ 96/150 min  │ │
│ │ Sitting high   │ │ On Track    │ │
│ └────────────────┘ └─────────────┘ │
│                                    │
│ Today's Overview                   │
│ [Steps] [Active] [Sitting] [Fitness]│
│                                    │
│ 🔔 2 activity events need confirm  │
│                                    │
│ Activity Health Components         │
│ MVPA        96/150 min      ↑      │
│ Strength    1/2 days        ↓      │
│ Sitting     7.6h/day        →      │
│ Consistency 4/5 days        ↑      │
│                                    │
│ Activity Mix                       │
│ Walking · Running · Fitness · Car  │
│                                    │
│ Daily Activity Timeline            │
│ 00:00 ━━━━╋━━━━╋━━━━╋━━━━ 24:00   │
│                                    │
│ bottom nav                         │
└────────────────────────────────────┘
```

## 9. 文案建议

### 总分解释

```text
Good
You are on track for weekly movement. Add one more strength day and break long sitting blocks.
```

### MVPA

```text
96 / 150 min
Moderate + vigorous activity this week
```

### Strength

```text
1 / 2 days
One more strength session recommended this week
```

### Sitting

```text
7.6 h/day
Try to break long sitting blocks
```

### Fitness 入口

```text
Fitness
38 min
Push dominant · View details
```

## 10. 不建议放在 Activity 主页首屏的内容

- 肌群热力人体图：放到 Fitness 详情页，不放 Activity 主页。
- 训练组数：这是 Fitness 子域信息，不是全天 Activity 主指标。
- 卡路里大数字：可辅助展示，但不应成为主卡。
- WHOOP 式 strain：没有心率时不适合做主指标，也容易把 Activity 引向竞技训练语境。

## 11. 最终页面主张

Activity 主页要像“全天行为仪表盘”，Fitness 页面才像“训练详情页”。

首页优先展示：

1. Activity Health 总信号；
2. MVPA 周进度；
3. 今日基础活动、活跃分钟、久坐、Fitness 入口；
4. 7 天健康组件；
5. 全天 timeline。

这样既延续了原 Fitness UI 的视觉语言，又把算法依据从“肌群均衡”升级到了 WHO / AHA / 24h movement guidelines 支持的全天活动框架。
