# Diet vs Fitness Agent 交接差异对照

## 1. 一句话判断

Diet Agent 的交接文档体系更像一个已经形成产品方法论的 Agent 文档包：

```text
总框架
→ Agent 定位
→ Balance / Finish 边界
→ Learning Period
→ 研发结构化输入
→ 指标计算
→ 输出解释
```

Fitness Agent 当前的交接更像一个方向正确、素材不少、但仍偏“项目推进说明”的文档包：

```text
模块背景
→ 当前进展
→ 数据采集
→ 动作识别
→ IMU 辅助
→ Fitness Balance 候选公式
→ 后续建议
```

所以两边最大的区别不是“想法谁更好”，而是：

```text
Diet 更像完整产品框架
Fitness 更像阶段性工作交接
```

---

## 2. 核心区别

### 2.1 Diet 有总框架，Fitness 缺总框架

Diet 有一份总指标框架文档，先定义 Relty 各类 Daily Activity Agent 的统一方法，再落到 Diet 本身。

关键特点：

1. 先讲 Relty 为什么需要 Balance / Finish。
2. 先讲什么能进 Balance，什么不能进 Balance。
3. 先讲 Finish 是什么，以及与 Balance 的关系。
4. 先讲 Learning Period、baseline、gap、goal suggestion。
5. 再落到 Diet Agent 的具体实现。

对应证据：

- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:11>) 明确说这是各类 Daily Activity Agent 的统一指标计算框架。
- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:142>) 定义了 Learning Period。
- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:203>) 明确写了 `Balance / Pattern 负责发现问题；Finish 负责把问题转换成用户确认后的阶段性目标完成度`。

Fitness 没有对应层级的总框架。它直接从“健身模块背景、数据采集、动作识别、IMU、Balance”开始讲，缺少以下上位定义：

1. Fitness Agent 在 Relty 全局指标体系中的位置。
2. Fitness Balance 和 Fitness Finish 的关系。
3. 是否有 Learning Period。
4. Goal 从哪里来。
5. 哪些内容属于 Balance，哪些属于 Finish，哪些只是解释层/趋势层。

对应证据：

- [健身模块产品文档.md](/Users/maxgao/Documents/交接文件/健身模块产品文档.md:43) 直接进入首页结构和训练报告定位。
- [健身模块产品文档.md](/Users/maxgao/Documents/交接文件/健身模块产品文档.md:89) 直接进入 Fitness Balance 说明。

### 2.2 Diet 把 Balance 和 Finish 分得很开，Fitness 目前只讲了 Balance

Diet 的文档体系里，Balance 和 Finish 是明确分开的两个层。

对应证据：

- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:93>) 开始系统定义 Finish。
- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:510>) 明确写 `Finish 和 Balance 必须分开`。
- [Diet Agent 进度文档.md](</Users/maxgao/Documents/dietagent交接/Diet Agent 进度文档.md:47>) 单独讨论 Goal / Finish 的创建方式。

Fitness 文档里虽然提到“计划”“下一次训练建议”，但没有把 Goal / Finish 单独抽出来讲。

结果是：

1. Fitness Balance 承担了太多“解释、建议、目标偏好”的角色。
2. 用户目标完成度这一层没有被正式定义。
3. 训练频率、训练量、连续推进这类东西，有一部分被塞进 Balance 里了。

这会让 fitness 看起来更像：

```text
一个训练理解分 + 一些建议
```

而不是：

```text
Balance 解释客观训练结构
+ Finish 解释目标完成度
```

### 2.3 Diet 有 Learning Period，Fitness 没有

Diet 很重要的一点是：目标不是让用户凭空填写，而是系统先学用户 baseline，再推荐 goal template。

对应证据：

- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:151>) `Agent activation → Learning Period → Baseline generation → Gap analysis → Goal suggestion → User confirmation → Finish tracking`
- [Relty 指标计算框架.md](</Users/maxgao/Documents/dietagent交接/Relty 指标计算框架.md:190>) 明确写 `Finish 的目标不应完全由用户自由创建`
- [Diet Agent 进度文档.md](</Users/maxgao/Documents/dietagent交接/Diet Agent 进度文档.md:59>) 明确倾向于引导或模板化 goal

