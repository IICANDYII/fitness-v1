# Relty Diet Balance / Goal / Baseline 新版 PRD

## 0. 文档状态

本 PRD 替代旧版 `Diet Balance Baseline 新版 PRD` 的产品定义。

旧版核心是：

```text
把 Diet Balance 从固定绝对公式升级为个性化 baseline 判断。
```

新版核心改为：

```text
Relty 用低摩擦记录获取长上下文；
软件端对凌乱上下文进行分级和编排；
让用户在主界面一眼看清今日总体概括和子 agent 入口；
再随着菜单层层深入，逐步看到更高密度的信息。
```

---

## 1. 产品定位

Relty 在硬件佩戴舒适性上不一定优于智能手表或其他通用设备，因此必须给用户一个足够强的使用理由。

这个理由不是“又一个分数”，而是：

```text
Relty 可以用低摩擦方式持续记录用户真实生活中的长上下文，
再把这些杂乱上下文压缩成用户能快速理解的状态反馈。
```

硬件端负责获取：

```text
饮食记录；
餐次结构；
能量摄入；
营养结构；
运动 / 活动上下文；
睡眠 / 恢复上下文；
身体状态上下文；
用户轻量 goal；
用户长期 baseline。
```

软件端负责过滤：

```text
哪些上下文今天重要；
哪些上下文只作为解释；
哪些上下文会影响分数；
哪些上下文应该延后展示；
哪些上下文应该交给子 agent 深挖。
```

软件端的首要目标不是制造更多 insight，而是完成信息编排：

```text
主界面：今日总体概括 + 子 agent 入口；
子 agent 主界面：对应领域概况 + 少量核心信息；
下钻菜单：更细颗粒度的数据、原因、趋势和证据。
```

用户不应该感觉自己在看一堆传感器和营养字段。

用户应该感觉：

```text
Relty 懂我今天为什么是这个状态。
```

---

## 2. 核心产品指标

新版 Relty 首页不应该围绕一堆并列指标展开，而应该优先突出两个核心指标：

```text
Balance
Goal
```

### 2.1 Balance 是什么

Balance 回答：

```text
你今天的身体 / 饮食 / 恢复状态是否平衡？
```

在 Diet 模块中，Diet Balance 回答：

```text
你今天的饮食是否接近健康、稳定、可解释的饮食状态？
```

Balance 的特点：

```text
就是一个分数；
更客观；
更像身体状态判断；
更依赖健康参考、baseline、数据质量和上下文；
不完全服务于用户当前 goal。
```

产品层不要把 Balance 自作主张改写成状态标签、情绪判断或另一套解释系统。

```text
Balance = Balance score
```

它可以有解释入口，但它本身就是分数。

### 2.2 Goal 是什么

Goal 回答：

```text
你今天是否在向你自己选的方向推进？
```

Goal 是用户在主界面用很低摩擦方式定义的方向，例如：

```text
Get slimmer
Get stronger
Keep fit
```

Goal 的特点：

```text
更主观；
更像用户当前意图；
用于给不同子 agent 设定默认解释方向；
颗粒度待定义；
不应该把过多细节摊在首页。
```

### 2.3 Balance / Goal 的张力

Balance 和 Goal 不能被合成一个总分。

它们并列存在时，二者之间可能产生有价值的张力。

典型例子：

```text
Goal 完成度很高，但 Balance 很低。
```

用户感受到的不是简单的“坏分数”，而是：

```text
Damn，连 AI 都知道我今天累坏了。
```

这类张力是 Relty 的重要产品资产。

它让用户感觉系统不是只会鼓励，也不是只会批评，而是在理解：

```text
你做到了什么；
你为此付出了什么；
你的身体是否承受了代价；
这种代价是否值得被看见。
```

但这种张力是否要被显式做成一个独立的 `Tension Insight` 模块，仍然待定。

---

## 3. 首页信息架构

首页应只展示少量高层信号，避免把长上下文直接摊开。

建议首页核心结构：

```text
Today
├─ Balance
├─ Goal
└─ 子 agent 入口
```

