# Post-selection refit result and sparse-core robustness gate — 2026-10-16

The PFER-stable post-selection refit confirms:

- Blind branches remain unsuitable for forced extreme sparsity. OLS/Ridge refitting does not recover the large prediction loss.
- Five-year forecast improves after refitting, but remains meaningfully worse than full Ridge.
- Three-year forecast is the only branch where the sparse core remains close to full Ridge after refitting.

Aggregate 3-year forecast RMSE:

- full Ridge: 5.084
- stable Lasso: 5.217
- stable OLS refit: 5.128
- stable Ridge refit: 5.129

The stable 3-year forecast core is:

Always selected across the outer folds:
- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_valdeltagande_gap_pp

Selected in four of five folds:
- lag1_bostadsbestandsforandring_pct

This motivates a final robustness comparison of a fixed 3-variable core and fixed 4-variable core against full Ridge across repeated municipality-group train/test partitions.

This remains research-only because the historical period has already informed core discovery. No new variables are introduced and the temporal monthly module remains deferred.
