# Relty 指标计算框架



## 文档信息

---

# 文档目的

本文档用于定义 Relty 中各类 Daily Activity Agent 的指标计算方式，包括：

1. 每个 Agent 是否可以生成 Balance；

2. 如果可以生成 Balance，其科学依据、输入数据、计算方式和边界是什么；

3. 如果不能生成 Balance，应当输出何种解释层、趋势层或风险提示；

4. 每个 Agent 后续如何接入 Finish，即用户自定义目标的完成情况；

5. App 端如何把复杂、多源、碎片化的日常数据转译成少量、可信、可解释的生活状态。

Relty 的硬件价值在于低摩擦、连续、上下文丰富的生活记录。

但低摩擦记录会天然产生大量碎片化、多来源、多 Agent 的数据。如果 App 直接展示这些数据，用户会面对信息过载、隐私压力和理解成本。

因此，Relty 的软件目标不是展示“用户今天发生了什么的全部数据”，而是完成“低摩擦理解”：

```Plain Text
复杂生活数据
→ 结构化识别
→ 科学边界判断
→ 少量可信指标
→ 可解释的 Daily Brief
→ 用户可执行的下一步
```

---

# 核心指标体系

Relty 当前指标体系分为两层：

```Plain Text
Relty Metrics
├── Balance
└── Finish
```

---

## 2\.1 Balance

Balance 是 Relty 对用户真实生活状态的客观解释层。

它不是一个简单的百分制总分，也不是把所有行为强行加权后得到的 0–100 总分。更准确地说，Balance 是一套让重要生活状态“向上浮现”的机制。

当某个 Agent 存在足够明确的科学依据、权威指南或可复现计算标准时，该 Agent 可以生成一个具体的 Balance 指标。

当某个 Agent 没有足够明确的绝对标准时\-\-\-\-正在试图拟定指标

```Plain Text
从健康、生活方式或行为质量角度看，
用户当前行为本身是否接近一个相对客观、可解释、可复现的标准；
以及哪些状态值得被优先浮现给用户。
```

Balance 的特点：

Balance 可以是：

```Plain Text
Diet Balance = 饮食结构与权威膳食指南的接近程度
Activity Balance = 运动行为与成人身体活动指南的接近程度
```

Balance 不应该是：

```Plain Text
用户今天心情不错，所以 Balance 高
用户今天工作很久，所以 Balance 高
用户今天社交很多，所以 Balance 高
用户今天训练很累，所以 Balance 高
用户今天穿搭很好看，所以 Balance 高
```

这些判断要么依赖用户目标，要么依赖主观偏好，要么缺乏统一科学标准，因此不能作为 Balance 主体。



---

## 2\.2 Finish

Finish 是一个相对值，用于衡量用户在当前目标周期内，对自己设定目标的完成情况。

Finish 不代表绝对健康质量，而代表：

```Plain Text
用户今天在自己设定的目标上推进了多少。
```

Finish 的核心不是：

```Plain Text
今天做得健不健康。
```

而是：

```Plain Text
用户是否在自己设定的目标周期里持续推进；
如果周期目标已经完成，今天是否仍然产生了额外正向行为。
```

因此，Finish 不是一个简单百分比，也不一定严格封顶在 100。

更准确地说，Finish 是一个周期累计完成分：

$Finish = Base\ Completion + Daily\ Boost$

其中：

$Base\ Completion = 周期目标的基础完成度$

$Daily\ Boost = 今天新增行为带来的额外奖励$

不同 Agent 的目标周期可能不同，因此 Finish 不一定每周归零更新。

例如：

```Plain Text
Diet Agent 的目标周期可能是 7 天；
Training Agent 的目标周期可能是 1 周或 4 周；
Focus Agent 的目标周期可能是当天、每周或一个项目周期。
```

具体周期应由 Agent 类型和用户目标共同决定。

---

### 2\.2\.1 Finish 的前置流程：Learning Period

每个 Agent 在首次开启后，都需要经历一段 Learning Period。

Learning Period 的目的不是改变 Balance 的客观标准，而是学习用户当前真实的生活 baseline。

完整流程为：

```Plain Text
Agent activation
→ Learning Period
→ Baseline generation
→ Gap analysis
→ Goal suggestion
→ User confirmation
→ Finish tracking
```

以 Diet Agent 为例，开启后的前 7 天可以作为饮食学习期。

系统在此期间学习用户的真实饮食习惯，例如：

```Plain Text
每天吃几餐
平均热量摄入
常见食物类型
蔬菜 / 水果 / 蛋白质 / 全谷物摄入情况
added sugar / sodium / refined grains 情况
外卖 / 餐厅频率
晚间进食情况
饮食记录完整度
```

学习期结束后，系统会生成用户当前的饮食 baseline，并将其与 Diet Balance、Energy Fit、Diet Timing 等指标进行对比，找出主要 gap。

例如：

```Plain Text
如果系统发现用户蔬菜摄入不足，可以推荐：
“是否将每周至少 5 天有蔬菜摄入设为目标？”

如果系统发现用户 added sugar 偏高，可以推荐：
“是否将每周含糖饮料不超过 2 次设为目标？”

如果系统发现用户长期能量摄入高于个人需求区间，可以推荐：
“是否将每日能量摄入调整到个人目标区间内设为目标？”
```

因此，Finish 的目标不应完全由用户自由创建。

更合理的方式是：

```Plain Text
系统基于学习期识别出的 gap 推荐可计算的 goal templates；
用户可以确认、跳过或微调目标参数；
目标确认后，系统进入正式 Finish 周期。
```

也就是说：

```Plain Text
Balance / Pattern 负责发现问题；
Finish 负责把问题转换成用户确认后的阶段性目标完成度。
```

---

### 2\.2\.2 Finish 的组成

Finish 由两部分组成：

```Plain Text
1. Base Completion
周期目标的基础完成度。

2. Daily Boost
今天新增行为带来的额外奖励。
```

其中：

$Base\ Completion = 当前周期内已经完成的目标比例$

$Daily\ Boost = 今天新增完成量对目标的额外推进$

这两个部分共同解决一个问题：

```Plain Text
用户既要看到周期目标的累计进度，也要看到今天新增行为对当前状态的贡献。
```

---

### 2\.2\.3 当日目标与周期性目标

Finish 同时支持两类目标：

```Plain Text
1. 当日目标；
2. 周期性目标。
```

---

#### 当日目标

当日目标指用户只需要在当天完成的目标。

例如：

```Plain Text
今天学习 2 小时；
今天步行 8000 步；
今天不喝含糖饮料；
今天记录三餐。
```

当日目标的完成情况由当天行为直接决定。

如果用户超额完成，可以产生额外奖励，但需要控制奖励幅度，避免鼓励无意义过量完成。

---

#### 周期性目标

周期性目标指用户在一个周期内逐步完成的目标。

例如：

```Plain Text
本周健身 3 次；
本周慢跑 2 次；
本周外卖不超过 2 次；
本月完成 12 次训练。
```

周期性目标不一定每天都完成，但每天的新增行为都可能推进周期进度。

当周期目标尚未完成时：

$Finish = Base\ Completion + Daily\ Completion$

当周期目标已经完成时：

$Finish = 100 + Extra\ Bonus$

这里的 Extra Bonus 应该是有限奖励，不应该鼓励用户为了刷分而过度完成。

---

### 2\.2\.4 Finish 总公式

Finish 的整体计算可以写为：

$Finish_t =
\sum_{a \in A_t} W_a
\sum_{g \in G_a}
\left[
100\omega_g \min \left( \frac{C_{g,t}}{Q_g}, 1 \right)
+
100\omega_g \kappa_g D_{g,t}
\right]$

其中：

$100\omega_g \min \left( \frac{C_{g,t}}{Q_g}, 1 \right)$

是 Base Completion，用来计算周期内已经沉淀的基础完成度。

$100\omega_g \kappa_g D_{g,t}$

是 Daily Boost，用来计算今天新增行为带来的额外奖励。

---

### 2\.2\.5 Daily Boost 计算方式

Daily Boost 根据目标类型不同，计算方式不同。

$D_{g,t} =
\begin{cases}
\dfrac{TodayUnits_{g,t}}{Q_g}, & period\ goal \
\dfrac{\max(TodayUnits_{g,t} - Q_g, 0)}{Q_g}, & daily\ goal
\end{cases}$

---

#### 周期性目标的 Daily Boost

对于周期性目标：

$D_{g,t} = \frac{TodayUnits_{g,t}}{Q_g}$

例如：

```Plain Text
本周目标是健身 3 次，今天完成 1 次。
```

则：

$D_{g,t} = \frac{1}{3}$

这表示今天的行为推进了周期目标的三分之一。

---

#### 当日目标的 Daily Boost

对于当日目标，Daily Boost 只计算超额完成部分：

$D_{g,t} =
\frac{\max(TodayUnits_{g,t} - Q_g, 0)}{Q_g}$

例如：

```Plain Text
今日目标是学习 2 小时，今日实际学习 3 小时。
```

则：

$D_{g,t} =
\frac{\max(3 - 2, 0)}{2}$

$D_{g,t} = 0.5$

这表示用户在完成当日目标后，又额外完成了 50% 的目标量。

---



### 2\.2\.6 符号说明

其中：

```Plain Text
A_t 表示今天参与 Finish 计算的 Agent 集合。
例如，今天 Diet、Training、Focus 都有 active goals，那么 A_t 就包含这三个 Agent。

G_a 表示某个 Agent 下正在追踪的目标集合。
例如，Diet Agent 下可能包含“减少外卖”“提高蔬菜摄入”“控制晚间高热量饮食”等目标。

W_a 是 Agent 权重，用来表示不同 Agent 在当前用户目标体系中的重要性。

ω_g 是 goal 权重，用来表示同一个 Agent 下不同目标的重要性。

Q_g 是某个 goal 的目标量。
例如，本周健身 3 次，则 Q_g = 3。

C_{g,t} 是当前周期内截至今天的累计完成量。
例如，本周目标是健身 3 次，目前已经完成 2 次，则 C_{g,t} = 2。

TodayUnits_{g,t} 是今天新增完成量。
例如，今天新增一次健身，则 TodayUnits_{g,t} = 1。

D_{g,t} 是今天新增行为相对于目标量的比例。

κ_g 是 Daily Boost 系数，用来控制今天新增行为带来的额外奖励幅度。
```



---

### 2\.2\.7 权重逻辑

Finish 中存在两层权重：

$W_a = Agent\ Weight$

$\omega_g = Goal\ Weight$

Agent 权重用于表示不同 Agent 在当前用户目标体系中的重要性。

例如：

```Plain Text
用户当前重点是训练和饮食，Training Agent 与 Diet Agent 的权重可以更高。
```

Goal 权重用于表示同一个 Agent 下不同目标的重要性。

例如 Diet Agent 下可能有：

```Plain Text
减少外卖；
提高蔬菜摄入；
控制晚间高热量饮食；
记录三餐。
```

这些目标不一定同等重要，因此可以分配不同 goal 权重。

需要注意：

```Plain Text
权重不应由系统随意决定。
权重应来自用户目标设置、产品默认目标模板，或后续个性化推荐机制。
```

---

### 2\.2\.8 Finish 的产品解释

用户侧不需要看到完整公式。

用户看到的应该是：

```Plain Text
你本周的训练目标已经完成 67%。
今天新增一次力量训练，让本周进度继续推进。
```

或者：

```Plain Text
你的本周饮食目标已经完成。
今天仍然保持了较好的饮食行为，因此获得额外推进。
```

也就是说，Finish 的用户解释应当围绕：

```Plain Text
1. 当前周期完成了多少；
2. 今天新增了什么；
3. 是否已经完成目标；
4. 是否有额外奖励；
5. 下一步该做什么。
```

---

### 2\.2\.9 Finish 的边界

Finish 可以上浮，但必须避免无脑鼓励过量完成。

例如：

```Plain Text
运动目标完成后继续运动，可以给少量 bonus，但不能鼓励用户为了刷分过度训练；
饮食记录目标完成后继续记录，可以给少量 bonus，但不能鼓励用户过度控制饮食；
学习目标完成后继续学习，可以给少量 bonus，但不能鼓励用户牺牲休息时间无限学习。
```

因此 Daily Boost 需要有边际递减或上限机制。

推荐原则：

$Base\ Completion \leq 100$

$Daily\ Boost \leq Daily\ Boost_{max}$

$Finish \geq 100
\Rightarrow
目标已完成，并存在额外推进$

这意味着：

```Plain Text
Finish 可以超过 100，但超过 100 的部分只代表额外推进，不代表越高越健康。
```

---

### 2\.2\.10 Finish 与 Balance 的关系

Finish 和 Balance 必须分开。

$Finish = 用户目标完成情况$

$Balance = 客观状态解释 / 科学标准判断 / 状态浮现机制$

例如：

