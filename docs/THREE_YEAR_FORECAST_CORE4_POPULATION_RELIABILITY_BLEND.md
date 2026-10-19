# Core-4 population reliability blend

The geographic error diagnostic shows the strongest error gradient by municipality size rather than by county.

Across 2019-2024, the smallest population decile has RMSE about 8.45 per 1,000 while the largest decile is about 4.00. Very high lagged inflow municipalities also have larger errors.

This exploratory test therefore keeps core-4 unchanged and applies only a reliability blend:

`blend = w * core4 + (1-w) * lag1_inflow`

with:

`w = population / (population + 10000)`

The constant 10,000 is fixed before running the test and is not optimized against the historical results. Small municipalities are pulled more toward persistence; large municipalities remain close to core-4.

This is research-only and cannot change production from the retrospective test alone.
