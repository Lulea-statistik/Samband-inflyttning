# Backward-window sensitivity study for rates_25_29

Date: 2026-10-20

## Decision

The backward-window sensitivity study is complete.

**Selected reference specification: 12 months (YoY percentage-point change).**

The shorter challengers 9, 6 and 3 months all underperform the frozen 12-month reference on common forecast origins.

This does **not** change the frozen structural core-4 and is **not** a production promotion by itself.

## Fixed design

All challenger tests used the same:

- feature family: `rates_25_29`
- features:
  - `bas2_age25_29_sysselsattningsgrad_..._pp`
  - `bas2_age25_29_arbetskraftsdeltagande_..._pp`
- feature lags: 1 and 2 months
- ridge alpha: 3, 10 and 30
- forecast horizons: 3, 6, 9 and 12 months
- seasonal-naive baseline
- common-origin requirement
- target periods
- training eligibility rule
- no feature reselection

The only changed element was the backward change window: 12 vs 9, 12 vs 6, and 12 vs 3 months.

## Results

### 9-month challenger

The 9-month window is worse than 12 months in every tested lag / alpha / forecast-horizon combination.

Selected RMSE deterioration versus 12 months:

- 3-month forecast horizon: about +8.6% to +12.8%
- 6-month forecast horizon: about +20.2% to +30.8%
- 9-month forecast horizon: about +22.9% to +37.3%
- 12-month forecast horizon: about +17.4% to +28.3%

Bias is consistently more negative than for 12 months.

### 6-month challenger

The 6-month window is also worse than 12 months in every tested combination.

Selected RMSE deterioration versus 12 months:

- 3-month forecast horizon: about +7.3% to +10.9%
- 6-month forecast horizon: about +21.0% to +34.1%
- 9-month forecast horizon: about +23.0% to +38.1%
- 12-month forecast horizon: about +17.2% to +29.8%

Bias is again consistently more negative than for 12 months.

### 3-month challenger

The 3-month window also loses in every tested combination.

Selected RMSE deterioration versus 12 months:

- 3-month forecast horizon: about +7.1% to +10.2%
- 6-month forecast horizon: about +18.8% to +32.6%
- 9-month forecast horizon: about +24.5% to +39.5%
- 12-month forecast horizon: about +19.3% to +31.4%

Bias is consistently more negative than for 12 months.

## Interpretation

The evidence does not support a shorter change window for the current `rates_25_29` candidate.

The 12-month transformation is not merely marginally better. It is more stable across:

- forecast horizons,
- alpha values,
- lag 1 vs lag 2,
- RMSE,
- MAE,
- bias.

The shorter windows appear to react more strongly to short-run labour-market variation but that responsiveness does not translate into better migration forecasts in this backtest. Instead it increases error and negative bias.

## Status

- 12-month backward window: **SELECTED**
- 9-month challenger: **REJECTED**
- 6-month challenger: **REJECTED**
- 3-month challenger: **REJECTED**
- feature reselection: **NO**
- structural core-4 changed: **NO**
- production changed: **NO**

The short-term rates_25_29 track should therefore continue with the 12-month YoY percentage-point representation as the fixed transformation unless a later, separately defined study provides new evidence.