```Plain Text
用户完成了“本周健身 5 次”的目标，Training Finish 可以很高。
但如果训练过量、休息不足，这不代表整体生活状态更健康。
```

再例如：

```Plain Text
用户完成了“今天少吃甜食”的目标，Diet Finish 可以很高。
但如果整体饮食结构不符合 HEI-2020，Diet Balance 不一定高。
```

因此：

$Finish \neq Balance$

Finish 负责回答：

```Plain Text
你有没有完成自己设定的目标？
```

Balance 负责回答：

```Plain Text
这个行为本身是否接近科学或健康标准？
```

两者可以同时出现在 Daily Brief 中，但不能互相替代。

---

# Agent 架构

![Image](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NjJlMWE3NDIxODVlNzMwM2Y0MWQ3MjAzOWU2ODg3MjZfODhhOTI4NDA2ZDA1ODE2YmVkZmQ4ZTMxNmNiNWFlZWJfSUQ6NzY0OTYyMDEzMDE4Nzg1NzEyOV8xNzgxMTU0MzYwOjE3ODEyNDA3NjBfVjM)

```Plain Text
Balance
└── Daily Activity
    ├── 运动
    │   └── 步行，慢跑
    ├── 训练
    │   └── 健身
    ├── 专注
    │   └── 工作，学习
    ├── 饮食
    │   └── 摄入，用餐时间
    ├── 放松
    │   └── 喝酒，社交，娱乐活动
    ├── 休息
    │   └── 纯休息
    └── 通勤
        └── 用于交通的时间
```

不同agent 的核心价值不是“把一天拆得很细”，而是判断：

```Plain Text
用户今天的行为结构中，哪些内容接近健康、稳定、可持续的生活方式；
哪些内容偏离了科学标准或近期基线；
哪些内容需要被优先浮现给用户。
```

但不是所有agent都能生成 Balance。

---

# Agent 输出类型

每个 Agent 的输出分为四类：

```Plain Text
1. Balance
2. Flag
3. Insight
4. Finish
```

---

## 4\.1 Balance

Balance 是正式的客观指标。

只有当某个领域存在明确、可引用、可复现的科学标准时，才能生成 Balance。

示例：

```Plain Text
Diet Balance
Activity Balance
```

---

## 4\.2 Finish

Finish 是用户目标完成度。

Finish 后续单独展开，本阶段只在每个 Agent 中预留接口。

## 4\.3 Flag

Flag 是风险提示。

当某个行为有明确风险证据，但没有足够统一的打分公式时，输出 Flag。

示例：

```Plain Text
late_meal_flag
long_sedentary_block_flag
alcohol_risk_flag
```

Flag 不应直接扣主分，除非有明确、公开、可复现的扣分标准。

---

## 4\.4 Insight

Insight 是趋势洞察。

当某个行为可以被记录和解释，但不能判断绝对好坏时，输出 Insight。

示例：

```Plain Text
Your commute time was longer than usual this week.
You had less unstructured downtime than your recent baseline.
Your study blocks were more fragmented today.
```

Insight 不应被伪装成健康分。

---

# Agent 总览表

---

# Agent 指标定义

---

## 6\.1 Diet Agent

### 6\.1\.1 Diet Agent 定义

Diet Agent 负责识别、记录和解释用户的饮食行为，包括：

```Plain Text
食物摄入
饮食结构
营养组成
热量摄入
用餐时间
饮食目标完成情况
```

Diet Agent 的核心任务不是简单记录“用户吃了什么”，而是把用户真实吃下去的一组食物转化为可计算、可解释、可对比的饮食质量指标。

---

### 6\.1\.2 Diet Finish

### 6\.1\.2 Diet Finish

Diet Finish 衡量用户在当前饮食目标周期内，对自己确认过的饮食目标完成了多少。

Diet Finish 不评价用户“吃得健不健康”。

饮食健康质量由 Diet Balance 负责，Diet Balance 使用 HEI\-2020 计算。

Diet Finish 评价的是：

```Plain Text
用户是否在当前饮食目标周期内，持续推进自己确认过的饮食改善目标。
```

因此：

```Plain Text
Diet Finish = 用户饮食目标完成度
Diet Balance = 用户饮食健康质量
```

两者必须分开。

更准确地说，Diet Finish 不是让用户一开始自由设置目标，而是基于 Diet Agent 的学习期结果进行引导：

```Plain Text
Learning Period
→ Baseline Generation
→ Gap Analysis
→ Goal Recommendation
→ User Pace Selection
→ Diet Finish Tracking
```

也就是说，Diet Finish 的目标来源不是用户凭空填写，而是系统基于用户真实饮食习惯和健康标准之间的 gap，推荐可计算、可执行、可追踪的目标模板。

---

#### a\. Diet Finish 的前置流程：Learning Period

Diet Agent 在首次开启后，需要先进入 Learning Period。

建议 v0 使用：

```Plain Text
Diet Learning Period = 7 days
```

学习期的目的不是给用户打正式 Finish 分数，而是学习用户当前真实的饮食 baseline。

在学习期内，系统主要观察：

```Plain Text
每天吃几餐
平均每日能量摄入
常见食物类型
蔬菜摄入频率
水果摄入频率
蛋白质来源稳定性
全谷物摄入情况
精制谷物摄入情况
added sugar 摄入情况
含糖饮料 / 甜品频率
外卖 / 餐厅频率
晚间进食情况
late heavy meal 情况
记录完整度与用户修正情况
```

学习期结束后，Diet Agent 会生成用户的饮食 baseline。

示例：

```Plain Text
过去 7 天，用户平均每日摄入约 2300 kcal；
蔬菜摄入达标天数为 2 / 7；
含糖饮料出现 4 次；
late heavy meal 出现 3 次；
碳水供能比例平均为 72%；
精制谷物摄入频率偏高；
蛋白质来源相对稳定。
```

这个 baseline 是用户当前真实习惯，不是健康目标。

---

#### b\. Baseline 与健康标准之间的 Gap

学习期结束后，系统将用户 baseline 与标准参考进行对比，识别 gap。

Gap 的来源主要包括四类：

```Plain Text
1. Diet Balance / HEI-2020 gap
2. Energy Fit gap
3. Macronutrient Range gap
4. Diet Timing gap
```

---

##### Diet Balance / HEI\-2020 gap

HEI\-2020 用于判断用户饮食结构和健康饮食模式之间的差距。

例如：

```Plain Text
蔬菜 component 偏低
水果 component 偏低
全谷物 component 偏低
refined grains 偏高
added sugars 偏高
sodium 偏高
saturated fats 偏高
```

这些 gap 可以被转化为具体目标。

例如：

```Plain Text
蔬菜摄入偏低
→ 推荐目标：每周至少 5 天有蔬菜摄入

added sugars 偏高
→ 推荐目标：每周含糖饮料 / 甜品不超过 X 次

refined grains 偏高
→ 推荐目标：每周至少 X 次用全谷物替代精制主食
```

---

##### Energy Fit gap

Energy Fit 用于判断用户能量摄入是否接近个人需求。

它需要读取用户初始化信息：

```Plain Text
年龄
sex
身高
体重
physical activity level
主要目标
```

如果系统发现：

```Plain Text
用户平均能量摄入长期高于个人需求区间
```

则可以推荐：

```Plain Text
是否将“每日能量摄入调整到个人目标区间内”设为目标？
```

不建议写成：

```Plain Text
要不要降低摄入总量？
```

更安全和产品化的表达是：

```Plain Text
要不要把每日摄入逐步调整到更适合你的目标区间？
```

原因是 Diet Finish 不能鼓励极端少吃，也不能把“吃得越少”当成完成目标。

---

##### Macronutrient Range gap

Macronutrient Range gap 用于判断宏量营养素比例是否长期偏离参考范围。

例如：

```Plain Text
碳水供能比例长期高于参考范围
脂肪供能比例长期高于参考范围
蛋白质摄入长期低于目标范围
```

以碳水为例，系统可以判断：

```Plain Text
用户过去 7 天平均碳水供能比例高于参考范围上限。
```

但产品侧不应简单说：

```Plain Text
你的碳水太高，要不要少吃碳水？
```

更合适的表达是：

```Plain Text
你最近的碳水比例偏高，主要来自精制主食和含糖饮料。要不要先从减少这些来源开始？
```

原因是：

```Plain Text
碳水不是天然负面指标；
全谷物、水果、豆类等也属于碳水来源；
真正需要优先处理的，通常是 refined grains、added sugars 和整体能量过量。
```

因此，碳水相关 gap 应优先拆成更可执行的目标：

```Plain Text
减少含糖饮料
减少甜品频率
减少精制主食频率
增加全谷物替代
让每日碳水比例回到参考范围
```

---

##### Diet Timing gap

Diet Timing gap 用于判断用户是否存在较稳定的晚间进食问题。

例如：

```Plain Text
late heavy meal 频率偏高
last caloric intake 经常接近休息窗口
eating window 明显后移
```

这些 gap 不进入 Diet Balance，但可以进入 Diet Finish 的目标建议。

例如：

```Plain Text
每周 late heavy meal 不超过 1 次
每周至少 5 天最后一次有热量摄入距离休息窗口足够远
```

---

#### c\. Gap 的计算方式

对于每个可追踪指标，系统先得到用户 baseline：

```Plain Text
baseline_value
```

然后得到该指标对应的参考标准：

```Plain Text
reference_target
```

reference\_target 可以是：

```Plain Text
最低目标值
最高限制值
目标区间
目标频率
```

不同类型 gap 的计算方式不同。

---

##### 正向不足型 gap

适用于：

```Plain Text
蔬菜摄入不足
水果摄入不足
全谷物摄入不足
蛋白质来源不足
```

计算方式：

```Plain Text
gap_severity = max((target_value - baseline_value) / target_value, 0)
```

例如：

```Plain Text
目标：每周至少 5 天有蔬菜摄入
baseline：过去 7 天只有 2 天

gap_severity = (5 - 2) / 5 = 0.6
```

表示该 gap 的严重程度为 60%。

---

##### 限制超标型 gap

适用于：

```Plain Text
含糖饮料过多
甜品过多
外卖过多
late heavy meal 过多
```

计算方式：

```Plain Text
gap_severity = max((baseline_value - limit_value) / tolerance_value, 0)
gap_severity = min(gap_severity, 1)
```

其中：

```Plain Text
baseline_value = 学习期观察到的当前频率
limit_value = 目标上限
tolerance_value = 用来计算超标程度的缓冲范围
```

例如：

```Plain Text
目标：每周含糖饮料不超过 2 次
baseline：过去 7 天含糖饮料 5 次
tolerance：3 次

gap_severity = (5 - 2) / 3 = 1
```

表示该 gap 已达到较高优先级。

---

##### 区间偏离型 gap

适用于：

```Plain Text
每日能量摄入目标区间
碳水供能比例目标区间
蛋白质摄入目标区间
脂肪供能比例目标区间
```

如果 baseline 落在目标区间内：

```Plain Text
gap_severity = 0
```

如果 baseline 高于上限：

```Plain Text
gap_severity = (baseline_value - upper_bound) / tolerance_value
gap_severity = min(max(gap_severity, 0), 1)
```

如果 baseline 低于下限：

```Plain Text
gap_severity = (lower_bound - baseline_value) / tolerance_value
gap_severity = min(max(gap_severity, 0), 1)
```

例如：

```Plain Text
碳水供能比例参考范围：45%–65%
baseline：72%
tolerance：7%

gap_severity = (72% - 65%) / 7% = 1
```

表示该 gap 达到较高优先级。

---

#### d\. Gap 优先级排序

学习期结束后，系统不应该把所有 gap 都推给用户。

应当只选择：

```Plain Text
1–3 个最重要、最确定、最可执行的 gap
```

推荐优先级计算方式：

```Plain Text
goal_priority =
gap_severity
× health_relevance
× confidence
× feasibility
× user_relevance
```

其中：

```Plain Text
gap_severity = 偏离程度
health_relevance = 该 gap 与健康饮食模式的相关性
confidence = 系统识别置信度
feasibility = 用户是否容易开始执行
user_relevance = 是否和用户当前目标相关
```

例如，系统发现以下 gap：

```Plain Text
蔬菜摄入不足
含糖饮料偏多
全谷物不足
晚间大餐偏多
碳水比例偏高
```

系统不应一次推荐 5 个目标，而应选出优先级最高的 1–3 个。

例如：

```Plain Text
1. 含糖饮料偏多
2. 蔬菜摄入不足
3. late heavy meal 偏多
```

然后生成可选择的目标建议。

---

#### e\. Gap 到 Goal Template 的映射

系统需要把 gap 转换成可计算的 goal template。

示例映射：

