# Diet Balance Calculator Change Log

This file records calculator edits so the workspace can be precisely rolled back later.

## 2026-06-15 - HEI + Kcal calculator full HEI-2020 moderation components

### Context

- Request: add the missing HEI-2020 moderation/balance fields to `relty_diet_balance_calculator_kcal.ps1`.
- Prior issue: HEI used only 9 food-pattern components and left `fatty_acids`, `sodium`, `added_sugars`, and `saturated_fats` unscored, causing a processed-food blind spot.

### Files changed

1. `relty_diet_balance_calculator_kcal.ps1`
   - Updated schema from `relty_diet_balance_calculator_kcal.v0_4` to `relty_diet_balance_calculator_kcal.v0_5`.
   - Added HEI scoring for available `daily_total.moderation_estimates`:
     - `saturated_fat_g` -> saturated fats percent energy, max 10 points.
     - `added_sugars_g` -> added sugars percent energy, max 10 points.
     - `sodium_mg` -> sodium g/1000 kcal, max 10 points.
     - `fatty_acids` -> `(PUFA + MUFA) / SFA`, max 10 points.
   - Preserved dynamic HEI numerator/denominator:
     - fields present are added to both `recognized_score_points` and `recognized_max_points`;
     - fields absent are excluded from both sides.
   - Preserved legacy behavior for older datasets without moderation fields: HEI max remains 60.
   - Added debug retention for moderation confidence/source/conversions.
   - Fixed incomplete record status:
     - incomplete rows now use `score_status = incomplete_partial_day`;
     - `ranking_status = not_ranked`;
     - `diet_balance_raw = null`;
     - `kcal_balance = null` with debug reason `missing_meals`.
   - Added CSV fields:
     - `ranking_status`
     - `is_partial_day_score`
     - `hei_recognized_score_points`
     - `hei_recognized_max_points`
     - `hei_unscored_components`
     - `partial_without_kcal_reference_raw`

2. `outputs/testset_master_all.diet_balance_kcal_results.json`
   - Recomputed and overwritten with v0.5 calculator output.

3. `outputs/testset_master_all.diet_balance_kcal_summary.csv`
   - Recomputed and overwritten with v0.5 calculator output.

4. `outputs/testset_master_all_kcal_report.md`
   - Rewritten with bilingual v0.5 report.
   - Includes A1 vs A2 difference, moderation-driven decrease list, HEI denominator 100 list, incomplete-record status, and the caveat that user05/user08/user09 do not decrease under the provided official thresholds and current data.

5. `outputs/v0_5_legacy_check/`
   - Temporary compatibility check output confirming old testset without moderation fields still has HEI max 60.

### Rollback instructions

To roll back this operation exactly:

1. Restore `relty_diet_balance_calculator_kcal.ps1` to the v0.4 version.
2. Regenerate or restore the v0.4 files:
   - `outputs/testset_master_all.diet_balance_kcal_results.json`
   - `outputs/testset_master_all.diet_balance_kcal_summary.csv`
   - `outputs/testset_master_all_kcal_report.md`
3. Delete `outputs/v0_5_legacy_check/`.
4. Remove this changelog section if the operation log itself should reflect the rollback.

### Verification commands

Run from `E:\01Internship\Relty\diet_balance_test`:

```powershell
.\relty_diet_balance_calculator_kcal.ps1 -InputJson .\test_sets\testset_master_all.json -OutputDir .\outputs
.\relty_diet_balance_calculator_kcal.ps1 -InputJson .\test_sets\diet_balance_testset_v2.json -OutputDir .\outputs\v0_5_legacy_check
```

Observed behavior:

- `userA1-clean` = 82.04 and `userA2-junk` = 71.64; A1 exceeds A2 by 10.40 points.
- Complete master records with moderation fields have HEI `recognized_max_points = 100`.
- Old v2 records without moderation fields keep HEI `recognized_max_points = 60`.
- Incomplete rows use `score_status = incomplete_partial_day` and `ranking_status = not_ranked`.
- `user05-01`, `user08-01`, and `user09-01` do not decrease under the provided thresholds because their moderation component averages are higher than their original food-pattern HEI averages.

## 2026-06-15 - HEI + Kcal calculator user-profile RDA/AI personalization

### Context