Fitness 这边没有对应机制。

目前 Fitness 更像：

```text
训练后识别
→ 给报告
→ 给建议
```

缺失的是：

1. 首次开启后先学用户训练 baseline。
2. 基于 baseline 识别 gap。
3. 把 gap 转成可确认的训练 goal。
4. 再计算 Fitness Finish。

这会导致 Fitness 的“计划”看起来有点悬空，因为还没有讲清楚：

```text
这个计划是从用户历史里学出来的
还是模型临时生成的
还是用户自己设的
```

### 2.4 Diet 有清楚的研发输入定义，Fitness 还停留在思路级

Diet 不只是讲公式，还专门写了一份“研发需要补什么结构化输出”的文档。

对应证据：

- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:7>) 先定义本阶段研发任务。
- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:30>) 明确说本阶段不是改公式，而是补齐公式所需结构化输入。
- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:168>) 给出目标 JSON 结构。

Fitness 这边虽然也提到固定模型输入格式：

- [健身模块产品文档.md](/Users/maxgao/Documents/交接文件/健身模块产品文档.md:349)

但它没有像 Diet 那样，单独把研发结构化输入写成一份规范，例如：

1. timeline 必须输出哪些字段。
2. 动作候选、器械候选、肌群候选的 schema。
3. low confidence 怎么表示。
4. 缺失数据是 `0`、`null` 还是 `unknown`。
5. 用户确认如何回流。

也就是说，Diet 是：

```text
公式要什么输入
→ 研发补什么字段
→ 字段长什么样
```

Fitness 现在更像：

```text
我们应该有视频、IMU、计划、候选动作
```

少了工程接口层。

### 2.5 Diet 的边界感更强，Fitness 的边界还比较松

Diet 文档一直在强调：

1. 哪些能进 Balance。
2. 哪些不能进 Balance。
3. 哪些先不做。
4. 哪些属于解释层，不属于主分。
5. 低置信度怎么处理。

对应证据：

- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:88>) 明确哪些指标暂时不处理。
- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:126>) 定义完整记录时缺失应记 0。
- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:148>) 定义不确定时输出 `range + confidence`。

Fitness 也有边界意识，但更多停留在口头提醒：

- [健身模块产品文档.md](/Users/maxgao/Documents/交接文件/健身模块产品文档.md:437) 不要过早承诺高精度组数/次数
- [健身模块产品文档.md](/Users/maxgao/Documents/交接文件/健身模块产品文档.md:439) 不要包装成专业教练替代品

问题在于，Fitness 还没有把这些边界翻译成结构化规则，例如：

1. 低置信度动作什么时候不进 Fitness Balance。
2. cardio-only session 的标准状态。
3. 同一动作识别不清时如何 fallback 到动作家族。
4. “组数不可信但动作可信”时怎么计算 exercise_unit。

### 2.6 Diet 文档更像 PM 写给跨团队协作，Fitness 更像前同事写给接手人

Diet 的文风很像标准 PM 协作文档：

1. 先写文档目的。
2. 先定义边界。
3. 再定义本阶段目标。
4. 再定义研发要补的字段。
5. 用结构化 JSON 讲清楚接口。

Fitness 文风更像阶段性交接 memo：

1. 我们现在做到了什么。
2. 遇到了什么问题。
3. 接手人下一步先做什么。
4. 我个人建议是什么。

对应证据：

- [Diet Recognition 研发需求.md](</Users/maxgao/Documents/dietagent交接/diet_balance_test/Diet Recognition 研发需求.md:5>) 从“文档目的”开始。
- [健身模块产品文档.md](/Users/maxgao/Documents/交接文件/健身模块产品文档.md:449) 有明显的“我个人的建议”段落。

这个差异不是坏事，但会影响落地效果：

```text
Diet 文档更适合直接给研发/算法/设计对齐
Fitness 文档更适合帮助新人理解现状
```

---

## 3. Fitness 当前没对上的地方

### 3.1 没对上 Relty 的统一 Agent 语言

Fitness 没有完整对上这些 Diet 已经建立的统一概念：

1. Balance
2. Finish
3. Learning Period
4. Baseline
5. Gap Analysis
6. Goal Suggestion
7. User Confirmation
8. Finish Tracking

