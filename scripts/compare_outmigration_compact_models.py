#!/usr/bin/env python3
"""Compact neutral outmigration model-size study.

Start from lag1 outmigration only, then add recurrent candidates individually and
in a few pre-specified small combinations. All comparisons use identical
municipality-blocked nested CV. No inflow incumbent privilege and no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
TARGET="utflyttning_per_1000"

# Candidates retained because ablation did not improve when removing them,
# plus a few recurrent structural controls. Explicitly exclude variables whose
# removal improved both windows (lagged inflow, students, built/constructed land).
BASE="lag1_utflyttning_per_1000"
ADDS=[
 "lag1_brott_per_100000",
 "lag1_kolada_langtidsarbetslosa_pct",
 "lag1_log_folkmangd",
 "lag1_arbetsloshet",
 "lag1_bas_ovriga_andel_pct",
 "lag1_andel_20_34",
 "lag1_log_fritidshus_per_1000_inv",
 "lag1_fardigstallda_bostader_per_1000",
]
EXCLUDED_FROM_COMPACT=[
 "lag1_inflyttning_per_1000",
 "lag1_andel_studerande",
 "lag1_bebyggd_anlagd_andel_land_pct"
]
for c in [TARGET,BASE]+ADDS:
    if c not in p: raise RuntimeError(f"Missing {c}")
    p[c]=pd.to_numeric(p[c],errors="coerce")

windows={"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]}
ALPHAS=[0.0,0.1,1.0,10.0]

models={"lag1_only":[BASE]}
for c in ADDS:
    models["lag1_plus__"+c]=[BASE,c]
models.update({
 "lag1_plus_labor":[BASE,"lag1_kolada_langtidsarbetslosa_pct","lag1_arbetsloshet"],
 "lag1_plus_structure":[BASE,"lag1_log_folkmangd","lag1_log_fritidshus_per_1000_inv"],
 "lag1_plus_crime_labor":[BASE,"lag1_brott_per_100000","lag1_kolada_langtidsarbetslosa_pct"],
 "lag1_plus_top3":[BASE,"lag1_brott_per_100000","lag1_kolada_langtidsarbetslosa_pct","lag1_log_folkmangd"],
 "lag1_plus_top5":[BASE,"lag1_brott_per_100000","lag1_kolada_langtidsarbetslosa_pct",
                   "lag1_log_folkmangd","lag1_arbetsloshet","lag1_bas_ovriga_andel_pct"]
})

def pipe(alpha):
    if alpha==0.0:
        # tiny ridge approximates OLS while retaining common implementation
        alpha=1e-10
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=alpha))

def choose(X,y,groups):
    inner=GroupKFold(n_splits=3)
    out=[]
    for a in ALPHAS:
        e=[]
        for tr,va in inner.split(X,y,groups):
            m=pipe(a);m.fit(X.iloc[tr],y[tr]);pr=m.predict(X.iloc[va])
            e.extend((y[va]-pr).tolist())
        out.append((float(np.sqrt(np.mean(np.square(e)))),a))
    out.sort(key=lambda z:(z[0],-z[1]))
    return out[0]

def evaluate(q,features):
    z=q.dropna(subset=[TARGET]+features).copy()
    # Require complete 290 municipality balance for every year.
    years=sorted(z.year.unique())
    if len(z)!=290*len(years) or z.groupby("year").kommun_kod.nunique().min()!=290:
        return None
    X=z[features]; y=z[TARGET].to_numpy(float); groups=z.kommun_kod.to_numpy()
    outer=GroupKFold(n_splits=5)
    errs=[];folds=[]
    for fold,(tr,te) in enumerate(outer.split(X,y,groups),1):
        best=choose(X.iloc[tr],y[tr],groups[tr])
        m=pipe(best[1]);m.fit(X.iloc[tr],y[tr]);pr=m.predict(X.iloc[te])
        e=y[te]-pr;errs.extend(e.tolist())
        folds.append({"fold":fold,"rmse":float(np.sqrt(np.mean(e*e))),
                      "mae":float(np.mean(np.abs(e))),"alpha":best[1]})
    return {"n":len(z),"rmse":float(np.sqrt(np.mean(np.square(errs)))),
            "mae":float(np.mean(np.abs(errs))),
            "bias_actual_minus_prediction":float(np.mean(errs)),"folds":folds}

res={"status":"outmigration_compact_model_size_study","production_changed":False,
     "inflow_model_changed":False,"target":TARGET,
     "excluded_from_compact_due_to_ablation_improvement":EXCLUDED_FROM_COMPACT,
     "models":models,"windows":{}}

for wn,years in windows.items():
    q=p[p.year.isin(years)].copy()
    rr={}
    for name,features in models.items():
        m=evaluate(q,features)
        if m is not None:
            rr[name]={"features":features,**m}
    base=rr["lag1_only"]
    for name,m in rr.items():
        m["delta_rmse_pct_vs_lag1_only"]=100*(m["rmse"]/base["rmse"]-1)
        m["delta_mae_pct_vs_lag1_only"]=100*(m["mae"]/base["mae"]-1)
    ranked=sorted(rr,key=lambda n:(rr[n]["rmse"],len(rr[n]["features"]),n))
    res["windows"][wn]={"years":years,"results":rr,"ranking":ranked}

# Stability score: mean RMSE change vs lag1-only across windows, lower is better.
score=[]
for name in models:
    vals=[]
    for wn in windows:
        if name in res["windows"][wn]["results"]:
            vals.append(res["windows"][wn]["results"][name]["delta_rmse_pct_vs_lag1_only"])
    if len(vals)==2:
        score.append({"model":name,"n_features":len(models[name]),
                      "mean_delta_rmse_pct_vs_lag1_only":float(np.mean(vals)),
                      "worst_window_delta_rmse_pct_vs_lag1_only":float(np.max(vals)),
                      "features":models[name]})
score.sort(key=lambda x:(x["mean_delta_rmse_pct_vs_lag1_only"],
                         x["worst_window_delta_rmse_pct_vs_lag1_only"],x["n_features"]))
res["cross_window_ranking"]=score
(D/"outmigration_compact_model_size_study.json").write_text(
 json.dumps(res,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(res,ensure_ascii=False,indent=2))
