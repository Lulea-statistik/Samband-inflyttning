#!/usr/bin/env python3
"""Blend 3y and 10y lag1-only outmigration predictions.

Uses already-generated rolling-origin predictions for 2013-2024, so there is no
new fitting or leakage. Tests convex blends of the locked 3y core and 10y
sensitivity reference nationally and for Lulea.

Research only. No production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
p=pd.read_csv(D/"outmigration_long_history_rolling_origin_predictions.csv",
              dtype={"kommun_kod":str})
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
p=p[(p.model=="lag1_only") & p.window.isin([3,10]) & p.forecast_year.between(2013,2024)].copy()

wide=p.pivot(index=["forecast_year","kommun_kod","actual"],columns="window",values="prediction").reset_index()
wide.columns=["forecast_year","kommun_kod","actual","pred3","pred10"]
if len(wide)!=12*290 or wide[["pred3","pred10"]].isna().any().any():
    raise RuntimeError("Incomplete common panel")

BLENDS={
 "blend_25_75":0.25,
 "blend_50_50":0.50,
 "blend_75_25":0.75
}

def metrics(actual,pred):
    e=np.asarray(pred,float)-np.asarray(actual,float)
    return {"n":int(len(e)),
            "rmse":float(np.sqrt(np.mean(e*e))),
            "mae":float(np.mean(np.abs(e))),
            "bias_prediction_minus_actual":float(np.mean(e))}

def eval_scope(df):
    out={}
    out["3y"]=metrics(df.actual,df.pred3)
    out["10y"]=metrics(df.actual,df.pred10)
    for name,w3 in BLENDS.items():
        pred=w3*df.pred3+(1-w3)*df.pred10
        out[name]=metrics(df.actual,pred)
    # year wins
    yearly={}
    for fy,g in df.groupby("forecast_year"):
        vals={
          "3y":metrics(g.actual,g.pred3)["rmse"],
          "10y":metrics(g.actual,g.pred10)["rmse"]
        }
        for name,w3 in BLENDS.items():
            vals[name]=metrics(g.actual,w3*g.pred3+(1-w3)*g.pred10)["rmse"]
        yearly[int(fy)]=vals
    wins={k:0 for k in ["3y","10y"]+list(BLENDS)}
    for vals in yearly.values():
        best=min(vals,key=vals.get);wins[best]+=1
    for name,m in out.items():
        m["years_best"]=int(wins[name])
    out["yearly"]=yearly
    return out

national=eval_scope(wide)
lulea=eval_scope(wide[wide.kommun_kod=="2580"])

# Paired municipality bootstrap for each blend versus 3y and 10y.
rng=np.random.default_rng(20261020)
munis=np.array(sorted(wide.kommun_kod.unique()))
boot={name:{"vs3":[],"vs10":[]} for name in BLENDS}
for _ in range(5000):
    sample=rng.choice(munis,size=len(munis),replace=True)
    g=pd.concat([wide[wide.kommun_kod.eq(m)] for m in sample],ignore_index=True)
    r3=metrics(g.actual,g.pred3)["rmse"]
    r10=metrics(g.actual,g.pred10)["rmse"]
    for name,w3 in BLENDS.items():
        rb=metrics(g.actual,w3*g.pred3+(1-w3)*g.pred10)["rmse"]
        boot[name]["vs3"].append(100*(rb/r3-1))
        boot[name]["vs10"].append(100*(rb/r10-1))

bootsum={}
for name,d in boot.items():
    bootsum[name]={}
    for ref,arr in d.items():
        a=np.asarray(arr,float)
        bootsum[name][ref]={
          "median_delta_rmse_pct":float(np.median(a)),
          "p025":float(np.quantile(a,.025)),
          "p975":float(np.quantile(a,.975)),
          "probability_blend_better":float(np.mean(a<0))
        }

# Conservative ranking: national RMSE first, then Lulea RMSE.
cands=list(BLENDS)
ranking=sorted(cands,key=lambda n:(national[n]["rmse"],lulea[n]["rmse"]))
best=ranking[0]

res={
 "status":"outmigration_3y_10y_blend_test",
 "production_changed":False,
 "common_years":list(range(2013,2025)),
 "national":national,
 "lulea":lulea,
 "bootstrap":bootsum,
 "ranking":ranking,
 "best_blend":best,
 "decision_note":"A blend is only a challenger; it does not replace the locked 3y core without a separate gate."
}
(D/"outmigration_3y_10y_blend_test.json").write_text(
 json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