```Plain Text
gap：蔬菜摄入不足
goal template：每周至少 X 天有蔬菜摄入

gap：水果摄入不足
goal template：每周至少 X 天有水果摄入

gap：全谷物不足
goal template：每周至少 X 次选择全谷物主食

gap：added sugars 偏高
goal template：每周含糖饮料 / 甜品不超过 X 次

gap：refined grains 偏高
goal template：每周精制主食不超过 X 次，或每周 X 次使用全谷物替代

gap：平均能量摄入高于个人目标区间
goal template：每周至少 X 天能量摄入进入个人目标区间

gap：碳水供能比例高于参考范围
goal template：每周至少 X 天碳水比例进入参考范围，或优先减少精制碳水来源

gap：late heavy meal 频率偏高
goal template：每周 late heavy meal 不超过 X 次
```

这里的关键是：

```Plain Text
系统发现 gap；
系统生成目标建议；
用户选择是否接受；
用户选择改善节奏；
用户确认后才进入 Finish 周期。
```

---

#### f\. 用户选择改善节奏

每个推荐目标都应提供至少两种改善节奏：

```Plain Text
1. Standard Path
2. Gradual Path
```

---

##### Standard Path

Standard Path 表示：

```Plain Text
本周期直接以健康参考标准作为目标。
```

例如：

```Plain Text
系统发现：过去 7 天含糖饮料 5 次
参考目标：每周不超过 2 次

Standard Path：
本周目标 = 含糖饮料不超过 2 次
```

再例如：

```Plain Text
系统发现：过去 7 天蔬菜摄入只有 2 天
参考目标：每周至少 5 天

Standard Path：
本周目标 = 至少 5 天有蔬菜摄入
```

Standard Path 适合：

```Plain Text
用户动力强
目标难度适中
gap 不极端
目标不会产生健康风险
```

---

##### Gradual Path

Gradual Path 表示：

```Plain Text
不要求用户立刻达到健康参考标准，而是从当前 baseline 出发，分多个周期逐步接近标准。
```

对于需要增加的目标：

```Plain Text
cycle_target_k = baseline_value + ramp_ratio_k × (reference_target - baseline_value)
```

对于需要减少的目标：

```Plain Text
cycle_target_k = baseline_value - ramp_ratio_k × (baseline_value - reference_target)
```

其中：

```Plain Text
k = 第 k 个目标周期
ramp_ratio_k = 当前周期推进比例
```

可以设置：

```Plain Text
cycle 1: ramp_ratio = 0.33
cycle 2: ramp_ratio = 0.66
cycle 3: ramp_ratio = 1.00
```

也就是说，系统用 3 个周期把用户从 baseline 推向 reference target。

---

##### Gradual Path 示例：蔬菜摄入不足

学习期发现：

```Plain Text
baseline：每周 2 天有蔬菜摄入
reference target：每周 5 天有蔬菜摄入
```

Standard Path：

```Plain Text
第 1 个周期目标：每周 5 天有蔬菜摄入
```

Gradual Path：

```Plain Text
第 1 个周期目标：每周 3 天有蔬菜摄入
第 2 个周期目标：每周 4 天有蔬菜摄入
第 3 个周期目标：每周 5 天有蔬菜摄入
```

---

##### Gradual Path 示例：含糖饮料偏多

学习期发现：

```Plain Text
baseline：每周 5 次含糖饮料
reference target：每周不超过 2 次
```

Standard Path：

```Plain Text
第 1 个周期目标：每周含糖饮料不超过 2 次
```

Gradual Path：

```Plain Text
第 1 个周期目标：每周含糖饮料不超过 4 次
第 2 个周期目标：每周含糖饮料不超过 3 次
第 3 个周期目标：每周含糖饮料不超过 2 次
```

---

##### Gradual Path 示例：碳水比例偏高

学习期发现：

```Plain Text
baseline：平均碳水供能比例 72%
reference range：45%–65%
```

系统不应直接推荐“少吃碳水”，而应优先定位来源：

```Plain Text
精制谷物偏高
含糖饮料偏高
甜品频率偏高
蛋白质 / 蔬菜占比不足
```

如果用户选择直接控制总碳水比例：

Standard Path：

```Plain Text
第 1 个周期目标：碳水供能比例进入 45%–65% 参考范围
```

Gradual Path：

```Plain Text
第 1 个周期目标：平均碳水供能比例 ≤ 70%
第 2 个周期目标：平均碳水供能比例 ≤ 68%
第 3 个周期目标：平均碳水供能比例 ≤ 65%
```

但产品默认更推荐把这个目标拆成更行为化的目标：

```Plain Text
每周含糖饮料不超过 X 次
每周 X 次用全谷物替代精制主食
每天至少 1 餐有明确蛋白质来源
每周至少 X 天有蔬菜摄入
```

这样比直接要求用户“降低碳水”更安全，也更可执行。

---

#### g\. 用户确认后的 Active Goal

用户选择推荐目标和改善节奏后，系统生成 active diet goal。

Active Goal 应包含：

```Plain Text
goal template
goal metric
baseline value
reference target
selected path
current cycle target
goal weight
boost coefficient
safety rule
```

示例：

```JSON
{
  "goal_id": "diet_goal_001",
  "agent": "diet",
  "user_id": "user_001",
  "status": "active",
  "created_from": {
    "source": "learning_period_gap",
    "gap_id": "gap_sugary_drink_high"
  },
  "goal_template": {
    "template_id": "sugary_drink_budget_weekly",
    "goal_type": "limit_budget",
    "metric_id": "sugary_drink_count",
    "display_name": "每周含糖饮料不超过 X 次"
  },
  "baseline": {
    "baseline_value": 5,
    "unit": "count_per_7_days",
    "learning_period_days": 7
  },
  "reference_target": {
    "max_allowed": 2,
    "unit": "count_per_7_days"
  },
  "selected_path": {
    "path_type": "gradual",
    "total_ramp_cycles": 3,
    "current_cycle_index": 1,
    "current_cycle_target": {
      "max_allowed": 4,
      "unit": "count_per_7_days"
    },
    "target_schedule": [
      {
        "cycle_index": 1,
        "max_allowed": 4
      },
      {
        "cycle_index": 2,
        "max_allowed": 3
      },
      {
        "cycle_index": 3,
        "max_allowed": 2
      }
    ]
  },
  "cycle": {
    "cycle_type": "rolling_7_days",
    "start_date": "2026-06-10",
    "end_date": "2026-06-16"
  },
  "weight": 0.35,
  "boost_coef": 0.1,
  "safety_rules": [
    "not_extreme_restriction",
    "do_not_reward_under_eating",
    "requires_user_confirmation"
  ]
}
```

---

#### h\. Learning Period 输出 JSON

Diet Agent 学习期结束后，需要输出 baseline、gap、推荐目标和节奏选项。

示例：

```JSON
{
  "agent": "diet",
  "user_id": "user_001",
  "status": "learning_completed",
  "learning_period": {
    "start_date": "2026-06-03",
    "end_date": "2026-06-09",
    "days_required": 7,
    "days_completed": 7
  },
  "baseline": {
    "avg_daily_energy_kcal": 2350,
    "vegetable_presence_days": 2,
    "fruit_presence_days": 1,
    "protein_presence_days": 5,
    "carb_energy_ratio_avg": 0.72,
    "refined_grains_frequency": 6,
    "sugary_drink_count": 5,
    "takeout_meals": 6,
    "late_heavy_meal_count": 3,
    "recording_complete_days": 5
  },
  "gaps": [
    {
      "gap_id": "gap_carb_ratio_high",
      "source_metric": "carb_energy_ratio_avg",
      "baseline_value": 0.72,
      "reference_range": {
        "lower_bound": 0.45,
        "upper_bound": 0.65
      },
      "gap_type": "range_high",
      "gap_severity": 1.0,
      "confidence": 0.76,
      "recommended_action_type": "reduce_or_rebalance"
    },
    {
      "gap_id": "gap_sugary_drink_high",
      "source_metric": "sugary_drink_count",
      "baseline_value": 5,
      "reference_target": {
        "max_allowed": 2
      },
      "gap_type": "limit_high",
      "gap_severity": 1.0,
      "confidence": 0.84,
      "recommended_action_type": "reduce_frequency"
    },
    {
      "gap_id": "gap_vegetable_low",
      "source_metric": "vegetable_presence_days",
      "baseline_value": 2,
      "reference_target": {
        "target_count": 5
      },
      "gap_type": "positive_low",
      "gap_severity": 0.6,
      "confidence": 0.82,
      "recommended_action_type": "increase_frequency"
    }
  ],
  "recommended_goals": [
    {
      "recommendation_id": "rec_001",
      "reason_gap_id": "gap_sugary_drink_high",
      "template_id": "sugary_drink_budget_weekly",
      "display_prompt": "过去 7 天里，你的含糖饮料频率偏高。要不要把减少含糖饮料设为本周目标？",
      "goal_options": [
        {
          "path_type": "standard",
          "label": "直接按推荐标准执行",
          "target": {
            "max_allowed": 2,
            "unit": "count_per_7_days"
          }
        },
        {
          "path_type": "gradual",
          "label": "按自己的节奏逐步减少",
          "target_schedule": [
            {
              "cycle_index": 1,
              "max_allowed": 4
            },
            {
              "cycle_index": 2,
              "max_allowed": 3
            },
            {
              "cycle_index": 3,
              "max_allowed": 2
            }
          ]
        }
      ],
      "editable_parameters": [
        "path_type",
        "cycle_type",
        "weight"
      ],
      "requires_user_confirmation": true
    },
    {
      "recommendation_id": "rec_002",
      "reason_gap_id": "gap_carb_ratio_high",
      "template_id": "carb_ratio_rebalance_weekly",
      "display_prompt": "过去 7 天里，你的碳水比例偏高，主要可能来自精制主食和含糖饮料。要不要先做一个逐步调整目标？",
      "goal_options": [
        {
          "path_type": "standard",
          "label": "直接进入参考范围",
          "target": {
            "upper_bound": 0.65,
            "unit": "energy_ratio"
          }
        },
        {
          "path_type": "gradual",
          "label": "逐步靠近参考范围",
          "target_schedule": [
            {
              "cycle_index": 1,
              "upper_bound": 0.70
            },
            {
              "cycle_index": 2,
              "upper_bound": 0.68
            },
            {
              "cycle_index": 3,
              "upper_bound": 0.65
            }
          ]
        }
      ],
      "safer_alternative_goals": [
        "sugary_drink_budget_weekly",
        "refined_grains_reduce_weekly",
        "whole_grain_replacement_weekly"
      ],
      "requires_user_confirmation": true
    }
  ],
  "finish_available": false
}
```

说明：

```Plain Text
learning_period 输出的是目标建议，不是正式 Finish 分数。
只有用户确认至少一个 goal 后，Diet Finish 才开始计算。
```

---

#### i\. Diet Finish 计算方式

用户确认目标后，Diet Finish 才开始计算。

Diet Finish 由两部分组成：

```Plain Text
Base Completion
Daily Boost
```

其中：

```Plain Text
Base Completion = 当前周期内已经完成的目标比例
Daily Boost = 今天新增行为对目标的额外推进
```

Diet Finish 总公式：

```Plain Text
DietFinish_t = BaseCompletion_t + DailyBoost_t
```

Base Completion：

```Plain Text
BaseCompletion_t =
100 × sum(weight_j × goalCompletion_j_t)
```

Daily Boost：

```Plain Text
DailyBoost_t =
min(
  100 × sum(weight_j × boostCoef_j × dailyProgress_j_t),
  DailyBoostMax
)
```

最终：

```Plain Text
DietFinish_t =
BaseCompletion_t + DailyBoost_t
```

其中：

```Plain Text
G = 当前 active diet goals 集合
weight_j = 第 j 个目标的权重
goalCompletion_j_t = 第 j 个目标当前周期内的完成度
boostCoef_j = 第 j 个目标的 Daily Boost 系数
dailyProgress_j_t = 今天新增行为对该目标的推进比例
DailyBoostMax = Diet Agent 单日额外奖励上限
```

边界：

```Plain Text
BaseCompletion_t <= 100
DailyBoost_t <= DailyBoostMax
DietFinish_t 可以超过 100
超过 100 只表示额外推进，不代表越高越健康
```

---

#### j\. Goal Completion 的计算方式

不同 goal type 使用不同计算方式。

---

##### 正向增加型目标

适用于：

```Plain Text
增加蔬菜摄入
增加水果摄入
增加全谷物摄入
增加蛋白质来源稳定性
```

计算方式：

```Plain Text
goalCompletion_j_t =
min(successCount_j_t / targetCount_j, 1)
```

例如：

```Plain Text
目标：本周至少 5 天有蔬菜摄入
当前完成：3 天

goalCompletion = min(3 / 5, 1) = 0.6
```

---

##### 限制预算型目标

适用于：

```Plain Text
含糖饮料不超过 X 次
甜品不超过 X 次
外卖不超过 X 次
late heavy meal 不超过 X 次
```

计算方式：

```Plain Text
elapsedRatio_t = elapsedDays_t / totalDays
```

如果当前使用量没有超过上限：

```Plain Text
complianceScore_j_t = 1
```

如果当前使用量超过上限：

