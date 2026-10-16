# Benchmark snapshot gap

The untouched core-4 scorer is fully pre-registered against the 2026-10-16 source snapshot.

A strict future comparison against the frozen 76-variable full-Ridge benchmark also requires the corresponding future predictor values for all 76 variables to be frozen in advance. The current source snapshot freezes only the four core variables at source-value level.

Therefore:

- core-4 future scoring is ready;
- full-Ridge future scoring is not yet source-vintage complete;
- a 76-feature benchmark matrix may be frozen before future scoring if it can be produced from documented pre-score vintages;
- otherwise the future test must be treated as core-4 absolute validation, with the historical full-Ridge comparison retained as contextual evidence.

The benchmark must not be reconstructed later from revised live data after the future score is known.

This does not reopen variable selection or model fitting.
