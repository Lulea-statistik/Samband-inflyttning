# Diagnostic conclusion for weak rolling-origin years 2017-2019

The weak years in the 6-year core-4 rolling-origin backtest are primarily a broad panel-wide level-shift problem, not an outlier problem.

## Main evidence

- 2016 target mean: 68.72 per 1,000.
- 2017 target mean: 66.45 while lagged inflow mean was 68.72.
- 2018 target mean: 62.46 while lagged inflow mean was 66.45.
- 2019 target mean: 58.99 while lagged inflow mean was 62.46.

The model therefore entered 2017-2019 with a strong autoregressive signal pointing to a higher level than the realized outcome.

Residuals confirm that the miss was broad:
- 2018: 80.7% of municipalities were overpredicted.
- 2019: 86.6% were overpredicted.
- Only about 10-14% of total absolute error came from the ten worst municipalities.

This means the poor years cannot mainly be explained by a handful of extreme municipalities.

## Coefficients

The lagged inflow coefficient remains positive and large across all rolling windows, roughly 0.65-0.81 in raw units. This is structurally reasonable but makes the model slow to adapt when the national municipal inflow level falls for several years.

The other two structural predictors are less stable:
- N03937 changes sign across rolling windows.
- Housing-stock change also changes sign and then becomes strongly positive in later windows.

This reinforces the interpretation that the most stable signal is lagged migration itself, while the structural variables mainly adjust around that level.

## Interpretation

The 2017-2019 weakness is best described as a momentum/level-adjustment problem:
the model uses last year's migration level well, but does not explicitly model whether that level is accelerating or decelerating.

This does NOT justify changing the frozen core-4 variable set. It motivates a separate, pre-specified temporal layer after the structural model has been evaluated.

The previously deferred monthly/temporal module remains separate from the structural core-4 lock.