- Request: the HEI + Kcal calculator must incorporate user sex, age, and weight.
- Existing issue: `relty_diet_balance_calculator_kcal.ps1` used global default age and sex for RDA/AI, and did not use per-user body weight.

### Files changed

1. `relty_diet_balance_calculator_kcal.ps1`
   - Updated schema from `relty_diet_balance_calculator_kcal.v0_3` to `relty_diet_balance_calculator_kcal.v0_4`.
   - Added `Get-UserProfileForScoring`.
   - RDA/AI now reads per-user profile fields when present:
     - `user_profile.age_years`
     - `user_profile.sex`
     - `user_profile.weight_kg`
   - Protein target changed from fixed sex-based adult fallback to weight-based target when possible:
     - `protein_target_g = 0.8 * weight_kg`
   - Fiber target continues to use age and sex.
   - Output JSON now includes `scoring_profile` and RDA/AI debug target source.
   - Output CSV now includes:
     - `scoring_age_years`
     - `scoring_sex`
     - `scoring_weight_kg`

2. `outputs/testset_master_all.diet_balance_kcal_results.json`
   - Recomputed and overwritten with v0.4 calculator output.

3. `outputs/testset_master_all.diet_balance_kcal_summary.csv`
   - Recomputed and overwritten with v0.4 calculator output.

4. `outputs/testset_master_all_kcal_report.md`
   - Rewritten to reflect v0.4 user-profile RDA/AI results.

### Rollback instructions

To roll back this operation exactly:

1. Restore `relty_diet_balance_calculator_kcal.ps1` to the version before this section.
2. Re-run the prior v0.3 calculator on `test_sets/testset_master_all.json` if the previous outputs are needed.
3. Restore or regenerate the previous `outputs/testset_master_all.diet_balance_kcal_results.json`.
4. Restore or regenerate the previous `outputs/testset_master_all.diet_balance_kcal_summary.csv`.
5. Restore or regenerate the previous `outputs/testset_master_all_kcal_report.md`.

### Verification commands

Run from `E:\01Internship\Relty\diet_balance_test`:

```powershell
.\relty_diet_balance_calculator_kcal.ps1 -InputJson .\test_sets\testset_master_all.json -OutputDir .\outputs
```

Expected behavior:

- Output schema is `relty_diet_balance_calculator_kcal.v0_4`.
- JSON user rows include `scoring_profile`.
- RDA/AI debug shows protein target source as `0.8 g/kg/day from user weight` when `weight_kg` exists.
- CSV includes `scoring_age_years`, `scoring_sex`, and `scoring_weight_kg`.

## 2026-06-15 - China DQD variant calculator

### Context

- Request: create a China-version calculator where HEI is replaced by DQI/DQD.
- DQD is treated as a diet quality distance: larger raw distance is worse.
- The calculator remaps DQD to `0-100`, where `100` means best and `0` means worst.
- Existing calculators were not overwritten.

### Files changed

1. `relty_diet_balance_calculator_china_dqd.ps1`
   - Created as a separate calculator variant.
   - Replaces the HEI module with `DQD_0_100`.
   - Keeps the five-module kcal formula structure:
     - `0.40*DQD_0_100`
     - `0.15*AMDR_Fit`
     - `0.20*RDA_AI_Adequacy`
     - `0.10*Meal_Timing`
     - `0.15*Kcal_Balance`
   - Adds `CalculateDqdAvailable`, which maps current structured recognition fields to China-style food-group target intervals:
     - total grains: `200-300 g/day`
     - whole grains: `50-150 g/day`
     - total vegetables: `300-500 g/day`
     - dark vegetables proxy: `150-250 g/day`
     - whole fruits: `200-350 g/day`
     - dairy milk equivalent: `300-500 g/day`
     - protein foods proxy: `120-200 g/day`
   - Adds DQD remap:
     - `DQD_0_100 = 100 * (1 - dqd_raw_distance / dqd_max_distance)`
     - `100` is best; `0` is worst.
   - Lists China guideline components that are not yet scored because current recognition fields do not provide them:
     - salt
     - cooking oil
     - soybeans and nuts
     - tubers
     - aquatic products separate from other protein
     - eggs separate from other protein
     - food variety
   - Writes distinct output files:
     - `<basename>.diet_balance_china_dqd_results.json`
     - `<basename>.diet_balance_china_dqd_summary.csv`
   - Uses schema `relty_diet_balance_calculator_china_dqd.v0_1`.

