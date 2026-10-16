# Current source gate conclusion and future snapshot protocol

## Housing blocker resolved to final-release equivalence

SCB's 2023 quality declaration for Bostadsbestånd states:

- only final statistics are reported;
- publication occurs once per year, in April;
- reference time is 31 December.

Therefore `lag1_bostadsbestandsforandring_pct` can be upgraded from an unknown-revision state to the same **strong final-release equivalence** evidence class used for the annual population/migration inputs. This is still not an exact archived API-value snapshot.

## Kolada blocker cannot be solved retrospectively from today's API

N03937 is now pinned and its current identity is verified. However Kolada's API terms explicitly state that:

- data may be revised without separate notice;
- individual KPIs may be removed without notice.

The current API therefore cannot certify the exact N03937 values that existed at a historical forecast origin. In addition, N03937 changes age definition from 18-64 through 2022 to 18-65 from 2023.

## Method decision

Do **not** keep iterating variable selection on 2021-2023 to work around this evidence limitation.

Instead:

1. retain the corrected core as a provisional predictive hypothesis;
2. classify N03937 as not historically as-of certifiable from current Kolada;
3. begin immutable dated source snapshots now;
4. use those snapshots for a genuinely future untouched validation year;
5. only after that confirmation reconsider production and the deferred temporal module.

A new manual workflow, `Snapshot forecast core sources`, stores timestamped SCB metadata plus Kolada N03937 metadata and annual municipality data without overwriting previous snapshots.
