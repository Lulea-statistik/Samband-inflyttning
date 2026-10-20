# Common-origin candidate comparison — locked 12-month backward window

This gate completes the current 12-month backward-window line before any 9/6/3-month challenger is introduced.

Arms:
- seasonal naive,
- Family1 BAS employed YoY with lag 1,
- Family1 BAS employed YoY with lag 2,
- rates_25_29 YoY pp with lag 1,
- rates_25_29 YoY pp with lag 2.

All arms are evaluated on exactly the same forecast origins and target periods.

Forecast horizons: 3, 6, 9, 12 months.
Ridge alphas: 3, 10, 30.
Training is strict rolling-origin: a row can enter training only when its complete target period has ended by the current origin.

Primary decision focus: 9 and 12 months.
Secondary reporting: 3 and 6 months.
