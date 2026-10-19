# 2025 untouched validation chain

The 2025 prospective validation now has two independent pre-scoring components.

## 1. Freeze readiness audit

The audit verifies that:
- core-4 and core-4 + trend3y predictions remain hash-identical to the frozen manifest;
- naive persistence remains hash-identical to its manifest;
- all three use the same 290 municipalities;
- Luleå (2580) is present;
- the training period is exactly 2019-2024;
- the 2025 predictor matrix contains no 2025 outcome values;
- the untouched scorer exists.

A successful audit writes:
`docs/data/three_year_forecast_2025_validation_readiness_audit.json`
with `validation_ready=true`.

## 2. Independent SCB outcome builder

`scripts/build_scb_2025_outcome.py` is outcome-only. It does not import model code or read frozen prediction files.

It builds:
`docs/data/outcomes/inflyttning_2025.csv`

from:
- SCB BE0101J / Flyttningar97, Inflyttningar;
- SCB BE0101A / BefolkningNy, Folkmängd.

Definition:
`inflyttning_per_1000 = 1000 * inflyttningar / population`

The workflow is manual-only. If 2025 is not yet available in both SCB tables, it fails without modifying the validation model or predictions.

## 3. Scoring

Only after the outcome file exists should the manual untouched scoring workflow be run.
