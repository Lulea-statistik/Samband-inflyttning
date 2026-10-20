#!/usr/bin/env python3
"""Robustness test for direct net migration in full Lulea population balance.

Compare:
- baseline separate inflow/outflow
- direct net, 6y
- direct net, 10y
- blends between baseline and direct-net 10y: 25/50/75% direct

Same birth, death, residual, and Y-1 exposure as the established full-component backtest.
Research only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p.sort_values(["kommun_kod","year"])
p["net_migration_per_1000"]=p["inflyttning_per_1000"]-p["utflyttning_per_1000"]

base=json.loads((D/"lulea_full_component_historical_backtest.json").read_text(encoding="utf-8"))
FEATURES=["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"]
ALPHAS=[0.0,0.1,1.0,10.0]

def model(a):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
                         Ridge(alpha=1e-10 if a==0 else a))

def choose_alpha(tr):
    yrs=sorted(int(x) for x in tr.year.unique())
    vy=yrs[-1]
    fit=tr[tr.year<vy]; val=tr[tr.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=model(a).fit(fit[FEATURES],fit["net_migration_per_1000"])
        pred=m.predict(val[FEATURES])
        e=pred-val["net_migration_per_1000"].to_numpy(float)
        scores.append((float(np.sqrt(np.mean(e*e))),a))
    return min(scores,key=lambda x:(x[0],-x[1]))[1]

rows=[]
for b in base["years"]:
    y=int(b["year"])
    lu=p[(p.year.eq(y))&(p.kommun_kod.eq("2580"))]
    if len(lu)!=1: continue
    r={
      "year":y,
      "actual_change":float(b["actual_change"]),
      "baseline_pred_change":float(b["pred_change"]),
      "baseline_error":float(b["error_actual_minus_prediction"])
    }
    direct={}
    for w in [6,10]:
        tr=p[p.year.isin(range(y-w,y))].dropna(subset=FEATURES+["net_migration_per_1000"]).copy()
        if len(tr)!=290*w: continue
        a=choose_alpha(tr)
        m=model(a).fit(tr[FEATURES],tr["net_migration_per_1000"])
        rate=float(m.predict(lu[FEATURES])[0])
        netp=rate*float(b["population_prev"])/1000.0
        pred=float(b["births_pred"])-float(b["deaths_pred"])+netp+float(b["residual_pred"])
        direct[w]=(pred,a,rate)
        r[f"direct_{w}y_pred_change"]=pred
        r[f"direct_{w}y_error"]=float(b["actual_change"])-pred
        r[f"direct_{w}y_rate"]=rate
        r[f"direct_{w}y_alpha"]=a
    if 10 in direct:
        d10=direct[10][0]
        for wd in [0.25,0.5,0.75]:
            pred=(1-wd)*float(b["pred_change"])+wd*d10
            key=int(wd*100)
            r[f"blend_{key}pct_direct_pred_change"]=pred
            r[f"blend_{key}pct_direct_error"]=float(b["actual_change"])-pred
    rows.append(r)

df=pd.DataFrame(rows)
cands={
 "baseline":"baseline_error",
 "direct_6y":"direct_6y_error",
 "direct_10y":"direct_10y_error",
 "blend_25pct_direct":"blend_25pct_direct_error",
 "blend_50pct_direct":"blend_50pct_direct_error",
 "blend_75pct_direct":"blend_75pct_direct_error"
}
summary={}
for name,col in cands.items():
    if col not in df: continue
    x=pd.to_numeric(df[col],errors="coerce").dropna().to_numpy(float)
    summary[name]={
      "n":int(len(x)),
      "rmse":float(np.sqrt(np.mean(x*x))),
      "mae":float(np.mean(np.abs(x))),
      "bias":float(np.mean(x)),
      "max_abs":float(np.max(np.abs(x))),
      "median_abs":float(np.median(np.abs(x)))
    }

out={
 "status":"lulea_direct_net_full_balance_robustness",
 "production_changed":False,
 "summary":summary,
 "ranking_rmse":sorted([{"candidate":k,**v} for k,v in summary.items()],
                       key=lambda z:(z["rmse"],z["mae"],z["max_abs"])),
 "years":rows
}
(D/"lulea_direct_net_full_balance_robustness.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
