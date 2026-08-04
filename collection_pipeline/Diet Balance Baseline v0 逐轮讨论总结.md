# Diet Balance Baseline v0 逐轮讨论总结

这个文件按协作轮次总结 Codex 和 Claude/CC 的讨论过程。它不是逐字转录，也不是内部思维链，而是每一轮可复盘的观点、挑战、回应和收敛结果。

原始轮次记录在：

- `ai_collab/diet_balance_baseline/CODEX_OUT.md`
- `ai_collab/diet_balance_baseline/CLAUDE_OUT.md`
- `ai_collab/diet_balance_baseline/DECISIONS.md`

## Round 0：协作机制与边界

### 用户目标

用户希望 Codex 和 Claude/CC 围绕 Diet Balance Baseline 自动化协作，而不是每次手动提醒对方去看文件。

### 协作机制

建立了文件式交接机制：

- `STATUS.md`：记录当前轮次、状态、当前 owner、next owner。
- `CODEX_OUT.md`：Codex 写自己的事实核查和工程判断。
- `CLAUDE_OUT.md`：Claude/CC 写自己的产品批判和模型判断。
- `DECISIONS.md`：沉淀双方共识。

### 分工

Codex 负责：

- 读 repo；
- 查本地数据结构；
- 判断字段是否存在；
- 判断方案是否可实现；
- 防止把不存在的数据当事实。

Claude/CC 负责：

- 做产品/模型批判；
- 挑出误导性指标；
- 做 red-team；
- 判断方案是否会产生错误激励。

### 总约束

双方一开始锁定：

- 不定义 Goal。
- 不展开 Finish。
- 不确定最终公式权重。
- 不把当前单日测试集伪装成 baseline。
- 不把 personal-normal 当成健康标准。

## Round 1：Codex 首轮事实核查

### Codex 做了什么

Codex 读取了：

- `Diet Balance Baseline 新版PRD.md`
- `references/relty_diet_balance_calculator_kcal.ps1`
- `references/relty_diet_balance_calculator.ps1`
- `references/test_sets/testset_master_all.json`
- `references/outputs/testset_master_all.diet_balance_kcal_results.json`
- `references/outputs/testset_master_all.diet_balance_kcal_summary.csv`
- `references/CHANGELOG_diet_balance_calculator.md`

### Codex 的主要发现

1. 当前 master test set 有 24 条用户日记录。
2. 这 24 条是不同用户/不同场景的单日记录，不是同一用户连续 7 天记录。
3. 20 条是 complete full-day record，4 条是不完整记录。
4. 当前 kcal 版 Diet Balance 公式是五模块：
   - `HEI_2020_available`
   - `AMDR_Fit`
   - `RDA_AI_Adequacy`
   - `Meal_Timing`
   - `Kcal_Balance`
5. `Meal_Timing` 当前是 placeholder，固定 100。
6. 当前数据有单日健康参考计算能力，但没有真实 baseline 所需的纵向数据。

### Codex 的首轮判断

Codex 提出候选 baseline 指标矩阵，并把指标分成：

- 当前本地文件已有；
- 可以从本地数据计算；
- 需要未来纵向 schema；
- 风险较高、不能进入 v0。

### Codex 问 Claude 的问题

Codex 让 Claude 判断：

- 哪些健康参考锚点必须保留；
- HEI components 应该算 baseline 还是 health-reference；
- 7 天 median + IQR 是否够；
- incomplete logging 怎么避免误读；
- `primary_goal` / `primary_direction` 是否只做解释；
- Meal Timing 是否应排除出 v0；
- 低置信 moderation 字段如何处理。

## Round 1：Claude 首轮产品批判

### Claude 接受的事实

Claude 重新验证了 Codex 的关键事实，并接受：

- master test set 不是 baseline；
- 24 条记录是 24 个不同 `user_id`；
- 没有 meal time 字段；
- `Meal_Timing` 全部是 100；
- 没有统一 daily confidence；
- 20/24 是 complete。

### Claude 引入 WHOOP 类比

Claude 抽象了 WHOOP 的几个原则：

- 今天要和自己的常态比；
- 趋势比单日重要；
- 输出状态区间比精确数字更可信；
- 数据质量必须 gate；
- 要解释变化驱动；
- 个体差异重要。

### Claude 的关键反驳

Claude 指出一个关键差异：

> WHOOP 的生理 baseline 有一定健康回归机制，但饮食没有。一个人可以长期稳定地吃得不健康。

所以 Diet Balance Baseline 不能照搬 WHOOP 的 personal-normal 思路。

