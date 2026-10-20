# Feature-count gate for rates_25_29

Date: 2026-10-20

## Decision

Keep **two variables** in the locked 12-month `rates_25_29` specification:

- YoY percentage-point change in employment rate, age 25–29
- YoY percentage-point change in labour-force participation, age 25–29

A one-variable simplification is not supported by the common-origin backtest.

## Why

On the most decision-relevant 9- and 12-month forecast horizons, using both variables consistently improves RMSE versus the best single-variable model.

### 9-month forecast horizon

Compared with the best one-variable arm, the two-variable model improves RMSE by about:

- alpha 3: roughly 7.1–8.0%
- alpha 10: roughly 7.9–8.3%

### 12-month forecast horizon

Compared with the best one-variable arm, the two-variable model improves RMSE by about:

- alpha 3: roughly 6.1–7.3%
- alpha 10: roughly 6.7–7.4%

MAE also generally improves, and the two-variable model has less negative bias than the labour-force-participation-only model.

## Shorter horizons

At 3 months, the incremental value of the second variable is small.

At 6 months, labour-force participation alone is competitive in some combinations, but the two-variable model remains best or near-best and is clearly stronger at the longer horizons.

## Interpretation

The two labour-market rates are related but not redundant for forecasting purposes.

The extra variable adds material and repeatable forecast value at the 9- and 12-month horizons, so the parsimony argument is not strong enough to justify dropping it.

## Status

- backward window: **12 months locked**
- selected feature count: **2**
- selected variables:
  - `bas2_age25_29_sysselsattningsgrad_yoy_pp`
  - `bas2_age25_29_arbetskraftsdeltagande_yoy_pp`
- alpha candidates: **3 and 10**
- lag candidates: **1 and 2**
- feature reselection: **NO**
- production changed: **NO**
- structural core-4 changed: **NO**

Next step: select the preferred alpha / lag combination using the now-fixed two-variable specification.
