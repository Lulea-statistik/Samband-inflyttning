# Final alpha and lag gate for rates_25_29

Date: 2026-10-20

## Decision

The preferred short-term monthly-module specification is:

- backward window: **12 months**
- variables: **2**
  - YoY percentage-point change in employment rate, age 25–29
  - YoY percentage-point change in labour-force participation, age 25–29
- ridge alpha: **3**
- publication lag: **1 month**
- forecast horizons: 3, 6, 9 and 12 months

Lag 2 is retained as a diagnostic challenger, not as the preferred operational specification.
Alpha 10 remains a robustness reference.

## Why alpha 3

With the two-variable specification fixed, alpha 3 gives the strongest or near-strongest RMSE on the decision-relevant longer horizons.

Relative to seasonal naive:

- 6 months, lag 1: RMSE about **-11.7%**
- 9 months, lag 1: about **-17.5%**
- 12 months, lag 1: about **-10.6%**

Alpha 10 is weaker at the same lag:

- 6 months: about **-10.3%**
- 9 months: about **-14.5%**
- 12 months: about **-7.6%**

The lower regularisation therefore retains useful signal without showing the fragility observed for alpha 30.

## Why lag 1

Lag 2 performs somewhat better at 3 and 6 months, but lag 1 is preferable overall because:

1. it is slightly stronger on the primary 9- and 12-month horizons;
2. it uses the freshest realistically available BAS observation;
3. the current forecast is materially less sensitive to the correction;
4. the temporal-stability tests support lag 1 across the key horizons;
5. it avoids the much larger downward current adjustment produced by lag 2.

At the current 2026M08 origin, alpha 3 gives:

| Horizon | Without monthly module | Lag 1 | Lag 2 |
|---|---:|---:|---:|
| 3 months | 1,227 | 1,219 | 1,171 |
| 6 months | 2,157 | 2,097 | 1,988 |
| 9 months | 2,928 | 2,880 | 2,716 |
| 12 months | 4,353 | 4,306 | 4,123 |

Lag 2 therefore changes the current 12-month forecast by about -230 persons, while lag 1 changes it by about -47 persons. The much larger lag-2 response is not supported by a corresponding improvement on the longer-horizon backtest.

## Historical marginal value of preferred monthly module

Using alpha 3 + lag 1, adding the monthly module to the formal short-term baseline improves RMSE by approximately:

- 3 months: **4.1%**
- 6 months: **11.7%**
- 9 months: **17.5%**
- 12 months: **10.6%**

MAE also improves at every horizon.

## Scope

This selects the preferred **short-term monthly residual module**.

It does not:
- alter the frozen structural core-4;
- revive the rejected direct annual-core4 × seasonal-share bridge;
- constitute a full production promotion of the combined long-term/short-term system.

## Status

- 12-month change window: **LOCKED**
- variables: **2 LOCKED**
- alpha: **3 SELECTED**
- lag: **1 SELECTED**
- lag 2: **DIAGNOSTIC CHALLENGER**
- alpha 10: **ROBUSTNESS REFERENCE**
- structural core-4 changed: **NO**
- production changed: **NO**
