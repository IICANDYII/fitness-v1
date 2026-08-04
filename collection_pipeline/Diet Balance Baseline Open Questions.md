# Diet Balance Baseline Open Questions

## Product Decisions

| id | question | status | source_type |
|---|---|---|---|
| OQ1 | Is `primary_goal` officially renamed to `primary_direction`, or only an alias? | open | local_file + inference |
| OQ2 | Should expected meal slots be fixed as breakfast/lunch/dinner, or user/culture-specific? | open | assumption |
| OQ3 | What user-facing wording should explain "better than your normal but still below health reference"? | open | inference |
| OQ4 | Should baseline status names be `partial_ready/ready/high_confidence_ready`, or simpler user-facing names? | open | inference |
| OQ13 | What exact user-facing wording should explain illness-context days without diagnosis or food advice? | open | inference |

## Data / Recognition Decisions

| id | question | status | source_type |
|---|---|---|---|
| OQ5 | Add net-new `energy_confidence_avg` from recognition, or derive it upstream before baseline? | open | inference |
| OQ6 | Add net-new `food_group_confidence_avg` from recognition, or derive it upstream before baseline? | open | inference |
| OQ7 | What is the official meaning of `kcal_range`: uncertainty, possible intake range, or both? | open | local_file |
| OQ8 | When will meal timestamps become available? | open | local_file |

## Engineering Decisions

| id | question | status | source_type |
|---|---|---|---|
| OQ9 | Where should the future baseline calculator live: separate script, current kcal calculator extension, or product service layer? | open | inference |
| OQ10 | Should synthetic 7-day fixture be generated after metric freeze using 7 of 9 complete `v2_baseline` records? | deferred | calculated_from_local_data + inference |
| OQ11 | What schema version name should v0 baseline use? | open | inference |
| OQ12 | Should baseline output store both numeric confidence and label confidence? | open | inference |

## Closed For v0

| decision | result |
|---|---|
| Goal/Finish | out of scope |
| Formula weights | out of scope |
| Meal Timing influence | future only |
| Weekday/weekend split | future only, but reserve `record_date` now |
| Personal-normal metric names | `energy.kcal_curve`, `macro.structure_curve`, `food_pattern.intake_curve` |
| Illness baseline behavior | illness days excluded from normal baseline; O2 Contextualize is recommended v0 default |
