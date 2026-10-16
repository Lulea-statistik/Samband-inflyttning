# Frozen candidate set for 3-year forecast branch

Date: 2026-10-16.

## Status

The neutral variable-selection phase for the **3-year forecast branch** is now closed.

The following four predictors constitute the frozen candidate set:

1. `lag1_inflyttning_per_1000`
2. `lag1_utflyttning_per_1000`
3. `lag1_kolada_arbetslosa_18_65_pct` (Kolada KPI N03937)
4. `lag1_bostadsbestandsforandring_pct`

This is a **candidate-set lock**, not a production-model approval.

## Why these four are frozen

After removal of the pre-existing lookahead-only turnout variables, the corrected stability study selected:

- inflow in 5/5 outer folds;
- outflow in 5/5;
- N03937 unemployment in 5/5;
- housing-stock change in 4/5.

No other feature reached comparable recurrence in the corrected no-lookahead sparse path.

## Method constraints from this point

The following are now prohibited for this branch unless a documented source-eligibility failure forces reopening:

- adding new predictors;
- swapping predictors after inspecting 2021-2023 outcomes;
- re-ranking variables;
- changing feature families to improve the same historical test period;
- introducing the deferred monthly temporal module.

Allowed work:

- source-vintage/snapshot verification;
- temporal validation on frozen data;
- comparison of OLS vs Ridge/refit on the **same four variables**;
- comparison against the frozen full-Ridge benchmark;
- production-readiness assessment;
- sensitivity analysis that does not alter the four-variable set.

## Source status

- Inflow/outflow: strong final-release equivalence from SCB, exact historical API snapshot unavailable.
- Housing-stock change: strong final-release equivalence from SCB; only final annual statistics are published.
- N03937: current identity pinned and snapshot captured, but historical as-of reconstruction cannot be certified retrospectively because Kolada may revise data without separate notice.

A first immutable source snapshot was captured on 2026-10-16 and is stored under `docs/data/source_snapshots/`.

## Definition break to retain

N03937 refers to ages **18-64 through 2022** and **18-65 from 2023**. This must remain explicit in all later validation and interpretation.

## Decision gate

The four variables may be promoted from `frozen_candidate_set` to production only after a future untouched temporal confirmation using predictor values frozen before the outcome becomes known.

Until then:

- production model unchanged;
- 3-year forecast variable set frozen;
- blind branches unchanged;
- monthly temporal module deferred.
