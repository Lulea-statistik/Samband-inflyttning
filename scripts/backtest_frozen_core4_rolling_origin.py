#!/usr/bin/env python3
"""Retrospective rolling-origin backtest for the frozen core-4.

Primary protocol:
- fixed 6-year training window
- one-year-ahead forecast
- move origin one year at a time
- frozen four predictors only
- OLS refit within each historical training window

Sensitivity only:
- 3-, 4-, and 5-year fixed windows
These are reported side-by-side and must not be used for post-hoc variable selection.

Important: historical panel values are today's reconstructed values, not exact
archived source vintages. This is therefore a retrospective rolling-origin
stability test, not a strict historical as-of backtest.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
lock=json.loads((D/"three_year_forecast_frozen_candidate_set.json").read_text(encoding="utf-8"))
features=lock["features"]
target="inflyttning_per_1000"
PRIMARY_WINDOW=6
SENSITIVITY_WINDOWS=[3,4,5]
WINDOWS=SENSITIVITY_WINDOWS+[PRIMARY_WINDOW]

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].astype(str).str.zfill(4)

need=["kommun_kod","year",target]+features
missing_cols=[c for c in need if c not in panel.columns]
if missing_cols:
    raise SystemExit(f"Missing columns: {missing_cols}")

# Coverage by year. Require all 290 municipalities for target + all four predictors.
coverage=[]
eligible_years=[]
for year in sorted(int(x) for x in panel["year"].dropna().unique()):
    q=panel.loc[panel.year==year,need]
    nmun=int(q.kommun_kod.nunique())
    counts={c:int(q[c].notna().sum()) for c in [target]+features}
    complete_rows=q[[target]+features].notna().all(axis=1)
    complete_codes=int(q.loc[complete_rows,"kommun_kod"].nunique())
    complete=(complete_codes==290)
    coverage.append({
      "year":year,
      "municipalities_in_panel":nmun,
      "complete_municipalities":complete_codes,
      "counts":counts,
      "complete":complete
    })
    if complete:
        eligible_years.append(year)

def metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return {
      "rmse":float(np.sqrt(np.mean(e**2))),
      "mae":float(np.mean(np.abs(e))),
      "bias":float(np.mean(e)),
      "median_ae":float(np.median(np.abs(e)))
    }

results=[]
pred_rows=[]
for window in WINDOWS:
    for forecast_year in eligible_years:
        train_years=list(range(forecast_year-window,forecast_year))
        if not all(y in eligible_years for y in train_years):
            continue
        tr=panel[panel.year.isin(train_years)][need].dropna().copy()
        te=panel[panel.year==forecast_year][need].dropna().copy()
        # Historical panel contains three extra/non-canonical municipality codes
        # in some years. Keep exactly the 290 codes with complete data in every
        # training year and the forecast year.
        sets=[]
        for yy in train_years+[forecast_year]:
            qq=panel[panel.year==yy][need].dropna()
            sets.append(set(qq["kommun_kod"]))
        common=set.intersection(*sets)
        if len(common)!=290:
            continue
        tr=tr[tr.kommun_kod.isin(common)].copy()
        te=te[te.kommun_kod.isin(common)].copy()
        if len(tr)!=290*window or len(te)!=290:
            continue

        model=make_pipeline(StandardScaler(),LinearRegression())
        model.fit(tr[features],tr[target])
        pred=model.predict(te[features])
        m=metrics(te[target].to_numpy(float),pred)
        lmask=te.kommun_kod.eq("2580").to_numpy()
        lulea=None
        if lmask.sum()==1:
            i=int(np.flatnonzero(lmask)[0])
            lulea={
              "actual":float(te.iloc[i][target]),
              "prediction":float(pred[i]),
              "residual_prediction_minus_actual":float(pred[i]-te.iloc[i][target])
            }

        rec={
          "window_years":window,
          "forecast_year":forecast_year,
          "training_years":train_years,
          "n_train":int(len(tr)),
          "n_test":int(len(te)),
          **m,
          "lulea":lulea
        }
        results.append(rec)
        for (_,row),pr in zip(te.iterrows(),pred):
            pred_rows.append({
              "window_years":window,
              "forecast_year":forecast_year,
              "kommun_kod":row["kommun_kod"],
              "actual":float(row[target]),
              "prediction":float(pr),
              "residual_prediction_minus_actual":float(pr-row[target])
            })

summary={}
for window in WINDOWS:
    rr=[r for r in results if r["window_years"]==window]
    if not rr:
        summary[str(window)]={"forecast_count":0}
        continue
    summary[str(window)]={
      "forecast_count":len(rr),
      "first_forecast_year":min(r["forecast_year"] for r in rr),
      "last_forecast_year":max(r["forecast_year"] for r in rr),
      "mean_rmse":float(np.mean([r["rmse"] for r in rr])),
      "median_rmse":float(np.median([r["rmse"] for r in rr])),
      "mean_mae":float(np.mean([r["mae"] for r in rr])),
      "mean_abs_bias":float(np.mean([abs(r["bias"]) for r in rr])),
      "mean_lulea_absolute_error":float(np.mean([abs(r["lulea"]["residual_prediction_minus_actual"]) for r in rr if r["lulea"]]))
    }

out={
 "status":"retrospective_core4_rolling_origin_backtest",
 "production_changed":False,
 "selection_phase_closed":True,
 "features":features,
 "method":"StandardScaler + OLS refit within each historical training window",
 "forecast_horizon_years":1,
 "primary_window_years":PRIMARY_WINDOW,
 "sensitivity_windows_years":SENSITIVITY_WINDOWS,
 "eligible_complete_years":eligible_years,
 "coverage":coverage,
 "summary_by_window":summary,
 "yearly_results":results,
 "limitations":[
   "Historical values use the current reconstructed panel and are not exact archived as-of source vintages.",
   "N03937 has a documented age-definition break: 18-64 through 2022, 18-65 from 2023.",
   "This test evaluates temporal robustness of the frozen variable set, not untouched future validity.",
   "Sensitivity windows are descriptive and must not be used for post-hoc variable selection."
 ]
}
(D/"three_year_forecast_core4_rolling_origin_backtest.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
pd.DataFrame(pred_rows).to_csv(D/"three_year_forecast_core4_rolling_origin_predictions.csv",index=False)
print(json.dumps({
 "eligible_complete_years":eligible_years,
 "summary_by_window":summary,
 "primary_yearly_results":[r for r in results if r["window_years"]==PRIMARY_WINDOW]
},ensure_ascii=False,indent=2))
