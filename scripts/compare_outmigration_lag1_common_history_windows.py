#!/usr/bin/env python3
"""Compare lag1-only outmigration training windows on identical forecast years.

Uses existing long-history rolling-origin predictions. Restricts all windows to
the common forecast years 2013-2024 so 3/5/6/10-year training windows are
directly comparable.

Research only. No production changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
p=pd.read_csv(D/"outmigration_long_history_rolling_origin_predictions.csv",
              dtype={"kommun_kod":str})
p=p[(p.model=="lag1_only") & p.window.isin([3,5,6,10]) & p.forecast_year.between(2013,2024)].copy()

expected=12*290
for w in [3,5,6,10]:
    q=p[p.window.eq(w)]
    if len(q)!=expected:
        raise RuntimeError(f"Window {w}: expected {expected} rows, got {len(q)}")

def metrics(g):
    e=g.error.to_numpy(float)
    return {
      "n":int(len(g)),
      "rmse":float(np.sqrt(np.mean(e*e))),
      "mae":float(np.mean(np.abs(e))),
      "bias_prediction_minus_actual":float(np.mean(e))
    }

out={"status":"outmigration_lag1_common_history_window_comparison",
     "production_changed":False,
     "model":"lag1_utflyttning_per_1000 only",
     "common_forecast_years":list(range(2013,2025)),
     "windows":{}}

year_table={}
for w in [3,5,6,10]:
    q=p[p.window.eq(w)]
    yearly={}
    for fy,g in q.groupby("forecast_year"):
        yearly[int(fy)]=metrics(g)
        year_table.setdefault(int(fy),{})[w]=yearly[int(fy)]["rmse"]
    out["windows"][str(w)]={"overall":metrics(q),"yearly":yearly}

# Per-year ranks and wins.
wins={w:0 for w in [3,5,6,10]}
ranks={w:[] for w in [3,5,6,10]}
for fy,vals in year_table.items():
    ordered=sorted(vals.items(),key=lambda kv:kv[1])
    for rank,(w,rmse) in enumerate(ordered,1):
        ranks[w].append(rank)
    wins[ordered[0][0]]+=1

for w in [3,5,6,10]:
    out["windows"][str(w)]["year_stability"]={
      "years_best":int(wins[w]),
      "share_years_best":float(wins[w]/len(year_table)),
      "mean_rank":float(np.mean(ranks[w])),
      "median_rank":float(np.median(ranks[w])),
      "worst_rank":int(np.max(ranks[w]))
    }

out["ranking_by_common_rmse"]=sorted(
    [int(w) for w in out["windows"]],
    key=lambda w:out["windows"][str(w)]["overall"]["rmse"])

# Conservative choice: lowest common-sample RMSE, tie-break MAE, then shorter window.
out["selected_window"]=min([3,5,6,10],
  key=lambda w:(out["windows"][str(w)]["overall"]["rmse"],
                out["windows"][str(w)]["overall"]["mae"],w))

(D/"outmigration_lag1_common_history_window_comparison.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
