# Three-year forecast core-4: provisional lock-in status — 2026-10-16

The repeated geographic robustness audit supports the four-variable core more strongly than the three-variable core.

## Robustness result

Across 100 repeated municipality-group train/test splits:

### Full Ridge
- mean RMSE: 5.063

### 3-variable core
- OLS mean RMSE: 5.162
- mean relative RMSE difference: +1.94%
- better than full Ridge in 28% of splits
- within 2% of full Ridge in 49% of splits
- within 5% in 83%

### 4-variable core
- OLS mean RMSE: 5.104
- mean relative RMSE difference: +0.81%
- better than full Ridge in 38% of splits
- within 2% of full Ridge in 65% of splits
- within 5% in 89%

The four-variable core is therefore the stronger sparse candidate:

- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_valdeltagande_gap_pp
- lag1_bostadsbestandsforandring_pct

## Important limitation

This does **not** constitute final lock-in. The core was discovered and stress-tested on the same historical era, so the repeated splits are robustness diagnostics rather than independent confirmation.

The neutral variable inventory currently marks **all four variables** as:

- `asof_verified = false`
- `method_definition_verified = false`

Therefore the next gate is source-vintage and exact feature-derivation verification, not another model-selection run on 2021–2023.

## Decision

- provisional sparse candidate: **core-4**
- core-3: retained only as sensitivity reference
- full Ridge: remains predictive benchmark
- no further variable reselection on 2021–2023
- no production change
- temporal/monthly module remains deferred

A future temporal confirmation may only be treated as genuine as-of validation after each core variable has passed the source-vintage and method-definition gate.