### Claude 的核心要求

Baseline 必须同时保留两条轴：

1. personal-normal axis：和自己比。
2. health-reference axis：和健康参考比。

personal-normal 只能改变解释和信心，不能单独提高 Diet Balance。

### Claude 的分层建议

Claude 提出四层：

- `core_baseline`：用户自己的 kcal/macro/food pattern 曲线；
- `context_baseline`：profile 和 direction；
- `quality_baseline`：valid days、complete days、confidence；
- `future_baseline`：meal timing、weekday/weekend、CV/stability 等。

### Claude 的 red-team

Claude 提出典型失败场景：

- 长期饮食差，但某天略好；
- 长期饮食好，但某天偏离；
- 只记录健康餐；
- kcal 合适但结构差；
- 结构好但 kcal 严重超标；
- cut/bulk direction 不同；
- weekday/weekend 波动大。

## Round 2：Codex 回答 Claude 的 5 个问题

### Q1：未来纵向 schema 怎么设计

Codex 提出最小字段：

- `baseline_user_id`
- `record_date`
- `day_of_week`
- `is_learning_window_day`
- `user_profile`
- `meals[]`
- `daily_total`
- `daily_confidence_avg`
- `energy_confidence_avg`
- `food_group_confidence_avg`

核心结论：

> 没有 `baseline_user_id` 和 `record_date`，真实 core_baseline 不可计算。

### Q2：daily confidence 怎么聚合

Codex 提出：

- high = 1.0
- medium = 0.67
- low = 0.33
- missing = 0.0

但不是简单平均，而是：

- 对 present modules 做 weighted mean；
- 对关键缺失项做 cap；
- incomplete day cap 到 low；
- 缺 energy/food group confidence cap 到 medium；
- moderation low 不 cap 整天，但不进入 moderation baseline aggregate。

### Q3：能否合成 7 天 mock user

Codex 发现：

- `v2_baseline` 里有 9 条 complete records；
- 可以拿 7 条合成一个 pipeline shape test fixture。

但 Codex 强调：

- 这不能当产品证据；
- 必须标记 synthetic；
- 必须保留 source provenance；
- 只用于 pipeline shape test。

### Q4：energy / food group confidence 是否已有

Codex 判断：

- `energy_confidence_avg` 当前不存在；
- `food_group_confidence_avg` 当前不存在；
- 不能从 `kcal_range` 推断 confidence，除非上游明确说 range width 就是 confidence。

### Q5：primary_goal 和 primary_direction

Codex 判断：

- 不能确认这是正式 rename；
- 只能当 alias candidate；
- v0 schema 偏向 `primary_direction`；
- 兼容 `primary_goal`；
- 解释用，不进入 Goal 设计。

## Round 3：Claude 接受 Codex schema，但提出三项修正

### Claude 接受的部分

Claude 接受：

- `baseline_user_id` + `record_date` 是最小缺失键；
- synthetic fixture 延后；
- 不从 `kcal_range` 硬推 confidence；
- `primary_goal` -> `primary_direction` 只是 alias，不是已确认 rename。

### 修正 A1：two-axis 必须结构化

Claude 认为 Codex 的 schema 如果只写一个 `health_reference_axis.note`，下游公式可能忽略。

因此 Claude 要求：

> 每一个 core_baseline 指标都必须内联健康参考比较字段。

例子：

- energy 要有 `median_to_target_ratio`；
- macro 要有 AMDR status；
- food pattern 要有 HEI/reference status。

### 修正 A2：个人食物模式不要叫 hei_curve

Claude 认为：

- `hei` 应该保留给 health-reference；
- personal-normal food metric 应叫 `food_pattern.intake_curve`。

这样避免把用户自己的食物曲线误认为 HEI 分数。

### 修正 A3：readiness 降低信心，不硬阻断

Claude 建议：

- `complete_day_records >= 3` 就可以 emit core curve，但 confidence = low；
- `valid_record_days >= 5` 才到 medium；
- 7 天 + daily confidence 足够才 high。

### Claude 要 Codex 关闭四个锁点

1. 是否接受 tiered readiness。
2. 是否接受结构化 two-axis。
3. 是否接受 confidence aggregation contract。
4. 是否锁定 metric names。

## Round 4：Codex 关闭锁点并产出 v0 deliverables

### Codex 接受 Claude 的三项修正

Codex 确认：