可选待定：

```text
Tension Insight / 今日解释句
```

它可以存在，但不是 v0 的必选项。

### 3.1 Balance 展示

首页展示一个主 Balance。

Diet 模块可以贡献 Diet Balance，但首页不一定直接暴露所有子分。

首页 Balance 就表达 Balance 分数。

```text
Balance: 82
```

如果需要解释，应该通过点击、展开或子 agent 入口进入，而不是把 Balance 改造成另一个概况标签。

### 3.2 Goal 展示

Goal 的首页颗粒度待定义。

可能形态包括：

```text
Goal: Get stronger
Goal completion: 78
```

或：

```text
Goal: Get stronger
Key driver: protein / training / recovery
```

不要在首页展示过多 goal 子指标。

原因：

```text
goal 指标越多，用户越像在看任务清单；
任务清单越强，Goal 和 Balance 的张力越弱；
张力越弱，Relty 越像普通 habit tracker。
```

### 3.3 Tension Insight

Tension Insight 待定。

它可能是一句轻量解释：

```text
You pushed hard today, but your balance is running low.
```

或：

```text
Your diet was not perfect, but it supported your slimming goal today.
```

或：

```text
Your balance is high, but today did not move your strength goal much.
```

这一区域的作用是把两个指标之间的关系说出来。

但 v0 不强制要求首页必须有这个模块。当前更高优先级是：

```text
信息分级；
信息编排；
主界面清晰；
子 agent 入口明确；
下钻信息密度递进。
```

---

## 4. Goal 颗粒度设计

Goal 的颗粒度分为三层。

### 4.1 L1: 主界面 Goal

主界面 Goal 必须低摩擦，但具体颗粒度待定义。

v0 建议三个选项：

```text
Get slimmer
Get stronger
Keep fit
```

可选扩展：

```text
Sleep better
Eat cleaner
Boost energy
```

但 v0 不建议超过 3 个主选项。

原因：

```text
主界面的 Goal 是产品叙事方向，不是详细计划；
选项越多，用户越需要思考；
思考越重，低摩擦优势越弱。
```

注意：这不是最终决策。Goal 可以不止是“一个方向 + 一个完成度”，但首页不能展示过多 goal 子指标。

### 4.2 L2: 子 Agent 预设 Goal

主 Goal 会下发给子 agent，成为默认解释方向。

例如：

```text
Get slimmer
→ Diet Agent 更关注能量平衡、饱腹感、蛋白质、晚间摄入；
→ Workout Agent 更关注消耗、恢复代价；
→ Recovery Agent 更关注疲劳和睡眠风险。
```

```text
Get stronger
→ Diet Agent 更关注蛋白质、总能量不足、训练后补给；
→ Workout Agent 更关注力量训练刺激；
→ Recovery Agent 更关注恢复是否跟得上。
```

```text
Keep fit
→ Diet Agent 更关注结构均衡和长期稳定；
→ Workout Agent 更关注活动连续性；
→ Recovery Agent 更关注整体状态。
```

L2 可以有更多内部指标，但默认不在首页展开。

### 4.3 L3: 子页面细化 Goal

用户进入子页面后，可以看到更细的 goal 解释。

Diet 子页面示例：

```text
Get slimmer
├─ Energy target alignment
├─ Protein support
├─ Fiber / satiety support
└─ Late heavy meal risk
```

Workout 子页面示例：

```text
Get stronger
├─ Training stimulus
├─ Progressive overload
├─ Recovery support
└─ Fueling sufficiency
```

L3 的原则：

```text
可以解释，不要抢首页；
可以服务子 agent，不要变成一堆主指标；
可以支持 drill-down，不要破坏 Balance / Goal 的二元张力。
```

---

## 5. Balance 颗粒度设计

Balance 也分三层。

### 5.1 L1: 主 Balance

首页只展示一个主 Balance。

它应该综合：

```text
Diet Balance；
Recovery / fatigue context；
Sleep context；
Activity load；
Illness / abnormal context；
Data quality。
```

