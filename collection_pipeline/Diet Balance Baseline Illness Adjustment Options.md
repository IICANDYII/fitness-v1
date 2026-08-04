# Diet Balance Baseline Illness Adjustment Options

## Premise

This document assumes illness has already been detected upstream. It does not define illness detection, diagnosis, disease-specific nutrition advice, Goal, Finish, or final formula weights.

source_type: assumption

## Problem

Illness can temporarily change appetite, meal frequency, food type, hydration behavior, energy intake, and logging completeness. If those days are treated as normal evidence, Diet Baseline may learn a false personal-normal curve. If Diet Balance is presented as a normal-day score, the product can create a readiness paradox: a user may be visibly unwell while the product still shows a high, success-like number.

source_type: inference

## User Observed Red-Team Case: Readiness Paradox

The user reported a real-world WHOOP-style failure mode: someone was sick, lying in a hospital bed on an IV drip, yet WHOOP returned a very high Recovery value, around 99. This is not used here as a verified WHOOP product fact; it is a product red-team example supplied by the user.

source_type: user_observation

Implication for Diet Balance Baseline:

- An illness flag must override normal score/readiness interpretation.
- A high-looking score during illness can be absurd or misleading if presented as "doing great."
- Annotating a normal score may be too weak if the visual treatment still behaves like a normal success metric.
- Illness context may suppress, relabel, and downgrade confidence, but must never numerically boost Diet Balance.

## Settled Baseline Behavior

Illness days are excluded from normal `core_baseline` learning. This is not a separate baseline policy block; it reuses the existing v0 output structure:

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

source_type: inference

Illness days do not count toward either `valid_record_days` or `complete_day_records`. When illness intervenes during onboarding, the learning window becomes "rolling until N valid days" rather than a strict 7 calendar days.

source_type: inference

## Three Converged Options

| option | baseline behavior | same-day presentation | v0 status | source_type |
|---|---|---|---|---|
| O1 Annotate | Freeze normal baseline; exclude illness day with `reason="illness_context"` | Show normal number with illness-context label | fallback | inference |
| O2 Contextualize | Freeze normal baseline; exclude illness day with `reason="illness_context"` | Hide formal score and ranking; show components plus neutral context; `confidence="contextual"`; no numeric boost | recommended v0 default | inference |
| O3 Separate illness track | Freeze normal baseline; store illness-context history separately | Compare to prior illness-context days only after enough examples exist | future_baseline only | inference |

## O1 Annotate: Fallback

| dimension | behavior |
|---|---|
| Baseline update | Exclude illness days from normal `core_baseline`. |
| Score | Compute normal score and show it with illness-context label. |
| Ranking | Prefer `not_ranked`; if product keeps ranking, it must be visually de-emphasized. |
| Pros | Lowest implementation complexity. |
| Cons | Still risks the readiness paradox: the user may see a normal-looking high or low number during a non-normal physiological context. |

source_type: inference

## O2 Contextualize: Recommended v0 Default

| dimension | behavior |
|---|---|
| Baseline update | Exclude illness days from normal `core_baseline`. |
| Formal score | Do not present the formal Diet Balance number as a normal-day judgment. |
| Components | Show component-level facts if useful, e.g. energy/food pattern/macro components, with context. |
| Ranking | `ranking_status="not_ranked"`. |
| Confidence | `confidence="contextual"` or equivalent label. |
| Non-negotiable | No numeric boost, no adjusted higher Diet Balance, no success badge based on illness context. |

source_type: inference

Suggested v0 output shape:

```json
{
  "health_context": {
    "illness_status": true,
    "illness_window_id": "illness_2026_06_16",
    "illness_day_index": 1
  },
  "quality_baseline": {
    "excluded_days": [
      {
        "record_date": "2026-06-16",
        "reason": "illness_context"
      }
    ]
  },
  "score_policy": {
    "score_status": "illness_context",
    "ranking_status": "not_ranked",
    "present_formal_score": false,
    "present_components": true,
    "confidence": "contextual",
    "interpretation_mode": "illness_context"
  }
}
```

`diet_balance_raw` may be stored internally for audit/debug if needed, but should not be surfaced as a normal-day judgment in O2.

source_type: inference

## O3 Separate Illness Track: Future Only

| dimension | behavior |
|---|---|
| Baseline update | Keep normal baseline frozen; optionally store illness-context days in future history. |
| Future comparison | Compare illness-context days to prior illness-context days only after enough repeated examples exist. |
| Risk | High overfitting and medical-advice risk; may normalize unhealthy illness intake if misused. |
| v0 status | Named deferral only. |

source_type: inference

## Product Wording Guardrail

Good wording stays about measurement:

- "These days are marked as illness-context, so they are not scored as usual or used to update your baseline."
- "We'll show the components, but not rank this day against your normal Diet Balance history."

Avoid wording that diagnoses, names a condition, prescribes foods, or implies the product knows what the user should medically do.

source_type: inference
