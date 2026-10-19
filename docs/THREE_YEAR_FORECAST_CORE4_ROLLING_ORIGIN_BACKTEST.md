# Frozen core-4 retrospective rolling-origin backtest

This replaces the 76-variable benchmark as the next primary diagnostic.

## Main question

How well would the frozen four-variable model have forecast the next year if we had repeatedly stood at historical forecast origins?

Primary design:
- fixed 6-year training window;
- one-year-ahead forecast;
- move the window forward one year at a time;
- use exactly the frozen core-4 variables;
- refit OLS only within the historical training window.

Example if data allow:
- train 2015-2020 -> forecast 2021;
- train 2016-2021 -> forecast 2022;
- train 2017-2022 -> forecast 2023;
- etc.

The script also reports fixed 3-, 4-, and 5-year windows as sensitivity analyses. They are not alternative variable-selection procedures and must not be used to choose predictors after seeing performance.

## Important limitation

This is a **retrospective reconstructed rolling-origin test**, not a strict archived as-of test. Historical panel values are today's reconstructed historical values. In particular, Kolada N03937 cannot be certified to the exact historical vintage for older forecast origins.

The test is still valuable for checking whether the frozen core-4 relationship is stable through time and whether performance collapses in particular years.

Outputs include annual RMSE/MAE/bias, Luleå error, aggregate metrics by window, and municipality-level predictions/residuals.
