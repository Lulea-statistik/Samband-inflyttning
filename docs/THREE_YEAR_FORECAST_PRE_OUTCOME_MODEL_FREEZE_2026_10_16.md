# Pre-outcome model freeze for the 3-year forecast branch

The variable set and core refit method are already locked. This step freezes the **actual fitted model parameters** before any future untouched outcome is scored.

Two models are frozen on the same 2021-2023 training panel:

1. **Frozen core-4 OLS** using the locked four predictors.
2. **Full no-lookahead Ridge benchmark**, with alpha chosen once by grouped 3-fold CV from the registered grid.

The output stores:

- exact feature order;
- training years and row count;
- SHA-256 hash of the canonical training matrix;
- scaler means/scales;
- fitted intercepts and coefficients;
- Ridge alpha and inner-CV scores;
- an explicit rule that future scoring must not refit, reselect or retune before the untouched score is recorded.

This closes an important loophole: future validation must evaluate the model that existed **before** the future outcome was observed, not a later refit using the same variable names.

Production remains unchanged.
