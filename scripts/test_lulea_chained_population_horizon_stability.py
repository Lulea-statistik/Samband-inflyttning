#!/usr/bin/env python3
"""Lulea chained population-level horizon stability test.

Evaluate baseline, direct-net 10y, and 75% direct blend over all available
rolling chained windows of 2, 3, 4, and 5 years within 2017-2024.

Each window starts from actual population immediately before the first forecast
year, then recursively uses predicted population as exposure. Component rates
remain each year's historical rolling-origin forecasts.

Research only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
base=json.loads((D/"lulea_full_component_historical_backtest.json").read_text(encoding="utf-8"))
rob=json.loads((D/"lulea_direct_net_full_balance_robustness.json").read_text(encoding="utf-8"))

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
lu=p[p.kommun_kod.eq("2580")][["year","folkmangd"]]
actual_pop={int(r.year):float(r.folkmangd) for r in lu.itertuples(index=False)}

b={int(r["year"]):r for r in base["years"]}
rr={int(r["year"]):r for r in rob["years"]}
avail=sorted(b)
candidates=["baseline","direct_10y","blend_75pct_direct"]

def mig_rate(c,y):
    x=b[y]; r=rr[y]
    sep=float(x["inflow_rate_pred"])-float(x["outflow_rate_pred"])
    direct=float(r["direct_10y_rate"])
    if c=="baseline": return sep
    if c=="direct_10y": return direct
    return 0.25*sep+0.75*direct

def run_window(years,c):
    start=years[0]-1
    pred=actual_pop[start]
    rows=[]
    for y in years:
        x=b[y]
        births=float(x["birth_rate_pred"])*pred/100.0
        deaths=float(x["death_rate_pred"])*pred/1000.0
        migration=mig_rate(c,y)*pred/1000.0
        change=births-deaths+migration+float(x["residual_pred"])
        pred_end=pred+change
        actual=actual_pop[y]
        rows.append({
          "year":y,
          "predicted_population_end":pred_end,
          "actual_population_end":actual,
          "level_error_actual_minus_prediction":actual-pred_end
        })
        pred=pred_end
    e=np.array([r["level_error_actual_minus_prediction"] for r in rows],float)
    return {
      "start_year":start,
      "forecast_years":years,
      "level_rmse":float(np.sqrt(np.mean(e*e))),
      "level_mae":float(np.mean(np.abs(e))),
      "final_error":float(e[-1]),
      "max_abs_error":float(np.max(np.abs(e))),
      "rows":rows
    }

out={
 "status":"lulea_chained_population_horizon_stability",
 "production_changed":False,
 "validation_type":"rolling chained population-level windows by horizon",
 "strict_single_origin_multiyear_forecast":False,
 "horizons":{},
 "aggregate":{}
}

for h in [2,3,4,5]:
    windows=[]
    for i in range(0,len(avail)-h+1):
        ys=avail[i:i+h]
        if ys != list(range(ys[0],ys[0]+h)): continue
        rec={"forecast_years":ys,"candidates":{}}
        for c in candidates:
            rec["candidates"][c]=run_window(ys,c)
        rec["winner"]=min(
          candidates,
          key=lambda c:(rec["candidates"][c]["level_rmse"],
                        rec["candidates"][c]["level_mae"],
                        abs(rec["candidates"][c]["final_error"]))
        )
        windows.append(rec)
    hs={"windows":windows,"candidate_summary":{}}
    for c in candidates:
        rms=[w["candidates"][c]["level_rmse"] for w in windows]
        mae=[w["candidates"][c]["level_mae"] for w in windows]
        fin=[abs(w["candidates"][c]["final_error"]) for w in windows]
        hs["candidate_summary"][c]={
          "n_windows":len(windows),
          "mean_rmse":float(np.mean(rms)),
          "median_rmse":float(np.median(rms)),
          "mean_mae":float(np.mean(mae)),
          "mean_abs_final_error":float(np.mean(fin)),
          "max_rmse":float(np.max(rms)),
          "wins":int(sum(w["winner"]==c for w in windows))
        }
    hs["ranking"]=sorted(
      [{"candidate":c,**v} for c,v in hs["candidate_summary"].items()],
      key=lambda z:(z["mean_rmse"],z["mean_mae"],z["mean_abs_final_error"])
    )
    out["horizons"][str(h)]=hs

for c in candidates:
    vals=[]
    for h in ["2","3","4","5"]:
        s=out["horizons"][h]["candidate_summary"][c]
        vals.append(s)
    out["aggregate"][c]={
      "mean_of_horizon_mean_rmse":float(np.mean([v["mean_rmse"] for v in vals])),
      "mean_of_horizon_mean_mae":float(np.mean([v["mean_mae"] for v in vals])),
      "total_window_wins":int(sum(v["wins"] for v in vals)),
      "total_windows":int(sum(v["n_windows"] for v in vals)),
      "worst_horizon_mean_rmse":float(max(v["mean_rmse"] for v in vals))
    }

out["aggregate_ranking"]=sorted(
 [{"candidate":c,**v} for c,v in out["aggregate"].items()],
 key=lambda z:(z["mean_of_horizon_mean_rmse"],
               z["mean_of_horizon_mean_mae"],
               z["worst_horizon_mean_rmse"])
)

(D/"lulea_chained_population_horizon_stability.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
