# Frozen core-4 refit method lock

The refit method for the frozen 3-year forecast core is now locked to **ordinary least squares (OLS)**.

## Evidence

Across 100 repeated municipality-group splits for 2021-2023:

| Model | Mean RMSE | Mean MAE |
|---|---:|---:|
| Full Ridge, inner-CV tuned | 5.1870 | 3.8895 |
| Frozen core-4 OLS | 5.3819 | 3.9927 |
| Frozen core-4 Ridge, inner-CV tuned | 5.3827 | 3.9927 |

The tuned sparse Ridge selected alpha 0.01 in 72 of 100 splits and otherwise remained weakly regularized. It therefore behaves essentially like OLS, while OLS is marginally better on both RMSE and MAE.

## Decision

For the frozen four-variable branch:

- predictors remain fixed;
- refit method is fixed to **OLS**;
- no further OLS-vs-Ridge tuning is allowed on the already inspected 2021-2023 period.

This is **not** a production-model win. The full tuned Ridge benchmark remains better historically:

- core-4 OLS mean RMSE is about **3.77% higher**;
- core-4 beats full Ridge in **12%** of repeated splits;
- core-4 is within **5%** of full Ridge in **62%** of splits.

The purpose of retaining core-4 OLS is parsimony, interpretability and a stable pre-registered challenger for future untouched validation.

## Next gate

The next meaningful decision must come from a future outcome evaluated against predictors frozen before that outcome was known. Until then:

- production unchanged;
- variable set frozen;
- refit method frozen to OLS;
- monthly temporal module deferred.
