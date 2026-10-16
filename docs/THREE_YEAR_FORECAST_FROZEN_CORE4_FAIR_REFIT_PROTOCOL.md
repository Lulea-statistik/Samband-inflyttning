# Frozen core-4 fair refit robustness protocol

The variable-selection phase is closed. This audit does **not** select or replace predictors.

Frozen core:
- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_kolada_arbetslosa_18_65_pct
- lag1_bostadsbestandsforandring_pct

The audit compares over 100 repeated municipality-group splits:

1. full no-lookahead Ridge with inner 3-fold grouped alpha tuning;
2. frozen core-4 Ridge with the same alpha grid and inner grouped tuning;
3. frozen core-4 OLS.

This corrects the earlier asymmetry where the full Ridge benchmark used fixed alpha=10 while the sparse model could be tuned.

The output is robustness evidence only. The period 2021-2023 has already been inspected and cannot become an untouched confirmation sample.

No production change, no variable reselection and no activation of the deferred temporal module.
