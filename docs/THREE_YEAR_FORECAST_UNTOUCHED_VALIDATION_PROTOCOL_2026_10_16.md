# Untouched temporal validation protocol — frozen 3-year forecast branch

This protocol is pre-registered after the candidate variables, refit method, fitted parameters and source snapshot have all been frozen.

## Frozen challenger

Core-4 OLS:
- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_kolada_arbetslosa_18_65_pct (N03937)
- lag1_bostadsbestandsforandring_pct

The exact fitted coefficients are stored in `docs/data/three_year_forecast_pre_outcome_frozen_models.json`.

## Frozen benchmark

The full no-lookahead Ridge benchmark is also stored in the same file. Its alpha and coefficients may not be retuned before the untouched score is recorded.

## Predictor vintage

The predictor values used for untouched scoring must come from the immutable source snapshot captured **2026-10-16T20:37:26Z** under:

`docs/data/source_snapshots/20261016T203726Z/`

Live source values may not replace snapshot values when producing the untouched score.

## Scoring rules

Before the outcome is inspected:

- no refit;
- no variable reselection;
- no alpha retuning;
- no new transforms;
- no replacement of N03937;
- no monthly temporal adjustment;
- no use of live revised source values.

When the future outcome becomes available, record at minimum:

- RMSE;
- MAE;
- bias / mean signed error;
- median absolute error;
- municipality-level residuals;
- Luleå residual separately;
- challenger minus benchmark loss;
- whether the challenger is within 2% and 5% of benchmark RMSE.

## Production decision

The untouched result must be written to the repository **before** any post-outcome refit or model change.

A production promotion decision may consider:
1. predictive loss relative to the frozen benchmark;
2. stability and interpretability benefits of core-4;
3. residual pathologies;
4. source-definition changes.

Failure of the untouched test does not authorize ad hoc variable substitution. Reopening the model requires a new, separately registered research cycle.

The deferred monthly temporal module remains out of scope until this structural confirmation is completed.
