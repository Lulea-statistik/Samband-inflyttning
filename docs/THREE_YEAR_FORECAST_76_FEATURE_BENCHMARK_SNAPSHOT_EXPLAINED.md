# What a 76-variable benchmark snapshot means

The frozen full-Ridge benchmark has 76 predictors. To compare it fairly with the frozen core-4 on a genuinely untouched future year, we need a **pre-outcome predictor matrix** for the benchmark.

This is not 76 separate snapshots in principle. The required artifact is:

- one row per municipality;
- exactly the frozen 76 predictor columns in the frozen feature order;
- values computed using only information available before the outcome is inspected;
- immutable timestamp, file hash and derivation/source record.

For 290 municipalities this is a 290 x 76 matrix (plus municipality/year keys).

Once frozen, the already locked scaler, alpha=10, intercept and coefficients can score the matrix directly. No fitting is needed.

The feasibility audit checks whether the existing panel already contains complete values for all 76 variables by target year. **Completeness alone does not prove as-of eligibility.** A complete historical row can still contain values that were published or revised later. Therefore a future benchmark matrix must be built and frozen prospectively.

Why this matters: without the matrix, a later full-Ridge score could accidentally use revised predictor values after the outcome became known. That would make the comparison with core-4 asymmetric.

The preferred workflow is therefore:
1. identify the next eligible target year;
2. wait until all required predictors for that target year are available;
3. build the 290 x 76 matrix without looking at the target outcome;
4. freeze matrix + hashes + source/vintage manifest;
5. only then score both frozen models when the outcome becomes eligible.