```Plain Text
complianceScore_j_t =
max(1 - (usedCount_j_t - maxAllowed_j) / tolerance_j, 0)
```

最终：

```Plain Text
goalCompletion_j_t =
elapsedRatio_t × complianceScore_j_t
```

这样可以避免限制类目标在周期第一天就显示 100，也可以避免把“越少越好”作为唯一导向。

---

##### 区间型目标

适用于：

```Plain Text
能量摄入进入目标区间
碳水比例进入参考范围
蛋白质摄入进入目标区间
脂肪比例进入参考范围
```

每天先判断是否达标。

如果今天进入目标区间：

```Plain Text
daySuccess_j_t = 1
```

如果今天没有进入目标区间：

```Plain Text
daySuccess_j_t = 0
```

周期完成度：

```Plain Text
goalCompletion_j_t =
min(successDays_j_t / targetDays_j, 1)
```

v0 建议先使用 pass / fail，不做过细的偏离惩罚，避免让用户过度关注单日波动。

---

##### 时间节律型目标

适用于：

```Plain Text
没有 late heavy meal
最后一次有热量摄入距离休息窗口足够远
饮食窗口相对稳定
```

计算方式：

```Plain Text
goalCompletion_j_t =
min(successDays_j_t / targetDays_j, 1)
```

---

#### k\. Daily Progress 的计算方式

Daily Progress 表示今天对某个目标的新增推进。

正向增加型目标：

```Plain Text
dailyProgress_j_t =
todaySuccess_j_t / targetCount_j
```

限制预算型目标：

```Plain Text
if todayViolationCount_j_t == 0:
    dailyProgress_j_t = 1 / totalDays
else:
    dailyProgress_j_t = 0
```

区间型目标：

```Plain Text
if todayValue_j_t is in targetRange_j:
    dailyProgress_j_t = 1 / targetDays_j
else:
    dailyProgress_j_t = 0
```

时间节律型目标：

```Plain Text
if todayTimingPassed_j_t == true:
    dailyProgress_j_t = 1 / targetDays_j
else:
    dailyProgress_j_t = 0
```

注意：

```Plain Text
限制类目标的 Daily Boost 应较小，避免用户因为“不吃 / 不喝 / 不记录某类行为”获得过高奖励。
Daily Boost 只表示今天对目标有推进，不表示越克制越健康。
```

---

#### l\. Diet Finish 每日输入 JSON

Diet Finish 每天计算时，需要读取三类数据：

```Plain Text
1. 用户当前 active diet goals
2. 当天 diet observation
3. 当前周期内累计 observation
```

当天 observation 示例：

```JSON
{
  "agent": "diet",
  "user_id": "user_001",
  "date": "2026-06-10",
  "diet_observation": {
    "meal_count": 3,
    "confirmed_meal_count": 2,
    "estimated_energy_kcal": 2100,
    "energy_data_confidence": 0.76,
    "vegetable_presence": true,
    "fruit_presence": false,
    "protein_presence_meals": 2,
    "carb_energy_ratio": 0.64,
    "sugary_drink_count": 0,
    "dessert_count": 1,
    "takeout_meal_count": 1,
    "late_heavy_meal_count": 0,
    "last_caloric_intake_gap_minutes": 120,
    "recording_complete": true
  },
  "data_quality": {
    "overall_confidence": 0.81,
    "needs_user_confirmation": false,
    "missing_meals_likely": false
  }
}
```

当前 active goals 示例：

```JSON
{
  "agent": "diet",
  "user_id": "user_001",
  "active_goals": [
    {
      "goal_id": "diet_goal_001",
      "goal_type": "limit_budget",
      "metric_id": "sugary_drink_count",
      "cycle_type": "rolling_7_days",
      "selected_path": "gradual",
      "baseline_value": 5,
      "reference_target": {
        "max_allowed": 2,
        "unit": "count_per_7_days"
      },
      "current_cycle_target": {
        "max_allowed": 4,
        "unit": "count_per_7_days"
      },
      "tolerance": 2,
      "weight": 0.35,
      "boost_coef": 0.1
    },
    {
      "goal_id": "diet_goal_002",
      "goal_type": "positive_frequency",
      "metric_id": "vegetable_presence_day",
      "cycle_type": "rolling_7_days",
      "selected_path": "standard",
      "baseline_value": 2,
      "reference_target": {
        "target_count": 5,
        "unit": "days_per_7_days"
      },
      "current_cycle_target": {
        "target_count": 5,
        "unit": "days_per_7_days"
      },
      "weight": 0.35,
      "boost_coef": 0.2
    }
  ]
}
```

---

#### m\. Diet Finish 输出 JSON

Diet Finish 每天输出一个结构化结果。

示例：

```JSON
{
  "agent": "diet",
  "user_id": "user_001",
  "date": "2026-06-10",
  "status": "active",
  "cycle": {
    "cycle_type": "rolling_7_days",
    "start_date": "2026-06-04",
    "end_date": "2026-06-10",
    "elapsed_days": 7,
    "total_days": 7
  },
  "diet_finish": {
    "score": 84.6,
    "base_completion": 80.2,
    "daily_boost": 4.4,
    "daily_boost_max": 10,
    "is_above_100": false
  },
  "goal_results": [
    {
      "goal_id": "diet_goal_001",
      "template_id": "sugary_drink_budget_weekly",
      "goal_type": "limit_budget",
      "metric_id": "sugary_drink_count",
      "selected_path": "gradual",
      "weight": 0.35,
      "baseline_value": 5,
      "current_cycle_target": {
        "max_allowed": 4,
        "unit": "count_per_7_days"
      },
      "reference_target": {
        "max_allowed": 2,
        "unit": "count_per_7_days"
      },
      "current_cycle_value": 1,
      "today_units": 0,
      "goal_completion": 1.0,
      "base_score_contribution": 35.0,
      "daily_progress": 0.1429,
      "daily_boost_contribution": 0.5,
      "confidence": 0.84,
      "status": "within_budget"
    },
    {
      "goal_id": "diet_goal_002",
      "template_id": "vegetable_presence_weekly",
      "goal_type": "positive_frequency",
      "metric_id": "vegetable_presence_day",
      "selected_path": "standard",
      "weight": 0.35,
      "baseline_value": 2,
      "current_cycle_target": {
        "target_count": 5,
        "unit": "days_per_7_days"
      },
      "reference_target": {
        "target_count": 5,
        "unit": "days_per_7_days"
      },
      "current_cycle_value": 4,
      "today_units": 1,
      "goal_completion": 0.8,
      "base_score_contribution": 28.0,
      "daily_progress": 0.2,
      "daily_boost_contribution": 1.4,
      "confidence": 0.82,
      "status": "in_progress"
    }
  ],
  "data_quality": {
    "overall_confidence": 0.82,
    "low_confidence_goals": [],
    "needs_user_confirmation": false
  }
}
```

---

#### n\. 异常与低置信度处理

Diet Finish 依赖用户饮食识别、估算和确认，因此必须处理低置信度情况。

如果当天数据置信度不足：

```Plain Text
不应强行计算完整 Finish。
```

可输出：

```JSON
{
  "agent": "diet",
  "user_id": "user_001",
  "date": "2026-06-10",
  "status": "insufficient_data",
  "diet_finish": {
    "score": null,
    "base_completion": null,
    "daily_boost": null
  },
  "reason": "low_confidence_or_missing_meals",
  "required_action": "user_confirmation",
  "data_quality": {
    "overall_confidence": 0.52,
    "missing_meals_likely": true,
    "needs_user_confirmation": true
  }
}
```

如果某个 goal 置信度不足：

```Plain Text
该 goal 可以暂不计入当天 Daily Boost；
Base Completion 可以沿用上一日或标记为 provisional；
系统应提示用户确认相关餐食。
```

---

#### o\. Diet Finish 的安全边界

Diet Finish 必须避免鼓励过度限制饮食。

不支持以下目标：

```Plain Text
摄入越低越好
极端低热量
跳餐 / 断食打卡
只吃某一种食物
完全不吃碳水
以体重快速下降为唯一目标
惩罚性饮食目标
```

范围类目标必须使用：

```Plain Text
target_range
```

而不是：

```Plain Text
lower_is_better
```

例如：

```Plain Text
每日能量摄入进入个人目标区间
```

可以作为目标。

但：

```Plain Text
每日摄入越低越好
```

不能作为目标。

系统默认不应自动生成激进的能量限制类目标。

对于以下用户，应使用更保守的饮食行为目标：

```Plain Text
未成年人
孕期 / 产后人群
慢性疾病人群
进食障碍风险人群
运动损伤或康复人群
```

更保守的目标包括：

```Plain Text
提高蔬菜摄入频率
减少含糖饮料频率
改善 late heavy meal 频率
规律记录三餐
增加优质蛋白来源稳定性
```

---

#### p\. Diet Finish 的最终计算边界

Diet Finish 只衡量用户确认后的饮食目标完成度。

最终结构：

```Plain Text
Diet Finish = user-confirmed diet goal completion

Learning Period = baseline learning and gap discovery

Gap Analysis = baseline vs health reference

Goal Recommendation = gap-to-goal template recommendation

User Pace Selection = standard path or gradual path

Base Completion = current cycle progress

Daily Boost = today's additional positive progress

Diet Balance = HEI-2020 based diet quality score

Energy Fit = independent explanatory layer

Diet Timing = independent explanatory layer
```

Diet Finish 不能被解释为：

```Plain Text
饮食健康质量
HEI-2020 分数
减脂效果
体重变化效果
医学营养治疗结果
越控制越好的分数
```

这些内容必须由其他指标或解释层处理。

---

### 6\.1\.3 Diet Balance

Diet Balance 是饮食健康质量指标，用来衡量用户最近一段时间的真实饮食结构，与北美权威膳食指南所定义的健康饮食模式之间的接近程度。

Diet Balance 由 USDA 发布的 Healthy Eating Index 计算而来。

https://www\.fns\.usda\.gov/cnpp/how\-hei\-scored

```Plain Text
Source:
https://www.fns.usda.gov/cnpp/how-hei-scored

Diet Balance = HEI-2020 Total Score
```

这个指标不是：

```Plain Text
减肥分数
卡路里打卡分数
AI 主观评价分数
用户满意度
```

它的本质是：

```Plain Text
用户实际吃下去的一组食物
→ 转换为 USDA 食物组与营养成分
→ 按 HEI-2020 官方 13 个 component 计分
→ 得到饮食健康质量分数
```

---

#### a\. HEI\-2020 的 13 个指标与权重

HEI\-2020 由 13 个 component 加总得到。

NCI / USDA 明确给出了每项最高分、满分标准、零分标准，并说明中间摄入量按比例得分。

NCI 说明：

```Plain Text
HEI-2020 和 HEI-2015 的 component 与 scoring standards 相同。
13 个 component 加总为 100 分。
大部分 component 按每 1000 kcal 的密度计算。
```

因此，Diet Balance 的计算不是 AI 自己判断，而是对官方 HEI\-2020 计算规则的产品化实现。

---

#### b\. 具体计算方式

#### c\. Adequacy 类指标

Adequacy 类指标的逻辑是：

```Plain Text
越多越好，但超过满分标准不继续加分。
```

例如 Total Vegetables：

```Plain Text
score = max_points × min(actual_density / full_score_standard, 1)
```

举例：

```Plain Text
用户今天蔬菜密度 = 0.55 cup eq / 1000 kcal
HEI 满分标准 = 1.1 cup eq / 1000 kcal
该项最高分 = 5

score = 5 × 0.55 / 1.1 = 2.5
```

---

#### d\. Moderation 类指标

Moderation 类指标的逻辑是：

```Plain Text
越少越好。
```

例如 Sodium：

```Plain Text
if actual_density <= full_score_standard:
    score = max_points

elif actual_density >= zero_score_standard:
    score = 0

else:
    score = max_points × (zero_score_standard - actual_density) / (zero_score_standard - full_score_standard)
```

举例：

```Plain Text
用户 sodium = 1.55 g / 1000 kcal
满分线 = 1.1 g / 1000 kcal
零分线 = 2.0 g / 1000 kcal
最高分 = 10

score = 10 × (2.0 - 1.55) / (2.0 - 1.1)
score = 5
```

---

#### e\. Fatty Acids

Fatty Acids 使用比例计算：

```Plain Text
ratio = (PUFA + MUFA) / SFA
```

计算方式：

```Plain Text
if ratio >= 2.5:
    score = 10

elif ratio <= 1.2:
    score = 0

else:
    score = 10 × (ratio - 1.2) / (2.5 - 1.2)
```

---

#### f\. 食物摄入数据输入与数据源

Diet Agent 不能只识别：

```Plain Text
这是米饭
这是鸡肉
这是沙拉
```

它最终必须把食物拆成 USDA 可计算的 food pattern components。

NCI 明确说明，计算 HEI 需要把食物映射到 food groups 和 nutrients，例如：

