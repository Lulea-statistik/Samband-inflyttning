# Temporal stability gate for rates_25_29

Date: 2026-10-20

## Decision

The 12-month `rates_25_29` specification passes the temporal-stability gate overall.

The aggregate improvement is not driven by a single forecast origin. For the stronger specifications, leave-one-origin-out RMSE remains better than seasonal naive.

However, alpha 30 with lag 2 is materially weaker at the 12-month forecast horizon and should not be the preferred specification.

## Key findings

### 3-month forecast horizon
Both lag 1 and lag 2 improve overall RMSE across alpha 3/10/30. Leave-one-origin-out remains better than seasonal naive in all tested cases.

The weakest calendar-year segment is 2025, where some combinations are slightly worse than seasonal naive, while 2024 and 2026 are clearly stronger.

### 6- and 9-month horizons
The candidate remains clearly better overall than seasonal naive and the gains survive leave-one-origin-out checks.

The improvement is broad rather than concentrated in one single origin.

### 12-month forecast horizon
This is the most important stability gate.

Alpha 3:
- lag 1: RMSE about -10.6% vs seasonal naive
- lag 2: RMSE about -10.4%
- both 2024 and 2025 beat seasonal naive
- all leave-one-origin-out variants remain better than seasonal naive

Alpha 10:
- lag 1: RMSE about -7.6%
- lag 2: RMSE about -7.2%
- both 2024 and 2025 beat seasonal naive
- all leave-one-origin-out variants remain better than seasonal naive

Alpha 30:
- lag 1 remains positive overall and survives leave-one-origin-out
- lag 2 is fragile:
  - 2024 RMSE is slightly worse than seasonal naive
  - removing one influential origin can erase the overall RMSE advantage

## Interpretation

The evidence supports keeping `rates_25_29` with the locked 12-month YoY percentage-point transformation.

The next decision should be restricted to:
- lag 1 vs lag 2
- alpha 3 vs alpha 10 as primary candidates

Alpha 30 should remain diagnostic rather than preferred.

No feature reselection is warranted.

## Status

- backward window 12 months: **LOCKED**
- temporal stability gate: **PASSED**
- alpha 3: **KEEP**
- alpha 10: **KEEP**
- alpha 30: **DIAGNOSTIC / NOT PREFERRED**
- lag 1: **KEEP**
- lag 2: **KEEP**
- production changed: **NO**
- structural core-4 changed: **NO**
