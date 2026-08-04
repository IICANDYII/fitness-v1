# Diet Balance Baseline v0 协作总结

## 1. 当前状态

Diet Balance Baseline v0 的定义阶段已经完成，并由 Claude 最终验收冻结。

冻结含义：

- 这是定义阶段输出，不是实现代码。
- 不定义 Goal 子模块。
- 不展开 Finish。
- 不确定最终公式权重。
- 下一阶段如果要继续，应进入实现阶段：纵向 schema、baseline 计算、合成 7 天 fixture、测试。

相关文件：

- `Diet Balance Baseline v0 指标定义.md`
- `Diet Balance Baseline v0 指标矩阵.csv`
- `Diet Balance Baseline Illness Adjustment Options.md`
- `Diet Balance Baseline Red-Team Cases.md`
- `Diet Balance Baseline Open Questions.md`
- `ai_collab/diet_balance_baseline/DECISIONS.md`
- `ai_collab/diet_balance_baseline/CODEX_OUT.md`
- `ai_collab/diet_balance_baseline/CLAUDE_OUT.md`

## 2. 核心结论

Diet Balance Baseline v0 是 Diet Agent 在 7 天学习期内，对同一用户饮食个人常态、健康参考差距、数据可信度的结构化摸排。

它不是：

- 目标；
- 分数；
- 最终公式；
- 对 Goal/Finish 的扩展；
- 对健康饮食标准的替代。

最重要的产品原则是双轴结构：

1. `personal-normal axis`：今天和用户自己的饮食常态相比。
2. `health-reference axis`：今天和健康参考锚点相比，例如 HEI、AMDR、RDA/AI、kcal target。

v0 的硬规则：

> personal-normal / context 可以改变解释、信心、排名资格，但不能单独提高 Diet Balance。

原因是：饮食没有 WHOOP 那类生理指标的自我健康回归机制。一个人的饮食习惯可以长期稳定但不健康，所以“比你平时好”不能等于“健康分更高”。

## 3. 现有数据判断

Codex 和 Claude 共同确认：

- 当前 master test set 不是 baseline。
- 它包含 24 个单日用户记录，而不是同一用户连续 7 天记录。
- 当前 repo 支持的是单日健康参考计算，不支持真实 personal-normal baseline。
- 要计算 baseline，必须新增纵向数据结构。

当前已有的信息可以支持：

- 单日 kcal；
- 单日 macro；
- 单日 food group；
- 单日 moderation estimates；
- 用户 profile；
- kcal target；
- Diet Balance 当前五模块计算。

当前缺失的信息包括：

- 同一用户连续多天记录；
- 稳定用户 ID；
- record date；
- meal timestamp；
- 统一 daily confidence；
- energy confidence；
- food group confidence；
- 用户修正/人工确认字段。

## 4. v0 分层结构

v0 baseline 分成四层。

### core_baseline

用户自己的饮食曲线，必须依赖纵向数据。

冻结的三个核心指标：

- `energy.kcal_curve`
- `macro.structure_curve`
- `food_pattern.intake_curve`

每个 core_baseline 指标必须内联健康参考字段，不能只输出个人常态。

例子：

- energy 不只输出 median kcal，还要输出 `median_to_target_ratio`。
- macro 不只输出 macro median，还要输出 AMDR status。
- food pattern 不只输出食物组中位数，还要输出 food pattern vs reference status。

### context_baseline

解释上下文，不直接加分。

包括：

- `profile.metabolic`
- `profile.direction`

`primary_goal` 和 `primary_direction` 暂时按 alias 处理，但不是已经确认的正式改名。

### quality_baseline

判断 baseline 是否可信。

包括：

- `valid_record_days`
- `complete_day_records`
- `daily_confidence_avg`
- `missing_meal_slots`
- `excluded_days`

### future_baseline

明确延后，不进入 v0 core。

包括：

- meal timing curve；
- weekday/weekend split；
- CV/stability labels；
- `trend.reference_convergence`；
- separate illness baseline track；
- synthetic 7-day fixture。

## 5. readiness 规则

v0 readiness 使用分层门槛：

| status | condition | confidence |
|---|---|---|
| `insufficient_data` | `complete_day_records < 3` | none |
| `partial_ready` | `complete_day_records >= 3` and `valid_record_days < 5` | low |
| `ready` | `complete_day_records >= 3` and `valid_record_days >= 5` | medium if daily confidence allows |
| `high_confidence_ready` | 7 days present and `daily_confidence_avg >= medium` | high |

解释：

- `complete_day_records >= 3` 是曲线存在的最低门槛。
- `valid_record_days >= 5` 是可相信的最低门槛。
- 7 天 + daily confidence 足够，才可能 high confidence。

## 6. confidence 规则

v0 采用 weighted mean + critical caps。

基本映射：

- `high = 1.0`
- `medium = 0.67`
- `low = 0.33`
- `missing = 0.0`

关键规则：