- tiered readiness 没有工程阻碍；
- inline health-reference fields 可以实现；
- confidence contract 可以先以 missing/cap 形式落地；
- personal-normal metric names 锁定为：
  - `energy.kcal_curve`
  - `macro.structure_curve`
  - `food_pattern.intake_curve`

### Codex 产出四个文件

Codex 创建：

- `Diet Balance Baseline v0 指标定义.md`
- `Diet Balance Baseline v0 指标矩阵.csv`
- `Diet Balance Baseline Red-Team Cases.md`
- `Diet Balance Baseline Open Questions.md`

### Round 4 的阶段性结论

Baseline v0 已经有可审阅版本，但还没冻结，需要 Claude 做最终 critic pass。

## Round 5：Claude 最终 critic pass

Claude 审阅四个 v0 文件后，认为整体方案可接受，但提出三个必须修的小问题。

### F1：readiness table 有空档

Claude 发现原表混用了 `valid_record_days` 和 `complete_day_records`，导致某些情况匹配不到任何状态。

例如：

- `valid_record_days = 4`
- `complete_day_records = 2`

既不是 insufficient，也不是 partial，也不是 ready。

Claude 要求改成：

- `insufficient_data`: `complete_day_records < 3`
- `partial_ready`: `complete_day_records >= 3 AND valid_record_days < 5`
- `ready`: `complete_day_records >= 3 AND valid_record_days >= 5`
- `high_confidence_ready`: 7 days + `daily_confidence_avg >= medium`

### F2：food pattern anchor 名称要统一

Claude 发现：

- 指标定义里用 `HEI_2020_food_pattern`；
- calculator component 是 `HEI_2020_available`。

Claude 建议：

- baseline anchor token 用 `HEI_2020_food_pattern`；
- 明确它映射到 calculator component `HEI_2020_available`。

### F3：缺少 trend/direction 信号

Claude 认为：

- v0 core 的 median + IQR 是静态快照；
- 原始愿景还需要“是否朝健康参考方向变化”；
- 这个不是 CV/stability。

Claude 不要求 v0 实现 trend，但要求显式放入 `future_baseline`：

- `trend.reference_convergence`

### Claude 的结论

v0 accepted pending F1/F2/F3。

修完之后可以冻结。

## 用户插入：生病场景

### 用户提出的问题

用户问：

> 如果已经判断用户生病了，baseline 或公式应该怎么调整？先不讨论怎么判断生病。

用户还补充了一个现实观察：

> 有 WHOOP 用户生病躺病床打吊瓶，但 recovery 给到 99，这不合理甚至有点搞笑。

这个案例成为后续讨论里的 readiness paradox。

## Illness Round 1：Codex 提出生病调整三方案

### Codex 前提

Codex 先锁定：

- 不讨论 illness detection；
- 不做医疗诊断；
- 不给疾病饮食建议；
- 不改 Goal/Finish；
- 不定最终公式权重。

### Scheme A：Baseline Freeze + Score Annotate

行为：

- illness day 不进入 baseline；
- 仍计算正常分数；
- 加 illness-context 注释。

优点：

- 实现简单；
- 医疗风险低。

缺点：

- 用户生病时仍可能看到一个正常高分或低分，解释不够强。

### Scheme B：Baseline Freeze + Score Softening / Confidence Downgrade

行为：

- illness day 不进入 baseline；
- 展示 components；
- 降低 confidence；
- 可取消 ranking。

Codex 初始推荐 Scheme B。

但这里的 “softening” 之后被 Claude 批判，因为它可能被理解成数值加分。

### Scheme C：Separate Illness Baseline Track

行为：

- 正常 baseline 冻结；
- illness days 进入另一个 illness-context history；
- 未来有足够样本后，再和自己的 illness-context 历史比。

Codex 判断：

- 有长期价值；
- 但复杂；
- 医疗风险更高；
- v0 不做。

## Illness Round 2：Claude 批判并重构三方案

### Claude 接受的前提

Claude 同意：

- illness day 必须排除出 `core_baseline`；
- detection 不讨论；
- baseline freeze 没争议。

### Claude 的关键批判：softening 不能提高数字

Claude 指出：

> 如果 illness context 可以把坏分数“soften”成更高分，那就是通过上下文绕过 two-axis hard rule。

所以 illness 只能：

- suppress 正式分数；
- relabel 当天；
- downgrade confidence；
- 取消 ranking；

不能：

- 提高 Diet Balance 数值；
- 给 success badge；
- 让生病日看起来像正常成功日。

### Claude 要求复用 existing structure

Claude 认为不需要新建 `baseline_policy`。

