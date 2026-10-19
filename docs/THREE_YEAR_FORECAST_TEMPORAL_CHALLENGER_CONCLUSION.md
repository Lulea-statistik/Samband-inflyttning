# Temporal challenger conclusion

The frozen structural core-4 remains unchanged.

Two temporal additions were tested with the same 6-year rolling-origin protocol over forecast years 2017-2024:

- 1-year momentum: inflow(t-1) - inflow(t-2)
- 3-year trend slope: slope across inflow(t-3), inflow(t-2), inflow(t-1)

## Aggregate result

Core-4:
- mean RMSE 6.7699
- mean MAE 5.1310
- mean absolute bias 3.1581

Core-4 + 1-year momentum:
- mean RMSE 6.8053
- RMSE change vs core-4: +0.52%
- mean MAE 5.1519
- mean absolute bias 3.1023

Core-4 + 3-year trend:
- mean RMSE 6.7109
- RMSE change vs core-4: -0.87%
- mean MAE 5.0710
- mean absolute bias 2.9282

## Weak years 2017-2019

Core-4 mean RMSE: 8.7689
3-year trend mean RMSE: 8.6797

The improvement is modest and does not solve the 2018 failure. It does improve 2019 materially.

## Later years 2020-2024

Core-4 mean RMSE: 5.5705
3-year trend mean RMSE: 5.5296

The trend version improves 2023 and 2024 but is slightly worse in 2020-2022.

## Decision

- Reject 1-year momentum as a preferred temporal challenger.
- Retain 3-year trend as a provisional research challenger only.
- Do not modify the structural core-4.
- Do not promote the temporal layer to production from this historical backtest alone.
- A future untouched comparison is required before any promotion.

The temporal challenger should remain a separate overlay so that core-4 continues to be interpretable and independently scoreable.
