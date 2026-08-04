# Diet Balance Baseline Red-Team Cases

## Purpose

These cases prevent Diet Baseline from looking useful while accidentally rewarding incomplete logs or stable unhealthy eating.

## Cases

| case_id | scenario | expected baseline interpretation | may raise Diet Balance? | confidence action | source_type |
|---|---|---|---|---|---|
| RT1 | Long-term poor diet, one slightly better day | Mark as better than personal normal, still below health reference | No | normal unless data quality poor | inference |
| RT2 | Long-term good diet, one off day | Mark as below personal normal, single-day outlier does not move baseline | No beyond normal daily score behavior | normal | inference |
| RT3 | User logs only healthy meals | Treat as incomplete logging, not low intake or improvement | No | downgrade; exclude incomplete day from kcal/food baseline | inference + local_file |
| RT4 | Kcal near target, poor food structure | Energy axis is fine, food-pattern reference gap remains visible | No | normal | inference |
| RT5 | Food structure good, kcal severely high | Food-pattern personal curve may look okay, kcal reference blocks blessing excess | No | normal | inference |
| RT6 | Cut vs bulk direction differs | Direction changes explanation only in v0 | No | normal | inference |
| RT7 | Weekday/weekend swing is large | v0 uses broader IQR and lower trust; split deferred | No | downgrade if spread large | inference |
| RT8 | Low-confidence sodium/sugar/sat-fat estimates | Carry as flagged context, exclude from moderation baseline aggregate below medium confidence | No | module-level downgrade | local_file + inference |
| RT9 | Meal timing appears perfect because placeholder is 100 | Ignore timing as a baseline driver | No | no timing confidence emitted | local_file |
| RT-I1 | User logs only "good" meals while ill | Exclude illness day from normal baseline; do not let a good-looking illness day inflate score or baseline | No | contextual; not ranked | inference |
| RT-I2 | Illness flag is stuck on or overbroad | Surface `baseline_status=insufficient_data` honestly if valid days are starved; do not backfill with illness days | No | audit exclusion; cap silent persistence | inference |
| RT-I3 | Illness flag is a false positive | Keep bounded illness window; resume normal learning after window; preserve `excluded_days` audit for recovery | No | contextual during bounded window | inference |
| RT-I4 | Chronic or recurring illness treated as new normal | v0 keeps normal baseline frozen and does not normalize illness intake; recurring-illness personalization is future-only | No | future-only, not v0 core | inference |

## Hard Rules

1. Personal-normal may change explanation and confidence, but not independently raise Diet Balance in v0.
2. Every core personal-normal metric must include inline health-reference comparison.
3. Incomplete days are excluded from kcal and food-pattern aggregates.
4. The master test set is not baseline evidence because it lacks same-user 7-day records.
5. Illness context may suppress, relabel, and downgrade confidence, but must never numerically boost Diet Balance.
