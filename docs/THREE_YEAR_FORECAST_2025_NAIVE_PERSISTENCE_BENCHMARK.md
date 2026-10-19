# 2025 naive persistence benchmark

A simple benchmark is frozen alongside the 2025 core-4 temporal gate.

Definition:

`prediction_2025 = inflow_per_1000_2024`

This is equivalent to the frozen predictor `lag1_inflyttning_per_1000`.

Purpose:

- test whether core-4 adds predictive value beyond carrying the latest observed level forward;
- provide a transparent benchmark that does not require model fitting;
- avoid using the 76-variable benchmark for this question.

This benchmark does not alter the frozen core-4, the temporal challenger, or production.
