# Diet Balance Baseline AI 协作工作流

## 0. 目标

本工作流用于让 Codex 和 Claude Code 围绕 Diet Balance Baseline 进行低幻觉协作。

当前目标不是定义 Goal，也不是重写旧 PRD。当前目标是：

```text
定义 Diet Balance Baseline 应该由哪些可观测指标构成；
让 baseline 能学习用户一周饮食曲线；
让 baseline 能模拟用户特异性；
为后续 Diet Balance 公式个体化计算提供标准。
```

最终产物应是一份候选 baseline 指标定义，而不是公式实现。

---

## 1. 共同背景

### 1.1 当前项目里 Diet Balance 的状态

当前计算器仍以绝对公式为主：

```text
Diet Balance =
0.40 * HEI_2020_available
+ 0.15 * AMDR_Fit
+ 0.20 * RDA_AI_Adequacy
+ 0.10 * Meal_Timing
+ 0.15 * Kcal_Balance
```

当前公式的问题：

```text
它能表达“是否接近健康参考标准”；
但还不能表达“这个判断对某个具体用户是否合理”；
也不能充分理解用户自己的曲线、波动范围和长期饮食特异性。
```

所以 baseline 的意义是：

```text
把 Diet Balance 从固定绝对标准，
推进到“科学标准 + 用户自身曲线”的个性化状态判断。
```

### 1.2 Baseline 的当前定义

来自现有文件 `Diet Balance Baseline 新版PRD.md`：

```text
Diet Baseline 是 Diet Agent 在一周学习期内，
对用户饮食基础状态和变化曲线的摸排结果。

它不是目标，也不是分数。

它是后续 Diet Balance 个性化计算的用户参照系。
```

学习期：

```text
7 days
valid_record_days >= 5
complete_day_records >= 3
average_daily_confidence >= medium
```

目前候选 baseline 维度：

```text
1. 用户代谢画像
2. 能量摄入曲线
3. 餐次与时间节律曲线
4. 宏量营养结构
5. 食物结构与 HEI / DQD 相关字段
6. 识别完整度与置信度
```

---

## 2. WHOOP Recovery 可借鉴的方法论

只借鉴方法论，不复刻其运动恢复算法。

根据 WHOOP 官方说明，Recovery 是每天早上计算的 readiness 百分比，用于表示身体对应激源后的恢复和当天可承受负荷。WHOOP 把 Recovery 分为 green / yellow / red zones，并把 HRV、静息心率、睡眠表现和呼吸频率纳入计算。WHOOP 也明确说没有单一“正确”的 Recovery score，因为它高度个人化。

参考：

- WHOOP Recovery Explained: https://www.whoop.com/us/en/thelocker/how-does-whoop-recovery-work-101/
- WHOOP HRV article: https://www.whoop.com/us/en/thelocker/heart-rate-variability-hrv/

可迁移到 Diet Balance Baseline 的原则：

```text
1. 不只看群体标准，也看个人长期曲线。
2. 关键指标必须在相对稳定的观察窗口内测量。
3. 今日状态需要和本人 baseline 比较，而不是只和平均人比较。
4. baseline 需要输出置信度。
5. baseline 可以解释个体差异，但不能把不健康常态合理化。
6. 单日异常不应被过度解释，连续趋势更重要。
```

---

## 3. 协作原则

### 3.1 防幻觉规则

Codex 和 Claude Code 都必须遵守：

```text
1. 每一个事实判断必须标注来源类型：
   - local_file
   - calculated_from_local_data
   - external_source
   - inference
   - assumption

2. 不允许把 assumption 写成 fact。

3. 不允许发明 WHOOP、HEI、RDA、AMDR 的具体公式。

4. 如果引用外部资料，必须给出链接和一句话摘要。

5. 如果基于本项目文件得出结论，必须写出文件名和相关字段。

6. 如果提出候选指标，必须说明：
   - 为什么需要它；
   - 数据从哪里来；
   - 是否可在 7 天内可靠估计；
   - 是否会影响公式；
   - 可能的误判风险。
```

