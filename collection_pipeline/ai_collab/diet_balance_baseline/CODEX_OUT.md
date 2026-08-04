# Codex Output

status: done_for_turn
owner: codex
round: 1

## Repo Facts

### Local files read

| source_type | source | evidence |
|---|---|---|
| local_file | `Diet Balance Baseline 新版PRD.md` | Defines Diet Baseline as a 7-day learning-period reference, not a goal and not a score. |
| local_file | `references/relty_diet_balance_calculator_kcal.ps1` | Current kcal calculator uses the five-module formula and requires `Kcal_Balance` for a formal `diet_balance`. |
| local_file | `references/relty_diet_balance_calculator.ps1` | Older non-kcal calculator remains present and uses a four-module formula. |
| local_file | `references/test_sets/testset_master_all.json` | Master test set contains 24 single-day user records with structured profile, meals, daily totals, food groups, moderation estimates, coverage flags, and estimated energy requirement. |
| local_file | `references/outputs/testset_master_all.diet_balance_kcal_results.json` | Existing kcal output schema is `relty_diet_balance_calculator_kcal.v0_5`. |
| local_file | `references/outputs/testset_master_all.diet_balance_kcal_summary.csv` | Summary CSV exposes top-level score status, formula components, profile fields, kcal target source, and ranking status. |
| local_file | `references/CHANGELOG_diet_balance_calculator.md` | Changelog records that the kcal calculator added Kcal Balance, user-profile RDA/AI personalization, HEI moderation fields, and incomplete-record handling. |

### Current master test set field coverage

| claim | source_type | source | evidence |
|---|---|---|---|
| The master test set has 24 user-day records. | calculated_from_local_data | `references/test_sets/testset_master_all.json` | `users=24`. |
| 20 records are complete full-day records and 4 are incomplete. | calculated_from_local_data | `daily_total.coverage_flags.full_day_record_complete` | 20 true, 4 not true. |
| All 24 records include `user_profile`. | calculated_from_local_data | `users[].user_profile` | 24/24 have profile. |
| All 24 records include age, sex, height, weight, physical activity level, and primary goal in `user_profile`. | calculated_from_local_data | `users[].user_profile.*` | 24/24 have `age_years`, `sex`, `height_cm`, `weight_kg`, `physical_activity_level`, `primary_goal`. |
| All 24 records include structured daily food group totals. | calculated_from_local_data | `daily_total.food_group_totals` | 24/24 have `food_group_totals`. |
| All 24 records include daily moderation estimates. | calculated_from_local_data | `daily_total.moderation_estimates` | 24/24 have moderation estimates. |
| All 24 records include estimated energy requirement. | calculated_from_local_data | `daily_total.estimated_energy_requirement_kcal` | 24/24 have target kcal source available. |
| The current master data is not a 7-day longitudinal record for one user. | local_file | `references/test_sets/testset_master_all.json` | Records are separate `user_id` values such as `user01-01`, `user02-01`, matched-pair tests, and synthetic edge cases. |

### Input fields present in master JSON

| group | source_type | source | field paths |
|---|---|---|---|
| user identity and scenario | local_file | `references/test_sets/testset_master_all.json` | `user_id`, `testset_group`, `profile` |
| user metabolic profile | local_file | same | `user_profile.age_years`, `user_profile.sex`, `user_profile.height_cm`, `user_profile.weight_kg`, `user_profile.physical_activity_level`, `user_profile.primary_goal` |
| meal structure | local_file | same | `meals[].meal_slot`, `meals[].foods`, `meals[].kcal_range`, `meals[].kcal_mid`, `meals[].macro_structure_pct.*`, `meals[].moderation_estimates.*`, `meals[].error` |
| daily energy and macros | local_file | same | `daily_total.available_meals`, `daily_total.kcal_range`, `daily_total.kcal_mid`, `daily_total.macro_structure_pct.protein`, `daily_total.macro_structure_pct.fat`, `daily_total.macro_structure_pct.carb` |
| daily food groups | local_file | same | `daily_total.food_group_totals.total_fruits_cup`, `whole_fruits_cup`, `fruit_juice_cup`, `total_vegetables_cup`, `greens_and_beans_cup`, `whole_grains_oz`, `refined_grains_oz`, `dairy_cup`, `total_protein_foods_oz`, `seafood_and_plant_proteins_oz`, `fiber_g_range`, `fiber_g_mid` |
| daily moderation | local_file | same | `daily_total.moderation_estimates.sodium_mg.value/confidence`, `added_sugars_g.value/confidence`, `saturated_fat_g.value/confidence`, `fatty_acids.pufa_g/mufa_g/sfa_g/ratio_pufa_mufa_over_sfa/confidence` |
| record completeness | local_file | same | `daily_total.coverage_flags.full_day_record_complete`, `missing_fruit_treated_as_zero`, `missing_dairy_treated_as_zero`, `missing_whole_grain_treated_as_zero` |
| energy target | local_file | same | `daily_total.estimated_energy_requirement_kcal`, `daily_total.energy_target_method` |

### Existing kcal output fields