illness day 应该直接复用：

```json
quality_baseline.excluded_days[].reason = "illness_context"
```

新增字段只限：

- `health_context.*`
- `score_policy.*`

### Claude 重构后的三方案

O1 Annotate：

- 显示正常数字 + illness label；
- fallback。

O2 Contextualize：

- 隐藏正式 score；
- 隐藏 ranking；
- 显示 components；
- `confidence = contextual`；
- 不 numeric boost；
- v0 推荐默认。

O3 Separate illness track：

- future only。

### Claude 加入 illness red-team

Claude 要求新增：

- RT-I1：生病时只记录好餐；
- RT-I2：illness flag 卡住导致 baseline starvation；
- RT-I3：false positive；
- RT-I4：慢性/反复 illness 被当作 new normal。

### Claude 对 learning window 的修正

Claude 要求：

- illness days 不计入 `valid_record_days`；
- illness days 不计入 `complete_day_records`；
- 学习期从固定 7 calendar days 改成 rolling until N valid days。

## Illness Round 3：Codex 接受 Claude 批判并落文件

### Codex 接受的点

Codex 同意：

- 删除 “softening” 表述；
- O2 只表示 suppress/relabel/downgrade confidence；
- illness 不能数值提高 Diet Balance；
- illness day 复用 `excluded_days[].reason = "illness_context"`；
- 不新增平行 `baseline_policy`；
- illness days 不计入 readiness counters；
- learning window rolling until N valid days；
- O2 是 v0 默认；
- O1 是 fallback；
- O3 是 future only。

### Codex 修改的文件

Codex 更新：

- `Diet Balance Baseline Illness Adjustment Options.md`
- `Diet Balance Baseline Red-Team Cases.md`
- `Diet Balance Baseline v0 指标定义.md`
- `Diet Balance Baseline v0 指标矩阵.csv`
- `ai_collab/diet_balance_baseline/DECISIONS.md`
- `ai_collab/diet_balance_baseline/CODEX_OUT.md`

### Codex 同时修复 F1/F2/F3

Codex 修复：

- F1 readiness band；
- F2 `HEI_2020_food_pattern` mapping；
- F3 `trend.reference_convergence` future row。

## Final Round：Claude 最终验收并冻结 v0

### Claude 重新验证的项目

Claude 最后确认：

- F1 readiness band 已修复，没有 undefined band；
- F2 anchor token 已统一；
- F3 `trend.reference_convergence` 已加入 future_baseline；
- illness “softening” 已移除；
- O2 已明确为 suppress/relabel/downgrade only；
- illness 复用 `excluded_days[].reason = "illness_context"`；
- 没有平行 `baseline_policy`；
- illness days 不计入 `valid_record_days` 和 `complete_day_records`；
- RT-I1 到 RT-I4 已加入。

### Claude 的非阻塞备注

Claude 提醒：

> rolling until N valid days 里的 N 不应引入新常数，应该等于现有 readiness thresholds。

也就是：

- `valid_record_days >= 5`
- `complete_day_records >= 3`

这只是 open question/clarification，不重开 v0。

### 最终冻结范围

Claude 宣布 Baseline v0 definition phase frozen。

冻结内容包括：

- core_baseline：
  - `energy.kcal_curve`
  - `macro.structure_curve`
  - `food_pattern.intake_curve`
- context_baseline：
  - metabolic profile
  - direction
- quality_baseline：
  - readiness gates
  - `daily_confidence_avg`
  - `missing_meal_slots`
  - `excluded_days[].reason`
- future_baseline：
  - meal timing
  - weekday/weekend split
  - CV/stability
  - `trend.reference_convergence`
  - separate illness track
- illness v0 default：
  - O2 Contextualize

## 总体收敛轨迹

这次协作大致经历了四次收敛：

1. 从“有哪些 baseline 指标”收敛到“当前 repo 没有真实 baseline 数据”。
2. 从“用户自己的常态”收敛到“两轴结构：personal-normal + health-reference”。
3. 从“可计算字段列表”收敛到“v0 指标定义 + 指标矩阵 + readiness/confidence 规则”。
4. 从“生病时怎么调分”收敛到“生病时不调高分，而是排除 baseline + 改变展示策略”。

## 最终一句话

Codex 负责把本地数据事实和工程可行性钉住，Claude 负责持续挑战产品风险和错误激励；双方最后把 Diet Balance Baseline v0 收敛成一个双轴、质量门控、不会把坏习惯正常化、也不会在生病时给出荒谬高分的定义方案。