这意味着它目前更像“健身模块”，还不完全像一个成熟的“Fitness Agent”。

### 3.2 没对上 Goal 的定义方式

Diet 已经明确：

```text
目标不应该完全由用户自由创建
而是系统根据学习期和 gap 推荐模板
```

Fitness 还没有明确：

1. 用户训练目标从哪里来。
2. 训练计划是模板化、引导式还是自由创建。
3. 周目标、阶段目标、单次训练计划是什么关系。
4. “完成一次计划”属于 Finish 还是 Balance。

### 3.3 没对上研发输入的颗粒度

Diet 已经到：

```text
哪个字段必须输出
哪个字段不确定时怎么表示
缺失值怎么处理
JSON schema 长什么样
```

Fitness 还主要停留在：

```text
应该结合图片序列、IMU、计划、动作候补
```

差了一层真正能开工的“structured output spec”。

### 3.4 没对上低置信度和缺失值规范

Diet 很清楚：

1. 全天记录完整但没识别到某类食物，记 0。
2. 不确定时保留字段，给 confidence，而不是直接删掉。

Fitness 没把类似规则写清楚，比如：

1. cardio-only 记什么状态。
2. low confidence 记什么状态。
3. 动作不确定但肌群大类可信，怎么记。
4. rep_count 不确定时，是 `null`、候选值，还是不出。

### 3.5 没对上“指标依赖什么输入”这件事

Diet 文档会先说：

```text
当前能识别什么
这些只能支持什么
还不能支持什么
因此要补哪些输入字段
```

Fitness 还没有把这条链路彻底写透。

例如它已经有 Balance v4，但尚未把以下依赖完全展开：

1. 动作到肌群映射表谁来维护。
2. 置信度、组数可信度、duration、user confirmation 如何进入公式。
3. 什么时候一段训练算有效 strength exercise。
4. 动作库和 7 大肌群如何一一对齐。

---

## 4. 风格差异总结

如果用一句话概括文风差异：

```text
Diet 是“产品系统设计文档”
Fitness 是“产品推进交接文档”
```

具体表现：

| 维度 | Diet Agent | Fitness Agent |
|---|---|---|
| 上位框架 | 强 | 弱 |
| Balance / Finish 边界 | 清楚 | 基本只写了 Balance |
| Goal 来源 | 清楚 | 模糊 |
| Learning Period | 有 | 没写 |
| 研发结构化输入 | 很强 | 较弱 |
| 数据字段规范 | 很细 | 主要是方向 |
| 边界状态 | 清楚 | 提醒多、规则少 |
| 文风 | 方法论 + 协作文档 | 交接 memo + 推进建议 |
| 可直接给研发开工程度 | 高 | 中 |

---

## 5. 对 Fitness 的修正建议

如果要把 Fitness 对齐到 Diet 的风格，建议补 5 份东西：

1. 一份 `Fitness Agent 指标框架`  
   明确 Fitness Balance、Fitness Finish、Training Trend、Coach Insight 的边界。

2. 一份 `Fitness Goal / Finish 设计文档`  
   明确 Learning Period、baseline、goal suggestion、user confirmation、finish tracking。

3. 一份 `Fitness Recognition Structured Output`  
   定义 timeline、action candidate、equipment candidate、muscle group、confidence、coverage flags、user confirmation fields 的 schema。

4. 一份 `Fitness Balance 输入字段说明`  
   把公式依赖拆成研发可实现字段，而不是只保留公式说明。

5. 一份 `Fitness 状态与边界规范`  
   明确 `active / low_confidence / cardio_only_session / insufficient_strength_data / not_in_overall_balance` 的触发条件。

---

## 6. 最关键的判断

Diet Agent 的成熟度高，不只是因为它公式更多，而是因为它已经形成了一套：

```text
产品概念
→ 指标边界
→ 目标机制
→ 数据输入
→ 结构化输出
→ 解释口径
```

Fitness Agent 现在最大的问题不是方向错，而是还停在：

```text
识别和公式都在推进
但 Agent 级产品框架还没完全立起来
```

这也是为什么你会明显感觉两边“风格不一样”。