| group | source_type | source | field paths |
|---|---|---|---|
| formal score | local_file | `references/outputs/testset_master_all.diet_balance_kcal_results.json` | `diet_balance`, `diet_balance_raw`, `score_status`, `ranking_status`, `is_partial_day_score`, `balance_method` |
| abstract subscores | local_file | same | `abstract_scores.structure`, `abstract_scores.nutrients`, `abstract_scores.rhythm`, `abstract_scores.energy` |
| formula components | local_file | same | `components.hei_2020_available`, `amdr_fit`, `rda_ai_adequacy`, `meal_timing`, `kcal_balance` |
| formula contributions | local_file | same | `contributions.hei_2020_available`, `amdr_fit`, `rda_ai_adequacy`, `meal_timing`, `kcal_balance` |
| profile used for scoring | local_file | same | `scoring_profile.age_years`, `sex`, `weight_kg`, `source` |
| HEI debug | local_file | same | `debug.hei_2020_available.components[]`, `recognized_score_points`, `recognized_max_points`, `moderation_estimates_used`, `food_group_totals_used`, `included_components` |
| RDA/AI debug | local_file | same | `debug.rda_ai_partial.user_profile_used`, `protein.actual_g/target_g/target_source/ratio/score`, `fiber.actual_g/target_g/ratio/score` |
| Kcal debug | local_file | same | `debug.kcal_balance.actual_kcal`, `target_kcal`, `actual_to_target_ratio`, `deviation_from_target`, `score`; `debug.kcal_target_source` |
| completeness/debug | local_file | same | `debug.coverage_flags`, `debug.ranked`, `debug.food_group_input_source`, `debug.meal_timing_policy` |

## Current Diet Balance Understanding

### Current formula

| claim | source_type | source | evidence |
|---|---|---|---|
| The current kcal calculator formula is five-module Diet Balance. | local_file | `references/relty_diet_balance_calculator_kcal.ps1`; output JSON `formula` | `0.40*HEI_2020_available + 0.15*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing + 0.15*Kcal_Balance`. |
| The older calculator still exists and uses a four-module formula. | local_file | `references/relty_diet_balance_calculator.ps1` | `0.50*HEI_2020_available + 0.20*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing`. |
| The collaboration workflow treats the five-module formula as the current Diet Balance context. | local_file | `Diet Balance Baseline AI协作工作流.md` | Section 1.1 lists the five-module formula and says current calculator is still absolute-formula-based. |

### Component status

| component | source_type | source | current behavior |
|---|---|---|---|
| `HEI_2020_available` | local_file | `relty_diet_balance_calculator_kcal.ps1` | Uses structured food group totals plus available moderation estimates; output debug shows component-level scoring and denominator. |
| `AMDR_Fit` | local_file | same | Uses daily macro percentages from `daily_total.macro_structure_pct`. |
| `RDA_AI_Adequacy` | local_file | same | Uses protein derived from kcal and protein percentage; uses fiber from structured fields; uses age/sex/weight where available. |
| `Meal_Timing` | local_file | same | Temporarily set to 100; debug policy says `temporary_full_score_until_reliable_multi_day_timing_data`. |
| `Kcal_Balance` | local_file | same | Requires complete-day record and target kcal; target can come from `daily_total.estimated_energy_requirement_kcal`; output includes actual/target ratio. |

## Candidate Baseline Metrics Matrix

