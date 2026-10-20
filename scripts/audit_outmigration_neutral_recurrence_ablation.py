#!/usr/bin/env python3
"""Neutral outmigration recurrence and ablation audit.

Starting point: completed from-zero outmigration nested CV.
This script does not select a final model. It identifies recurrent variables in the
forecast branch and tests whether their removal materially changes municipality-
blocked nested-CV performance in both 3- and 5-year windows.

No inflow incumbent privilege. No production changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

D=Path("docs/data")
prior=json.loads((D/"outmigration_neutral_from_zero_geographic_nested_cv.json").read_text(encoding="utf-8"))
inv=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
gate=json.loads((D/"neutral_80_candidate_data_gate.json").read_text(encoding="utf-8"))
records={x["feature"]:x for x in inv["records"]}

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag["kommun_kod"]=lag["kommun_kod"].astype(str).str.zfill(4)
official=set(lag.loc[lag.target_year==2024,"kommun_kod"])
if len(official)!=290: raise RuntimeError("Invalid municipality reference")
wide=(lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
      .reset_index().rename(columns={
        "target_year":"year",
        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"}))
p=(p[p.kommun_kod.isin(official)&p.year.between(2019,2023)]
   .merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one"))
TARGET="utflyttning_per_1000"
allnames=list(records)
for name in allnames+[TARGET]:
    if name not in p: raise RuntimeError(f"Missing {name}")
    p[name]=pd.to_numeric(p[name],errors="coerce")

windows={"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]}
GRID=[(a,l) for a in [0.03,0.3,3.0,30.0] for l in [0.3,0.8,1.0]]

def eligible(years):
    return sorted(n for n in allnames if all(gate["variables"][n][str(y)]==290 for y in years))

def pipe(alpha,l1):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
        ElasticNet(alpha=alpha,l1_ratio=l1,max_iter=9000,tol=1e-4,random_state=51))

def choose(X,y,groups):
    inn=GroupKFold(n_splits=3)
    scores=[]
    for a,l in GRID:
        e=[]; nz=[]
        for tr,va in inn.split(X,y,groups):
            m=pipe(a,l); m.fit(X.iloc[tr],y[tr]); pr=m.predict(X.iloc[va])
            e.extend((y[va]-pr).tolist())
            nz.append(int(np.sum(np.abs(m[-1].coef_)>1e-8)))
        scores.append((float(np.sqrt(np.mean(np.square(e)))),float(np.mean(nz)),a,l))
    scores.sort(key=lambda z:(z[0],z[1],-z[2],-z[3]))
    return scores[0]

def evaluate(q,features):
    X=q[features]; y=q[TARGET].to_numpy(float); groups=q.kommun_kod.to_numpy()
    outer=GroupKFold(n_splits=5); errors=[]; fold_rows=[]
    for fold,(tr,te) in enumerate(outer.split(X,y,groups),1):
        best=choose(X.iloc[tr],y[tr],groups[tr])
        m=pipe(best[2],best[3]); m.fit(X.iloc[tr],y[tr]); pr=m.predict(X.iloc[te])
        e=y[te]-pr; errors.extend(e.tolist())
        fold_rows.append({"fold":fold,"rmse":float(np.sqrt(np.mean(e*e))),
                          "mae":float(np.mean(np.abs(e))),"alpha":best[2],
                          "l1_ratio":best[3],
                          "nonzero":int(np.sum(np.abs(m[-1].coef_)>1e-8))})
    return {"rmse":float(np.sqrt(np.mean(np.square(errors)))),
            "mae":float(np.mean(np.abs(errors))),
            "bias_actual_minus_prediction":float(np.mean(errors)),
            "folds":fold_rows}

# Recurrence: >=3 of 5 outer folds in either forecast window.
freq={}
for key in ["five_forecast","three_forecast"]:
    for feat,n in prior["results"][key]["selection_frequency_outer_folds"].items():
        freq.setdefault(feat,{})[key]=int(n)
recurrent=sorted(f for f,d in freq.items() if max(d.values())>=3)

out={"status":"outmigration_neutral_recurrence_ablation",
     "production_changed":False,"inflow_model_changed":False,
     "target":TARGET,"recurrent_rule":"selected in >=3/5 outer folds in either forecast window",
     "recurrent_features":[{"feature":f,"theme":records[f]["theme"],
                            "five_folds":freq.get(f,{}).get("five_forecast",0),
                            "three_folds":freq.get(f,{}).get("three_forecast",0)}
                           for f in recurrent],
     "windows":{}}

for name,years in windows.items():
    q=p[p.year.isin(years)].copy().sort_values(["kommun_kod","year"]).reset_index(drop=True)
    feats=eligible(years)
    if len(q)!=290*len(years): raise RuntimeError("Unbalanced panel")
    full=evaluate(q,feats)
    tests={"full_pool":full}
    for feat in recurrent:
        if feat not in feats: continue
        r=evaluate(q,[f for f in feats if f!=feat])
        r["delta_rmse_pct_vs_full"]=100*(r["rmse"]/full["rmse"]-1)
        r["delta_mae_pct_vs_full"]=100*(r["mae"]/full["mae"]-1)
        tests["drop__"+feat]=r
    pair=[f for f in ["lag1_inflyttning_per_1000","lag1_utflyttning_per_1000"] if f in feats]
    if len(pair)==2:
        r=evaluate(q,[f for f in feats if f not in pair])
        r["delta_rmse_pct_vs_full"]=100*(r["rmse"]/full["rmse"]-1)
        r["delta_mae_pct_vs_full"]=100*(r["mae"]/full["mae"]-1)
        tests["drop__migration_history_pair"]=r
    out["windows"][name]={"years":years,"n_candidates_full":len(feats),"tests":tests}

# Rank recurrent features by harm from removal, averaged across available windows.
rank=[]
for feat in recurrent:
    vals=[]
    for name in windows:
        x=out["windows"][name]["tests"].get("drop__"+feat)
        if x: vals.append(x["delta_rmse_pct_vs_full"])
    if vals:
        rank.append({"feature":feat,"theme":records[feat]["theme"],
                     "mean_delta_rmse_pct_when_removed":float(np.mean(vals)),
                     "min_delta_rmse_pct_when_removed":float(np.min(vals)),
                     "max_delta_rmse_pct_when_removed":float(np.max(vals))})
rank.sort(key=lambda r:r["mean_delta_rmse_pct_when_removed"],reverse=True)
out["ablation_rank"]=rank
(D/"outmigration_neutral_recurrence_ablation.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
