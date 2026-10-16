# Follow-up after nested 1-SE Elastic Net stability run

The first nested Elastic Net stability run completed successfully.

Key finding: every one of the 20 outer-fold 1-SE choices selected `l1_ratio = 1.0`, i.e. pure Lasso rather than a mixed Elastic Net solution.

Ridge had the lowest aggregate RMSE in all four branches. The 1-SE Lasso models were somewhat sparser, but their complementary-pairs mean selected size `q` was generally too large for the conservative PFER=1 bound to yield a valid stability threshold. Only two outer folds in the 3-year forecast branch were PFER-feasible; both selected the same four stable predictors:

- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- lag1_bostadsbestandsforandring_pct
- lag1_valdeltagande_gap_pp

This is **not** yet a lock-in decision because feasibility failed in the other folds.

## Next neutral diagnostic

Run a dedicated Lasso stability path. For every outer training fold:

1. retain the frozen candidate universe;
2. evaluate the pre-specified Lasso alpha path with inner grouped CV;
3. identify the ordinary 1-SE Lasso;
4. estimate complementary-pairs selection stability along the full alpha path;
5. determine where PFER=1 first becomes feasible without imposing a manual top-N or selection-frequency threshold;
6. prefer a non-empty PFER-feasible stable set that is still within the 1-SE error envelope;
7. if none exists, report the best-RMSE PFER-feasible stable set outside 1-SE only as a diagnostic of the predictive cost of strict stability control.

Production remains unchanged. The monthly temporal module remains deferred.