```Plain Text
sodium
fatty acids
fruits
vegetables
grains
dairy
protein foods
added sugars
```

NCI / USDA 使用 FNDDS 和 FPED 来完成这种映射。

---

#### g\. 产品侧需要的输入

USDA FPED 会把 FNDDS 中的食物和饮料转换成 USDA Food Patterns components。

这些 components 包括：

```Plain Text
fruits
vegetables
dairy
grains
protein foods
added sugars
solid fats
oils
```

这些就是 HEI 计算需要的底层变量。

因此，产品侧需要的不是简单的食物名称，而是：

```Plain Text
食物识别结果
份量估计
能量估计
USDA food group 映射
营养成分映射
Food Pattern components 映射
用户确认 / 修正
```

---

#### h\. 热量怎么处理

热量必须看，但不应该直接塞进 HEI 主分。

原因是 HEI 衡量的是 diet quality，不是 diet quantity。

HEI 使用 density approach，把饮食质量和饮食数量拆开。

因此产品里应该是：

```Plain Text
Diet Balance = HEI-2020

Energy Fit = 单独解释层
```

也就是说：

```Plain Text
饮食结构是否健康
```

和：

```Plain Text
热量摄入是否接近个人需求
```

应该分开解释。

---

#### i\. Energy Fit 的科学来源

北美能量需求可以使用 NASEM 2023 Dietary Reference Intakes for Energy 的 EER 方程。

NASEM 说明 EER 用于估计个人或群体合适能量摄入，方程基于：

```Plain Text
年龄
性别
体力活动水平
身高
体重
```

并适用于美国和加拿大。

成人男性 19\+ 的 EER 例子：

```Plain Text
Inactive:
EER = 753.07 − 10.83 × age + 6.50 × height + 14.10 × weight

Low active:
EER = 581.47 − 10.83 × age + 8.30 × height + 14.94 × weight

Active:
EER = 1004.82 − 10.83 × age + 6.52 × height + 15.91 × weight

Very active:
EER = −517.88 − 10.83 × age + 15.61 × height + 19.11 × weight
```

NASEM 公式中：

```Plain Text
age = 年
height = 厘米
weight = 公斤
```

Energy Fit 的产品定位：

```Plain Text
Energy Fit 是解释层，不进入 Diet Balance。
```

---

### 6\.1\.4 用餐时间处理与评价

用餐时间目前不进入 Diet Balance。

原因是现有研究对“固定几点吃饭最好”没有足够确定的统一标准。

尤其是早餐时间，不能写成：

```Plain Text
早上 8:30 最健康
起床后一小时必须吃早餐
不吃早餐直接扣分
```

这类规则目前不适合进入绝对健康判断。

但有一类证据相对明确：

```Plain Text
晚间进食、睡前进食，尤其是睡前吃高热量或高碳水餐，
可能对血糖代谢和昼夜节律产生负面影响。
```

因此 Diet Agent 只保留确定性相对较高的 timing 判断，但这些判断只生成 flag 或 insight，不进入 Diet Balance。

当前产品没有 Sleep Agent，因此涉及 sleep baseline 的判断需要谨慎处理。

如果没有用户稳定睡眠数据，不应声称：

```Plain Text
用户睡前 1 小时进食
用户在睡眠窗口内进食
```

可以改为：

```Plain Text
late evening eating
user-defined rest window
habitual inactive period
eating window trend
```

---

#### a\. Last Caloric Intake Before Rest

定义：

用户当天最后一次有热量摄入的时间，距离其习惯休息时段或用户定义休息窗口的间隔。

如果未来接入睡眠数据，可以使用 sleep baseline。

当前没有 Sleep Agent 时，应使用更保守的表述。

计算方式：

```Plain Text
last_caloric_gap = rest_window_start - last_caloric_intake_time
```

产品处理：

```Plain Text
该指标不扣 Diet Balance，只生成 timing flag。
```

示例：

```JSON
{
  "late_eating_flag": true,
  "reason": "Last caloric intake happened close to the user's usual rest period."
}
```

参考研究：

Garaulet / Scheer / Saxena 团队的 randomized crossover study 比较了习惯睡眠前 4 小时进食与睡眠前 1 小时进食。结果显示，晚吃条件下褪黑素水平更高，胰岛素反应更低，餐后血糖反应更高。

```Plain Text
https://diabetesjournals.org/care/article/45/3/512/139100/Interplay-of-Dinner-Timing-and-MTNR1B-Type-2
```

---

#### b\. Late Heavy Meal

定义：

用户在较晚时段摄入高热量餐或明显高碳水餐。

当前没有 Sleep Agent 时，不建议直接写成“睡前 2 小时内”。

更稳妥的判断方式：

```Plain Text
if meal_time is close to user_defined_rest_window
and meal_energy >= daily_energy_intake × 25%:
    late_heavy_meal = true
```

或者：

```Plain Text
if meal_time is in late evening
and refined_grains / added_sugars / high glycemic carbs 明显偏高:
    late_heavy_meal = true
```

产品处理：

```Plain Text
Late Heavy Meal 不进入 HEI 主分，但作为高优先级解释项。
```

示例文案：

```Plain Text
Your last heavy meal was close to your usual rest period. This may affect overnight glucose control and appetite regulation.
```

参考研究：

2022 年 Cell Metabolism 的 randomized crossover trial 在控制总热量、饮食组成、睡眠、光照和体力活动的情况下，比较 early eating 与 late eating。研究显示 late eating 会增加饥饿感、降低能量消耗，并改变脂肪组织代谢相关通路。

```Plain Text
https://www.cell.com/cell-metabolism/fulltext/S1550-4131(22)00397-7
```

---

#### c\. Biological Night Eating

定义：

用户在自己的习惯休息窗口或生物夜间估计区间内发生进食。

当前没有 Sleep Agent 时，该指标只能作为低置信度估计，不应作为强判断。

计算方式：

```Plain Text
if caloric_intake_time between estimated_biological_night_start and estimated_biological_night_end:
    biological_night_eating = true
```

产品处理：

```Plain Text
该指标只作为风险提示，不进入 Diet Balance。
```

示例：

```JSON
{
  "biological_night_eating_flag": true,
  "confidence": "medium",
  "reason": "Calories were consumed during the estimated biological night period."
}
```

用户文案：

```Plain Text
Night eating detected.

You consumed calories during a period that appears close to your usual rest window.
```

参考研究：

Chellappa 等人在 Science Advances 发表的模拟夜班实验显示，夜间进食会造成 central circadian clock 与 peripheral glucose rhythm 的错位，并损害葡萄糖耐受；而将进食限制在白天可以防止这种 glucose intolerance。

```Plain Text
https://www.science.org/doi/10.1126/sciadv.abg9910
```

---

#### d\. Eating Window

定义：

用户当天第一口有热量摄入到最后一口有热量摄入之间的时间长度。

计算方式：

```Plain Text
eating_window = last_caloric_intake_time - first_caloric_intake_time
```

产品处理：

```Plain Text
Eating Window 只作为趋势指标，不进入 Diet Balance。
```

不建议设置固定扣分规则，例如：

```Plain Text
进食窗口超过 12 小时扣分
进食窗口必须 8 小时以内
```

原因是 time\-restricted eating 有一定研究支持，但不同人群、不同作息、不同训练目标下没有足够统一的绝对标准。

可展示为趋势：

```Plain Text
This week, your eating window shifted later and became less consistent.
```

---

#### e\. Breakfast Timing

早餐时间暂时不进入 Diet Balance。

不采用以下规则：

```Plain Text
早上 8:30 吃早餐最好
起床后 30 分钟必须吃早餐
不吃早餐直接扣分
```

原因是早餐相关研究中，观察性研究较多，容易受到生活方式混杂因素影响。

早餐时间可以记录，但不适合作为确定性健康扣分项。

产品只保留：

```Plain Text
first_caloric_intake_time
breakfast_skipping_frequency
first_meal_variability
```

作为长期趋势观察，不进入 Diet Balance。

---

#### f\. Diet Timing 的产品输出

Diet Timing 不作为主分，只输出 flags 和 trend。

推荐 JSON：

```JSON
{
  "diet_timing": {
    "included_in_balance": false,
    "method": "relative_to_user_defined_rest_window_or_estimated_inactive_period",
    "last_caloric_intake_gap_minutes": 45,
    "late_eating_flag": true,
    "late_heavy_meal_flag": true,
    "biological_night_eating_flag": false,
    "eating_window_hours": 12.5,
    "breakfast_timing_used_for_scoring": false
  }
}
```

对应用户文案：

```Plain Text
Your main diet quality score is based on HEI-2020.

Meal timing is shown separately because only late-night and rest-adjacent eating currently has strong enough evidence for product-level warnings.
```

---

### 6\.1\.5 Diet Balance 的最终计算边界

Diet Balance 只由 HEI\-2020 计算。

不进入 Diet Balance 的内容：

```Plain Text
热量摄入
减脂目标
增肌目标
早餐时间
吃饭速度
外卖频率
餐厅频率
用餐情绪
用餐社交场景
拍照完整度
用户主观满意度
```

这些可以作为解释层、行为层或 Diet Finish 的目标完成层，但不能进入 Diet Balance。

最终结构：

```Plain Text
Diet Balance = HEI-2020 Total Score

Energy Fit = independent explanatory layer

Diet Timing = independent explanatory layer

Diet Finish = user-goal completion layer
```

---

## 6\.2 Training Agent

### 6\.2\.1 Training Agent 定义

Training Agent 负责识别、记录和解释用户的训练行为。

在当前产品架构中，Training Agent 对应的是 Daily Activity 下的“训练”，主要包括：

```Plain Text
健身房训练
力量训练
自重训练
器械训练
阻力带训练
HIIT / 课程训练
有明确训练目的的跑步、骑行或其他结构化训练
```

Training Agent 关注的是：

```Plain Text
用户是否进行了有计划、有目的、结构化的训练行为；
其中肌肉强化活动是否达到公共健康指南推荐的最低水平；
训练目标是否被推进；
训练负荷是否有长期变化。
```

Training Agent 不等于 Activity Agent。

Activity Agent 主要处理：

```Plain Text
步行
快走
慢跑
跑步
爬楼
主动通勤中的步行 / 骑行
其他日常中高强度移动类身体活动
```

Training Agent 主要处理：

```Plain Text
肌肉强化活动
力量训练
结构化训练计划
训练完成度
训练负荷
训练动作
训练部位
训练规律
```

需要特别说明：

```Plain Text
CDC / WHO 的完整身体活动建议包含两部分：

1. 有氧身体活动
2. 肌肉强化活动
```

由于 Relty 当前产品架构将“运动”和“训练”拆成两个 Agent，因此：

```Plain Text
Activity Agent 处理有氧身体活动剂量。
Training Agent 处理肌肉强化活动与结构化训练。
```

因此，本节中的 Training Balance 不是完整身体活动健康建议的全部，而是其中的 muscle\-strengthening activity 部分。

当前章节主要定义：

```Plain Text
训练行为的识别方式
Training Finish 的目标完成逻辑
Training Balance 的肌肉强化活动计算方式
训练相关扩展指标
```

本节暂不讨论 Training Agent 与 Activity Agent 之间的数据共享、合并和去重问题。

当前只定义 Training Agent 自身的 Balance 计算方式。

---

### 6\.2\.2 Training Finish

Training Finish 衡量用户在当前训练目标周期内的完成情况。

它表示：

```Plain Text
用户今天在自己设定的训练目标上推进了多少。
```

例如：

```Plain Text
用户目标：本周完成 3 次健身房训练
用户目标：本周完成 2 次力量训练
用户目标：本月卧推训练 8 次
用户目标：每周完成 2 次下肢训练
用户目标：按照计划完成 Push / Pull / Legs 循环
用户目标：每周完成 1 次 HIIT 课程
```

Training Finish 的具体算法后续单独定义。

需要注意：

```Plain Text
Training Finish 不等于 Training Balance。

Training Finish 是用户目标完成度。
Training Balance 是基于公共健康指南，对肌肉强化活动是否达标进行客观计算。
```

例如：

```Plain Text
用户目标是“本周练 5 次胸”：
Training Finish 可能很高，因为用户完成了自己的目标；
Training Balance 不一定高，因为公共健康角度还要看是否覆盖主要肌群。
```

---

### 6\.2\.3 Training Balance

Training Balance 是肌肉强化活动的公共健康建议达标分。

它不评价训练效果，而是看用户最近 7 天是否完成了足够频率的肌肉强化活动，并且训练是否覆盖主要肌群。

Training Balance 的核心不是：

```Plain Text
举了多重
练得多累
练了多少卡路里
训练表现提升了多少
是否增肌成功
```

Training Balance 的核心是：

```Plain Text
最近 7 天内，用户是否完成了足够频率、覆盖主要肌群的肌肉强化活动。
```

Training Balance 衡量的是：

```Plain Text
Muscle-strengthening Activity Compliance
肌肉强化活动达标情况
```

