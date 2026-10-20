#!/usr/bin/env python3
"""Compare separate migration-component forecasts with a direct Lulea net-migration baseline.

Research diagnostic only; no production model changes.

Direct net-migration candidates use national rolling training and only lagged migration rates:
- lag1 net migration per 1000
- lag1 inflow + lag1 outflow per 1000
Windows: 3, 6, 10 years.
Evaluation: Lulea 2017-2024 on same years as the full component backtest.
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
p["lag1_net_migration_per_1000"]=p.groupby("kommun_kod")["net_migration_per_1000"].shift(1)

full=json.loads((D/"lulea_full_component_historical_backtest.json").read_text(encoding="utf-8"))
sep=pd.DataFrame(full["years"])
sep["separate_net_pred_per_1000"]=sep["inflow_rate_pred"]-sep["outflow_rate_pred"]

ALPHAS=[0.0,0.1,1.0,10.0]
SPECS={
 "lag1_net":["lag1_net_migration_per_1000"],
 "lag1_in_out":["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"]
}

def model(a):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
                         Ridge(alpha=1e-10 if a==0 else a))

def choose_alpha(tr,features):
    yrs=sorted(int(x) for x in tr.year.unique())
    vy=yrs[-1]
    fit=tr[tr.year<vy]; val=tr[tr.year.eq(vy)]
    scores=[]
    for a in ALPHAS:
        m=model(a).fit(fit[features],fit["net_migration_per_1000"])
        pred=m.predict(val[features])
        err=pred-val["net_migration_per_1000"].to_numpy(float)
        scores.append((float(np.sqrt(np.mean(err*err))),a))
    return min(scores,key=lambda x:(x[0],-x[1]))[1]

rows=[]
for y in sep.year.astype(int):
    lu=p[(p.year.eq(y))&(p.kommun_kod.eq("2580"))]
    if len(lu)!=1: continue
    actual=float(lu.net_migration_per_1000.iloc[0])
    base=sep[sep.year.eq(y)].iloc[0]
    rec={
      "year":int(y),
      "actual_net_per_1000":actual,
      "separate_net_pred_per_1000":float(base.separate_net_pred_per_1000),
      "separate_error_actual_minus_prediction":actual-float(base.separate_net_pred_per_1000)
    }
    for name,features in SPECS.items():
        for w in [3,6,10]:
            tr=p[p.year.isin(range(y-w,y))].dropna(subset=features+["net_migration_per_1000"]).copy()
            key=f"{name}_{w}y"
            if len(tr)!=290*w:
                rec[key]=None
                continue
            a=choose_alpha(tr,features)
            m=model(a).fit(tr[features],tr["net_migration_per_1000"])
            pred=float(m.predict(lu[features])[0])
            rec[key]=pred
            rec[key+"_alpha"]=a
            rec[key+"_error_actual_minus_prediction"]=actual-pred
    rows.append(rec)

df=pd.DataFrame(rows)
cands=["separate_net_pred_per_1000"]+[f"{s}_{w}y" for s in SPECS for w in [3,6,10]]
summary={}
for c in cands:
    err_col="separate_error_actual_minus_prediction" if c=="separate_net_pred_per_1000" else c+"_error_actual_minus_prediction"
    if err_col not in df: continue
    x=pd.to_numeric(df[err_col],errors="coerce").dropna().to_numpy(float)
    summary[c]={
      "n":int(len(x)),
      "rmse_per_1000":float(np.sqrt(np.mean(x*x))),
      "mae_per_1000":float(np.mean(np.abs(x))),
      "bias_actual_minus_prediction":float(np.mean(x))
    }

out={
 "status":"lulea_direct_net_migration_diagnostic",
 "production_changed":False,
 "purpose":"Compare current separate inflow/outflow forecasts with direct net-migration baselines.",
 "summary":summary,
 "ranking":sorted(
   [{"candidate":k,**v} for k,v in summary.items()],
   key=lambda z:(z["rmse_per_1000"],z["mae_per_1000"])
 ),
 "years":rows
}
(D/"lulea_direct_net_migration_diagnostic.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
