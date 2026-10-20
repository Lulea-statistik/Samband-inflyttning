#!/usr/bin/env python3
"""Strict single-origin Lulea multiyear challenger with deterministic fading.

Goal:
Improve on the constant-rate strict single-origin baseline without future-data leakage.

At each origin:
- birth/death/direct-net rates start at the origin+1 rolling-origin forecast
- each rate fades toward its pre-origin 10y Lulea historical mean
- fading strengths are fixed ex ante and compared on historical origins:
  0.00 (constant), 0.10, 0.20, 0.30 per forecast year
- balance residual fades toward zero at the same rate
- population is recursive predicted exposure

No future observed component values are used inside a path.
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
p=p.sort_values(["kommun_kod","year"])
p["net_migration_per_1000"]=p["inflyttning_per_1000"]-p["utflyttning_per_1000"]

t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
lu=p[p.kommun_kod.eq("2580")].merge(
    t[t.kommun_kod.eq("2580")][["year","fodelsetal_per_100","dodstal_per_1000"]],
    on="year",how="left"
)
actual={int(r.year):float(r.folkmangd) for r in lu.itertuples(index=False)}
b={int(r["year"]):r for r in base["years"]}
rr={int(r["year"]):r for r in rob["years"]}

origins=[2016,2017,2018,2019]
horizons=[2,3,4,5]
fades=[0.0,0.1,0.2,0.3]
rows=[]

def hist_mean(col,origin,window=10):
    x=lu[(lu.year<=origin)&(lu.year>=origin-window+1)][col].dropna()
    return float(x.mean())

for origin in origins:
    first=origin+1
    if first not in b or first not in rr: continue
    start_birth=float(b[first]["birth_rate_pred"])
    start_death=float(b[first]["death_rate_pred"])
    start_net=float(rr[first]["direct_10y_rate"])
    start_res=float(b[first]["residual_pred"])
    mean_birth=hist_mean("fodelsetal_per_100",origin,10)
    mean_death=hist_mean("dodstal_per_1000",origin,10)
    mean_net=hist_mean("net_migration_per_1000",origin,10)

    for fade in fades:
        for h in horizons:
            end=origin+h
            if end not in actual: continue
            pred=actual[origin]
            path=[]
            for step,y in enumerate(range(origin+1,end+1),start=1):
                # step 1 uses the one-year-ahead origin forecast unchanged.
                # Thereafter exponentially fade toward pre-origin historical means.
                k=max(0,step-1)
                w=(1.0-fade)**k
                birth=w*start_birth+(1-w)*mean_birth
                death=w*start_death+(1-w)*mean_death
                net=w*start_net+(1-w)*mean_net
                res=w*start_res
                births=birth*pred/100.0
                deaths=death*pred/1000.0
                migration=net*pred/1000.0
                change=births-deaths+migration+res
                pred=pred+change
                path.append({
                  "year":y,"step":step,
                  "birth_rate":birth,"death_rate":death,"net_rate":net,
                  "residual":res,"predicted_population":pred,
                  "actual_population":actual.get(y),
                  "error_actual_minus_prediction":None if y not in actual else actual[y]-pred
                })
            err=actual[end]-pred
            rows.append({
              "origin_year":origin,"horizon_years":h,"target_year":end,
              "fade_per_year":fade,
              "historical_mean_birth_rate":mean_birth,
              "historical_mean_death_rate":mean_death,
              "historical_mean_net_rate":mean_net,
              "predicted_population":pred,"actual_population":actual[end],
              "error_actual_minus_prediction":err,"absolute_error":abs(err),
              "relative_error_pct":100.0*err/actual[end],
              "path":path
            })

flat=pd.DataFrame([{k:v for k,v in r.items() if k!="path"} for r in rows])
summary={}
for fade in fades:
    z=flat[flat.fade_per_year.eq(fade)]
    x=z.error_actual_minus_prediction.to_numpy(float)
    by_h={}
    for h in horizons:
        y=z[z.horizon_years.eq(h)].error_actual_minus_prediction.to_numpy(float)
        by_h[str(h)]={
          "n":int(len(y)),
          "rmse":float(np.sqrt(np.mean(y*y))),
          "mae":float(np.mean(np.abs(y))),
          "bias":float(np.mean(y))
        }
    summary[str(fade)]={
      "n":int(len(x)),
      "rmse":float(np.sqrt(np.mean(x*x))),
      "mae":float(np.mean(np.abs(x))),
      "bias":float(np.mean(x)),
      "max_abs":float(np.max(np.abs(x))),
      "by_horizon":by_h
    }

ranking=sorted(
 [{"fade_per_year":float(k),**{kk:vv for kk,vv in v.items() if kk!="by_horizon"}}
  for k,v in summary.items()],
 key=lambda z:(z["rmse"],z["mae"],abs(z["bias"]),z["max_abs"])
)

out={
 "status":"lulea_strict_single_origin_fading_diagnostic",
 "production_changed":False,
 "strict_single_origin_multiyear_forecast":True,
 "future_observed_components_used":False,
 "method":"Fade initial one-year-ahead component forecasts toward pre-origin 10y Lulea historical means; residual fades toward zero.",
 "summary":summary,
 "ranking":ranking,
 "rows":rows
}
(D/"lulea_strict_single_origin_fading_diagnostic.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
