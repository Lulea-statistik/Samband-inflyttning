#!/usr/bin/env python3
"""Strict single-origin Lulea component-specific fading diagnostic.

Extends the prior common-fade test by:
1) testing common fades 0.4, 0.5, 0.6, 0.7;
2) testing component-specific fading where one component fades faster/slower.

All targets are pre-origin Lulea 10y historical means; residual fades toward zero.
No future observed component values are used inside any forecast path.
Research only; no production change.
"""
import json
from pathlib import Path
import itertools
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

def hist_mean(col,origin,window=10):
    x=lu[(lu.year<=origin)&(lu.year>=origin-window+1)][col].dropna()
    return float(x.mean())

def run_spec(name,fb,fd,fm,fr):
    rows=[]
    for origin in origins:
        first=origin+1
        if first not in b or first not in rr: continue
        sb=float(b[first]["birth_rate_pred"])
        sd=float(b[first]["death_rate_pred"])
        sm=float(rr[first]["direct_10y_rate"])
        sr=float(b[first]["residual_pred"])
        mb=hist_mean("fodelsetal_per_100",origin,10)
        md=hist_mean("dodstal_per_1000",origin,10)
        mm=hist_mean("net_migration_per_1000",origin,10)

        for h in horizons:
            end=origin+h
            if end not in actual: continue
            pred=actual[origin]
            path=[]
            for step,y in enumerate(range(origin+1,end+1),start=1):
                k=max(0,step-1)
                wb=(1-fb)**k; wd=(1-fd)**k; wm=(1-fm)**k; wr=(1-fr)**k
                birth=wb*sb+(1-wb)*mb
                death=wd*sd+(1-wd)*md
                net=wm*sm+(1-wm)*mm
                res=wr*sr
                change=birth*pred/100.0-death*pred/1000.0+net*pred/1000.0+res
                pred += change
                path.append({"year":y,"predicted_population":pred,"actual_population":actual.get(y)})
            err=actual[end]-pred
            rows.append({
              "spec":name,"fade_birth":fb,"fade_death":fd,"fade_migration":fm,"fade_residual":fr,
              "origin_year":origin,"horizon_years":h,"target_year":end,
              "predicted_population":pred,"actual_population":actual[end],
              "error_actual_minus_prediction":err,"absolute_error":abs(err),
              "path":path
            })
    return rows

specs=[]
for f in [0.4,0.5,0.6,0.7]:
    specs.append((f"common_{f:.1f}",f,f,f,f))

# Component sensitivity around common 0.5
for comp in ["birth","death","migration","residual"]:
    for f in [0.0,0.3,0.7,1.0]:
        vals={"birth":0.5,"death":0.5,"migration":0.5,"residual":0.5}
        vals[comp]=f
        specs.append((f"{comp}_{f:.1f}_others_0.5",vals["birth"],vals["death"],vals["migration"],vals["residual"]))

rows=[]
for s in specs:
    rows.extend(run_spec(*s))

flat=pd.DataFrame([{k:v for k,v in r.items() if k!="path"} for r in rows])
summary={}
for name,grp in flat.groupby("spec"):
    x=grp.error_actual_minus_prediction.to_numpy(float)
    byh={}
    for h in horizons:
        y=grp[grp.horizon_years.eq(h)].error_actual_minus_prediction.to_numpy(float)
        byh[str(h)]={
          "n":int(len(y)),
          "rmse":float(np.sqrt(np.mean(y*y))),
          "mae":float(np.mean(np.abs(y))),
          "bias":float(np.mean(y))
        }
    first=grp.iloc[0]
    summary[name]={
      "fade_birth":float(first.fade_birth),
      "fade_death":float(first.fade_death),
      "fade_migration":float(first.fade_migration),
      "fade_residual":float(first.fade_residual),
      "n":int(len(x)),
      "rmse":float(np.sqrt(np.mean(x*x))),
      "mae":float(np.mean(np.abs(x))),
      "bias":float(np.mean(x)),
      "max_abs":float(np.max(np.abs(x))),
      "by_horizon":byh
    }

ranking=sorted(
 [{"spec":k,**{kk:vv for kk,vv in v.items() if kk!="by_horizon"}} for k,v in summary.items()],
 key=lambda z:(z["rmse"],z["mae"],abs(z["bias"]),z["max_abs"])
)

out={
 "status":"lulea_strict_single_origin_component_fading_diagnostic",
 "production_changed":False,
 "strict_single_origin_multiyear_forecast":True,
 "future_observed_components_used":False,
 "summary":summary,
 "ranking":ranking,
 "rows":rows
}
(D/"lulea_strict_single_origin_component_fading_diagnostic.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({"status":out["status"],"ranking":ranking[:12]},ensure_ascii=False,indent=2))