v0 如果只有 Diet 模块成熟，也可以先用 Diet Balance 作为主 Balance 的一个主要来源，但文案上不要把主 Balance 永久等同于 Diet Balance。

### 5.2 L2: 模块 Balance

子页面展示模块级 Balance。

例如：

```text
Diet Balance
Recovery Balance
Workout Balance
Sleep Balance
```

模块 Balance 可以有独立解释，但不能在首页并列展示太多。

### 5.3 L3: 组件解释

Diet Balance 组件可以包括：

```text
Food pattern
Macro fit
Nutrient adequacy
Energy balance
Meal rhythm
Baseline progress
Data confidence
```

这些是解释层，不是首页核心层。

---

## 6. Baseline 的新定位

Baseline 不再只是“Diet Balance 的个性化分数补丁”。

新版中，Baseline 是连接长上下文和轻量展示的压缩层。

它回答：

```text
这个用户自己的常态是什么？
今天和自己的常态相比，有什么变化？
这些变化是健康改善、目标推进、异常代价，还是只是噪声？
```

Baseline 的用途分三类。

### 6.1 用于 Balance

Baseline 帮助 Balance 判断：

```text
今天是否偏离用户常态；
偏离是否朝健康参考方向；
偏离是否可能是异常上下文；
当前数据是否足够可信。
```

### 6.2 用于 Goal

Baseline 帮助 Goal 判断：

```text
今天是否比用户自己的通常状态更接近 goal；
这种接近是否可持续；
是否以牺牲 Balance 为代价。
```

### 6.3 用于 Tension Insight

Baseline 可能帮助解释 Balance / Goal 张力：

```text
你今天确实比平时更接近减脂目标；
但你的能量不足和恢复压力也比平时更明显。
```

或：

```text
你今天 Balance 很高；
但对增肌 goal 来说，蛋白质和训练刺激都没有明显推进。
```

此能力待定，不作为 v0 必做模块。

---

## 7. Diet Balance v0 的位置

Diet Balance 仍然是 Diet Agent 的核心模块指标。

它回答：

```text
今天的饮食是否平衡？
```

Diet Balance v0 建议保留健康参考锚点：

```text
HEI / food pattern；
AMDR；
RDA / AI；
Energy target；
Meal rhythm；
Data confidence。
```

Baseline 可以作为 Diet Balance 的个性化层，但必须保留两个事实：

```text
personal-normal: 和用户自己的常态相比如何；
health-reference: 和健康参考相比如何。
```

新版允许 baseline progress 作为分数加成或 overflow 保存，但产品解释必须避免把坏习惯正常化。

例子：

```text
如果用户长期饮食很差，今天略有改善：
Goal progress 可以承认“比你平时更好”；
Balance 仍应显示“还不够平衡”。
```

---

## 8. Goal / Balance 张力矩阵

Goal / Balance 张力是一个重要产品假设，但是否在 v0 首页显式展示待定。

可作为后续设计评估的四类状态：

| Balance | Goal | 用户感受 | 产品解释方向 |
|---|---|---|---|
| high | high | 顺利、被肯定 | 你今天既推进目标，也照顾了身体状态 |
| low | high | 被理解、被看见 | 你完成了目标，但代价偏高 |
| high | low | 被温和提醒 | 你状态不错，但今天没有明显推进目标 |
| low | low | 被接住而不是被批评 | 今天整体吃力，先恢复秩序 |

最有产品情绪价值的是：

```text
low Balance + high Goal
```

这不是失败态，而是 Relty 最能体现“懂你”的场景。

但当前 PRD 不要求必须输出独立的 `Tension Insight`。

---

## 9. Illness / Abnormal Context

如果上游已经判断用户处于生病、异常疲劳、输液、恢复期等上下文，Relty 不应该机械给出“恢复很好”或“饮食很好”的结论。

原则：

```text
异常上下文不进入正常 baseline 学习；
异常上下文可以改变解释；
异常上下文不应该凭空提高 Balance；
异常上下文可以降低 score confidence；
异常上下文应该触发更温和的 presentation。
```