| metric_id | source_type | source_file | source_field | existing_data_available | 7_day_estimable | possible_balance_module_affected | risk |
|---|---|---|---|---|---|---|---|
| `profile.age_sex_height_weight` | local_file | `testset_master_all.json` | `user_profile.age_years`, `sex`, `height_cm`, `weight_kg` | yes in master data, 24/24 | yes if profile is collected once; not learned from diet records | `RDA_AI_Adequacy`, `Kcal_Balance` | Profile may be stale or user-entered incorrectly. |
| `profile.activity_level` | local_file | same | `user_profile.physical_activity_level` | yes in master data, 24/24 | yes as context if collected; not inferable from meals alone | `Kcal_Balance` | Activity level is coarse and may be self-report. |
| `profile.primary_direction` | local_file | PRD uses `primary_direction`; test set uses `primary_goal` | `user_profile.primary_goal` | yes in master data, but name differs from PRD | yes as context if collected; not inferable from current records | `Kcal_Balance`, interpretation layer | Naming mismatch; Goal expansion is explicitly out of scope. |
| `energy.daily_kcal_mid` | local_file | `testset_master_all.json` | `daily_total.kcal_mid`; `meals[].kcal_mid` | yes | yes if >=5 valid days; current master is single-day examples only | `Kcal_Balance`, possible future energy baseline | Kcal recognition error propagates into baseline. |
| `energy.daily_kcal_range` | local_file | same | `daily_total.kcal_range`; `meals[].kcal_range` | yes | yes if daily records exist across 7 days | `Kcal_Balance`, confidence | Range may reflect recognition uncertainty, not true intake variation. |
| `energy.target_kcal` | local_file | same | `daily_total.estimated_energy_requirement_kcal`; output `debug.kcal_target_source` | yes, 24/24 source from estimated requirement | yes if profile is available | `Kcal_Balance` | Estimated requirement is calculated context, not observed baseline. |
| `energy.kcal_vs_target_ratio` | calculated_from_local_data | kcal output JSON | `debug.kcal_balance.actual_to_target_ratio` | yes for complete records; output has 20 complete_with_kcal and 4 incomplete_partial | yes for complete days only | `Kcal_Balance` | Incomplete days must not be treated as low intake. |
| `energy.kcal_vs_baseline_ratio` | inference | future baseline output | no direct field; would require learned median/mean from same user days | no in current master single-day data | yes only after multi-day same-user records exist | future personalized energy interpretation | Cannot compute from current master data without fabricating longitudinal history. |
| `meal_rhythm.meal_count_per_day` | local_file | `testset_master_all.json` | `daily_total.available_meals`; `meals[].meal_slot` | yes | yes if daily records exist | `Meal_Timing`, data quality | Available meals may reflect logging completeness, not actual meal count. |
| `meal_rhythm.breakfast_lunch_dinner_presence` | local_file | same | `meals[].meal_slot` | yes | yes if daily records exist | `Meal_Timing`, baseline confidence | Missing meal could mean skipped meal or unlogged meal. |
| `meal_rhythm.first_last_caloric_time` | local_file | current files | no timestamp fields observed | no | no | `Meal_Timing` | PRD asks for timing curve, but current master lacks times. |
| `meal_rhythm.late_heavy_meal_count` | local_file | current files | no meal time fields observed | no | no | `Meal_Timing` | Cannot distinguish late dinner from normal dinner without timestamps. |
| `meal_rhythm.largest_meal_slot` | calculated_from_local_data | `testset_master_all.json` | `meals[].meal_slot` + `meals[].kcal_mid` | computable from existing meal kcal | yes if daily records exist | `Meal_Timing`, interpretation | Meal slot granularity is coarse; no clock time. |
| `macro.carb_fat_protein_pct` | local_file | `testset_master_all.json` | `daily_total.macro_structure_pct.*`; output `debug.amdr.*` | yes | yes if daily records exist | `AMDR_Fit` | Percentages hide absolute gram adequacy and total kcal effects. |
| `macro.macro_stability` | inference | future aggregation | daily macro pct exists, but multi-day same-user records do not | no in master; yes with 7-day same-user data | `AMDR_Fit`, explanation | Stability from 7 days may be fragile for irregular eaters. |
| `macro.reference_gap` | calculated_from_local_data | kcal output JSON | `components.amdr_fit`; `debug.amdr.carb_score/fat_score/protein_score` | yes per day | yes if daily records exist | `AMDR_Fit` | AMDR gap is an absolute reference anchor, not a personal baseline by itself. |
| `food_pattern.hei_food_groups` | local_file | `testset_master_all.json` | `daily_total.food_group_totals.*` | yes | yes if daily records exist | `HEI_2020_available`, structure | Food-group estimates depend on recognition quality. |
| `food_pattern.fiber_g` | local_file | same | `daily_total.food_group_totals.fiber_g_mid`, `fiber_g_range`; output `debug.rda_ai_partial.fiber.actual_g` | yes | yes if daily records exist | `RDA_AI_Adequacy`, HEI-related interpretation | Fiber may come from estimates rather than measured nutrition facts. |
| `food_pattern.moderation` | local_file | same | `daily_total.moderation_estimates.sodium_mg`, `added_sugars_g`, `saturated_fat_g`, `fatty_acids` | yes | yes if daily records exist, but confidence is often field-level low in sample | `HEI_2020_available` | Current data may have low confidence; over-weighting can punish or reward noisy estimates. |
| `food_pattern.hei_components` | local_file | kcal output JSON | `debug.hei_2020_available.components[]` | yes in output | yes for complete days | `HEI_2020_available` | HEI component scores are health-reference anchors, not personal-normal metrics. |
| `quality.full_day_record_complete` | local_file | `testset_master_all.json` | `daily_total.coverage_flags.full_day_record_complete`; output `score_status`, `ranking_status` | yes | yes | all modules through confidence/gating | Complete flag may rely on upstream recognition/logging policy. |
| `quality.valid_record_days` | inference | future aggregation | current file has per-day completeness, not multi-day counts for one user | no in master; yes with 7-day same-user data | baseline readiness | Need user-level longitudinal grouping. |
| `quality.complete_day_records` | inference | future aggregation | current file has daily completeness, not same-user 7-day records | no in master; yes with 7-day same-user data | baseline readiness | Same issue as above. |
| `quality.average_daily_confidence` | local_file/inference | current fields | moderation fields have confidence; no unified daily confidence field observed | partial | only partial unless daily confidence is added | baseline confidence | Need a defined aggregation rule and more confidence fields. |
| `quality.missing_meal_slots` | calculated_from_local_data | `meals[].meal_slot`, `daily_total.available_meals` | computable for expected breakfast/lunch/dinner slots | yes | baseline confidence, `Meal_Timing` | Assumes expected meal slots are breakfast/lunch/dinner. |
| `quality.user_correction_count` | local_file | current files | no observed field | no | no | baseline confidence | Needs product/event logging not present in test set. |
| `quality.manual_confirmed_records` | local_file | current files | no observed field | no | no | baseline confidence | Needs product/event logging not present in test set. |

## Data Gaps

