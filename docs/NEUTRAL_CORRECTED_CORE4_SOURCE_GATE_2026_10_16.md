# Corrected no-lookahead 3-year forecast core — source gate

After removing the two pre-existing `LOOKAHEAD_ONLY_FEATURES`, the corrected PFER-stable sets show a new recurring sparse core.

## Corrected recurring variables

Selected in all 5 outer folds:
- `lag1_inflyttning_per_1000`
- `lag1_utflyttning_per_1000`
- `lag1_kolada_arbetslosa_18_65_pct`

Selected in 4 of 5:
- `lag1_bostadsbestandsforandring_pct`

The employment seasonality measure appears only in one fold and is not promoted to the core.

## Predictive status

Corrected 3-year forecast aggregate RMSE:
- full Ridge: 5.219
- 1-SE Lasso: 5.307
- PFER-stable Lasso: 5.644
- PFER-stable OLS refit: 5.445

The corrected sparse model is therefore weaker than the earlier contaminated core, as expected after removing the lookahead turnout variable. It remains a research candidate, not a production lock-in.

## Source/method gate

Method derivations are explicit for all four recurring variables, but none is yet certified as historical as-of data.

A specific reproducibility issue exists for the Kolada unemployment candidate: the executable code currently resolves its KPI id dynamically from semantic title plus recent municipality coverage. Repository diagnostics identify the candidate as N03937, but strict historical forecasting requires the exact KPI identity and replacement/publication history to be frozen and audited.

No further variable reselection should be run now. The next work is source-vintage verification for:
1. Kolada unemployment;
2. SCB migration + population denominator;
3. SCB housing stock.

The temporal monthly module remains deferred.
