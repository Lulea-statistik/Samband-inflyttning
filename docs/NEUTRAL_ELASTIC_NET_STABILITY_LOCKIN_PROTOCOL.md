# Neutral model selection lock-in protocol

Status: **pre-registered research workflow; production is unchanged**

This document records the agreed work order for narrowing the migration-regression models before any new temporal/monthly module is introduced.

## Freeze

Until the neutral variable lock-in is completed:

- do not add new candidate variables to the main selection universe;
- do not add monthly/temporal predictors;
- do not manually promote variables because they are substantively attractive;
- do not choose an arbitrary fixed number of predictors;
- do not remove a predictor solely because its pairwise correlation with another predictor exceeds a fixed threshold.

The temporal module is explicitly deferred until this protocol has produced a locked model specification.

## Objective

Determine, separately for the 3-year and 5-year windows and for the blind and forecast branches:

1. how much predictive performance is available from the frozen candidate universe;
2. how much sparsity can be obtained without material predictive loss;
3. which predictors are selected stably enough to justify lock-in.

## Model tournament

### A. Full Ridge benchmark

- all eligible frozen candidates;
- StandardScaler inside the training pipeline;
- Ridge alpha remains the existing research benchmark value 10;
- evaluated only on outer geographic validation folds.

### B. Nested 1-SE Elastic Net

Elastic Net is used as the neutral sparse-selection engine because it combines L1 selection with L2 shrinkage and is better suited than pure Lasso to correlated predictor sets.

Hyperparameters are tuned **inside each outer training fold**:

- l1_ratio: 0.10, 0.25, 0.50, 0.75, 0.90, 1.00;
- regularization strength over a pre-specified logarithmic alpha grid;
- inner GroupKFold by municipality.

The 1-SE rule is used. Among models whose mean inner-CV RMSE is within one standard error of the minimum, choose the simplest model measured by mean number of active coefficients. Remaining ties are resolved deterministically in favor of stronger regularization.

The resulting number of predictors is therefore an output, not a user-chosen cap.

### C. Stability-selected Elastic Net

Within each outer training fold:

1. keep the hyperparameters selected by the nested 1-SE procedure;
2. repeatedly split municipality groups into complementary half-samples;
3. fit the model to each half and its complement;
4. record predictor selection frequencies and thematic-family selection frequencies;
5. derive the selection-probability threshold from the conservative Meinshausen-Buehlmann PFER bound with target expected false selections = 1.

If the bound cannot attain PFER <= 1 because the selected model is too dense, this is reported as **infeasible**. No arbitrary 70%, 80%, 90%, or top-N substitute is allowed in that case.

A stable Elastic Net refit is evaluated only when the PFER-derived stable set is non-empty in every outer fold.

## Validation rules

All target-informed operations must occur inside the training data of the relevant fold:

- scaling;
- hyperparameter tuning;
- sparsity choice;
- stability estimation;
- variable selection.

Outer validation remains grouped by municipality. The existing historical years have already been inspected repeatedly, so these results are **research diagnostics**, not a claim of pristine future holdout validation.

## Correlated predictors

No hard pre-filter such as |rho| >= 0.85 -> keep one variable is used. Previous research-only tests showed that this worsened three of four model branches.

Instead report both:

- exact predictor stability;
- thematic-family stability.

This allows several correlated indicators to compete without declaring one of them the true representative in advance.

## Lock-in decision

For each of the four branches compare:

1. full Ridge;
2. nested 1-SE Elastic Net;
3. PFER-controlled stability-selected Elastic Net, where feasible.

Preferred lock-in logic:

- if the stability-selected model retains predictive performance within uncertainty of the larger alternatives, lock the stable model;
- if it loses materially, retain the larger 1-SE Elastic Net or Ridge benchmark rather than forcing sparsity;
- do not interpret selected coefficients causally.

Only after this decision is frozen may the separate monthly **temporal signals** module be developed and tested as an incremental layer.

## Current implementation

Research script:

`scripts/compare_nested_1se_elastic_net_stability.py`

Output:

`docs/data/neutral_nested_1se_elastic_net_stability.json`

Workflow:

`Compare nested 1-SE Elastic Net stability`