| gap | source_type | source | why it matters |
|---|---|---|---|
| No same-user 7-day longitudinal data in the master test set. | local_file | `references/test_sets/testset_master_all.json` | Baseline medians, IQR, CV, stability, and personal-normal ranges require repeated days for the same user. |
| No meal clock timestamps. | local_file | same | PRD fields such as first caloric intake time, last caloric intake time, and late heavy meals cannot be computed. |
| No unified daily confidence field. | local_file | same | PRD requires `average_daily_confidence >= medium`; current data has some field-level confidence but no daily aggregate. |
| No food-group confidence field observed. | local_file | same | `food_group_confidence_avg` cannot be computed from current master fields. |
| No energy confidence field observed. | local_file | same | `energy_confidence_avg` cannot be computed from current master fields. |
| No user correction or manual confirmation fields. | local_file | same | `user_correction_count` and `manual_confirmed_records` are not currently available. |
| PRD field name differs from test data for user direction. | local_file | PRD vs master JSON | PRD says `primary_direction`; master JSON uses `user_profile.primary_goal`. |
| Meal Timing is not yet a real score. | local_file | kcal output debug | `debug.meal_timing_policy = temporary_full_score_until_reliable_multi_day_timing_data`. |

## Risks

| risk | source_type | source | explanation |
|---|---|---|---|
| Treating current master data as a baseline would be a hallucination. | inference | based on `user_id` and testset groups | The master file is a suite of single-day scenarios and edge cases, not a 7-day record for one user. |
| Personal-normal metrics can normalize unhealthy behavior if not paired with health-reference anchors. | local_file | `Diet Balance Baseline 新版PRD.md` | PRD explicitly says baseline median is current normal, not a recommendation. |
| Incomplete-day records can distort kcal and food-pattern baseline. | local_file | output `score_status` and `ranking_status` | The kcal calculator already excludes incomplete partial-day records from ranking/formal score. |
| Food-group and moderation estimates are recognition-derived. | local_file | `food_group_totals`, `moderation_estimates.*.confidence` | Baseline should carry confidence and not over-interpret noisy estimates. |
| `primary_goal` should not pull this workstream into Goal design. | local_file | workflow and PRD | Both explicitly say do not define Goal submodules; use direction only as context. |
| Current `Meal_Timing=100` can mislead if treated as evidence of good timing. | local_file | output debug | It is a placeholder until reliable timing data exists. |

## Assumptions

| assumption | source_type | reason |
|---|---|---|
| Expected meal slots for missing-slot detection are breakfast, lunch, and dinner. | assumption | Current master examples use these slots, but the product may support snacks or culturally different meal patterns. |
| A future 7-day baseline data model will group records by stable user identity. | assumption | Required to compute user-specific medians/IQR/CV but not represented by current master test set. |
| `primary_goal` in the test set is intended to map to PRD `primary_direction`. | assumption | Names differ; needs product confirmation. |

## Questions for Claude

1. Which of the available health-reference anchors must remain non-negotiable in baseline v0: HEI food pattern, AMDR, RDA/AI, kcal target, or all of them?
2. Should metrics derived from `HEI_2020_available.components[]` be classified as `core_baseline`, or should they remain health-reference context separate from personal-normal baseline?
3. For 7-day learning, is median + IQR enough for kcal and macro curves, or should v0 avoid variability labels until more than 7 days exist?
4. How should v0 prevent incomplete logging from looking like low kcal or low food intake improvement?
5. Should `primary_goal`/`primary_direction` affect only interpretation in v0, or can it affect future `Kcal_Balance` personalization?
6. Since current files lack timestamps, should Meal Timing be excluded from v0 baseline formula influence and kept as future/context only?
7. How much confidence should be required before using low-confidence moderation fields such as sodium, added sugars, saturated fat, and fatty acids in baseline?
8. Should weekday/weekend separation be deferred because current data has no dates, or is it important enough to add to the required future schema now?

---

# Codex Output — Round 2 Response to Claude

status: done_for_turn
owner: codex
round: 2

## Claim

Claude's critique is accepted: current local files can support health-reference anchors and schema design, but cannot compute a real personal-normal Diet Baseline until the data model stores same-user, dated, multi-day records.

## Evidence

- source_type: local_file
- source: `ai_collab/diet_balance_baseline/CLAUDE_OUT.md`
- evidence: Claude independently re-checked 24 unique single-day `user_id` values, no `*time*` fields, placeholder `Meal_Timing = 100`, and no daily aggregate confidence field.

- source_type: calculated_from_local_data
- source: `references/test_sets/testset_master_all.json`
- evidence: Complete records by `testset_group`: `v2_baseline=9`, `A_processed_blindspot=2`, `C_calorie_density_dilution=3`, `D_moderation_perverse_incentive=2`, `E_fruit_juice_leak=3`, `v2_synthetic=1`; these are scenario groups, not same-user days.

## Reasoning

The available local data has rich per-day nutrition fields but lacks the two keys needed for personal-normal baseline: stable same-user grouping and day/date order. Therefore Round 2 should define the minimum longitudinal schema and confidence gates rather than pretending the current master set can produce a real baseline.

## Risk

The largest engineering risk is building pipeline code against synthetic same-user data and later forgetting that it was only a test harness. Any synthetic 7-day mock must carry explicit provenance fields and must not be used as product evidence.

## Answers to Claude's 5 Questions

### Q1. Future longitudinal schema: minimum field set

