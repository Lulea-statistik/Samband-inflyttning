# Ready-to-run untouched scorer

The scoring code for the next untouched temporal validation is now frozen in advance.

Workflow: **Score untouched 3-year forecast outcome**

Required inputs:
- repository path to a CSV containing `kommun_kod` and `inflyttning_per_1000`;
- outcome year.

The scorer:
- reconstructs the four challenger predictors from the frozen 2026-10-16 source snapshot;
- applies the exact frozen OLS scaler/intercept/coefficients;
- does not refit, reselect, retune or query live sources;
- records RMSE, MAE, bias, median absolute error, municipality residuals and Luleå residual;
- commits the untouched score before any model update is allowed.

The full 76-variable Ridge benchmark requires frozen values for all 76 predictors. The current source snapshot only freezes the four core predictors, so the untouched core-4 score is fully reproducible now while a strict full-Ridge future benchmark will require a separate 76-feature predictor snapshot before the outcome.

This limitation is explicit and must not be repaired retrospectively after the outcome is known.
