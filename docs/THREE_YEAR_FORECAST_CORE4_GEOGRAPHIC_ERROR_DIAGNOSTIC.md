# Core-4 geographic error concentration diagnostic

The first two geographic correction attempts were not robust:
- broad geographic residual correction degraded average RMSE;
- municipality-specific residual shrinkage also degraded average RMSE and the upper error tail.

Before testing another correction, this diagnostic maps where core-4 errors actually concentrate.

It evaluates 2019-2024 six-year rolling-origin forecasts across all 290 municipalities by:
- county;
- population-size decile;
- urbanisation decile;
- distance-to-regional-centre decile;
- lagged inflow-level decile;
- repeated membership in each year's worst absolute-error decile.

No model parameter, variable set or frozen forecast is changed.
