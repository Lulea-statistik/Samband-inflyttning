# Geographic equity post-processing gate

Date: 2026-10-20

## Decision

Reject the median-shrinkage post-processing challenger.

The frozen 6-year core-4 remains the reference model.

## Result

Across gamma = 0, 0.25, 0.5 and 1.0, the challenger worsens both overall accuracy and geographic tail error.

Relative to core-4:

- pooled RMSE: about **+4.2% to +4.7%**
- p90 municipality RMSE: about **+1.3% to +2.0%**
- worst-decile mean municipality RMSE: about **+5.6% to +6.3%**
- dispersion of municipality RMSE: also worsens

No gamma satisfies the pre-specified decision rule.

## Interpretation

Shrinking municipality forecasts toward the annual cross-sectional median does not reduce geographic inequality in forecast quality. It makes the difficult municipalities worse while also degrading pooled accuracy.

This path is therefore closed.

## Next research direction

Keep:
- 6-year training window
- locked core-4 feature set
- no production change

Test dispersion-aware model fitting instead of post-processing, using historical municipality difficulty measured strictly from prior training data.

Primary metrics:
- pooled RMSE
- p90 municipality RMSE
- worst-decile mean municipality RMSE

Guardrail:
- geographic tail metrics must improve
- pooled RMSE may deteriorate by at most 1%