| field | source_type | status | why needed |
|---|---|---|---|
| `baseline_user_id` | inference | required new or mapped field | Groups repeated days for one person; current `user_id` is a scenario/day id and is not suitable. |
| `record_date` | inference | required new field | Enables 7-day window, ordering, weekday/weekend, and stale-record checks. |
| `day_index_in_learning_window` | inference | optional but useful derived field | Makes fixed 7-day learning-window outputs easier to audit. |
| `day_of_week` | inference | derived from `record_date` or provided | Enables future weekday/weekend split. |
| `is_learning_window_day` | inference | optional flag | Separates baseline-learning records from later scoring records. |
| `daily_total.available_meals` | local_file | exists now | Required for record completeness and missing-slot checks. |
| `daily_total.coverage_flags.full_day_record_complete` | local_file | exists now | Required to exclude incomplete days from kcal/food baseline aggregates. |
| `meals[].meal_slot` | local_file | exists now | Supports coarse meal presence and largest-meal-slot metrics. |
| `meals[].kcal_mid` | local_file | exists now | Supports largest-meal-slot and meal kcal distribution. |
| `daily_total.kcal_mid` | local_file | exists now | Required for energy curve median/IQR. |
| `daily_total.kcal_range` | local_file | exists now | Useful as uncertainty context, not true intake spread. |
| `daily_total.estimated_energy_requirement_kcal` | local_file | exists now | Health-reference anchor for kcal curve. |
| `daily_total.macro_structure_pct.*` | local_file | exists now | Required for macro curve median/IQR. |
| `daily_total.food_group_totals.*` | local_file | exists now | Required for food-pattern curve. |
| `daily_total.moderation_estimates.*.confidence` | local_file | partial exists now | Supports moderation confidence gate. |
| `daily_confidence_avg` | inference | net-new or derived field | Required by PRD readiness rule. |
| `energy_confidence_avg` | inference | net-new or derived field | PRD asks for energy confidence; no current field observed. |
| `food_group_confidence_avg` | inference | net-new or derived field | PRD asks for food-group confidence; no current field observed. |
| `manual_confirmed` | local_file | not observed | Needed for future high-trust records. |
| `user_correction_count` | local_file | not observed | Needed for correction-aware confidence. |

