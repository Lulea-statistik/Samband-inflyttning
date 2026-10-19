# Untouched 2025 temporal scorer

This scorer is the execution side of the prospective 2025 temporal validation gate.

It compares the already frozen municipality-level forecasts:

- core-4
- core-4 + pre-registered 3-year trend

against a supplied 2025 outcome file.

## Required outcome file

CSV columns:

- `kommun_kod`
- `inflyttning_per_1000`

Optional `year` is allowed but, if present, must be 2025.

All 290 municipalities must be present. The scorer refuses partial scoring.

## Integrity checks

Before scoring, the script verifies:

- the freeze manifest status;
- forecast year = 2025;
- exact SHA-256 hash of `predictions_2025.csv`;
- exactly 290 unique municipality predictions;
- no duplicate outcome municipality rows.

## Metrics

Primary:
- RMSE

Secondary:
- MAE
- mean signed error / bias
- median absolute error
- Luleå absolute error
- challenger minus core-4 RMSE
- within 1%, 2% and 5% flags

The scorer never refits the model and never reconstructs or redefines predictors.