它不是：

```Plain Text
训练质量
训练效果
力量水平
肌肉增长效果
训练计划完成度
训练恢复状态
```

---

#### a\. Training Balance 计算公式与分数定义

Training Balance 使用 rolling 7 days 作为计算窗口。

$window_t = [t-6, t]$

定义：

$S_t$= 最近 7 天内符合条件的 strength\_training\_events 集合

事件进入 S\_t 的条件：

```Plain Text
1. event_time 在 rolling 7 days 内
2. event_type 属于 muscle-strengthening / resistance training
3. training_intensity >= moderate
4. confidence >= confidence_threshold
```

其中，muscle\-strengthening / resistance training 包括：

```Plain Text
自重训练
自由重量训练
器械训练
阻力带训练
核心训练
其他以增强肌肉力量或肌耐力为目的的训练
```

Training Balance 由两个部分组成：

```Plain Text
1. Strength Training Frequency Score
2. Major Muscle Group Coverage Score
```

原因是 CDC / WHO 的肌肉强化建议同时包含两个关键要求：

```Plain Text
每周 2 天或以上
覆盖所有主要肌群
```

---

##### Strength Training Frequency Score

先计算最近 7 天内有多少天进行了符合条件的肌肉强化训练。

```Plain Text
strength_days_7d = count_distinct_days(S_t)
```

频率分数为：

```Plain Text
frequency_score_t = 70 × min(strength_days_7d / 2, 1)
```

其中：

```Plain Text
2 天 = 成人每周肌肉强化活动的最低推荐频率
70 = Training Balance 中频率部分的权重
```

解释：

```Plain Text
0 天训练 → frequency_score = 0
1 天训练 → frequency_score = 35
2 天或以上训练 → frequency_score = 70
```

注意：

```Plain Text
CDC / WHO 只明确提出“每周至少 2 天”。
因此，Training Balance 的公共健康主分不把 3 天、4 天简单线性解释为更高健康分。
超过 2 天的训练频率可以进入 Training Trend / Training Load / Training Finish，但不直接提高 Training Balance 主分。
```

---

##### Major Muscle Group Coverage Score

CDC 成人指南明确提到，肌肉强化活动应覆盖所有主要肌群：

```Plain Text
legs
hips
back
abdomen
chest
shoulders
arms
```

产品侧可映射为：

```Plain Text
下肢 / legs
髋部 / hips
背部 / back
核心 / abdomen
胸部 / chest
肩部 / shoulders
手臂 / arms
```

计算最近 7 天内被训练覆盖到的主要肌群数量：

```Plain Text
covered_muscle_groups_7d = unique_major_muscle_groups(S_t)
```

主要肌群总数：

```Plain Text
total_major_muscle_groups = 7
```

肌群覆盖率：

```Plain Text
coverage_ratio_t = count(covered_muscle_groups_7d) / 7
```

覆盖分数为：

```Plain Text
coverage_score_t = 30 × coverage_ratio_t
```

其中：

```Plain Text
30 = Training Balance 中肌群覆盖部分的权重
```

解释：

```Plain Text
覆盖 7 / 7 个主要肌群 → coverage_score = 30
覆盖 5 / 7 个主要肌群 → coverage_score ≈ 21.4
覆盖 3 / 7 个主要肌群 → coverage_score ≈ 12.9
```

---

##### Training Balance 最终公式

Training Balance 为：

```Plain Text
TrainingBalance_t = frequency_score_t + coverage_score_t
```

展开为：

```Plain Text
TrainingBalance_t
= 70 × min(strength_days_7d / 2, 1)
+ 30 × count(covered_muscle_groups_7d) / 7
```

其中：

```Plain Text
strength_days_7d = 最近 7 天内符合条件的肌肉强化训练天数
covered_muscle_groups_7d = 最近 7 天内被训练覆盖到的主要肌群集合
```

因此：

```Plain Text
Training Balance = 100
```

表示用户最近 7 天内：

```Plain Text
1. 至少 2 天进行了肌肉强化活动；
2. 最近 7 天内覆盖了所有主要肌群。
```

需要注意：

```Plain Text
Training Balance 当前不按 Activity Balance 那样向 200 延展。
```

原因是：

```Plain Text
Activity Balance 有 WHO 的 150–300 分钟推荐范围，可以映射出 100–200 的区间。

Training Balance 对肌肉强化活动的公共健康建议主要是“每周 2 天或以上，覆盖主要肌群”。
目前 CDC / WHO 没有给出类似“2 天 = 100，4 天 = 200”的公共健康剂量区间。
```

所以，Training Balance 的公共健康主分建议保留为：

```Plain Text
0–100 guideline compliance score
```

额外训练量不进入 Training Balance 主分，而进入：

```Plain Text
Training Load
Training Volume
Training Trend
Training Finish
```

---

##### 示例计算

用户最近 7 天训练情况：

```Plain Text
周一：胸、肩、手臂
周三：腿、髋、背、核心
```

计算：

```Plain Text
strength_days_7d = 2

covered_muscle_groups_7d
= {chest, shoulders, arms, legs, hips, back, abdomen}

coverage_ratio = 7 / 7 = 1
```

频率分数：

```Plain Text
frequency_score
= 70 × min(2 / 2, 1)
= 70
```

覆盖分数：

```Plain Text
coverage_score
= 30 × 1
= 30
```

Training Balance：

```Plain Text
TrainingBalance
= 70 + 30
= 100
```

---

##### 不同情况示例

情况 1：最近 7 天只练了 1 天，但练了全身。

```Plain Text
strength_days_7d = 1
coverage_ratio = 7 / 7 = 1

TrainingBalance
= 70 × min(1 / 2, 1) + 30 × 1
= 35 + 30
= 65
```

情况 2：最近 7 天练了 3 天，但只练胸、肩、手臂。

```Plain Text
strength_days_7d = 3
coverage_ratio = 3 / 7

TrainingBalance
= 70 × min(3 / 2, 1) + 30 × 3 / 7
= 70 + 12.9
= 82.9
```

情况 3：最近 7 天练了 2 天，并覆盖所有主要肌群。

```Plain Text
strength_days_7d = 2
coverage_ratio = 7 / 7

TrainingBalance
= 70 × min(2 / 2, 1) + 30 × 1
= 100
```

---

#### b\. 科学依据与计量基础

Training Balance 使用以下研究和指南作为依据：

```Plain Text
1. CDC Adult Physical Activity Guidelines
https://www.cdc.gov/physical-activity-basics/guidelines/adults.html

2. WHO 2020 Guidelines on Physical Activity and Sedentary Behaviour
https://pmc.ncbi.nlm.nih.gov/articles/PMC7719906/

3. Physical Activity Guidelines for Americans, 2nd edition
https://health.gov/sites/default/files/2019-09/Physical_Activity_Guidelines_2nd_edition.pdf

4. ACSM Physical Activity Guidelines
https://acsm.org/education-resources/trending-topics-resources/physical-activity-guidelines/

5. Resistance Training and Mortality Risk: A Systematic Review and Meta-Analysis
https://pubmed.ncbi.nlm.nih.gov/35599175/

6. Muscle-strengthening activities are associated with lower risk and mortality in major non-communicable diseases
https://pmc.ncbi.nlm.nih.gov/articles/PMC9209691/

7. Dose-response relationship between weekly resistance training volume and increases in muscle mass
https://pubmed.ncbi.nlm.nih.gov/27433992/

8. Session-RPE Method for Training Load Monitoring
https://pmc.ncbi.nlm.nih.gov/articles/PMC5673663/

9. The Relationship Between Acute:Chronic Workload Ratios and Injury Risk in Sports
https://www.dovepress.com/the-relationship-between-acute-chronic-workload-ratios-and-injury-risk-peer-reviewed-fulltext-article-OAJSM
```

CDC 成人身体活动指南指出：

```Plain Text
成年人每周需要至少 150 分钟中等强度有氧活动，
或 75 分钟高强度有氧活动，
或二者的等量组合。

成年人还需要每周至少 2 天肌肉强化活动。
```

CDC 进一步说明，肌肉强化活动需要在每周 2 天或以上进行，并覆盖所有主要肌群，包括：

```Plain Text
legs
hips
back
abdomen
chest
shoulders
arms
```

在 Relty 当前 Agent 架构中：

```Plain Text
150 分钟中等强度有氧活动 / 75 分钟高强度有氧活动
→ Activity Agent

每周至少 2 天肌肉强化活动
→ Training Agent
```

WHO 2020 指南同样指出：

```Plain Text
成年人应在每周 2 天或以上进行中等或更高强度的肌肉强化活动，并涉及所有主要肌群。
```

因此，Training Balance 的主公式采用：

```Plain Text
训练频率
+
主要肌群覆盖
```

作为公共健康意义上的肌肉强化活动达标计算方式。

---

#### c\. 年龄与适用人群边界

Training Balance 当前默认适用于：

```Plain Text
一般成年人
```

因为 CDC / WHO 的身体活动建议会根据年龄和特殊人群进行区分，所以 Training Agent 需要读取用户初始化阶段输入的年龄信息。

当前 v0 处理方式：

```Plain Text
18–64 岁一般成年人：
使用成人肌肉强化活动建议。

65 岁及以上老年人：
暂不单独调整 Training Balance 公式。
后续应加入老年人专属建议，包括平衡能力、功能性力量和跌倒风险相关训练。

慢性疾病、孕期 / 产后、残障、运动损伤或康复人群：
暂不单独调整 Training Balance 公式。
后续根据指南扩展独立计算边界。
```

因此，当前公式不是对所有人群的最终版本，而是 v0 的一般成年人版本。

本公式依赖初始化阶段至少提供：

```Plain Text
年龄
```

后续如果要做更细分的训练强度解释、训练目标或个性化推荐，还会使用：

```Plain Text
身高
体重
sex
fitness level
主要目标
训练经验
慢性疾病 / 孕期 / 受伤情况
```

其中，慢性疾病、孕期、受伤情况等只作为后续优化方向，当前 v0 不进入计算。

---

#### d\. Training Event 输入

每个被识别出的训练事件需要包含以下字段：

```JSON
{
  "event_id": "training_001",
  "user_id": "user_001",
  "start_time": "2026-06-10T18:30:00",
  "end_time": "2026-06-10T19:15:00",
  "duration_minutes": 45,
  "training_type": "resistance_training",
  "training_mode": "free_weight",
  "detected_exercises": ["squat", "bench_press", "row"],
  "major_muscle_groups": ["legs", "hips", "chest", "back", "arms"],
  "training_intensity": "moderate",
  "confidence": 0.84,
  "source": ["vision", "imu", "user_confirmation"]
}
```

核心字段：

```Plain Text
duration_minutes
training_type
training_mode
detected_exercises
major_muscle_groups
training_intensity
confidence
```

其中：

```Plain Text
duration_minutes 用于记录训练时长。
training_type 用于判断是否属于肌肉强化活动。
training_mode 用于区分自由重量、器械、自重、阻力带等训练方式。
detected_exercises 用于识别具体训练动作。
major_muscle_groups 用于计算主要肌群覆盖率。
training_intensity 用于判断是否达到 moderate or greater intensity。
confidence 用于过滤低置信度训练事件。
```

---

#### e\. 什么算 muscle\-strengthening activity

Training Agent 中可进入 Training Balance 的 muscle\-strengthening activity 包括：

```Plain Text
自重训练
自由重量训练
器械训练
阻力带训练
壶铃训练
核心训练
以提升肌肉力量或肌耐力为目的的训练课程
```

不直接进入 Training Balance 的内容包括：

```Plain Text
拉伸
放松
按摩
散步
普通通勤
单纯热身
轻松活动
以有氧为主的跑步 / 骑行
```

这些内容可以进入其他 Agent 或解释层，但不进入 Training Balance 主公式。

需要注意：

```Plain Text
HIIT / 课程训练是否进入 Training Balance，取决于其中是否包含明确的肌肉强化内容。
```

如果课程主要是心肺训练，则不进入 Training Balance。

如果课程包含明确阻力训练、自重力量训练或主要肌群力量训练，则可以进入 Training Balance。

---

#### f\. 为什么不按训练重量或卡路里算主分

Training Balance 不使用以下变量作为主计算方式：

```Plain Text
训练重量
训练总负重
训练消耗卡路里
训练后疲劳程度
训练酸痛程度
训练表现提升
```

原因：

```Plain Text
训练重量高度依赖动作类型、训练经验、性别、体重、目标和技术水平；
训练消耗卡路里估计误差大；
疲劳和酸痛不等于训练质量；
训练表现提升属于训练目标和训练进步，不属于公共健康最低建议；
不同用户的训练目标差异很大，不能用统一重量或表现标准评价。
```

因此，Training Balance 主分只衡量：

```Plain Text
是否达到公共健康意义上的肌肉强化活动最低建议。
```

更细的训练重量、容量、表现、进步和疲劳，应进入：

