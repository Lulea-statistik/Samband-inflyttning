# Core-4 geographic residual adjustment study

This research track starts from the frozen sparse core-4 as the **average-municipality forecast**.

The structural model is not reopened. Instead, a second-stage geographic layer is tested against already generated rolling-origin residuals.

## Question

Does core-4 have persistent geographic bias, and can a simple geographic adjustment reduce the worst geographic forecast errors without degrading average forecast accuracy?

## Pre-specified arms

1. Core-4 unchanged.
2. Geographic Ridge using municipality size, urbanization and distance to regional centre.
3. County-level historical residual mean, shrunk toward zero.
4. Geographic Ridge plus county effects.

All adjustments for forecast year Y are trained only on residuals from earlier forecast years.

## Evaluation

Primary:
- RMSE

Geographic-extreme diagnostics:
- p95 absolute error
- maximum absolute error
- share of municipality forecasts with absolute error >10 per 1,000
- persistent county-level residual bias
- Luleå annual errors

A geographic layer is considered promising only if it improves average RMSE and reduces the upper tail of errors. This retrospective study cannot itself promote a layer to production.
