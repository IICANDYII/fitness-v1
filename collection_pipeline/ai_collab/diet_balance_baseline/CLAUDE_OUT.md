# Claude Code Output

status: done_for_turn
owner: claude
round: 1

> Verification note: Before writing, Claude independently re-checked Codex's load-bearing
> evidence against the real files (calculated_from_local_data):
> - `references/test_sets/testset_master_all.json`: 24 records, 24 **unique** `user_id`
>   (`user01-01 … user24-01`); no `*time*` field anywhere in a record; `moderation_estimates.sodium_mg.confidence = "low"`; no daily-aggregate confidence key; 20/24 `full_day_record_complete = true`.
> - `references/outputs/testset_master_all.diet_balance_kcal_results.json`: `components.meal_timing == 100` for **all** records; `debug.meal_timing_policy = temporary_full_score_until_reliable_multi_day_timing_data`; `score_status` = 20 `complete_with_kcal_balance`, 4 `incomplete_partial_day`.
> Conclusion: Codex's Repo Facts are accurate. I build on them rather than re-deriving them.

---

## Transferable WHOOP Principles

source_type for WHOOP: `external_source`
source: WHOOP Recovery Explained (https://www.whoop.com/us/en/thelocker/how-does-whoop-recovery-work-101/); WHOOP HRV (https://www.whoop.com/us/en/thelocker/heart-rate-variability-hrv/), as cited in `Diet Balance Baseline AI协作工作流.md` §2.

| # | Principle (abstracted) | How it maps to Diet Balance Baseline |
|---|---|---|
| P1 | Compare today to the person's own normal range, not only to the population. | Baseline must learn the user's own kcal/macro/food-pattern distribution, then judge a day relative to it. |
| P2 | Trend beats a single day; one outlier should not dominate. | A single deviant day must not move baseline; baseline = central tendency + spread over the window. |
| P3 | Output a state/zone (green/yellow/red), not a falsely precise number. | Baseline should emit ranges + a readiness/quality state, not a single point estimate pretending to precision. |
| P4 | Gate on data quality; readiness is only trustworthy when inputs are. | `baseline_confidence` must gate every personal-normal claim; low-confidence inputs cannot found a baseline. |
| P5 | Attribute change to drivers (sleep, strain…). | Baseline should expose *which* curve moved (energy vs macro vs food pattern), supporting explanation not just a score. |
| P6 | There is no single "correct" recovery score; it is highly individual. | Reject one universal "ideal day"; the user's own curve is a first-class reference. |

**Critical disanalogy (this is the load-bearing point for v0).**
WHOOP's physiological baselines (HRV, RHR) are *self-normalizing toward health* — the body's homeostasis pulls the personal normal toward a healthy attractor. **Diet has no such homeostat.** A user's personal-normal diet can drift arbitrarily far from health and stay stable there. Therefore WHOOP's "trust the personal normal" cannot be imported wholesale. Diet Balance Baseline must keep **two axes simultaneously** (consistent with workflow §9):

- `personal-normal axis` — today vs this user's own curve. **Requires longitudinal data.**
- `health-reference axis` — this user's curve and today vs HEI/AMDR/RDA/kcal anchors. **Available per-day today.**

P1/P2/P6 may govern the personal-normal axis only; they must never be allowed to override the health-reference axis.

---

## Critique of Candidate Metrics

**Headline finding (inference, grounded in Codex facts + my re-check):** The master test set is 24 *distinct single-day* users. Therefore **every personal-normal metric in Codex's matrix is currently non-computable** (`kcal_vs_baseline_ratio`, `macro_stability`, `valid_record_days`, `complete_day_records` — Codex already marks these `inference`/`no`). What *is* computable today is exclusively **per-day, absolute, health-reference** quantity. In other words: **the repo today supports the health-reference axis and provides ~zero evidence for the personal-normal axis.** A "baseline" built only from what is computable now would be the failure mode the workflow warns about — *the absolute standard with a new name.*

Concrete challenges to specific rows:

1. **`energy.kcal_vs_target_ratio`, `macro.reference_gap`, `food_pattern.hei_components`, `food_pattern.moderation` (as scored).**
   These are comparisons to an external standard (`estimated_energy_requirement_kcal`, AMDR, HEI). They are **already Diet Balance**, not baseline. Pulling them into baseline double-counts the health-reference axis and dilutes the meaning of "baseline = the user's own curve." → Keep them as the *health-reference anchor* that the personal curve is measured against, not as baseline metrics themselves.

2. **`profile.*` (age/sex/height/weight/activity/direction).**
   These do **not** describe the user's eating curve. They *parameterize the health reference* (they set RDA/kcal targets). Valid and necessary, but they are `context`, not `core`. Risk Codex flagged (stale/self-report) is real; they should never raise Balance on their own.

3. **`meal_rhythm.*`.** Split sharply:
   - `meal_count_per_day`, `breakfast_lunch_dinner_presence`, `largest_meal_slot` are computable **but confounded**: with no timestamps and logging-driven `available_meals`, you cannot distinguish *skipped meal* from *unlogged meal*. Building a personal rhythm baseline on this will encode logging behavior as eating behavior. → quality-gated context at most, not core.
   - `first_last_caloric_time`, `late_heavy_meal_count` are **non-computable** (no time fields — I verified zero `*time*` keys). → future only.
   - `Meal_Timing` is a hard-wired `100` placeholder. It must be **excluded from any baseline influence**; treating `100` as evidence of good rhythm is a hallucination vector.

4. **`food_pattern.moderation` low confidence.** In the actual data, `sodium_mg.confidence = "low"`. A personal-normal moderation baseline founded on low-confidence recognition would be noise dressed as a user trait. → require a confidence floor before these enter any baseline aggregate.

5. **Naming risk (`primary_goal` vs PRD `primary_direction`).** Agreed with Codex — but note the deeper risk: `goal`-named fields tempt scope creep into Goal design, which is explicitly out of scope. In v0, direction is **interpretation context only**.

---

## Proposed Baseline Layers

Status legend: `computable_now` = from current per-day data; `needs_longitudinal_schema` = needs same-user ≥5/7-day records that do not yet exist.

### core_baseline — the user's own curve (the reason "baseline" exists)
These are the personal-normal distributions. **All are `needs_longitudinal_schema`.** This is the honest v0 position: core baseline is *defined* now but *not yet computable* from the master set.

| metric | what curve it captures | reliability condition | axis | balance module (future) |
|---|---|---|---|---|
| `energy.kcal_curve` (median + IQR of complete-day `daily_total.kcal_mid`) | habitual energy intake & its spread | ≥5 valid complete days | personal-normal, anchored by `target_kcal` | `Kcal_Balance` |
| `macro.structure_curve` (median of `macro_structure_pct.*`) | habitual macro split | ≥5 valid days | personal-normal, anchored by AMDR | `AMDR_Fit` |
| `food_pattern.hei_curve` (median of per-day HEI food-group totals) | habitual diet quality pattern | ≥5 valid days, conf ≥ medium | personal-normal, anchored by HEI | `HEI_2020_available` |

### context_baseline — explains differences, does not score
| metric | role | source | risk |
|---|---|---|---|
| `profile.metabolic` (age/sex/ht/wt/activity) | sets RDA/kcal targets | `user_profile.*` (computable_now) | stale/self-report |
| `profile.direction` | interpretation only in v0 | `user_profile.primary_goal` (computable_now) | naming mismatch; do not expand into Goal |

### quality_baseline — decides whether the curve is trustworthy
| metric | role | status |
|---|---|---|
| `quality.valid_record_days`, `quality.complete_day_records` | learning-period readiness gates (PRD §learning) | needs_longitudinal_schema |
| `quality.daily_confidence_avg` | per-day trust; PRD wants `average_daily_confidence ≥ medium` | **not present** — only field-level confidence exists; needs a defined aggregation rule |
| `quality.missing_meal_slots` | flags logging gaps; downgrades rhythm/energy confidence | computable_now (under the bkfst/lunch/dinner assumption) |

### future_baseline — valuable, not in v0
`meal timing curve` (needs timestamps), `weekday/weekend split` (needs dates), `macro/energy CV & stability labels` (fragile at 7 days), `user_correction_count`, `manual_confirmed_records` (need product event logging).

---

## Anti-Hallucination Checks

1. **Do not call the master test set a baseline.** It is 24 distinct single-day scenarios (re-verified). Any personal-normal number "computed" from it would be fabricated longitudinal history. (Agrees with Codex Risk row 1.)
2. **Do not relabel a health-reference anchor as a personal baseline.** `kcal_vs_target`, `amdr_fit`, `hei_components` measure distance to an external standard, not user specificity.
3. **`Meal_Timing = 100` is a placeholder, not a signal.** Exclude from baseline influence until real timing data exists.
4. **Confidence is mandatory, not decorative.** No personal-normal metric may be emitted without a `baseline_confidence`; low-confidence inputs (e.g. observed `sodium` low) cannot found a baseline.
5. **Two axes must both survive into v0.** If a future formula consumes only the personal-normal axis it normalizes bad habits; only the health-reference axis and it is not personalized.

---

## Red-Team Scenarios

For each: should it raise Diet Balance? change explanation only? downgrade confidence?

| # | User type | Baseline behavior | May raise Balance? | Confidence |
|---|---|---|---|---|
| 1 | Chronically poor, one slightly-better day | Personal-normal: "above your normal." Health-ref: still low. | **No.** Explanation only ("better than your usual"); single day, P2 trend rule blocks baseline shift. | normal |
| 2 | Chronically good, one off day | Personal-normal: "below your normal." Health-ref: still acceptable. | No score penalty beyond the day's own Balance; baseline unchanged (single outlier). | normal |
| 3 | Logs only healthy meals (incomplete) | `missing_meal_slots` high → incomplete day. Must not read as low intake / improvement. | **No.** Exclude from kcal/food baseline; **downgrade confidence**. | **downgraded** |
| 4 | kcal near target, poor food structure | Energy curve fine; HEI curve low. Two axes diverge → expose both. | No — energy adequacy must not mask structure. Explanation shows the split. | normal |
| 5 | Good structure, severe kcal excess | HEI curve ok; energy curve far above target. | No — health-reference kcal anchor dominates; baseline records high-energy normal but flags it, does not bless it. | normal |
| 6 | Cut vs bulk user (direction differs) | `profile.direction` changes *interpretation* of kcal-vs-target only. | Not in v0 (direction = interpretation only). Avoids Goal scope creep. | normal |
| 7 | Large weekday/weekend swing | v0: single curve with wider IQR → lower stability/confidence. Split is `future_baseline`. | No; wide spread should **lower** confidence, not raise Balance. | downgraded if spread large |

Governing rule across all: **the personal-normal axis may change the *explanation* and the *confidence*, but in v0 it may not by itself raise Diet Balance above what the health-reference axis allows.**

---

## Answers to Codex's Questions

1. **Non-negotiable anchors:** all four (HEI, AMDR, RDA/AI, kcal target) stay as health-reference anchors — they are the guardrail axis. None may be dropped in favor of personal-normal.
2. **`HEI components[]` classification:** **health-reference context, NOT core_baseline.** Core baseline is the user's *own curve*; HEI components are the standard that curve is measured against.
3. **Median + IQR vs no variability labels:** median + IQR is acceptable for `core_baseline` energy/macro/food curves; **avoid CV/"stability" labels in v0** (fragile at 7 days — defer to future_baseline).
4. **Incomplete logging:** gate hard. Incomplete days are excluded from kcal/food baseline aggregates and **downgrade `baseline_confidence`**; never interpreted as low intake or improvement (Red-Team #3).
5. **`primary_goal`/`direction`:** **interpretation only in v0.** Future `Kcal_Balance` personalization is plausible but deferred to avoid Goal scope creep.
6. **Meal Timing:** **exclude from v0 baseline formula influence; future/context only** — no timestamps, and the current `100` is a placeholder.
7. **Low-confidence moderation:** require a confidence floor (≥ medium) before sodium/added-sugars/sat-fat/fatty-acids enter any baseline aggregate; below floor, carry as flagged context only.
8. **Weekday/weekend:** **defer the split to future_baseline**, but I recommend Codex add `date`/`day_of_week` to the **required future longitudinal schema now**, because retrofitting dates later is costly and the split is product-important.

---

## Questions for Codex

1. Can you specify the **future longitudinal schema** (same-user grouping key + per-day `date`) so core_baseline becomes computable? What is the minimum field set?
2. For `quality.daily_confidence_avg` (absent today): propose a concrete **aggregation rule** over existing field-level confidences (e.g., min vs weighted mean across food-group + moderation + energy). Which fields feed it?
3. Of the 20 complete days, how many distinct `testset_group`s could be **synthesized into a mock 7-day single user** purely for pipeline testing (clearly labeled synthetic, not a real baseline)?
4. Does the calculator already expose a per-day **energy/food-group confidence** anywhere I can map to `energy_confidence_avg` / `food_group_confidence_avg`, or are these net-new?
5. Confirm the `primary_goal` → `primary_direction` mapping is a **rename only** (no semantic change) so we can treat direction uniformly.

---

# Claude Code Output — Round 3 Response to Codex

status: done_for_turn
owner: claude
round: 3

## Claim

Codex's Round 2 schema, confidence rule, and v0 output contract are accepted with three product-side amendments: (a) the two-axis invariant must be **structural**, not a prose note; (b) personal-normal food metric must drop the `hei` name; (c) readiness should **degrade confidence**, not hard-block, between the PRD's `>=3` and `>=5` thresholds. With these, we are ready to draft baseline v0.

## Acceptance of Codex Round 2

Accepted as-is: the minimum longitudinal schema (`baseline_user_id` + `record_date` as the two missing keys), the synthetic-fixture provenance discipline (`synthetic_baseline_fixture=true`, `for_pipeline_shape_test_only_not_product_evidence`), the "do not derive energy confidence from `kcal_range`" guard, and the `primary_goal`→`primary_direction` *alias-not-confirmed-rename* stance. No objection.

## Amendments (product / scoring critic)

**A1 — Make the two-axis invariant structural.**
In Codex's v0 output contract, `health_reference_axis.note` is prose and a downstream formula can ignore it. Instead, **every `core_baseline` metric must carry its health-reference comparison inline**, so the personal-normal value is never readable without its anchor:
```json
"energy_kcal": { "median": 2100, "iqr": [1900,2300], "median_to_target_ratio": 1.02, "anchor": "estimated_energy_requirement_kcal" }
"macro_pct":   { "carb_median": 0.52, "amdr_carb_status": "within", ... }
"food_pattern":{ "vegetable_cup_median": 1.5, "hei_direction": "below_reference", ... }
```
Rule: no personal-normal field is emitted without a sibling `*_vs_reference` / `*_status` field. This is what stops a future formula from blessing a stable-but-unhealthy curve.

**A2 — Rename the personal-normal food metric.** Accept Codex's concern (their Q4). Use `food_pattern.intake_curve` for the personal-normal medians; reserve `hei_*` strictly for the health-reference axis. Same principle for energy/macro: the curve is personal, the `*_vs_reference` field is the anchor.

**A3 — Readiness degrades confidence, not availability.** See answer to Codex Q1 below.

## Answers to Codex's 5 Questions

**Q1 — readiness threshold.** Tiered, not a single gate:
- `context_baseline` (profile/direction): ready immediately (collected, not learned).
- `quality_baseline`: computable from day 1.
- `core_baseline` curves: emit at **`complete_day_records >= 3`** (honors PRD minimum) but force **`baseline_confidence = low`**; reach **`medium`** only at **`>= 5`** valid days, **`high`** only at 7 with `daily_confidence_avg >= medium`. So PRD's `>=3` is the floor for *existence*, `>=5` is the floor for *trust*. Keep the threshold uniform across kcal/macro/food (don't fork per-metric) and let confidence carry the nuance.

**Q2 — min vs weighted-mean-with-caps.** Use **your weighted-mean-with-critical-caps**, not pure `min`. Pure `min` is too brittle — one low field tanks the day and perversely discourages logging. Keep coverage as a **hard gate** (incomplete → cap `low`) and keep "missing energy/food-group → cap `medium`". One tweak: `missing=0.0` must trigger the cap, **not** silently flow into the weighted mean (otherwise a missing module both caps *and* drags the mean = double penalty). Cap, then mean over present modules.

**Q3 — synthetic fixture now or later.** **Later** — after baseline v0 metric definitions are frozen. Building the fixture now risks ossifying a record shape before metrics settle, and your own risk (forgetting it's synthetic) compounds the longer it sits unused. Add it in the implementation phase, clearly labeled, once the v0 list is final.

**Q4 — `hei_curve` naming.** Agreed — rename (see A2). Personal-normal name must not contain `hei`/`amdr`; those words belong to the health-reference axis only.

**Q5 — timestamps now or optional.** **Reserve the field now, optional, no v0 dependency.** Define `meals[].time` (or `meals[].start_time`) in the schema so it's forward-compatible, but do not require population and keep Meal Timing **out of v0 baseline influence**. Requiring timestamps immediately would block the entire longitudinal rollout on an upstream recognition capability that may not exist yet. When timing recognition lands, the field populates and Meal Timing leaves placeholder status — no schema migration needed.

## Convergence Readiness

We have now covered facts (R1), WHOOP transfer + critique (R1), and data mapping + schema (R2). Agreement is broad. I propose the **next turn is the convergence/arbiter step (baseline v0 draft)**. Before we can freeze v0, exactly these must be closed:

1. Confirm tiered readiness (3 = exists/low, 5 = medium) — Codex agree/counter?
2. Confirm structural two-axis (A1: inline `*_vs_reference` on every core metric) — any engineering objection?
3. Confirm `daily_confidence_avg` numeric mapping + caps as the v0 contract (pending real `energy_confidence`/`food_group_confidence` net-new fields).
4. Lock the personal-normal metric names (`energy.kcal_curve`, `macro.structure_curve`, `food_pattern.intake_curve`).

## Questions for Codex

1. Any engineering cost to A1 (inline `*_vs_reference` on each core metric)? The calculator already computes these anchors per-day (`debug.kcal_balance.actual_to_target_ratio`, `debug.amdr.*`, HEI components) — is it just a matter of carrying them through to the baseline aggregate?
2. Do you agree readiness should emit-at-3 / trust-at-5 rather than hard-block at one threshold?
3. For v0, can `daily_confidence_avg` ship with `energy_confidence`/`food_group_confidence` treated as `missing` (→ capped at `medium`) until the net-new fields exist, so the contract is usable before recognition adds them?
4. If we agree on the four lock items above, shall the next round produce the joint **Baseline v0 定义 + 指标矩阵** (the four final deliverable files in workflow §11)?

---

# Claude Code Output — Round 5 Final Critic Pass (v0 acceptance review)

status: done_for_turn
owner: claude
round: 5

## Claim

The four v0 deliverables are accepted as a sound candidate. I have **three concrete findings**: two are small consistency fixes; one is a substantive omission against the original product vision (a missing *trend/direction* signal). I recommend v0 = **accepted pending these fixes** rather than fully frozen.

I reviewed all four files: `Diet Balance Baseline v0 指标定义.md`, `…指标矩阵.csv`, `…Red-Team Cases.md`, `…Open Questions.md`. The two-axis invariant is correctly encoded structurally (inline `*_vs_reference` on every core metric; RT Hard Rule 2), readiness is tiered, confidence caps avoid the double-penalty, and exclusions (timing, weekday/weekend, CV, synthetic fixture) are explicit and labeled. Good.

## Finding F1 (fix) — readiness table has an undefined band

source_type: inference; source: `Diet Balance Baseline v0 指标定义.md` §3.

The table mixes two counters across rows:
- `insufficient_data`: gated on `valid_record_days < 3`
- `partial_ready`: gated on `complete_day_records >= 3`
- `ready`: gated on `valid_record_days >= 5 AND complete_day_records >= 3`

A user with `valid_record_days = 4, complete_day_records = 2` matches **none** of the rows (not insufficient by valid<3, not partial by complete>=3, not ready). Fix: make every row use **both** counters with no gap, e.g.:
- `insufficient_data`: `complete_day_records < 3` (regardless of valid days)
- `partial_ready`: `complete_day_records >= 3 AND valid_record_days < 5`
- `ready`: `complete_day_records >= 3 AND valid_record_days >= 5`
- `high_confidence_ready`: 7 days present AND `daily_confidence_avg >= medium`

This makes `complete_day_records` the existence floor (matches PRD) and `valid_record_days` the trust step.

## Finding F2 (fix) — health-reference anchor name for food pattern is inconsistent

source_type: inference; source: `…指标定义.md` (`reference_anchor: "HEI_2020_food_pattern"`) vs `…指标矩阵.csv` (`HEI_2020_food_pattern`) vs the calculator component `HEI_2020_available`.
Pick one canonical anchor token and use it everywhere. Recommend `HEI_2020_food_pattern` for the personal-curve anchor (keeps it distinct from the scored component `HEI_2020_available`), and state the mapping once so nobody re-conflates them.

## Finding F3 (substantive — add to future_baseline) — no trend/direction signal

source_type: inference; source: `Diet Balance Baseline AI协作工作流.md` §9 ("这个用户是否正在朝更健康的参考方向变化") and WHOOP principle P5.

v0 core captures **median + IQR** — a *static snapshot* of the window. But the original vision and the WHOOP transfer both call for "is the user trending toward the healthy reference?" — a **direction** signal, which is **not** the same as the deferred CV/stability label (stability = how noisy; trend = which way it's moving). Right now this is silently absent, not explicitly deferred.

I do **not** argue it enters v0 core (7 days is too short for a robust slope — agrees with the CV deferral logic). But it should be an **explicit `future_baseline` row** (e.g. `trend.reference_convergence`) so it is a named, deferred item rather than an accidental gap. Otherwise a future formula author may assume baseline already encodes direction.

## Recommendation

v0 = **accepted pending F1 + F2 fixes and the F3 future-row addition**. None changes the architecture; all three are one small Codex edit away. After that, I consider Baseline v0 frozen and the workstream ready to exit the definition phase.

## Questions for Codex (final)

1. F1/F2: agree to apply as described? (pure consistency, no semantic change)
2. F3: agree to add `trend.reference_convergence` as a `future_baseline` row in the matrix + a one-line note in §7 exclusions, marked "future, not v0; distinct from CV/stability"?
3. After these, do you concur v0 is frozen and we record it as the converged outcome in `DECISIONS.md`?

---

# Claude Code Output — Illness Adjustment Critique

status: done_for_turn
owner: claude
round: illness_insert_claude

## Claim

I accept the shared premise (illness already detected upstream; detection out of scope) and Codex's baseline-freeze. But Codex's framing buries the only real decision under three schemes. **Reframing: baseline behavior is already settled — illness days are excluded from `core_baseline`, full stop. The single live question is same-day score *presentation*.** On that question I endorse a **tightened Scheme B as the v0 default**, with one non-negotiable correction that Codex's "softening" wording currently violates.

## The key correction — "softening" must never raise the number

source_type: inference; source: v0 hard rule (`DECISIONS.md`, RT Hard Rule 1: personal-normal/context may change explanation + confidence but must NOT independently raise Diet Balance).

Codex's Scheme B says "score softening / confidence downgrade." **"Softening" a bad illness-day score is a backdoor that inflates Diet Balance via a context flag — exactly what our two-axis invariant forbids.** Illness is a context signal, not a health-reference improvement. So in v0, illness may:
- **suppress** the formal score/ranking/badge,
- **relabel** the day as illness-context,
- **downgrade confidence**,

but it must **never numerically boost** the raw Diet Balance. If we keep "softening" it must mean *suppress/relabel*, not *raise*. I recommend dropping the word "softening" entirely to avoid the ambiguity.

## Reuse existing structure — illness is just another exclusion reason

source_type: local_file; source: `Diet Balance Baseline v0 指标定义.md` §5 — the v0 output already has `quality_baseline.excluded_days[].reason`.
Illness needs **no parallel mechanism**: an illness day is an excluded day with `reason: "illness_context"`. This collapses Codex's `baseline_policy.exclude_from_core_baseline` into the structure we already froze. Keep `health_context.*` (upstream input) and `score_policy.*` (presentation) as the only genuinely new fields.

## Three converged options (reframed on score presentation)

| option | baseline | same-day score presentation | v0? |
|---|---|---|---|
| **O1 = Annotate** (Codex A) | freeze + exclude | show normal number + illness label | fallback |
| **O2 = Contextualize** (Codex B, tightened) | freeze + exclude | **hide formal score & ranking**; show components + neutral context; `confidence=contextual`; **no numeric boost** | **recommended default** |
| **O3 = Separate illness track** (Codex C) | freeze + store illness-context history | compare to prior illness days once enough exist | future_baseline only |

I push O2 further than Codex: **hide the formal number for v0, don't "optionally" show it.** Surfacing a raw Diet Balance during illness invites both the "unfair score" feeling (O1's flaw) and the softening-inflation trap. Store `diet_balance_raw` internally for audit if desired, but do not present it as a judgment.

## Illness-specific red-team (additions to Red-Team Cases)

| id | scenario | required behavior |
|---|---|---|
| RT-I1 | User logs only "good" meals while ill | Exclusion already prevents learning; also must NOT let a good illness day inflate score or baseline. |
| RT-I2 | Illness flag stuck on / overbroad → baseline starvation | If illness days block readiness, surface `baseline_status=insufficient_data` **honestly**; do not backfill with illness days. Cap how long exclusion can silently persist. |
| RT-I3 | Illness flag is a false positive | Window is bounded; post-window days resume normal learning; keep `excluded_days` audit so a wrong exclusion is recoverable, not silently lost. |
| RT-I4 | Chronic/recurring illness treated as "new normal" | v0 keeps normal baseline frozen and does NOT normalize illness intake. Recurring-illness personalization is O3/future, never an excuse to bless unhealthy intake. |

## Answers to Codex's 5 Questions

1. **A or B default:** **O2 (tightened B)** — suppress formal score + ranking, contextual confidence, no numeric inflation. O1 as the low-complexity fallback if product wants to keep showing a number.
2. **Show `diet_balance_raw`?** No — components only, `ranking_status=not_ranked`. Keep raw internally for audit, not as a surfaced judgment.
3. **Is C too risky / future?** Yes — **explicitly `future_baseline`**, for the same reason CV/stability and weekday-split are deferred, plus added medical-advice/overfitting risk. Name it so it's a deliberate deferral, not a gap.
4. **Wording that avoids medical advice:** keep it about the *measurement*, not the body. Neutral, non-diagnostic, non-prescriptive, no food prescriptions. Good: "These days are marked as illness-context, so we're not scoring them as usual or updating your baseline." Avoid: naming the illness, implying diagnosis, or "because you're sick, eat/avoid X."
5. **Count toward readiness?** **Exclude from BOTH `valid_record_days` and `complete_day_records`** — illness days are not valid normal evidence. **Important refinement:** to stop a brief illness from permanently blocking readiness, define the learning window as *"until N valid days"* (rolling) rather than strictly 7 calendar days when illness intervenes. Otherwise a 2-day flu could deny a baseline indefinitely.

## Questions for Codex

1. Agree to drop "softening" and make O2 mean *suppress/relabel only, never boost*?
2. Agree illness = `excluded_days[].reason="illness_context"` reusing the frozen v0 structure (no parallel `baseline_policy` block)?
3. Agree the learning window becomes "rolling until N valid days" when illness days intervene, so brief illness doesn't permanently block readiness?
4. Note: v0 fixes **F1/F2/F3 from my Round 5 pass are still pending** — fold them in together with this illness layer in your next turn?

---

# Claude Code Output — Final Acceptance (v0 FROZEN)

status: done_for_turn
owner: claude
round: v0_freeze

## Claim

**Baseline v0 is accepted and frozen as definition-phase output.** I directly verified every edit; no blocker remains.

## Verification (calculated_from_local_data — I re-read the files)

| item | check | result |
|---|---|---|
| F1 readiness band | `定义.md §3` rows now gated on `complete_day_records` (<3 / >=3&<5 / >=5) | fixed, no undefined band |
| F2 anchor token | canonical `HEI_2020_food_pattern`, mapped once to component `HEI_2020_available`; CSV columns are anchor vs affected-module (correctly distinct) | fixed |
| F3 trend signal | `trend.reference_convergence` present in `矩阵.csv` + `定义.md §7`, marked `future_only`, explicitly distinct from CV/stability | added |
| Illness "softening" | removed; O2 = suppress/relabel/downgrade-confidence only, never numeric boost (Red-Team hard rule added) | correct |
| Illness reuse | `quality_baseline.excluded_days[].reason="illness_context"`, no parallel `baseline_policy` block | correct |
| Illness readiness | excluded from both `valid_record_days` and `complete_day_records`; rolling-until-N-valid-days | correct |
| RT-I1..I4 | present in `Red-Team Cases.md` | correct |

I also note Codex correctly tagged the hospital/IV high-score observation as `user_observation` (not fact). It does strengthen O2 over O1, and the existing RT-I framing already covers it.

## One non-blocking open item (for the open-questions file)

The rolling learning window says "until **N** valid days" but N is unspecified. It should **not** introduce a new constant — N must equal the already-frozen readiness thresholds (`valid_record_days >= 5`, `complete_day_records >= 3`). Recommend recording this as an explicit clarification in `Open Questions.md` rather than reopening v0.

## v0 Frozen Scope (definition phase only — not implementation)

- core_baseline: `energy.kcal_curve`, `macro.structure_curve`, `food_pattern.intake_curve` (all `needs_longitudinal_schema`, each carrying inline `*_vs_reference`).
- context_baseline: profile metabolic + direction (interpretation-only).
- quality_baseline: readiness gates + `daily_confidence_avg` (weighted-mean + caps) + `missing_meal_slots` + `excluded_days[].reason` (incl. `illness_context`).
- future_baseline: meal timing, weekday/weekend split, CV/stability, `trend.reference_convergence`, illness separate track (O3).
- Illness v0 default = O2 Contextualize.
- Hard invariant preserved end-to-end: personal-normal / context may change explanation + confidence + ranking eligibility, **never** raise Diet Balance by itself.

Definition phase complete. Next phase (when the user chooses) is implementation: longitudinal schema build + the deferred synthetic fixture — out of scope for this discussion.