```Plain Text
Training Finish
Training Load
Training Volume
Training Trend
```

---

#### g\. 可选扩展指标 1：Training Volume Index

Training Volume Index 用于衡量用户一周内完成了多少阻力训练容量。

它不进入 Training Balance 主分，但可以作为 Training Agent 的扩展指标。

适用场景：

```Plain Text
用户有明确训练目标，例如增肌、力量提升、训练规律提升。
```

常见计算方式：

```Plain Text
weekly_sets_per_muscle_group = Σ hard_sets for each major muscle group in rolling 7 days
```

其中：

```Plain Text
hard_sets = 有明确训练刺激的有效训练组
```

可进一步计算：

```Plain Text
TrainingVolumeIndex_t
= average_over_muscle_groups(min(weekly_sets_muscle_group / target_sets, 1))
```

其中：

```Plain Text
target_sets 可以根据用户目标设定。
```

例如：

```Plain Text
维持健康 / 初级训练目标：target_sets 可以较低
增肌目标：target_sets 可以更高
```

研究依据：

```Plain Text
Resistance training volume 与肌肉增长存在剂量反应关系。
Schoenfeld 等人的系统综述和 meta-analysis 显示，weekly resistance training volume 增加与肌肉肥大增益增加相关。
```

但需要注意：

```Plain Text
Training Volume Index 是训练目标相关指标，不是公共健康 Balance 主分。
```

---

#### h\. 可选扩展指标 2：Volume Load

Volume Load 用于衡量某次训练或某周训练的外部负荷。

公式：

```Plain Text
volume_load = Σ(sets × reps × weight)
```

例如：

```Plain Text
卧推 3 组 × 10 次 × 40kg

volume_load = 3 × 10 × 40 = 1200 kg
```

Volume Load 可以用于观察：

```Plain Text
同一动作的训练负荷变化
同一训练周期内的负荷趋势
用户训练是否有递进
```

但需要注意：

```Plain Text
Volume Load 不能跨动作直接比较。
```

例如：

```Plain Text
深蹲 2000kg volume load
不等于
侧平举 2000kg volume load
```

因此，Volume Load 适合做：

```Plain Text
单动作趋势
单肌群趋势
训练计划进展
```

不适合作为 Training Balance 主分。

---

#### i\. 可选扩展指标 3：Progressive Overload Index

Progressive Overload Index 用于衡量用户训练负荷是否在长期逐步提升。

基础公式可以是：

```Plain Text
progressive_overload_ratio
= current_period_volume_load / baseline_period_volume_load
```

例如：

```Plain Text
current_period = 最近 4 周
baseline_period = 之前 4 周
```

也可以按动作计算：

```Plain Text
exercise_progress_ratio
= current_estimated_1RM / baseline_estimated_1RM
```

用途：

```Plain Text
判断训练是否有长期进展
判断训练负荷是否停滞
辅助 Training Finish 和训练建议
```

需要注意：

```Plain Text
Progressive Overload 是训练进步指标，不是公共健康 Balance 主分。
```

原因是：

```Plain Text
公共健康建议只要求成年人每周进行肌肉强化活动；
并不要求所有用户都持续增加重量或训练容量。
```

---

#### j\. 可选扩展指标 4：Session\-RPE Training Load

如果产品允许用户在训练后输入主观用力程度 RPE，可以计算 Session\-RPE Training Load。

公式：

```Plain Text
session_RPE_load = session_duration_minutes × session_RPE
```

其中：

```Plain Text
session_RPE = 用户对本次训练整体强度的主观评分
```

例如：

```Plain Text
训练 45 分钟
RPE = 7

session_RPE_load = 45 × 7 = 315 AU
```

AU 表示 arbitrary units，即任意单位。

Session\-RPE 的价值是：

```Plain Text
用一个简单方式同时考虑训练时长和主观强度。
```

它适合做：

```Plain Text
Training Load
Fatigue Trend
Training Strain
Training Plan Adjustment
```

但它不适合作为 Training Balance 主分。

原因：

```Plain Text
RPE 是主观输入；
不同用户对 RPE 的理解不同；
它更像内部训练负荷指标，而不是公共健康达标指标。
```

---

#### k\. 可选扩展指标 5：Acute:Chronic Workload Ratio

如果产品长期积累训练负荷数据，可以计算 Acute:Chronic Workload Ratio。

公式：

```Plain Text
ACWR = acute_training_load / chronic_training_load
```

其中：

```Plain Text
acute_training_load = 最近 7 天训练负荷
chronic_training_load = 过去 3–6 周平均训练负荷
```

可用的 training\_load 可以来自：

```Plain Text
session_RPE_load
volume_load
训练时长
训练次数
```

ACWR 的作用是：

```Plain Text
观察用户近期训练负荷是否相对长期水平突然升高。
```

需要注意：

```Plain Text
ACWR 在运动科学中存在争议，不应作为强判断或医学风险预测。
```

因此，ACWR 只能作为：

```Plain Text
Training Load Insight
Training Strain Flag
```

不能作为 Training Balance 主分，也不能输出确定性的伤病预测。

---

#### l\. 不进入 Training Balance 的变量

不进入 Training Balance 主分的内容：

```Plain Text
训练重量
训练总负重
训练消耗热量
训练时长
训练后酸痛
训练后主观爽感
用户增肌目标
用户减脂目标
用户力量目标
训练计划完成度
跑步配速
有氧活动剂量
```

原因：

```Plain Text
Training Balance 只衡量肌肉强化活动是否达到公共健康最低建议；
训练重量、训练容量、训练目标和训练表现高度个体化；
有氧活动剂量属于 Activity Agent；
增肌、减脂、力量目标属于 Training Finish 或 Training Trend；
训练后酸痛和疲劳不能直接代表训练质量。
```

---

#### m\. Training Balance 的最终计算边界

Training Balance 的最终公式为：

```Plain Text
S_t = {training_event_i | event_i in rolling 7 days,
                          event_type = muscle_strengthening,
                          training_intensity >= moderate,
                          confidence_i >= threshold}

strength_days_7d = count_distinct_days(S_t)

covered_muscle_groups_7d = unique_major_muscle_groups(S_t)

coverage_ratio_t = count(covered_muscle_groups_7d) / 7

TrainingBalance_t
= 70 × min(strength_days_7d / 2, 1)
+ 30 × coverage_ratio_t
```

其中：

```Plain Text
Training Balance = 100
```

表示：

```Plain Text
最近 7 天内至少 2 天进行了肌肉强化活动；
并且最近 7 天内覆盖所有主要肌群。
```

最终结构：

```Plain Text
Training Balance = muscle-strengthening guideline compliance

Training Finish = user-goal completion layer

Training Volume = optional goal-specific training metric

Volume Load = optional exercise-level progression metric

Progressive Overload = optional long-term training progress metric

Session-RPE Load = optional subjective training load metric

ACWR = optional training strain insight, not medical prediction

Aerobic Activity Dose = Activity Agent
```

Training Balance 不能被解释为：

```Plain Text
用户训练质量
用户训练进步
用户绝对力量水平
用户肌肉增长效果
用户恢复状态
用户伤病风险预测
用户减脂效果
```

这些内容必须由其他指标或解释层处理。

---

## 6\.3 Activity Agent

### 6\.3\.1 Activity Agent 定义

Activity Agent 负责识别、记录和解释用户的日常运动行为。

在当前产品架构中，Activity Agent 对应的是 Daily Activity 下的“运动”，主要包括：

```Plain Text
步行
快走
慢跑
跑步
爬楼
主动通勤中的步行 / 骑行
其他可识别的中高强度移动类身体活动
```

Activity Agent 关注的是：

```Plain Text
用户最近一段时间的有氧身体活动剂量，是否接近公共健康指南推荐的水平。
```

Activity Agent 不负责评价训练计划、训练质量或训练完成度。

以下内容不在 Activity Agent 内处理：

```Plain Text
健身房力量训练
器械训练
训练计划完成度
训练负荷递进
训练表现
训练恢复
肌肉强化活动是否达标
```

这些内容已在 Training Agent 中单独定义。

需要特别说明：

```Plain Text
CDC / WHO 的完整身体活动建议包含两部分：

1. 有氧身体活动
2. 肌肉强化活动
```

由于 Relty 当前产品架构将“运动”和“训练”拆成两个 Agent，因此：

```Plain Text
Activity Agent 只处理有氧身体活动剂量。
Training Agent 后续处理肌肉强化活动与结构化训练。
```

因此，本节中的 Activity Balance 不是完整身体活动健康建议的全部，而是其中的 aerobic physical activity 部分。

当前章节主要定义：

```Plain Text
用户日常身体活动的识别方式
Activity Finish 的目标完成逻辑
Activity Balance 的有氧身体活动剂量计算方式
```

本节暂不讨论不同模块之间的数据共享、去重或跨模块合并问题。

当前只定义 Activity Agent 自身的 Balance 计算方式。

---

### 6\.3\.2 Activity Finish

Activity Finish 衡量用户在当前运动目标周期内的完成情况。

它表示：

```Plain Text
用户今天在自己设定的运动目标上推进了多少。
```

例如：

```Plain Text
用户目标：本周步行 5 天
用户目标：每天快走 30 分钟
用户目标：本周主动通勤 3 次
用户目标：每天饭后散步 15 分钟
```

Activity Finish 的具体算法后续单独定义。

需要注意：

```Plain Text
Activity Finish 不等于 Activity Balance。
Activity Finish 是用户目标完成度。
Activity Balance 是基于公共健康指南和身体活动剂量的客观计算。
```

---

### 6\.3\.3 Activity Balance

Activity Balance 用来衡量用户最近一段时间的有氧身体活动剂量，与成人身体活动公共健康建议之间的接近程度。

Activity Balance 不使用“步数”作为主计算依据。

Activity Balance 的核心计算单位是：

```Plain Text
MVPA MET-minutes / week
```

其中：

```Plain Text
MVPA = Moderate-to-Vigorous Physical Activity
MET = Metabolic Equivalent of Task
```

Activity Balance 的本质是：

```Plain Text
用户最近 7 天内的中高强度有氧身体活动
→ 转换为 MET-minutes
→ 与公共健康推荐基准比较
→ 得到 Activity Balance
```

Activity Balance 衡量的是：

```Plain Text
Aerobic Physical Activity Dose
有氧身体活动剂量
```

它不是：

```Plain Text
完整身体活动健康分
训练质量
训练效果
心肺适能
卡路里消耗
健身表现
训练计划完成度
肌肉强化活动达标情况
```

肌肉强化活动是 CDC / WHO 身体活动建议的一部分，但在 Relty 当前架构中，它属于 Training Agent 的计算范围，不进入 Activity Balance。

---

#### a\. Activity Balance 计算公式与分数定义

Activity Balance 使用 rolling 7 days 作为计算窗口。

$window_t = [t-6, t]$

定义：

$A_t = {activity_event_i \mid event_i \in window_t,\ estimated_MET_i \geq 3.0,\ confidence_i \geq threshold}$

其中：

```Plain Text
A_t = 最近 7 天内符合条件的 Activity events 集合
event_i = 第 i 个 Activity event
estimated_MET_i = 第 i 个活动事件的估计 MET
confidence_i = 第 i 个活动事件的识别置信度
threshold = 系统设定的最低置信度阈值
```

Activity Balance 只计算中高强度身体活动，即：

$estimated_MET_i \geq 3.0$

轻强度活动不进入 Activity Balance 主公式。

最近 7 天的 MVPA MET\-minutes 计算为：

$MVPA_METmin_{7d,t} = \sum_{i \in A_t} duration_i \times estimated_MET_i$

其中：

```Plain Text
duration_i = 第 i 个活动事件的持续分钟数
estimated_MET_i = 第 i 个活动事件的估计 MET
```

Activity Balance 原始值为：

$ActivityBalance_t = 100 \times \frac{MVPA_METmin_{7d,t}}{600}$

其中：

$600\ MET\text{-}min/week$

作为成人最低有氧身体活动推荐线的产品化基准。

600 MET\-min/week 的来源是：

$150\ min \times 4.0\ MET = 600\ MET\text{-}min/week$

以及：

$75\ min \times 8.0\ MET = 600\ MET\text{-}min/week$

也就是说：

```Plain Text
150 分钟中等强度活动 ≈ 600 MET-min/week
75 分钟高强度活动 ≈ 600 MET-min/week
```

因此：

$ActivityBalance_t = 100$

表示最近 7 天的有氧身体活动剂量达到最低公共健康推荐线。

如果：

$MVPA_METmin_{7d,t} = 1200$

则：

$ActivityBalance_t = 100 \times \frac{1200}{600} = 200$

即 Activity Balance = 200，约对应 WHO 推荐范围中的更高健康收益上限。

系统内部建议同时保留两个值：

$ActivityBalance_raw_t = 100 \times \frac{MVPA_METmin_{7d,t}}{600}$