2. `outputs/testset_D_moderation_perverse_incentive.diet_balance_china_dqd_results.json`
   - Verification output generated with `-DefaultTargetKcal 2200`.

3. `outputs/testset_D_moderation_perverse_incentive.diet_balance_china_dqd_summary.csv`
   - Verification summary generated with `-DefaultTargetKcal 2200`.

4. `outputs/china_dqd_no_target_check/`
   - Temporary verification output showing that no target kcal produces `score_status = kcal_target_unavailable`.

### Rollback instructions

To roll back this operation exactly:

1. Delete `relty_diet_balance_calculator_china_dqd.ps1`.
2. Delete `outputs/testset_D_moderation_perverse_incentive.diet_balance_china_dqd_results.json`.
3. Delete `outputs/testset_D_moderation_perverse_incentive.diet_balance_china_dqd_summary.csv`.
4. Delete `outputs/china_dqd_no_target_check/`.
5. Remove this changelog section if the operation log itself should reflect the rollback.

### Verification commands

Run from `E:\01Internship\Relty\diet_balance_test`:

```powershell
.\relty_diet_balance_calculator_china_dqd.ps1 -InputJson .\test_sets\testset_D_moderation_perverse_incentive.json -OutputDir .\outputs\china_dqd_no_target_check
.\relty_diet_balance_calculator_china_dqd.ps1 -InputJson .\test_sets\testset_D_moderation_perverse_incentive.json -OutputDir .\outputs -DefaultTargetKcal 2200
```

Expected behavior:

- Without a target kcal, user rows have `score_status = kcal_target_unavailable` and no fabricated `diet_balance_raw`.
- With `-DefaultTargetKcal 2200`, user rows have `score_status = complete_with_kcal_balance` and a five-module China DQD Diet Balance score.

## 2026-06-15 - Kcal Balance variant calculator

### Context

- Request: add a new Kcal module with weight `0.15`, without overwriting the existing formula calculator.
- Product clarification: HEI and AMDR should keep their original interpretation; daily total kcal should be handled as a separate module because kcal only has meaning against personal energy need or expenditure.

### Files changed

1. `relty_diet_balance_calculator_kcal.ps1`
   - Created as a separate calculator variant copied from `relty_diet_balance_calculator.ps1`.
   - Original `relty_diet_balance_calculator.ps1` was not modified.
   - Added optional `-DefaultTargetKcal` parameter.
   - Added target kcal lookup from structured fields:
     - `daily_total.target_kcal`
     - `daily_total.tdee_kcal`
     - `daily_total.estimated_energy_requirement_kcal`
     - `daily_total.energy_requirement_kcal`
     - `daily_total.energy_need_kcal`
     - `daily_total.recommended_kcal`
     - same names at user root level
     - fallback to `-DefaultTargetKcal` when provided
   - Added `Kcal_Balance` scoring:
     - full score when `actual_kcal / target_kcal` is between `0.90` and `1.10`
     - linearly decreases to `0` when deviation reaches `50%` or more
     - if no target kcal is available, marks `score_status = kcal_target_unavailable` and does not fabricate a Diet Balance score
   - Added five-module formula:
     - `0.40*HEI_2020_available`
     - `0.15*AMDR_Fit`
     - `0.20*RDA_AI_Adequacy`
     - `0.10*Meal_Timing`
     - `0.15*Kcal_Balance`
   - Writes distinct output files:
     - `<basename>.diet_balance_kcal_results.json`
     - `<basename>.diet_balance_kcal_summary.csv`
   - Updated schema to `relty_diet_balance_calculator_kcal.v0_3`.

2. `outputs/testset_D_moderation_perverse_incentive.diet_balance_kcal_results.json`
   - Verification output generated with `-DefaultTargetKcal 2200`.

3. `outputs/testset_D_moderation_perverse_incentive.diet_balance_kcal_summary.csv`
   - Verification summary generated with `-DefaultTargetKcal 2200`.

4. `outputs/kcal_no_target_check/`
   - Temporary verification output showing that no target kcal produces `score_status = kcal_target_unavailable`.

### Rollback instructions

