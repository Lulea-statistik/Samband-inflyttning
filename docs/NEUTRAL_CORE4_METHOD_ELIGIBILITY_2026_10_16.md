# Core-4 method audit: turnout predictor is not strict-as-of eligible

The provisional four-variable 3-year forecast core cannot be locked as currently derived.

## Finding

`lag1_valdeltagande_gap_pp` is built from election-year district turnout gaps and annualized by linear interpolation between election years. It is also explicitly listed in `LOOKAHEAD_ONLY_FEATURES` in `scripts/build_analysis.py`.

For an intervening historical year, interpolation can use a later election outcome. A one-year lag does not remove that information leak. Therefore this feature is **ineligible for strict historical/as-of forecasting in its current derivation**.

The same applies to `lag1_valdeltagande_pct`.

This is a method-eligibility correction, not a performance-driven exclusion.

## Other three core variables

Their executable derivations are now method-traceable:

- `lag1_inflyttning_per_1000`: SCB inflow divided by population, per 1,000, then lagged one year.
- `lag1_utflyttning_per_1000`: SCB outflow divided by population, per 1,000, then lagged one year.
- `lag1_bostadsbestandsforandring_pct`: annual percent change in SCB total dwelling stock, then lagged one year.

Their exact historical source vintages remain uncertified, so they are not yet `asof_verified`.

## Required next model action

Repeat the already registered neutral 3-year forecast selection/stability protocol with **only** the two code-declared `LOOKAHEAD_ONLY_FEATURES` excluded. No new predictors, no manual substitute for turnout, no altered thresholds.

This exception to the 'no more reselection on 2021–2023' rule is required because the previously selected core contained a predictor that fails the pre-existing strict forecast eligibility rule.

Production remains unchanged and the monthly temporal module remains deferred.