- 只对 present modules 算 weighted mean。
- missing module 触发 cap，但不再参与平均，避免双重惩罚。
- incomplete day 把 daily confidence cap 到 `low`。
- 缺失 `energy_confidence_avg` 或 `food_group_confidence_avg` 时，cap 到 `medium`。
- low moderation confidence 不直接 cap 整天，但对应 moderation aggregate 不进入 baseline。

## 7. 生病场景的最终结论

用户插入的问题是：如果系统已经知道用户生病了，baseline 或公式要怎么调整？检测方法不讨论。

最终结论：

- 生病日不进入正常 `core_baseline`。
- 生病日不计入 `valid_record_days`。
- 生病日不计入 `complete_day_records`。
- onboarding 学习窗口从严格 7 个日历日，变成 rolling until N valid days。
- 这里的 N 不引入新常数，应等于现有 readiness threshold。

结构上不新增平行 `baseline_policy`，而是复用：

```json
{
  "quality_baseline": {
    "excluded_days": [
      {
        "record_date": "2026-06-16",
        "reason": "illness_context"
      }
    ]
  }
}
```

## 8. 生病时的三种展示方案

### O1 Annotate

显示正常数字，但加 illness-context 标签。

状态：fallback。

问题：如果用户生病躺床上，产品还显示一个高分，即使有标签，也可能显得荒谬。

### O2 Contextualize

隐藏正式 Diet Balance 分数和排名，只展示组件与中性上下文。

状态：v0 推荐默认方案。

规则：

- `ranking_status = not_ranked`
- `present_formal_score = false`
- `confidence = contextual`
- 可展示 component-level 信息
- 不给成功 badge
- 不做数值加分

这是为了解决用户提到的 readiness paradox：人生病住院打吊瓶时，产品不应该还给出正常高分式反馈。

### O3 Separate Illness Track

未来为 illness context 单独建历史轨道。

状态：future only。

原因：

- 复杂度高；
- 容易过拟合；
- 有医疗建议风险；
- 可能错误地把 illness intake 正常化。

## 9. 生病场景硬规则

illness context 可以：

- suppress 正式分数；
- relabel 当天状态；
- downgrade confidence；
- 取消排名；
- 阻止 baseline 学习。

illness context 不能：

- 数值提高 Diet Balance；
- 让 illness day 看起来像正常成功日；
- 生成医疗诊断；
- 推荐疾病相关饮食；
- 把 recurring illness intake 当作健康新常态。

## 10. 红队案例

v0 记录了常规红队案例：

- 长期差饮食，只是某天略好；
- 长期好饮食，某天偏离；
- 只记录健康餐；
- kcal 接近目标但食物结构差；
- 食物结构好但 kcal 严重超标；
- cut/bulk direction 不同；
- weekday/weekend 波动大；
- moderation confidence 低；
- Meal Timing placeholder = 100。

生病专项红队：

- RT-I1：生病时只记录“好餐”，不能提高分数或污染 baseline。
- RT-I2：illness flag 卡住，不能用 illness day 回填 baseline，应诚实显示 insufficient data。
- RT-I3：illness false positive，要有 bounded window 和 excluded_days audit。
- RT-I4：慢性/反复 illness，v0 不能把 illness intake 当成新常态。

## 11. v0 未做的事情

v0 不做：

- 最终公式权重；
- Goal；
- Finish；
- Meal Timing 真实打分；
- weekday/weekend split；
- CV/stability labels；
- trend.reference_convergence 实现；
- separate illness baseline track；
- synthetic 7-day fixture；
- medical advice。

这些都被显式延期或排除。

## 12. 下一阶段建议

如果要进入实现阶段，建议按这个顺序：

1. 建立纵向 schema：`baseline_user_id` + `record_date` + per-day nutrition fields。
2. 实现 readiness 和 confidence gate。
3. 先实现 `quality_baseline` 和 `context_baseline`。
4. 再实现三个 core curves：energy、macro、food_pattern。
5. 增加 illness exclusion 和 O2 score presentation policy。
6. 生成合成 7 天 fixture，只用于 pipeline shape test，不作为产品证据。
7. 增加 red-team tests，尤其是 incomplete logging 和 illness paradox。

## 13. 最适合阅读的文件顺序

如果只想看结论：

1. `Diet Balance Baseline v0 协作总结.md`
2. `Diet Balance Baseline v0 指标定义.md`
3. `Diet Balance Baseline Illness Adjustment Options.md`

如果想看指标表：

1. `Diet Balance Baseline v0 指标矩阵.csv`

如果想看讨论过程：

1. `ai_collab/diet_balance_baseline/DECISIONS.md`
2. `ai_collab/diet_balance_baseline/CODEX_OUT.md`
3. `ai_collab/diet_balance_baseline/CLAUDE_OUT.md`

## 14. 一句话最终版

Diet Balance Baseline v0 是一个不加分、不替代公式的用户饮食常态与数据质量层；它必须同时携带健康参考锚点，不能把稳定但不健康的饮食正常化；生病日不进入正常 baseline，v0 默认隐藏正式分数和排名，只做 illness-context 的组件展示与信心降级。
