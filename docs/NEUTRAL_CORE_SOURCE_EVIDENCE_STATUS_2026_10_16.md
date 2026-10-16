# Core source evidence update after SCB finality review

SCB's 2023 methodology for population statistics states that preliminary data are revised as late notifications arrive, but that once December/Q4/full-year statistics are published, the statistics become final and no further revisions are made.

## Consequence for migration and population denominator

For a research forecast origin after the 2023 full-year releases, this substantially strengthens the evidence for:

- lag1_inflyttning_per_1000
- lag1_utflyttning_per_1000
- their population denominator

The evidence is classified as **strong final-release equivalence**, not exact archived table vintage. We still do not possess a historical POST-response snapshot from Flyttningar97/BefolkningNy.

Therefore these variables remain `asof_verified=false` under the project's strictest definition, but they are no longer in the same weak evidence category as before.

## Housing remains blocked

Wayback captured the BO0104T04 table page on 2024-03-02, before the official 2023 housing-stock release on 2024-04-18. This proves that table-page existence does not establish the presence of 2023 values.

A housing-specific finality/revision rule or archived value snapshot is still required.

## Kolada remains blocked

N03937 is now pinned in code and its current identity is verified. Historical publication/replacement timing remains uncertified, and the age definition changes from 18-64 through 2022 to 18-65 from 2023.

## Decision

No further model selection. The two remaining source blockers are:
1. housing-stock revision/finality evidence;
2. Kolada N03937 historical publication evidence and explicit handling of the definition break.

Production remains unchanged and the monthly temporal module stays deferred.