Minimum record shape:

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
    "energy_confidence_avg": "medium",
    "food_group_confidence_avg": "medium"
  }
}
```

### Q2. `daily_confidence_avg` aggregation rule

Codex proposal, source_type: inference.

Do not use a single weighted mean alone, because a severe low-confidence sub-area can hide inside averages. Use a two-stage rule:

1. Convert confidence labels to numeric values: `high=1.0`, `medium=0.67`, `low=0.33`, `missing=0.0`.
2. Compute module confidence:
   - `energy_confidence`: net-new preferred; fallback derived from kcal source quality if available. Current master has no explicit energy confidence.
   - `food_group_confidence`: net-new preferred; current master has food-group totals but no food-group confidence.
   - `moderation_confidence`: mean of present `daily_total.moderation_estimates.*.confidence`.
   - `coverage_confidence`: `1.0` if full day complete, `0.33` if incomplete.
3. Compute `daily_confidence_avg = min(weighted_mean(module confidences), minimum_critical_module_cap)`.
4. Critical cap rule:
   - if `coverage_confidence < medium`, cap daily confidence at `low`;
   - if energy or food-group confidence is missing, cap at `medium` until net-new fields exist;
   - if moderation confidence is low, do not cap the whole day, but exclude moderation baseline aggregates below the threshold.

This is conservative enough to avoid a polished-looking average from laundering incomplete records.

### Q3. Synthetic mock 7-day single user from complete days

| claim | source_type | source | answer |
|---|---|---|---|
| There are enough complete records in `v2_baseline` to synthesize a 7-day mock. | calculated_from_local_data | `references/test_sets/testset_master_all.json` | `v2_baseline` has 9 complete records. |
| The synthetic mock must not be treated as a real baseline. | inference | based on scenario-group semantics | These records are different users/scenarios, not repeated observations of one user. |

Recommended pipeline-test approach:

- Use 7 of the 9 complete `v2_baseline` records.
- Rewrite copies into a separate test fixture, not the source master file.
- Add `baseline_user_id = "synthetic_pipeline_user_001"`.
- Add sequential `record_date` values.
- Add `synthetic_baseline_fixture = true`.
- Preserve original `source_user_id` and `source_profile`.
- Label the fixture: `for_pipeline_shape_test_only_not_product_evidence`.

Other complete scenario groups are useful for red-team unit tests but not for a neutral 7-day mock because they are paired edge-case controls.

### Q4. Are `energy_confidence_avg` / `food_group_confidence_avg` derivable today?

| field | source_type | current availability | answer |
|---|---|---|---|
| `energy_confidence_avg` | local_file | not observed in master JSON or kcal output | Net-new preferred; only `kcal_range` exists, but range is not explicitly confidence. |
| `food_group_confidence_avg` | local_file | not observed in master JSON or kcal output | Net-new preferred; food-group totals exist without confidence. |
| `moderation_confidence_avg` | local_file | partially derivable | `daily_total.moderation_estimates.*.confidence` exists. |
| `coverage_confidence` | calculated_from_local_data | derivable | `full_day_record_complete` can gate completeness. |

Do not derive energy confidence from kcal range unless the upstream recognition contract explicitly says the range width represents confidence. That would otherwise be an assumption.

### Q5. Confirm `primary_goal` -> `primary_direction`

Codex cannot confirm this as a fact from local files. Current evidence:

| source_type | source | evidence |
|---|---|---|
| local_file | `Diet Balance Baseline 新版PRD.md` | Uses `primary_direction` in the example profile. |
| local_file | `references/test_sets/testset_master_all.json` | Uses `user_profile.primary_goal`. |

Engineering recommendation, source_type: inference:

- Treat this as a rename candidate, not a confirmed rename.
- In v0 schema, prefer `primary_direction`.
- During migration, accept `primary_goal` as a backward-compatible alias.
- Keep it interpretation-only in baseline v0.
- Do not infer Goal submodules from either name.

## Claude Layer Mapping to Local Data

| layer | metric family | computability against current local files | required action |
|---|---|---|---|
| `core_baseline` | `energy.kcal_curve` | not computable as real baseline | add longitudinal schema; synthetic fixture only for pipeline shape |
| `core_baseline` | `macro.structure_curve` | not computable as real baseline | add longitudinal schema |
| `core_baseline` | `food_pattern.hei_curve` | not computable as real baseline | add longitudinal schema + food-group confidence |
| `context_baseline` | `profile.metabolic` | computable now | keep as context, not score |
| `context_baseline` | `profile.direction` | field exists as `primary_goal`; PRD says `primary_direction` | migrate/alias; interpretation-only |
| `quality_baseline` | `valid_record_days` | not computable as same-user count | add `baseline_user_id` + `record_date` |
| `quality_baseline` | `complete_day_records` | not computable as same-user count | add `baseline_user_id` + `record_date`; use existing full-day flag |
| `quality_baseline` | `daily_confidence_avg` | partially designable, not directly present | add or derive with explicit aggregation contract |
| `quality_baseline` | `missing_meal_slots` | computable with assumption | formalize expected slots or allow user/culture-specific slots |
| `future_baseline` | meal timing curve | not computable | add meal timestamps |
| `future_baseline` | weekday/weekend split | not computable today | add `record_date`; derive `day_of_week` |
| `future_baseline` | CV/stability labels | not recommended at 7 days | defer beyond v0 |
| `future_baseline` | corrections/manual confirmation | not observed | add product event fields |

## Data Contract Draft for Baseline v0 Outputs

source_type: inference

```json
{
  "baseline_status": "ready | insufficient_data",
  "baseline_user_id": "user_123",
  "learning_window": {
    "start_date": "2026-06-10",
    "end_date": "2026-06-16",
    "learning_period_days": 7,
    "valid_record_days": 6,
    "complete_day_records": 4
  },
  "baseline_confidence": "low | medium | high",
  "core_baseline": {
    "energy_kcal": {
      "median": 2100,
      "iqr": [1900, 2300],
      "complete_days_used": 4,
      "health_reference_anchor": "estimated_energy_requirement_kcal"
    },
    "macro_pct": {
      "carb_median": 0.52,
      "fat_median": 0.30,
      "protein_median": 0.18,
      "health_reference_anchor": "AMDR"
    },
    "food_pattern": {
      "vegetable_cup_median": 1.5,
      "whole_fruits_cup_median": 0.5,
      "whole_grains_oz_median": 1.0,
      "refined_grains_oz_median": 4.0,
      "fiber_g_median": 14,
      "health_reference_anchor": "HEI_2020_available"
    }
  },
  "context_baseline": {
    "profile_source": "user_profile",
    "primary_direction": "maintain"
  },
  "quality_baseline": {
    "missing_meal_slots": ["breakfast"],
    "daily_confidence_avg": "medium",
    "excluded_days": [
      { "record_date": "2026-06-12", "reason": "incomplete_partial_day" }
    ]
  },
  "health_reference_axis": {
    "note": "Health anchors constrain interpretation; personal-normal does not bless unhealthy stable behavior."
  }
}
```

## Questions for Claude

1. Should `baseline_status=ready` require `complete_day_records >= 3` exactly as PRD says, or should kcal/food-pattern core baselines require `complete_day_records >= 5` while profile/context can be ready earlier?
2. For confidence aggregation, do you prefer a hard minimum rule (`daily_confidence = min(modules)`) or the proposed weighted mean with critical caps?
3. Should synthetic 7-day fixtures be added to the repo now as a separate file, or should they wait until after the baseline metric definitions are finalized?
4. Is `food_pattern.hei_curve` the right name, or should v0 avoid "HEI" in the personal-normal metric name to prevent mixing personal curve with health-reference score?
5. Should future schema require meal timestamps immediately, or keep timestamps optional until Meal Timing leaves placeholder status?

---

# Codex Output — Round 4 Convergence

status: done_for_turn
owner: codex
round: 4

## Claim

The four lock items are closed. Codex accepts Claude's Round 3 amendments and produced the Baseline v0 draft deliverables.

## Evidence

- source_type: local_file
- source: `ai_collab/diet_balance_baseline/CLAUDE_OUT.md`
- evidence: Claude Round 3 accepts Codex schema and asks Codex to close tiered readiness, structural two-axis, confidence contract, and names.

- source_type: local_file
- source: `ai_collab/diet_balance_baseline/DECISIONS.md`
- evidence: Round 2-3 converging points already record the two missing keys, structural two-axis, naming, tiered readiness, confidence caps, and deferred synthetic fixture.

## Lock Items Closed

| lock item | Codex decision | source_type | engineering note |
|---|---|---|---|
| Tiered readiness | accepted: emit core curves at `complete_day_records >= 3` with low confidence; medium at `>=5`; high at 7 days with `daily_confidence_avg >= medium` | inference | No engineering blocker; this is output-state logic. |
| Structural two-axis | accepted: every core metric must include inline health-reference comparison fields | inference + local_file | No engineering blocker; per-day anchors already exist in kcal output debug for kcal ratio, AMDR, and HEI components. |
| `daily_confidence_avg` contract | accepted: weighted mean over present modules plus critical caps; missing energy/food-group confidence caps at medium until net-new fields exist | inference | Avoid double penalty by excluding missing modules from the mean while applying caps. |
| Metric names | locked: `energy.kcal_curve`, `macro.structure_curve`, `food_pattern.intake_curve` | inference | Avoids mixing personal-normal metric names with HEI/AMDR health-reference names. |

## Answers to Claude Round 3 Questions

1. A1 engineering cost is low-to-medium. The anchor values are already present per day for kcal (`debug.kcal_balance.actual_to_target_ratio`), AMDR (`debug.amdr.*`), and HEI component debug. Baseline aggregation must carry median personal values plus an aggregated reference status; no formula-weight work is needed.
2. Codex agrees with emit-at-3 / trust-at-5 rather than a single hard block.
3. Codex agrees v0 can ship the confidence contract with `energy_confidence` and `food_group_confidence` treated as missing, capped at medium, until recognition adds net-new fields.
4. Codex agrees the next artifact is the joint Baseline v0 draft. Files produced:
   - `Diet Balance Baseline v0 指标定义.md`
   - `Diet Balance Baseline v0 指标矩阵.csv`
   - `Diet Balance Baseline Red-Team Cases.md`
   - `Diet Balance Baseline Open Questions.md`

## Risk

These deliverables are still a candidate definition, not calculator implementation. No formula weights are finalized, no Goal/Finish scope is added, and the current master test set remains unsuitable as real baseline evidence.

---

# Codex Output — Illness Adjustment Insert

status: done_for_turn
owner: codex
round: illness_insert_codex_proposal

## Claim

If the system has already determined the user is sick, Diet Baseline should treat that period as a temporary exception window, not as normal baseline evidence; Diet Balance should either freeze, annotate, or use a special illness-mode scoring policy depending on product risk tolerance.

## Evidence

- source_type: inference
- source: baseline v0 decisions
- evidence: v0 already separates personal-normal axis from health-reference axis, excludes incomplete/low-confidence data from core aggregation, and prevents single-day outliers from moving baseline.

- source_type: assumption
- source: user instruction
- evidence: The illness detection problem is explicitly out of scope for this insert; assume an upstream system provides `illness_status=true` and an illness window.

## Scope

Not discussed here:

- how to detect illness;
- medical diagnosis;
- disease-specific nutrition advice;
- changing Goal/Finish;
- final formula weights.

Discussed here:

- how illness-tagged days affect baseline learning;
- how illness-tagged days affect same-day Diet Balance interpretation;
- what output fields are needed.

## Three Candidate Schemes

### Scheme A — Baseline Freeze + Score Annotate

| item | proposal |
|---|---|
| Baseline learning | Exclude illness-tagged days from `core_baseline` aggregation. Existing baseline is frozen. |
| Diet Balance formula | Keep existing health-reference calculation, but mark `illness_adjustment_mode = annotate_only`. |
| User interpretation | Explain that intake may be temporarily atypical due to illness; avoid treating deviation from baseline as habit change. |
| Output fields | `illness_status`, `illness_window_id`, `excluded_from_baseline=true`, `diet_balance_interpretation_context=illness`. |
| Pros | Lowest engineering and medical risk; does not invent disease nutrition logic. |
| Cons | Score may still look harsh during illness; user may feel unfairly judged. |
| Best use | Mild/uncertain illness states, or first v0 implementation. |

source_type: inference

### Scheme B — Baseline Freeze + Score Softening / Confidence Downgrade

| item | proposal |
|---|---|
| Baseline learning | Exclude illness-tagged days from `core_baseline`; do not update personal-normal curves. |
| Diet Balance formula | Keep component scores visible, but lower score confidence and optionally suppress formal ranking/badges. |
| User interpretation | Show "illness-context day" rather than normal Diet Balance judgement; emphasize recovery-context interpretation. |
| Output fields | `score_status=illness_context`, `diet_balance_confidence=low_or_contextual`, `ranking_status=not_ranked`, `excluded_from_baseline=true`. |
| Pros | Avoids punishing illness-driven low appetite, bland diet, missed meals, or unusual eating. |
| Cons | Needs product decision on whether to still display numeric score; may reduce comparability. |
| Best use | Fever, GI symptoms, appetite loss, or other illness windows likely to distort intake. |

source_type: inference

### Scheme C — Separate Illness Baseline Track

| item | proposal |
|---|---|
| Baseline learning | Do not merge illness days into normal baseline. Store them under `illness_context_history` or `temporary_exception_baseline`. |
| Diet Balance formula | Normal Diet Balance remains anchored to health reference; illness mode can compare current illness-day intake to prior illness-context days if enough exist. |
| User interpretation | "Compared with your usual illness-context pattern..." only after repeated illness windows exist. |
| Output fields | `normal_baseline_excluded=true`, `illness_context_history_updated=true`, `illness_context_sample_count`, `illness_context_confidence`. |
| Pros | Preserves normal baseline while allowing future personalization for recurring illness contexts. |
| Cons | Most complex; high risk of overfitting and accidental medical interpretation; likely not v0. |
| Best use | Future version for users with repeated short illness episodes or medically supervised contexts. |

source_type: inference

## Codex Recommendation

Use Scheme B as v0 product behavior, with Scheme A as the fallback if product wants lower complexity.

Reasoning:

- Scheme A is safe but may still produce a normal-looking score during a non-normal physiological state.
- Scheme B keeps the baseline clean and also avoids over-interpreting the daily score.
- Scheme C is valuable but should be deferred because it creates a separate physiological context model and could drift into medical advice.

## Proposed v0 Fields

| field | source_type | status | note |
|---|---|---|---|
| `health_context.illness_status` | assumption | upstream input | Boolean or enum supplied by detection layer. |
| `health_context.illness_window_id` | assumption | upstream input | Groups days in the same illness episode. |
| `health_context.illness_day_index` | assumption | optional upstream/derived | Useful for temporary window handling, not diagnosis. |
| `baseline_policy.exclude_from_core_baseline` | inference | required | True for illness-tagged days in Scheme A/B/C. |
| `score_policy.score_status` | inference | required for Scheme B | Suggested value: `illness_context`. |
| `score_policy.ranking_status` | inference | required for Scheme B | Suggested value: `not_ranked`. |
| `score_policy.interpretation_mode` | inference | required | Suggested value: `illness_context_annotation`. |
| `illness_context_history` | inference | future only | Scheme C, not v0. |

## Questions for Claude

1. Should v0 choose Scheme A or Scheme B as the default illness behavior?
2. Should illness-context days still show `diet_balance_raw`, or should they show components only with `ranking_status=not_ranked`?
3. Is Scheme C too medically risky for this product stage, or should it remain explicitly future_baseline?
4. What wording prevents the product from giving disease-specific advice while still being empathetic?
5. Should illness-context days count toward `valid_record_days` for learning-period readiness, or be excluded from both `valid_record_days` and `complete_day_records`?

---

# Codex Output - Illness Closure + v0 Fixes

status: done_for_turn
owner: codex
round: illness_insert_codex_closure

## Claim

Codex accepts Claude's illness reframing and applied the pending v0 fixes F1/F2/F3. Baseline v0 can now treat illness as a presentation/context layer plus baseline exclusion, not as a numeric score boost or a parallel baseline policy.

source_type: inference

## Illness Decisions Accepted

| question | Codex answer | source_type |
|---|---|---|
| Drop "softening"? | Accepted. v0 wording should not use "softening" because it can imply numeric inflation. O2 means suppress/relabel/downgrade confidence only. | inference |
| Can illness numerically boost Diet Balance? | No. Illness context may hide the formal score, remove ranking, show components, and mark confidence contextual, but must never raise `diet_balance` or create a success badge. | inference |
| Reuse `excluded_days`? | Accepted. Illness day = `quality_baseline.excluded_days[].reason = "illness_context"`. No parallel `baseline_policy` block in v0. | inference |
| Learning window behavior? | Accepted. Illness days are excluded from both `valid_record_days` and `complete_day_records`; onboarding becomes rolling until N valid days when illness intervenes. | inference |
| Default option? | O2 Contextualize is the recommended v0 default; O1 Annotate is fallback; O3 Separate illness track is future-only. | inference |

## User Readiness-Paradox Case

The user's observation of a sick user in hospital/IV context receiving a very high recovery-like score is recorded as `source_type=user_observation`, not as a verified external product fact. Codex agrees this strengthens O2 over O1: a normal-looking high score during illness can be misleading even if it is merely annotated.

source_type: user_observation + inference

## Files Updated

| file | change | source_type |
|---|---|---|
| `Diet Balance Baseline Illness Adjustment Options.md` | Rewrote A/B/C into O1 Annotate, O2 Contextualize, O3 Separate illness track; removed `baseline_policy`; added v0 output shape using `health_context`, `quality_baseline.excluded_days`, and `score_policy`. | local_file |
| `Diet Balance Baseline Red-Team Cases.md` | Added RT-I1 through RT-I4 and a hard rule that illness may suppress/relabel/downgrade but never numerically boost Diet Balance. | local_file |
| `Diet Balance Baseline v0 指标定义.md` | Applied F1 readiness table fix; added illness rolling-window rule; added canonical `HEI_2020_food_pattern` mapping; added `trend.reference_convergence` and separate illness track to exclusions. | local_file |
| `Diet Balance Baseline v0 指标矩阵.csv` | Added `trend.reference_convergence` as `future_baseline`, distinct from CV/stability. | local_file |
| `ai_collab/diet_balance_baseline/DECISIONS.md` | Recorded Codex acceptance and v0 freeze candidate after F1/F2/F3 + illness closure. | local_file |

## v0 Fixes Applied

| finding | result | source_type |
|---|---|---|
| F1 readiness undefined band | Fixed readiness rows to use `complete_day_records < 3`, `complete_day_records >= 3 AND valid_record_days < 5`, and `complete_day_records >= 3 AND valid_record_days >= 5`. | inference |
| F2 food-pattern anchor token | Canonical token is `HEI_2020_food_pattern`; it maps to calculator component `HEI_2020_available` while keeping personal-normal name `food_pattern.intake_curve`. | inference + local_file |
| F3 missing trend/direction signal | Added `trend.reference_convergence` as a future item, explicitly distinct from CV/stability and not v0 core. | inference |

## Handoff To Claude

Please do a final acceptance pass on the updated illness layer and F1/F2/F3 edits. If no blocker remains, record Baseline v0 as frozen definition-phase output.
