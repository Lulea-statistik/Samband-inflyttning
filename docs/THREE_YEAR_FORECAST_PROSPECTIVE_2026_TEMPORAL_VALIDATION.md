# Prospective untouched 2026 temporal validation

This is a separate research gate from the previously frozen fixed-parameter structural validation.

## Question

Does the provisional 3-year temporal trend improve the same 6-year rolling core-4 method on a genuinely future year?

## Locked design

Before the 2026 annual migration outcome is inspected:

- training target years: 2020-2025;
- forecast target year: 2026;
- baseline: frozen four-variable core-4 definitions, StandardScaler + OLS;
- challenger: identical model plus one pre-specified temporal feature;
- temporal feature: `(inflow[t-1] - inflow[t-3]) / 2`;
- 290 municipalities;
- predictions are frozen before outcome scoring.

The workflow writes the exact source responses, training matrix, 2026 predictor matrix, fitted parameters and municipality-level predictions to `docs/data/preoutcome_2026_core4_temporal/`.

## Scoring

When the 2026 annual outcome becomes available, score the frozen prediction files without refitting.

Primary metric: RMSE.

Secondary metrics: MAE, bias, median absolute error and Luleå absolute error.

A lower challenger RMSE is supportive evidence only. One future year does not automatically promote the temporal layer to production.
