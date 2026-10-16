# SCB core source-origin gate — 2026-10-16

The corrected sparse forecast core contains three SCB-dependent components:

- lagged inflow per 1,000;
- lagged outflow per 1,000;
- lagged annual housing-stock change.

## Official publication anchors for reference year 2023

- Full-year population 2023: SCB release **2024-02-22**.
- Additional 2023 population/migration statistics: SCB release **2024-03-22**.
- Housing stock at 31 Dec 2023: SCB release **2024-04-18**.

These are official product-level publication anchors. They are **not equivalent to an archived PxWeb table snapshot**.

## Forecast-origin implications

### Origin 2024-01-01
Blocked. The required 2023 full-year information had not yet reached the official product publication anchors.

### Origin 2024-05-01
All three official anchors had passed, so this origin is plausible for a research-only as-of reconstruction. However it is **not yet certified** because the exact historical table versions and any later revisions have not been frozen.

## Decision

- Do not call 2024-05-01 a genuine historical holdout yet.
- Do not mark any of these SCB-derived variables `asof_verified=true`.
- Next evidence must be version-specific/archived table evidence or a source archive that establishes the values available at the chosen origin.
- No further model selection while this source gate is open.

The Kolada unemployment KPI identity has separately been frozen to N03937, but its historical publication/replacement history remains a separate gate.