To roll back this operation exactly:

1. Delete `relty_diet_balance_calculator_kcal.ps1`.
2. Delete `outputs/testset_D_moderation_perverse_incentive.diet_balance_kcal_results.json`.
3. Delete `outputs/testset_D_moderation_perverse_incentive.diet_balance_kcal_summary.csv`.
4. Delete `outputs/kcal_no_target_check/`.
5. Remove this changelog section if the operation log itself should reflect the rollback.

### Verification commands

Run from `E:\01Internship\Relty\diet_balance_test`:

```powershell
.\relty_diet_balance_calculator_kcal.ps1 -InputJson .\test_sets\testset_D_moderation_perverse_incentive.json -OutputDir .\outputs\kcal_no_target_check
.\relty_diet_balance_calculator_kcal.ps1 -InputJson .\test_sets\testset_D_moderation_perverse_incentive.json -OutputDir .\outputs -DefaultTargetKcal 2200
```

Expected behavior:

- Without a target kcal, user rows have `score_status = kcal_target_unavailable` and no fabricated `diet_balance_raw`.
- With `-DefaultTargetKcal 2200`, user rows have `score_status = complete_with_kcal_balance` and a five-module Diet Balance score.

## 2026-06-15 - Diet Recognition v2 input support

### Context

- Request: update the formula calculator based on the newer Diet Recognition PRD.
- Correction from product owner: the main PRD is older than the formula calculator. The current calculation standard is the calculator formula, not the HEI-only text in the main PRD.
- Current formula standard: `Diet Balance = 0.50*HEI_2020 + 0.20*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing`.
- Recognition PRD constraint: calculator inputs should use structured food-group fields from `food_group_estimates`, `food_group_totals`, and `coverage_flags`.

### Files changed

1. `relty_diet_balance_calculator.ps1`
   - Replaced the Markdown-only mandatory `-InputMarkdown` interface with a compatible multi-input interface:
     - `-InputPath`
     - `-InputJson`
     - legacy `-InputMarkdown`
   - Added JSON parsing for `nutrition_results.json` style batch outputs.
   - Added structured food-group ingestion:
     - first reads `daily_total.food_group_totals`
     - otherwise sums `meals[].food_group_estimates`
     - falls back to legacy food-name keyword estimates only when structured fields are absent
   - Renamed internal food-group fields to match the v2 PRD:
     - `total_fruits_cup`
     - `whole_fruits_cup`
     - `fruit_juice_cup`
     - `total_vegetables_cup`
     - `greens_and_beans_cup`
     - `whole_grains_oz`
     - `refined_grains_oz`
     - `dairy_cup`
     - `total_protein_foods_oz`
     - `seafood_and_plant_proteins_oz`
     - `fiber_g`
   - Initially changed `diet_balance` to HEI-only based on the stale main PRD; this was corrected in the same work session after product clarification.
   - Final behavior keeps the calculator's composite formula:
     - `0.50*HEI_2020_available`
     - `0.20*AMDR_Fit`
     - `0.20*RDA_AI_Adequacy`
     - `0.10*Meal_Timing`
   - AMDR, protein/fiber adequacy, and temporary Meal Timing are included in the main score per the current calculator standard.
   - Added `unscored_components` in HEI debug output for fields intentionally skipped by the v2 recognition PRD:
     - `fatty_acids`
     - `sodium`
     - `added_sugars`
     - `saturated_fats`
   - Updated output schema to `relty_diet_balance_calculator.v0_2`.

2. `Relty 指标计算框架.md`
   - Updated stale HEI-only Diet Balance content to match the calculator-backed composite standard.
   - Added Diet Recognition v2 structured input expectations to the Diet Balance section.
   - Clarified that the skipped recognition fields from the newer PRD are not part of this stage's structured input.

3. `CHANGELOG_diet_balance_calculator.md`
   - Created this rollback-oriented operation log.

### Rollback instructions

To roll back this operation exactly:

1. Restore `relty_diet_balance_calculator.ps1` to the pre-2026-06-15 version from version control or a backup.
2. Restore `Relty 指标计算框架.md` to the pre-2026-06-15 version from version control or a backup.
3. Delete `CHANGELOG_diet_balance_calculator.md` if the operation log itself should not remain.
4. Delete regenerated output files from `outputs/` if they were produced during verification.

