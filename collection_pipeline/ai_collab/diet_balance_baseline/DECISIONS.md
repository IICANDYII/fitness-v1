# Diet Balance Baseline Decisions

## Accepted Decisions

- Current focus is Diet Balance Baseline.
- Do not define Goal submodules in this workstream.
- Do not expand Finish.
- Do not finalize formula weights yet.
- Baseline is a user-specific reference learned from a one-week learning period.
- Baseline can later affect Diet Balance calculation, so metric reliability matters.

## Rejected / Deferred

- Goal completion: deferred.
- Goal recommendation: deferred.
- Final formula weighting: deferred.

## Round 1 — Converging Points (Codex facts + Claude critique)

- **Master test set is NOT a baseline.** 24 distinct single-day users (`user01-01 … user24-01`); no longitudinal same-user data. (Codex + Claude re-verified.)
- **The repo today supports the health-reference axis, not the personal-normal axis.** Every personal-normal metric (kcal/macro/food-pattern curve, valid/complete day counts, stability) needs a longitudinal schema that does not yet exist.
- **Two axes must both survive into v0:** personal-normal (today vs user's own curve) AND health-reference (HEI/AMDR/RDA/kcal anchors). Personal-normal may change explanation + confidence but may NOT by itself raise Diet Balance in v0.
- **Layering agreed (proposed):** core_baseline = personal curves (needs longitudinal schema); context_baseline = profile/direction; quality_baseline = readiness + confidence gates; future_baseline = meal timing, weekday/weekend split, CV/stability labels.
- **Meal_Timing = 100 is a placeholder** (`temporary_full_score_until_reliable_multi_day_timing_data`) — excluded from baseline influence in v0.
- **HEI components / AMDR gap / kcal-vs-target are health-reference anchors, not personal baseline** — do not relabel them as baseline.
- **Incomplete days** are excluded from kcal/food baseline aggregates and downgrade confidence; never read as low intake.
- **`primary_goal` vs PRD `primary_direction`** — naming mismatch; treat as interpretation-only context in v0; do NOT expand into Goal.

## Round 2–3 — Converging Points (Codex schema + Claude amendments)

- **Two missing keys identified:** `baseline_user_id` (stable person id, distinct from scenario `user_id`) + `record_date`. With these, core_baseline becomes computable. Minimum longitudinal schema drafted by Codex; accepted by Claude.
- **Two-axis invariant is now STRUCTURAL (Claude A1):** every `core_baseline` metric carries an inline `*_vs_reference` / `*_status` field (e.g. `median_to_target_ratio`, `amdr_carb_status`, `hei_direction`). No personal-normal value may be emitted without its health anchor. Replaces the prose-only `health_reference_axis.note`.
- **Naming locked (Claude A2 + Codex Q4):** personal-normal metrics = `energy.kcal_curve`, `macro.structure_curve`, `food_pattern.intake_curve`. The words `hei`/`amdr` belong to the health-reference axis ONLY.
- **Readiness = tiered (Claude Q1):** core_baseline emits at `complete_day_records >= 3` with `baseline_confidence = low`; `medium` at `>= 5`; `high` at 7 days with `daily_confidence_avg >= medium`. PRD `>=3` = floor for existence, `>=5` = floor for trust. Context_baseline ready immediately; quality_baseline from day 1.
- **`daily_confidence_avg` rule (Codex + Claude):** weighted mean of module confidences (high=1.0/medium=0.67/low=0.33/missing=0.0) WITH critical caps; coverage is a hard gate (incomplete → cap `low`); missing energy/food-group → cap `medium`. Missing modules trigger the cap but do NOT also drag the mean (avoid double penalty). Pure `min` rejected as too brittle.
- **`energy_confidence_avg` / `food_group_confidence_avg` are NET-NEW** (not derivable today; do NOT infer from `kcal_range`). v0 contract ships with them as `missing` (→ capped medium) until recognition adds them.
- **`primary_goal` → `primary_direction`:** treat as alias, NOT a confirmed rename (needs product confirmation). v0 schema prefers `primary_direction`, accepts `primary_goal` as backward-compat alias; interpretation-only.
- **Synthetic 7-day fixture: DEFERRED** to implementation phase, after v0 metric list is frozen. Must carry `synthetic_baseline_fixture=true` + `for_pipeline_shape_test_only_not_product_evidence` + preserved source provenance. 7 of 9 complete `v2_baseline` records usable.
- **Meal timestamps:** field reserved (optional) in schema now; no v0 dependency; Meal Timing stays out of v0 baseline influence until recognition populates times.

## Open Items to Close Before Freezing Baseline v0

All four lock items are closed by Codex Round 4.

1. Codex confirmed tiered readiness (emit-at-3 / trust-at-5).
2. Codex confirmed A1 structural two-axis has no engineering blocker.
3. Codex confirmed `daily_confidence_avg` mapping + caps as the v0 contract with energy/food-group treated as `missing` until net-new.
4. Codex locked the three personal-normal metric names.

Draft deliverables produced:

- `Diet Balance Baseline v0 指标定义.md`
- `Diet Balance Baseline v0 指标矩阵.csv`
- `Diet Balance Baseline Red-Team Cases.md`
- `Diet Balance Baseline Open Questions.md`

## Open Questions (carried to Round 2)

- Define the future longitudinal schema (same-user key + per-day `date`/`day_of_week`) so core_baseline becomes computable. (Claude→Codex Q1)
- Define an aggregation rule for `daily_confidence_avg` from existing field-level confidences. (Claude→Codex Q2; Codex Q ref)
- Whether to synthesize a labeled mock 7-day single user from complete days for pipeline testing only. (Claude→Codex Q3)
- Are `energy_confidence_avg` / `food_group_confidence_avg` derivable today or net-new fields? (Claude→Codex Q4)
- Confirm `primary_goal` → `primary_direction` is a rename only. (Claude→Codex Q5)
- Median+IQR accepted for v0 curves; CV/stability labels deferred (fragile at 7 days).
- Weekday/weekend split deferred to future_baseline, but add `date` to the required future schema now.

## User Insert — Illness Adjustment

User asked: if the system already knows the user is sick, how should baseline or Diet Balance formula behavior adjust? Illness detection itself is out of scope.

### Codex proposal (3 schemes) + Claude critique — converging points

- **Settled, not in dispute:** illness days are excluded from `core_baseline` (freeze). The only live decision is same-day **score presentation**.
- **Reuse, no parallel mechanism (Claude):** an illness day = `quality_baseline.excluded_days[].reason = "illness_context"` in the already-frozen v0 output. New fields limited to `health_context.*` (upstream input) + `score_policy.*` (presentation).
- **Key correction (Claude):** drop the word "softening." Illness is a context flag; it may suppress/relabel score+ranking and downgrade confidence, but must **NEVER numerically raise** Diet Balance (enforces RT Hard Rule 1).
- **Three converged options (reframed on presentation):** O1 Annotate (show number + label) = fallback; **O2 Contextualize (recommended v0 default)** = hide formal score & ranking, components only, contextual confidence, no boost; O3 Separate illness track = future_baseline only.
- **Readiness (Claude→Codex Q5):** illness days excluded from BOTH `valid_record_days` and `complete_day_records`; learning window becomes "rolling until N valid days" so a brief illness doesn't permanently block readiness.
- **Medical-advice guardrail:** wording stays about the measurement ("not scored as usual / baseline paused"), never diagnostic or prescriptive; never name the illness or recommend foods.
- **Codex accepted Claude illness critique:** drop "softening"; O2 means suppress/relabel/downgrade confidence only, never numeric boost; reuse `quality_baseline.excluded_days[].reason = "illness_context"`; illness days excluded from both `valid_record_days` and `complete_day_records`; learning window becomes rolling until N valid days.
- **v0 default illness behavior:** O2 Contextualize = hide formal score and ranking, show components + neutral context, `confidence=contextual`, no score inflation. O1 Annotate is fallback; O3 Separate illness track is future-only.
- **v0 fixes applied by Codex:** F1 readiness bands fixed; F2 canonical food-pattern anchor token = `HEI_2020_food_pattern` mapped to calculator component `HEI_2020_available`; F3 `trend.reference_convergence` added as future_baseline and distinct from CV/stability.

### Current Codex closure

Codex updated:

- `Diet Balance Baseline Illness Adjustment Options.md`
- `Diet Balance Baseline Red-Team Cases.md`
- `Diet Balance Baseline v0 指标定义.md`
- `Diet Balance Baseline v0 指标矩阵.csv`
- `ai_collab/diet_balance_baseline/CODEX_OUT.md`

Claude should now perform final acceptance pass. If no blocker remains, Baseline v0 can be recorded as frozen definition-phase output.

### v0 FROZEN (Claude final acceptance)

- Claude directly verified F1/F2/F3 + the illness layer in the deliverable files; all correct. **Baseline v0 is frozen as definition-phase output** (not implementation).
- Hard invariant confirmed end-to-end: personal-normal / context may change explanation + confidence + ranking eligibility, **never** raise Diet Balance by itself.
- One non-blocking clarification (record in `Open Questions.md`, do NOT reopen v0): the illness rolling-window "N valid days" must equal the existing readiness thresholds (`valid_record_days >= 5`, `complete_day_records >= 3`), not a new constant.
- Next phase (only when user chooses) = implementation: longitudinal schema build + deferred synthetic fixture. Out of scope for this discussion.

Historical note: Codex's initial A/B/C schemes were reframed after Claude critique. The current converged labels are O1 Annotate (fallback), O2 Contextualize (recommended v0 default), and O3 Separate illness track (future-only). The old phrase "Score Softening" is retired because it could imply numeric score inflation.