$ActivityBalance_guideline_band_t = min(ActivityBalance_raw_t, 200)$

其中：

```Plain Text
ActivityBalance_raw_t = 真实身体活动剂量相对最低推荐线的倍数
ActivityBalance_guideline_band_t = 用于公共健康推荐范围解释的内部边界值
```

Activity Balance 不按百分制封顶。

因此不使用：

$ActivityBalance_t = min(100 \times \frac{MVPA_METmin_{7d,t}}{600}, 100)$

而使用：

$ActivityBalance_t = 100 \times \frac{MVPA_METmin_{7d,t}}{600}$

Activity Balance 可以超过 100。

但需要说明：

```Plain Text
100 对应最低推荐线。
200 对应更高健康收益推荐范围上限。
超过 200 可以记录，但不应继续线性解释为“越高越健康”。
```

---

#### b\. 科学依据与计量基础

Activity Balance 使用以下研究和指南作为依据：

1\. CDC Adult Physical Activity Guidelines
https://www\.cdc\.gov/physical\-activity\-basics/guidelines/adults\.html

2\. CDC Older Adult Activity Guidelines
https://www\.cdc\.gov/physical\-activity\-basics/guidelines/older\-adults\.html

3\. WHO 2020 Guidelines on Physical Activity and Sedentary Behaviour
https://pmc\.ncbi\.nlm\.nih\.gov/articles/PMC7719906/

4\. WHO Physical Activity Fact Sheet
https://www\.who\.int/news\-room/fact\-sheets/detail/physical\-activity

5\. 2024 Adult Compendium of Physical Activities
https://pmc\.ncbi\.nlm\.nih\.gov/articles/PMC10818145/

6\. IPAQ scoring protocol / MET\-minutes system
https://pmc\.ncbi\.nlm\.nih\.gov/articles/PMC2219963/

CDC 成人身体活动指南指出：

```Plain Text
成年人每周需要至少 150 分钟中等强度有氧活动，
或 75 分钟高强度有氧活动，
或二者的等量组合。

成年人还需要每周至少 2 天肌肉强化活动。
```

在 Relty 当前 Agent 架构中：

```Plain Text
150 分钟中等强度有氧活动 / 75 分钟高强度有氧活动
→ Activity Agent

每周至少 2 天肌肉强化活动
→ Training Agent
```

WHO 2020 指南进一步给出范围：

```Plain Text
成年人每周应进行 150–300 分钟中等强度有氧活动，
或 75–150 分钟高强度有氧活动，
或二者的等量组合。
```

WHO 2020 指南同时指出，不同年龄与特殊人群存在不同建议，包括：

```Plain Text
成年人
老年人
儿童和青少年
孕期 / 产后人群
慢性疾病人群
残障人群
```

当前 v0 版本暂时只处理一般成年人，不单独处理慢性疾病、孕期、残障等特殊情况。

老年人推荐中的 balance training、跌倒风险和功能性活动，也暂时不进入 Activity Agent 当前计算。

这些人群差异会作为后续优化目标。

Compendium of Physical Activities 提供了不同身体活动的标准化 MET 估计值，用于把不同类型活动转化为可比较的身体活动剂量。

IPAQ 体系中，身体活动常用：

```Plain Text
MET-minutes / week
```

作为连续计量单位。

因此，Activity Agent 不直接用“走了多少步”计算 Balance，而是用：

```Plain Text
活动持续时间 × 活动 MET
```

来计算最近 7 天的有氧身体活动剂量。

---

#### c\. 年龄与适用人群边界

Activity Balance 当前默认适用于：

```Plain Text
一般成年人
```

因为 CDC / WHO 的身体活动建议会根据年龄和特殊人群进行区分，所以 Activity Agent 需要读取用户初始化阶段输入的年龄信息。

当前 v0 处理方式：

```Plain Text
18–64 岁一般成年人：
使用成人有氧身体活动建议。

65 岁及以上老年人：
暂不单独调整 Activity Balance 公式。
后续应加入老年人专属建议，包括平衡活动与功能性活动。

慢性疾病、孕期 / 产后、残障、运动损伤或康复人群：
暂不单独调整 Activity Balance 公式。
后续根据指南扩展独立计算边界。
```

因此，当前公式不是对所有人群的最终版本，而是 v0 的一般成年人版本。

本公式依赖初始化阶段至少提供：

```Plain Text
年龄
```

后续如果要做更细分的活动强度解释、能量估计或个性化推荐，还会使用：

```Plain Text
身高
体重
sex
fitness level
主要目标
慢性疾病 / 孕期 / 受伤情况
```

其中，慢性疾病、孕期、受伤情况等只作为后续优化方向，当前 v0 不进入计算。

---

#### d\. 为什么不用步数作为主分

步数可以记录，但不适合作为 Activity Balance 的主计算方式。

原因：

```Plain Text
1. 10000 步不是 CDC / WHO 的正式身体活动推荐阈值。
2. 同样步数在不同速度、坡度、步幅、负重下，对身体刺激不同。
3. 步数无法覆盖骑行、爬楼、部分通勤活动等非步行活动。
4. 步数无法区分轻强度散步和中高强度快走。
```

因此产品结构应该是：

```Plain Text
Activity Balance = MVPA MET-minutes / week

Steps = explanation / trend
```

步数只能作为解释层和趋势信息，不进入 Activity Balance 主公式。

---

#### e\. MET 与活动强度分类

MET 是身体活动研究中常用的代谢当量单位。

```Plain Text
1 MET ≈ 安静坐着时的能量消耗
```

Activity Agent 按 estimated\_MET 对活动强度进行分类：

$estimated_MET_i < 3.0 \Rightarrow light$

$3.0 \leq estimated_MET_i < 6.0 \Rightarrow moderate$

$estimated_MET_i \geq 6.0 \Rightarrow vigorous$

对应伪代码为：

```Plain Text
if estimated_MET < 3.0:
    intensity = light

elif 3.0 <= estimated_MET < 6.0:
    intensity = moderate

elif estimated_MET >= 6.0:
    intensity = vigorous
```

Activity Balance 主分只计算：

```Plain Text
moderate
vigorous
```

不计算：

```Plain Text
light
unknown
low_confidence
```

轻强度活动可以记录，但不进入 Activity Balance 主计算。

---

#### f\. 计算时间窗口

Activity Balance 使用 rolling 7 days。

$window_t = [t-6, t]$

原因是 CDC / WHO 的成人身体活动建议都是按“每周”定义的。

因此，某一天的 Activity Balance 不是只看当天，而是看最近 7 天的累计有氧身体活动剂量。

---

#### g\. Activity Event 输入

每个被识别出的活动事件需要包含以下字段：

```JSON
{
  "event_id": "activity_001",
  "user_id": "user_001",
  "start_time": "2026-06-10T08:20:00",
  "end_time": "2026-06-10T08:45:00",
  "duration_minutes": 25,
  "activity_type": "brisk_walking",
  "estimated_MET": 3.8,
  "intensity_class": "moderate",
  "confidence": 0.86,
  "source": ["imu", "location", "vision"]
}
```

核心字段：

```Plain Text
duration_minutes
activity_type
estimated_MET
intensity_class
confidence
```

其中：

```Plain Text
duration_minutes 用于计算活动时长。
activity_type 用于标记活动类型。
estimated_MET 用于计算身体活动剂量。
intensity_class 用于判断是否进入 MVPA。
confidence 用于过滤低置信度事件。
```

Activity Agent 不需要在自身事件中打：

```Plain Text
is_structured_training = true / false
```

这个字段会把 Activity Agent 和 Training Agent 的边界处理前置到单个事件内，容易造成判断混乱。

当前阶段，Activity Agent 只对自身识别到的运动事件负责；跨 Agent 的共享、合并和去重问题后续单独讨论。

---

#### h\. 示例计算

用户最近 7 天 Activity events：

```Plain Text
快走 40 分钟，MET = 3.8
快走 30 分钟，MET = 3.8
慢跑 25 分钟，MET = 7.0
步行通勤 50 分钟，MET = 3.3
```

计算：

$MVPA_METmin_{7d,t}
= 40 \times 3.8$

- 30 \\times 3\.8

- 25 \\times 7\.0

- 50 \\times 3\.3
 

$MVPA_METmin_{7d,t}
= 152 + 114 + 175 + 165$

$MVPA_METmin_{7d,t} = 606$

Activity Balance：

$ActivityBalance_t
= 100 \times \frac{606}{600}
= 101$

---

#### i\. 不进入 Activity Balance 的变量

不进入 Activity Balance 的内容：

```Plain Text
步数
总运动时间
轻强度活动时间
总热量消耗
站立时长
通勤总时长
肌肉强化活动
训练计划完成度
用户减脂目标
用户跑步配速目标
训练后的主观感受
```

原因：

```Plain Text
步数不是 CDC / WHO 的正式身体活动推荐主标准；
总运动时间不区分强度；
轻强度活动可以记录，但不进入 MVPA 主计算；
热量消耗估计误差大；
通勤本身不是健康活动，只有其中的主动移动部分可以进入 Activity；
肌肉强化活动属于完整身体活动建议的一部分，但在 Relty 当前架构中由 Training Agent 处理；
减脂、配速、训练表现属于 Finish 或 Training，不属于 Activity Balance。
```

---

#### j\. Activity Balance 的最终计算边界

Activity Balance 只衡量 Activity Agent 识别到的有氧身体活动剂量。

最终结构：

```Plain Text
Activity Balance = MVPA MET-minutes / week based aerobic physical activity dose

Steps = independent explanatory layer

Light Activity = independent explanatory layer

Sedentary Time = independent flag / trend layer

Active Commute = can contribute to Activity Balance if MET >= 3.0

Muscle-strengthening Activity = handled by Training Agent

Activity Finish = user-goal completion layer
```

Activity Balance 不能被解释为：

```Plain Text
完整身体活动健康分
用户训练质量
用户训练进步
用户心肺适能
用户恢复状态
用户消耗热量
用户减脂效果
肌肉强化活动达标情况
```

这些内容必须由其他 Agent 或解释层处理。

---

### 6\.3\.4 Activity Balance 的最终计算边界

Activity Balance 的最终公式为：

$A_t = {activity_event_i \mid event_i \in rolling\ 7\ days,\ estimated_MET_i \geq 3.0,\ confidence_i \geq threshold}$

$MVPA_METmin_{7d,t} = \sum_{i \in A_t} duration_i \times estimated_MET_i$

$ActivityBalance_t = 100 \times \frac{MVPA_METmin_{7d,t}}{600}$

系统内部可额外保留：

$ActivityBalance_guideline_band_t = min(ActivityBalance_t, 200)$

不进入 Activity Balance 的内容：

```Plain Text
肌肉强化活动
训练计划完成度
力量训练质量
训练负荷
步数
热量消耗
轻强度活动
用户运动目标
用户体重目标
用户主观疲劳
```

这些可以作为解释层、趋势层或 Activity Finish / Training Finish 的目标完成层，但不能进入 Activity Balance 主计算。

最终结构：

```Plain Text
Activity Balance = MVPA MET-minutes / week

Activity Trend = steps / light activity / active commute / weekly distribution

Activity Finish = user-goal completion layer

Muscle-strengthening Activity = Training Agent

Training = separate agent
```

## 6\.4 Focus Agent

---

## 6\.5 Relax Agent

---

## 6\.6 Rest Agent

---

## 6\.7 Commute Agent

---

# Daily Brief 输出原则

Relty Home 不应直接展示所有原始数据。

Home 应该输出 Daily Brief。

Daily Brief 的目标是：

```Plain Text
用少量信息回答：
今天用户的生活状态有什么值得注意？
为什么？
下一步可以做什么？
```

Daily Brief 不应该是：

```Plain Text
你今天走了多少步
你吃了多少卡路里
你坐了多久
你工作了多久
你社交了多久
```

而应该是：

```Plain Text
你的饮食结构接近健康模式，但晚间进食偏晚。
你本周身体活动量接近建议标准，但力量训练还不足。
你今天的工作块比平时更碎片化，且休息时间较少。
```

---

## 7\.1 Daily Brief 信息优先级

Daily Brief 只展示 1–3 个重点。

优先级排序：

```Plain Text
1. 高置信度健康风险
2. 有科学依据的 Balance 变化
3. 与用户目标相关的 Finish 进展
4. 明显偏离用户近期基线的生活节奏变化
5. 普通趋势洞察
```

---

## 7\.2 Daily Brief 标准格式

```JSON
{
  "daily_brief": {
    "main_status": "待补",
    "summary": "待补",
    "highlights": [
      {
        "agent": "Diet",
        "type": "balance / flag / insight / finish",
        "priority": "high / medium / low",
        "title": "待补",
        "reason": "待补",
        "action": "待补"
      }
    ]
  }
}
```

---

# 数据置信度原则

所有 Agent 输出都必须带置信度。

```Plain Text
confidence = high / medium / low
```

展示规则：

低置信度信号不能制造焦虑。

---