示例：

```text
Goal: completed
Balance: 68
Context: abnormal / low confidence
```

这能避免类似：

```text
用户躺在病床上打吊瓶，但 recovery = 99
```

这种明显违背常识的产品体验。

---

## 10. 数据与输出结构草案

### 10.1 首页输出

```json
{
  "today": {
    "balance": {
      "score": 68
    },
    "goal": {
      "primary_goal": "get_stronger",
      "completion": 86,
      "state": "strong_progress"
    }
  }
}
```

可选扩展：

```json
{
  "tension": {
    "type": "high_goal_low_balance",
    "message": "You pushed hard today, but your balance is running low."
  }
}
```

### 10.2 Diet 子页面输出

```json
{
  "diet": {
    "diet_balance": 72,
    "goal_support": {
      "primary_goal": "get_slimmer",
      "score": 81,
      "drivers": ["energy_alignment", "protein_support", "fiber_support"]
    },
    "baseline_context": {
      "compared_to_your_normal": "better",
      "compared_to_health_reference": "still_below_reference",
      "confidence": "medium"
    }
  }
}
```

### 10.3 Baseline records

Baseline records 应存储每日已计算过的组件分数，避免每次都从原始饮食数据重算。

建议字段：

```json
{
  "record_date": "2026-06-16",
  "component_scores_100": {
    "hei_2020_available": 64,
    "amdr_fit": 82,
    "rda_ai_adequacy": 71,
    "meal_timing": 100,
    "kcal_balance": 76
  },
  "component_score_source": "stored_from_daily_calculation",
  "daily_context": {
    "illness_context": false,
    "complete_day_record": true,
    "confidence": "medium"
  }
}
```

如果历史 records 没有这些组件分数，计算器可以 fallback 重算。

但产品层定义应该是：

```text
baseline records 优先存储可直接聚合的每日组件分数；
重算只是兼容机制，不是主路径。
```

---

## 11. v0 范围

### 11.1 v0 必须做

```text
主界面只保留 Balance / Goal 两个核心指标；
Goal 保持低摩擦，具体颗粒度待定义；
子 agent 使用主 Goal 作为默认解释方向；
Diet 子页面展示 Diet Balance、Goal Support、Baseline Context；
Baseline records 存储每日组件分数和中位数；
明确主界面、子 agent 主界面、下钻菜单的信息层级；
异常上下文进入解释和 confidence，不进入正常 baseline 学习。
```

### 11.2 v0 不做

```text
不把所有 goal 子指标放到首页；
不把 Balance 和 Goal 合成一个总分；
不把 Balance 改造成状态标签或情绪判断；
不让 baseline 直接把坏习惯正常化；
不在首页展示完整营养报表；
不做复杂自定义 goal builder；
不做医疗诊断；
不把 illness day 当作正常恢复高分。
```

---

## 12. 关键产品约束

1. Balance 和 Goal 必须保持并列，不能互相吞并。
2. Balance 就是分数；解释可以下钻，但不要替换 Balance 本体。
3. Goal 颗粒度待定义，但首页不能展示过多 goal 子指标。
4. 子页面可以展开 goal 解释，但不能让首页变成任务清单。
5. Baseline 是长上下文压缩层，不只是分数修正器。
6. Tension Insight 待定，不是 v0 强制模块。
7. 异常上下文必须改变解释，否则产品会出现明显违背常识的高分。
8. 所有复杂指标都应服务于信息分级和编排，而不是让用户读懂系统。

---

## 13. 成功标准

v0 成功不是用户觉得“分数很准”。

v0 成功是用户在关键场景下觉得：

```text
它知道我今天做到了什么；
它也知道我为此付出了什么；
它没有用一堆指标压我；
它让我在主界面一眼看清今日总体概括；
它让我知道该进入哪个子 agent 看更多。
```

尤其是当：

```text
Goal high + Balance low
```

用户不一定需要立刻看到一条 Tension Insight，但产品结构必须保留未来表达这种张力的空间。