### Verification commands

Run from `E:\01Internship\Relty\diet_balance_test`:

```powershell
.\relty_diet_balance_calculator.ps1 -InputJson .\nutrition_results.json -OutputDir .\outputs
```

Expected behavior:

- Produces a JSON output file under `outputs/`.
- Produces a CSV summary under `outputs/`.
- For current v1 sample JSON without structured v2 fields, `food_group_input_source` should be `legacy_food_name_keyword_fallback`.
- Output `formula` should be `Diet Balance = 0.50*HEI_2020_available + 0.20*AMDR_Fit + 0.20*RDA_AI_Adequacy + 0.10*Meal_Timing`.

## 2026-06-15 - Dynamic denominator audit

### Context

- Request: check whether the calculator preserves dynamic scoring behavior.
- Required behavior:
  - Recognition-required food pattern fields such as fruits, whole grains, refined grains, vegetables, dairy, protein foods, and fiber should count as zero when not recognized.
  - Temporarily skipped hard-to-recognize fields such as sodium, added sugars, saturated fat, and fatty acid quality should be removed from both numerator and denominator.

### Audit result

- `relty_diet_balance_calculator.ps1` already matches the requested behavior.
- `CalculateHeiAvailable` always includes the currently required food-pattern components in `components`, so missing fruit / whole grain / vegetable / dairy / protein values enter as zero and reduce the score.
- `refined_grains` is included as a moderation component. If refined grains are recognized at a high density, it reduces the score; if no refined grains are recognized, it receives full moderation credit.
- `sodium`, `added_sugars`, `saturated_fats`, and `fatty_acids` are listed in `unscored_components` and are not added to `components`, so they are excluded from both `recognized_score_points` and `recognized_max_points`.

### Files changed

1. `CHANGELOG_diet_balance_calculator.md`
   - Added this audit note only.

### Rollback instructions

To roll back this audit note, remove the `2026-06-15 - Dynamic denominator audit` section from this file. No calculator code rollback is needed because no calculation logic was changed in this audit.

## 2026-06-15 - Testset v2 execution and incomplete-day denominator fix

### Context

- Request: run `test_sets/diet_balance_testset_v2.json`, provide results, and write a report with interpretation.
- During testing, `user11-01` exposed an incomplete-day edge case. The record has breakfast only and explicitly says missing groups should not be zero-filled.

### Files changed

1. `relty_diet_balance_calculator.ps1`
   - Added `Get-HeiComponentInclusion`.
   - For complete records, all currently required HEI food-pattern components remain in the denominator.
   - For incomplete records, only meal-level `food_group_estimates` fields explicitly present are included in the HEI denominator.
   - Added `included_components` to HEI debug output.

2. `diet_balance_testset_v2_report.md`
   - Created the test report and interpretation.

3. `outputs/diet_balance_testset_v2.diet_balance_results.json`
   - Regenerated calculator output for the v2 testset.

4. `outputs/diet_balance_testset_v2.diet_balance_summary.csv`
   - Regenerated summary CSV for the v2 testset.

5. `CHANGELOG_diet_balance_calculator.md`
   - Added this operation record.

### Result summary

- Users tested: 11
- Average Diet Balance: 61.22
- Minimum: 51.42
- Maximum: 92.01
- High band, >= 80: 2 users
- Medium band, 60-79.99: 1 user
- Low band, < 60: 8 users

### Rollback instructions

To roll back this operation:

1. Restore `relty_diet_balance_calculator.ps1` to the version before `Get-HeiComponentInclusion` was added.
2. Delete `diet_balance_testset_v2_report.md`.
3. Delete regenerated files:
   - `outputs/diet_balance_testset_v2.diet_balance_results.json`
   - `outputs/diet_balance_testset_v2.diet_balance_summary.csv`
4. Remove this changelog section.

## 2026-06-15 - Bilingual report update

### Context

- Request: report output should be bilingual, with Chinese first.
- Permission boundary observed: only the Markdown report and this operation log were edited. No formula or calculator code was changed.

### Files changed

1. `diet_balance_testset_v2_report.md`
   - Rewritten into a bilingual report.
   - Chinese report appears first.
   - English report appears second.
   - Result numbers and interpretations were preserved.

