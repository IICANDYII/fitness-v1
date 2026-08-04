# Diet Balance Baseline v0 指标定义

## 1. 一句话定义

Diet Balance Baseline v0 是 Diet Agent 在 7 天学习期内，对同一用户饮食个人常态曲线、健康参考锚点差距、以及数据可信度的结构化摸排结果；它不是目标、不是分数，也不替代 Diet Balance 公式。

source_type: inference  
source: `Diet Balance Baseline 新版PRD.md`, `ai_collab/diet_balance_baseline/CODEX_OUT.md`, `ai_collab/diet_balance_baseline/CLAUDE_OUT.md`

## 2. v0 核心原则

| principle_id | principle | source_type | note |
|---|---|---|---|
| P0 | 不定义 Goal，不展开 Finish，不写最终公式权重 | local_file | 来自协作工作流和 DECISIONS |
| P1 | baseline 必须同时保留 personal-normal axis 和 health-reference axis | inference | 防止一刀切，也防止把坏习惯正常化 |
| P2 | personal-normal 可以改变解释和信心，不应在 v0 单独提高 Diet Balance | inference | Claude Round 1 red-team 共识 |
| P3 | 每个 core_baseline 指标必须内联健康参考比较字段 | inference | 结构性 two-axis，不只写 prose note |
| P4 | incomplete day 不进入 kcal/food baseline 聚合 | local_file + inference | 计算器已有 incomplete status；baseline 沿用硬门槛 |
| P5 | Meal Timing 暂不进入 v0 baseline influence | local_file | 当前 calculator debug 显示 timing 是 placeholder 100 |

## 3. Baseline readiness

| status | condition | confidence | source_type |
|---|---|---|---|
| `insufficient_data` | `complete_day_records < 3` | none | inference |
| `partial_ready` | `complete_day_records >= 3` and `valid_record_days < 5` | low | inference |
| `ready` | `complete_day_records >= 3` and `valid_record_days >= 5` | medium if daily confidence allows | inference |
| `high_confidence_ready` | 7 days present and `daily_confidence_avg >= medium` | high | inference |

PRD 原始条件是 `learning_period_days >= 7`, `valid_record_days >= 5`, `complete_day_records >= 3`, `average_daily_confidence >= medium`。v0 解释为：`complete_day_records >= 3` 是曲线存在的最低门槛，`valid_record_days >= 5` 是可相信的最低门槛。

Illness-context days do not count toward either `valid_record_days` or `complete_day_records`. When illness intervenes, the learning window becomes "rolling until N valid days" rather than a strict 7 calendar-day window.

source_type: inference

## 4. 最小纵向输入 schema

```json
{
  "baseline_user_id": "user_123",
  "record_date": "2026-06-16",
  "day_of_week": "Tuesday",
  "is_learning_window_day": true,
  "user_profile": {
    "age_years": 30,
    "sex": "female",
    "height_cm": 165,
    "weight_kg": 60,
    "physical_activity_level": "active",
    "primary_direction": "maintain"
  },
  "meals": [
    {
      "meal_slot": "breakfast",
      "time": null,
      "kcal_mid": 520,
      "kcal_range": [450, 590],
      "macro_structure_pct": { "protein": 18, "fat": 30, "carb": 52 }
    }
  ],
  "daily_total": {
    "available_meals": 3,
    "kcal_mid": 2100,
    "kcal_range": [1900, 2300],
    "estimated_energy_requirement_kcal": 2050,
    "macro_structure_pct": { "protein": 18, "fat": 30, "carb": 52 },
    "food_group_totals": {},
    "moderation_estimates": {},
    "coverage_flags": { "full_day_record_complete": true },
    "daily_confidence_avg": "medium",
    "energy_confidence_avg": null,
    "food_group_confidence_avg": null
  }
}
```

## 5. v0 输出结构草案

```json
{
  "baseline_status": "ready",
  "baseline_confidence": "medium",
  "baseline_user_id": "user_123",
  "learning_window": {
    "start_date": "2026-06-10",
    "end_date": "2026-06-16",
    "learning_period_days": 7,
    "valid_record_days": 6,
    "complete_day_records": 4
  },
  "core_baseline": {
    "energy": {
      "metric_id": "energy.kcal_curve",
      "median_kcal": 2100,
      "iqr_kcal": [1900, 2300],
      "median_to_target_ratio": 1.02,
      "vs_reference_status": "near_target",
      "reference_anchor": "estimated_energy_requirement_kcal"
    },
    "macro": {
      "metric_id": "macro.structure_curve",
      "carb_pct_median": 0.52,
      "fat_pct_median": 0.30,
      "protein_pct_median": 0.18,
      "amdr_carb_status": "within",
      "amdr_fat_status": "within",
      "amdr_protein_status": "within",
      "reference_anchor": "AMDR"
    },
    "food_pattern": {
      "metric_id": "food_pattern.intake_curve",
      "vegetable_cup_median": 1.5,
      "whole_fruits_cup_median": 0.5,
      "whole_grains_oz_median": 1.0,
      "refined_grains_oz_median": 4.0,
      "fiber_g_median": 14,
      "food_pattern_vs_reference_status": "below_reference",
      "reference_anchor": "HEI_2020_food_pattern"
    }
  },
  "context_baseline": {
    "profile_source": "user_profile",
    "primary_direction": "maintain"
  },
  "quality_baseline": {
    "daily_confidence_avg": "medium",
    "missing_meal_slots": [],
    "excluded_days": []
  }
}
```

Canonical food-pattern anchor token: `HEI_2020_food_pattern`. This names the health-reference anchor attached to `food_pattern.intake_curve`. It maps to the current calculator/scoring component `HEI_2020_available`, but the personal-normal metric name must remain `food_pattern.intake_curve` to avoid re-labeling a user curve as an HEI score.

source_type: inference + local_file
source: `references/relty_diet_balance_calculator_kcal.ps1`, `references/outputs/testset_master_all.diet_balance_kcal_results.json`

## 6. Confidence rule

source_type: inference

1. Convert labels: `high=1.0`, `medium=0.67`, `low=0.33`, `missing=0.0`.
2. Compute weighted mean over present modules only.
3. Apply critical caps:
   - incomplete day caps daily confidence at `low`;
   - missing `energy_confidence_avg` or `food_group_confidence_avg` caps at `medium`;
   - low moderation confidence excludes moderation aggregates from baseline, but does not alone cap the full day.
4. Missing modules trigger caps but do not also drag the weighted mean.

## 7. v0 exclusions

| item | status | reason |
|---|---|---|
| Meal timing curve | future_baseline | no timestamp fields in current local data |
| Weekday/weekend split | future_baseline | needs `record_date`; schema reserves it now |
| CV/stability labels | future_baseline | fragile at 7 days |
| `trend.reference_convergence` | future_baseline | direction toward/away from health reference is distinct from CV/stability; 7 days is too short for robust trend |
| Separate illness baseline track | future_baseline | high overfitting and medical-advice risk; v0 only excludes illness days from normal baseline |
| Synthetic 7-day fixture | deferred | generate only after v0 metric list is frozen |
| Formula weights | rejected/deferred | explicitly out of scope |
| Goal/Finish | rejected/deferred | explicitly out of scope |