### 3.2 输出格式要求

每轮讨论都用以下格式：

```markdown
## Claim
一句话结论。

## Evidence
- source_type:
- source:
- evidence:

## Reasoning
为什么这个证据支持该结论。

## Risk
可能的幻觉、偏差或产品风险。

## Open Question
需要对方挑战或补充的问题。
```

---

## 4. 角色分工

### 4.1 Codex 角色

Codex 负责：

```text
1. 阅读本地项目文件。
2. 汇总当前 Diet Balance 计算器已有字段。
3. 找出现有 test_sets 中已经具备的数据。
4. 判断候选 baseline 指标是否能从现有数据生成。
5. 设计可验证的数据表和 schema 草案。
6. 挑战 Claude 提出的不可落地指标。
```

Codex 不负责：

```text
1. 空想最终公式；
2. 发明没有数据来源的指标；
3. 定义 Goal 子模块；
4. 直接改公式。
```

### 4.2 Claude Code 角色

Claude Code 负责：

```text
1. 从产品/指标建模角度挑战 baseline 定义。
2. 对照 WHOOP Recovery 的个体化思路，抽象可迁移原则。
3. 检查 baseline 是否能体现用户特异性。
4. 检查 baseline 是否会把不健康常态合理化。
5. 提出更好的指标分层、风险边界和命名。
6. 挑战 Codex 的工程落地假设。
```

Claude Code 不负责：

```text
1. 编造本地数据；
2. 声称某指标已存在，除非 Codex 提供本地证据；
3. 展开 Goal/Finish；
4. 直接给公式权重定案。
```

---

## 5. 推荐讨论轮次

### Round 1: 事实盘点

目标：

```text
确认项目当前 Diet Balance 已有什么字段、缺什么字段。
```

Codex 输出：

```text
本地文件事实表：
- calculator fields
- test_sets fields
- output fields
- existing formula
- current baseline PRD fields
```

Claude 输出：

```text
基于 Codex 事实表，指出哪些字段足以定义 baseline，哪些还只是愿望。
```

### Round 2: WHOOP 方法论迁移

目标：

```text
明确 WHOOP Recovery 中哪些原则能迁移到 Diet Balance Baseline。
```

Claude 输出：

```text
WHOOP-like baseline principles:
- personal normal range
- trend over single day
- readiness/state zone
- confidence
- behavior impact
- guardrails
```

Codex 输出：

```text
这些原则在本地数据中如何映射：
- 哪些能做
- 哪些要补数据
- 哪些不能做
```

### Round 3: Baseline 候选指标矩阵

目标：

```text
把 baseline 指标拆成必选、可选、暂不做。
```

统一输出表：

```markdown
| 指标 | 层级 | 数据来源 | 7天可估计性 | 影响哪个 Balance 模块 | 风险 | 优先级 |
|---|---|---|---|---|---|---|
```

层级建议：

```text
core_baseline: 必须有，否则 baseline 不成立
context_baseline: 用于个性化解释
quality_baseline: 用于判断 baseline 是否可信
future_baseline: 有价值但暂不进入 v0
```

### Round 4: 反例压力测试

目标：

```text
防止 baseline 定义看起来漂亮，但实际会误导。
```

必须测试这些用户类型：

```text
1. 长期吃得很差，但突然一天稍好
2. 长期吃得很好，但一天偏离
3. 记录不完整，只记录健康餐
4. 热量接近目标，但食物结构很差
5. 食物结构不错，但总热量严重过高
6. 减脂用户和增肌用户热量解释不同
7. 周末饮食和工作日饮食差异很大
```

每个反例都问：

```text
baseline 应该如何解释？
是否允许提高 Balance？
是否只允许改变解释，不改变分数？
是否需要置信度降级？
```