2. `CHANGELOG_diet_balance_calculator.md`
   - Added this operation record.

### Rollback instructions

To roll back this operation:

1. Restore `diet_balance_testset_v2_report.md` to the previous English-only version.
2. Remove this changelog section.

## 2026-06-15 - Report clarification for dynamic denominator and incomplete records

### Context

- Request: clarify what dynamic HEI denominator means, confirm whether results are calculated rather than fabricated, and ensure incomplete records are not ranked with complete records.
- Permission boundary observed: only the Markdown report and this operation log were edited. No formula or calculator code was changed.

### Files changed

1. `diet_balance_testset_v2_report.md`
   - Clarified that only the HEI subscore denominator is dynamic.
   - Clarified that AMDR, RDA/AI, Meal Timing, and top-level formula weights are not dynamic in the current calculator.
   - Added an explicit result-source statement saying report values come from calculator output JSON/CSV.
   - Recomputed report-level ranking and distribution to include only complete records.
   - Moved `user11-01` into a separate incomplete-record table.
   - Added present/missing meals for `user11-01`: present `breakfast`, missing `lunch`, `dinner`.

2. `CHANGELOG_diet_balance_calculator.md`
   - Added this operation record.

### Rollback instructions

To roll back this operation:

1. Restore `diet_balance_testset_v2_report.md` to the previous bilingual version.
2. Remove this changelog section.

## 2026-06-15 - China DQD calculator sync to v0_2 and master rerun

### Context

- Request: China version was still behind the HEI+Kcal calculator fixes and needed to be brought forward before reporting `testset_master_all.json`.
- Permission: calculator changes were authorized by the user in this thread. This entry records the formula/calculator sync and the generated outputs.

### Files changed

1. `relty_diet_balance_calculator_china_dqd.ps1`
   - Updated schema from `relty_diet_balance_calculator_china_dqd.v0_1` to `relty_diet_balance_calculator_china_dqd.v0_2`.
   - Added user-profile-aware RDA/AI scoring:
     - protein target uses `0.8 g/kg/day` when `user_profile.weight_kg` is available.
     - fiber target uses `user_profile.age_years` and `user_profile.sex` when available.
   - Fixed incomplete-record handling:
     - incomplete rows use `score_status = incomplete_partial_day`.
     - incomplete rows use `ranking_status = not_ranked`.
     - incomplete rows do not receive formal `Diet Balance` or `Kcal_Balance`.
     - diagnostic `no_kcal_reference_raw` is kept for traceability only.
   - Added summary fields for ranking status, partial-day status, and scoring profile.
   - Kept the China DQD design boundary explicit: HEI `moderation_estimates` are not directly added as DQD components in v0_2.

2. `outputs/testset_master_all.diet_balance_china_dqd_results.json`
   - Regenerated by running the China DQD calculator on `test_sets/testset_master_all.json`.
   - Overwrote the prior China DQD result JSON.

3. `outputs/testset_master_all.diet_balance_china_dqd_summary.csv`
   - Regenerated by running the China DQD calculator on `test_sets/testset_master_all.json`.
   - Overwrote the prior China DQD summary CSV.

4. `outputs/testset_master_all_china_dqd_report.md`
   - Rewritten as a bilingual report, Chinese first and English second.
   - Updated source schema to v0_2.
   - Updated complete-record ranking and incomplete-record table from the regenerated outputs.
   - Clarified that A1/A2 remain tied because current China DQD does not score HEI moderation fields.

### Result summary

- Input: `test_sets/testset_master_all.json`
- Complete records ranked: 20
- Incomplete records not ranked: 4
- Complete-record average Diet Balance: 65.28
- Highest complete record: `user10-01`, 87.96
- Lowest complete record: `user05-01`, 49.37
- A1/A2 difference in China DQD v0_2: 0.00, because the current DQD mapping does not include moderation fields.

### Rollback instructions

To roll back this operation:

1. Restore `relty_diet_balance_calculator_china_dqd.ps1` to the v0_1 version.
2. Restore or delete regenerated outputs:
   - `outputs/testset_master_all.diet_balance_china_dqd_results.json`
   - `outputs/testset_master_all.diet_balance_china_dqd_summary.csv`
   - `outputs/testset_master_all_china_dqd_report.md`
3. Remove this changelog section.
