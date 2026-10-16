# PFER stability path result and next gate — 2026-10-16

The PFER-feasible Lasso path audit confirms that strict sparse stability behaves very differently by model branch.

## Blind branches

No PFER-feasible stable set exists inside the 1-SE envelope in any outer fold.

Forcing PFER=1 outside 1-SE collapses the blind models to roughly 1–5 predictors and causes a very large prediction loss:

- five-year blind: Ridge RMSE 8.590 vs PFER-stable Lasso 13.662;
- three-year blind: Ridge RMSE 8.082 vs PFER-stable Lasso 13.388.

Current interpretation: the blind signal is distributed across many predictors. Do **not** force a tiny sparse model solely for interpretability.

## Forecast branches

Five-year forecast remains only moderately compatible with strict sparsity:

- Ridge RMSE 5.274;
- PFER-stable Lasso RMSE 5.701;
- stable sets contain 2–4 predictors, with lagged inflow and outflow recurring in every fold.

Three-year forecast is the strongest sparse candidate:

- Ridge RMSE 5.084;
- 1-SE Lasso RMSE 5.133;
- PFER-stable Lasso RMSE 5.217.

The PFER-stable set is nearly invariant across folds. The recurring core is:

- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_valdeltagande_gap_pp

and `lag1_bostadsbestandsforandring_pct` is present in four of five folds.

## Next neutral gate

Before rejecting or accepting the sparse forecast core, test **post-selection refitting**.

Reason: the current stable model is evaluated with Lasso shrinkage still applied. A small selected set may lose accuracy because coefficients remain shrunk, not because the omitted variables are essential.

For each training-only PFER-stable set compare:

1. original stable Lasso;
2. OLS refit on the same selected variables;
3. inner-CV-tuned Ridge refit on the same selected variables;
4. full Ridge benchmark.

No variable set is manually changed. If refitting recovers most of the Ridge performance, the sparse core remains a credible lock-in candidate. If it does not, the omitted variables are carrying real predictive signal and sparsity should not be forced.

Production and the deferred temporal module remain unchanged.