### Round 5: 收敛 baseline v0

目标：

```text
产出一版 baseline v0 指标定义，不碰公式。
```

最终输出：

```text
1. Baseline v0 定义
2. Baseline v0 指标清单
3. 每个指标的数据来源
4. 每个指标的可靠性条件
5. 每个指标将来可能影响的公式模块
6. 不进入 v0 的指标
7. 未解决问题
```

---

## 6. 给 Codex 的 Prompt

```text
你是 Codex，当前任务不是写代码，而是作为 repo-grounded analyst 参与 Diet Balance Baseline 定义讨论。

请先阅读以下本地文件：
- Diet Balance Baseline 新版PRD.md
- relty_diet_balance_calculator_kcal.ps1
- relty_diet_balance_calculator.ps1
- test_sets/testset_master_all.json
- outputs/testset_master_all.diet_balance_kcal_results.json
- outputs/testset_master_all.diet_balance_kcal_summary.csv
- CHANGELOG_diet_balance_calculator.md

当前产品方向：
- 不再修旧 PRD。
- 不定义 Goal 子模块。
- 不展开 Finish。
- 当前 focus 是 Diet Balance。
- 下一步要定义 Diet Balance Baseline。
- Baseline 是一周学习期对用户基础情况和曲线的摸排。
- Baseline 后续会影响 Diet Balance 公式，所以 baseline 指标必须足够可靠、可解释、可落地。
- 希望参考 WHOOP Recovery 的个体化 baseline 思路：学习用户自己的曲线，模拟用户特异性，再用于当天状态判断。

你的任务：
1. 只基于本地文件整理当前项目事实，不要猜。
2. 输出当前 Diet Balance 公式、输入字段、输出字段、测试集中已有字段。
3. 判断现有数据能否支持以下 baseline 维度：
   - 用户代谢画像
   - 能量摄入曲线
   - 餐次与时间节律
   - 宏量营养结构
   - 食物结构/HEI/DQD 字段
   - 数据完整度与置信度
4. 对每个候选 baseline 指标输出：
   - source_type
   - local source file
   - field path
   - 是否现有数据可计算
   - 7 天学习期是否足够
   - 可能影响哪个 Diet Balance 模块
   - 风险
5. 不要定义公式权重。
6. 不要定义 Goal/Finish。
7. 把所有 assumption 单独列出来。

输出格式：

## Repo Facts
## Current Diet Balance Understanding
## Candidate Baseline Metrics Matrix
## Data Gaps
## Risks
## Questions for Claude
```

---

## 7. 给 Claude Code 的 Prompt

```text
你是 Claude Code，当前任务不是写代码，而是作为 product/scoring-model critic 参与 Diet Balance Baseline 定义讨论。

你需要基于 Codex 提供的 repo facts 进行分析。不要声称本地文件中存在某字段，除非 Codex 已经提供证据。

产品方向：
- 当前 focus 是 Diet Balance，不是 Goal。
- 不定义 Goal 子模块。
- 不展开 Finish。
- Baseline 是一周学习期对用户饮食基础状态和曲线的摸排。
- Baseline 后续会影响 Diet Balance 公式，所以指标定义必须严谨。
- 参考 WHOOP Recovery 的方法论：先学习个人常态，再判断当天相对本人常态的状态；但不能把不健康常态合理化。

你需要做：
1. 抽象 WHOOP Recovery 方法论中可迁移到 Diet Balance Baseline 的原则。
2. 挑战 Codex 的候选 baseline 指标：
   - 是否真的能表达用户特异性？
   - 是否只是绝对标准换了个名字？
   - 是否会奖励不健康常态？
   - 是否能在 7 天内可靠估计？
   - 是否存在记录不完整导致的偏差？
3. 提出 baseline v0 的指标分层：
   - core_baseline
   - context_baseline
   - quality_baseline
   - future_baseline
4. 对每个指标给出产品解释：
   - 它描述用户哪种曲线？
   - 它为什么会影响 Diet Balance？
   - 它应该只影响解释，还是未来可能影响公式？
5. 不要写具体公式权重。
6. 不要定义 Goal/Finish。

输出格式：

## Transferable WHOOP Principles
## Critique of Candidate Metrics
## Proposed Baseline Layers
## Anti-Hallucination Checks
## Red-Team Scenarios
## Questions for Codex
```

