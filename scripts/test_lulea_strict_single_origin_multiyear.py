#!/usr/bin/env python3
"""Strict single-origin multi-year Lulea population forecast diagnostic.

Purpose:
Test cumulative population forecast performance when every multi-year path is
generated from information available at the initial origin only.

This first strict diagnostic focuses on the promoted Lulea direct-net migration
candidate and simple persistence for demographic rates:
- birth rate: hold the origin-year forecast rate constant through horizon
- death rate: hold the origin-year forecast rate constant through horizon
- migration: hold the origin-year direct-net 10y forecast rate constant
- residual: hold the origin-year residual correction constant
- population exposure: recursive predicted population

This is intentionally conservative and leakage-free. It does not yet forecast
future explanatory variables. Research only; no production change.
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

lu=p[p.kommun_kod.eq("2580")][["year","folkmangd"]].copy()
actual={int(r.year):float(r.folkmangd) for r in lu.itertuples(index=False)}
b={int(r["year"]):r for r in base["years"]}
rr={int(r["year"]):r for r in rob["years"]}

# origins must have a model forecast for origin+1 and observed population through +5
origins=[2016,2017,2018,2019]
horizons=[2,3,4,5]
rows=[]

for origin in origins:
    first=origin+1
    if first not in b or first not in rr or origin not in actual:
        continue
    birth_rate=float(b[first]["birth_rate_pred"])
    death_rate=float(b[first]["death_rate_pred"])
    mig_rate=float(rr[first]["direct_10y_rate"])
    residual=float(b[first]["residual_pred"])
    for h in horizons:
        end=origin+h
        if end not in actual:
            continue
        pred=actual[origin]
        path=[]
        for y in range(origin+1,end+1):
            births=birth_rate*pred/100.0
            deaths=death_rate*pred/1000.0
            migration=mig_rate*pred/1000.0
            change=births-deaths+migration+residual
            pred=pred+change
            path.append({
              "year":y,
              "predicted_population":pred,
              "actual_population":actual.get(y),
              "error_actual_minus_prediction":None if y not in actual else actual[y]-pred
            })
        err=actual[end]-pred
        rows.append({
          "origin_year":origin,
          "horizon_years":h,
          "target_year":end,
          "start_population_actual":actual[origin],
          "held_birth_rate_per_100":birth_rate,
          "held_death_rate_per_1000":death_rate,
          "held_direct_net_rate_per_1000":mig_rate,
          "held_residual_persons":residual,
          "predicted_population":pred,
          "actual_population":actual[end],
          "error_actual_minus_prediction":err,
          "absolute_error":abs(err),
          "relative_error_pct":100.0*err/actual[end],
          "path":path
        })

df=pd.DataFrame([{k:v for k,v in r.items() if k!="path"} for r in rows])
summary={}
for h in horizons:
    x=df[df.horizon_years.eq(h)].error_actual_minus_prediction.to_numpy(float)
    if len(x)==0: continue
    summary[str(h)]={
      "n_origins":int(len(x)),
      "rmse_persons":float(np.sqrt(np.mean(x*x))),
      "mae_persons":float(np.mean(np.abs(x))),
      "bias_actual_minus_prediction":float(np.mean(x)),
      "max_abs_error_persons":float(np.max(np.abs(x)))
    }

allx=df.error_actual_minus_prediction.to_numpy(float)
out={
 "status":"lulea_strict_single_origin_multiyear_diagnostic",
 "production_changed":False,
 "strict_single_origin_multiyear_forecast":True,
 "method":"Hold initial-origin birth, death, direct-net migration and residual rates/corrections constant; recursively forecast population.",
 "important_limitation":"This is a leakage-free baseline for multi-year use, but does not yet forecast future explanatory variables or demographic rates dynamically.",
 "summary_by_horizon":summary,
 "overall":{
   "n_paths":int(len(allx)),
   "rmse_persons":float(np.sqrt(np.mean(allx*allx))),
   "mae_persons":float(np.mean(np.abs(allx))),
   "bias_actual_minus_prediction":float(np.mean(allx))
 },
 "rows":rows
}
(D/"lulea_strict_single_origin_multiyear_diagnostic.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
