# Geographic equity weighted-calibration gate

Date: 2026-10-20

## Decision

Reject the weighted-calibration challenger.

The frozen 6-year core-4 OLS model remains the reference.

## Result

The out-of-time selector chose lambda = 0 in every forecast year 2020-2024. That means historical evidence did not support extra weighting toward municipalities with larger prior errors.

Even with lambda = 0, the linear calibration layer itself substantially worsened performance:

- pooled RMSE: **+11.9%**
- p90 municipality RMSE: **+11.2%**
- worst-decile mean municipality RMSE: **+12.9%**
- SD of municipality RMSE: **+11.3%**

The share of municipalities with RMSE > 10 also increased materially.

## Interpretation

The frozen core-4 predictions are already better calibrated than a second-stage linear mapping of actual on predicted values.

Neither:
- median shrinkage, nor
- weighted post-calibration

improves geographic equity.

## Next research direction

Keep fixed:
- 6-year training window
- same four core-4 variables
- same 290 municipalities
- same rolling-origin evaluation
- production frozen

Test robust estimators inside the model fit itself:
1. ordinary OLS reference
2. Huber regression
3. quantile-style median regression if operationally feasible
4. municipality-balanced / tail-aware sample weighting

Primary gate:
- lower p90 municipality RMSE
- lower worst-decile mean municipality RMSE
- pooled RMSE deterioration <= 1%