---

## 8. 仲裁 Prompt

这一轮用于把 Codex 和 Claude 的讨论收敛成一版 baseline v0。

```text
你现在是仲裁者。请整合 Codex 的 repo-grounded facts 和 Claude 的 product/model critique。

目标：
输出 Diet Balance Baseline v0 的候选定义。

硬性约束：
- 不定义 Goal。
- 不展开 Finish。
- 不写最终公式权重。
- 不把 assumption 写成 fact。
- 每个指标必须有数据来源或明确标为 future。
- 每个指标必须说明是否能在 7 天学习期内可靠估计。
- baseline 可以学习个人常态，但不能把不健康常态合理化。

请输出：
1. Baseline v0 一句话定义
2. Baseline v0 指标分层
3. core_baseline 指标表
4. context_baseline 指标表
5. quality_baseline 指标表
6. future_baseline 指标表
7. Red-team 场景下的处理原则
8. 尚未决策的问题

所有指标表必须包含：
- metric_id
- human_name
- source_type
- source_field
- learning_window
- reliability_condition
- user_specificity_signal
- possible_balance_module_affected
- risk
- v0_status
```

---

## 9. 我当前对 Diet Balance Baseline 的理解

Diet Balance 不应该被 baseline 完全替代。

更合理的理解是：

```text
Diet Balance = 健康参考标准下的饮食状态判断
Diet Baseline = 用户自身饮食常态与曲线
Personalized Diet Balance = 在健康参考标准约束下，理解用户自身曲线后的状态判断
```

Baseline 不是：

```text
目标；
任务；
完成度；
奖励系统；
用户想做什么。
```

Baseline 是：

```text
这个用户通常怎么吃；
这个用户的饮食曲线有多稳定；
这个用户今天是否偏离本人常态；
这个用户是否正在朝更健康的参考方向变化；
这个判断的置信度有多高。
```

最关键的设计难点：

```text
既要学习用户特异性，
又不能把用户长期不健康状态当作健康标准。
```

所以 baseline 应该有两条轴：

```text
1. personal-normal axis
   今天相对本人常态如何？

2. health-reference axis
   本人常态和今天状态相对健康参考标准如何？
```

只有这两条轴同时存在，后续公式才不会滑向两个极端：

```text
只看绝对标准 → 不够个性化；
只看个人 baseline → 容易把坏习惯正常化。
```

---

## 10. 建议优先争论的问题

让 Codex 和 Claude 先集中讨论这 8 个问题：

```text
1. 7 天是否足以建立 Diet Baseline？哪些指标足够，哪些不够？
2. baseline 应该输出“个人常态区间”，还是只输出均值/中位数？
3. 哪些指标必须有 health-reference anchor？
4. 哪些指标只适合解释，不适合进入公式？
5. 如何处理不完整记录和只记录健康餐的问题？
6. 如何处理“长期不健康但稳定”的用户？
7. 如何区分工作日 baseline 和周末 baseline？
8. baseline_confidence 应该由哪些数据质量指标决定？
```

---

## 11. 推荐最终产物文件

建议最终让 AI 产出：

```text
Diet Balance Baseline v0 指标定义.md
Diet Balance Baseline v0 指标矩阵.csv
Diet Balance Baseline Red-Team Cases.md
Diet Balance Baseline Open Questions.md
```

这些产物先用于讨论和产品判断，不直接进入计算器实现。
