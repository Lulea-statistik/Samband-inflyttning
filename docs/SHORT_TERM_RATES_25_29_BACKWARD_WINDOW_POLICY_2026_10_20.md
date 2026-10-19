# Backward-window test policy for rates_25_29

Date: 2026-10-20

## Decision

The current `rates_25_29` validation track is locked to a **12-month backward window (YoY)** until the existing validation line is complete.

No shorter backward window may replace or tune the current candidate during this phase.

Current candidate features:
- `bas2_age25_29_sysselsattningsgrad_yoy_pp`
- `bas2_age25_29_arbetskraftsdeltagande_yoy_pp`

Forecast horizons remain:
- 3 months
- 6 months
- 9 months
- 12 months

## Current line to finish

Complete the 12-month-backward candidate comparison on identical forecast origins:
1. seasonal naive,
2. Family1 narrow BAS YoY,
3. `rates_25_29` lag 1 month,
4. `rates_25_29` lag 2 months,
5. alpha 3 / 10 / 30 where applicable.

Primary focus remains 9 and 12 month forecast horizons.

## Later sensitivity study

Only after the 12-month-backward track is complete, test alternative backward windows:
- 9 months,
- 6 months,
- optionally 3 months.

Rules for that sensitivity study:
- identical forecast origins,
- identical target periods,
- identical publication-lag assumptions,
- no feature-family reselection,
- no change to frozen core-4,
- report RMSE, MAE and bias for all 3/6/9/12 month forecast horizons.

The shorter windows are challengers to the already completed 12-month specification, not tuning inputs during the current line.
