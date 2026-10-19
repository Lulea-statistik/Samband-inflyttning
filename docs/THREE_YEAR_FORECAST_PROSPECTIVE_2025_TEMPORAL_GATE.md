# Prospective untouched temporal gate: 2025, not 2026

The attempted 2026 freeze was correctly blocked because the verified source snapshot captured on 2026-10-16 contains annual SCB migration and population only through 2024. The frozen core-4 requires t-1 migration/population predictors, so a valid 2026 predictor row cannot yet be constructed without 2025 annual source values.

Therefore the earliest currently valid prospective untouched target is **2025**:

- training target years: 2019-2024;
- forecast target year: 2025;
- predictors for target 2025 use source year 2024;
- source values come from immutable snapshot `20261016T203726Z`;
- baseline: core-4;
- challenger: core-4 + pre-registered 3-year trend;
- no refit/reselection/redefinition before the frozen predictions are scored.

The failed 2026 workflow is retained as evidence that the availability gate worked. A 2026 freeze may only be created once the required 2025 predictor sources exist and are snapshotted before the 2026 outcome is inspected.
