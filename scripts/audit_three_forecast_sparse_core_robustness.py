#!/usr/bin/env python3
"""Research-only robustness audit for the 3-year forecast sparse core.

Compares the previously discovered fixed 3- and 4-variable cores against full
Ridge across repeated municipality-group train/test splits. No new variables are
introduced and no production files are changed.

This is NOT an independent untouched validation because the candidate cores were
discovered using the same historical period. It is a sensitivity/robustness audit.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
read=lambda n:json.loads((D/n).read_text(encoding="utf-8"))
pool={r["feature"]:r for r in read("neutral_variable_pool_reboot.json")["records"]}
coverage=read("neutral_80_candidate_data_gate.json")["variables"]

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].str.zfill(4)
emp=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
emp["kommun_kod"]=emp["kommun_kod"].str.zfill(4)
codes=set(emp.loc[emp.target_year==2024,"kommun_kod"]); assert len(codes)==290
extra=(emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
       .reset_index()
       .rename(columns={"target_year":"year",
                        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
                        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"}))
p=(panel[panel.kommun_kod.isin(codes)&panel.year.between(2021,2023)]
   .merge(extra,on=["year","kommun_kod"],how="left",validate="one_to_one")
   .sort_values(["kommun_kod","year"]).reset_index(drop=True))

full_candidates=sorted(n for n in pool if n in p and all(coverage[n][str(y)]==290 for y in range(2021,2024)))
core3=[
    "lag1_inflyttning_per_1000",
    "lag1_utflyttning_per_1000",
    "lag1_valdeltagande_gap_pp",
]
core4=core3+["lag1_bostadsbestandsforandring_pct"]
for n in core4: assert n in full_candidates

RIDGE_ALPHAS=[0.01,0.1,1.0,3.0,10.0,30.0,100.0]
N_SPLITS=100
TEST_SIZE=0.20
SEED=20261016

x=p[full_candidates].astype(float)
y=p.inflyttning_per_1000.to_numpy(float)
g=p.kommun_kod.to_numpy()

def rmse(y,pred): return float(np.sqrt(np.mean((y-pred)**2)))
def mae(y,pred): return float(np.mean(np.abs(y-pred)))

def tune_ridge(tx,ty,tg,names):
    scores=[]
    for a in RIDGE_ALPHAS:
        losses=[]
        for tr,va in GroupKFold(3).split(tx,ty,tg):
            m=make_pipeline(StandardScaler(),Ridge(alpha=a)).fit(tx.iloc[tr][names],ty[tr])
            losses.append(rmse(ty[va],m.predict(tx.iloc[va][names])))
        scores.append((float(np.mean(losses)),a))
    return min(scores,key=lambda z:(z[0],z[1]))[1]

def fit_predict(tx,ty,tg,vx,names,kind):
    if kind=="ols":
        m=make_pipeline(StandardScaler(),LinearRegression()).fit(tx[names],ty)
        return m.predict(vx[names]),None
    a=tune_ridge(tx,ty,tg,names)
    m=make_pipeline(StandardScaler(),Ridge(alpha=a)).fit(tx[names],ty)
    return m.predict(vx[names]),a

records=[]
splitter=GroupShuffleSplit(n_splits=N_SPLITS,test_size=TEST_SIZE,random_state=SEED)
for i,(tr,te) in enumerate(splitter.split(x,y,g),1):
    tx,vx=x.iloc[tr],x.iloc[te];ty,vy=y[tr],y[te];tg=g[tr]

    # full Ridge benchmark retains the established alpha=10 benchmark
    full=make_pipeline(StandardScaler(),Ridge(alpha=10.0)).fit(tx,ty)
    pf=full.predict(vx)

    p3o,_=fit_predict(tx,ty,tg,vx,core3,"ols")
    p3r,a3=fit_predict(tx,ty,tg,vx,core3,"ridge")
    p4o,_=fit_predict(tx,ty,tg,vx,core4,"ols")
    p4r,a4=fit_predict(tx,ty,tg,vx,core4,"ridge")

    vals={
        "full_ridge":(pf,None),
        "core3_ols":(p3o,None),
        "core3_ridge":(p3r,a3),
        "core4_ols":(p4o,None),
        "core4_ridge":(p4r,a4),
    }
    row={"split":i,"n_test_rows":len(te),"n_test_municipalities":len(set(g[te]))}
    base=rmse(vy,pf)
    for name,(pred,a) in vals.items():
        r=rmse(vy,pred)
        row[name]={"rmse":r,"mae":mae(vy,pred),"ridge_alpha":a,
                   "delta_rmse_vs_full":float(r-base),
                   "relative_rmse_vs_full_pct":float(100*(r/base-1))}
    records.append(row)

def summarize(name):
    dr=np.array([r[name]["delta_rmse_vs_full"] for r in records],float)
    rel=np.array([r[name]["relative_rmse_vs_full_pct"] for r in records],float)
    rms=np.array([r[name]["rmse"] for r in records],float)
    return {
        "mean_rmse":float(rms.mean()),
        "median_rmse":float(np.median(rms)),
        "mean_delta_rmse_vs_full":float(dr.mean()),
        "median_delta_rmse_vs_full":float(np.median(dr)),
        "delta_rmse_p05":float(np.quantile(dr,.05)),
        "delta_rmse_p95":float(np.quantile(dr,.95)),
        "mean_relative_rmse_vs_full_pct":float(rel.mean()),
        "relative_rmse_p05_pct":float(np.quantile(rel,.05)),
        "relative_rmse_p95_pct":float(np.quantile(rel,.95)),
        "share_splits_better_than_full":float(np.mean(dr<0)),
        "share_splits_within_2pct_of_full":float(np.mean(rel<=2)),
        "share_splits_within_5pct_of_full":float(np.mean(rel<=5)),
    }

out={
    "status":"research_only_three_forecast_sparse_core_robustness",
    "production_changed":False,
    "period":[2021,2022,2023],
    "n_rows":len(p),
    "n_municipalities":len(set(g)),
    "full_candidate_count":len(full_candidates),
    "core3":core3,
    "core4":core4,
    "protocol":{
        "splitter":"GroupShuffleSplit by municipality",
        "n_splits":N_SPLITS,
        "test_size":TEST_SIZE,
        "random_state":SEED,
        "full_ridge_alpha":10.0,
        "sparse_ridge_alphas":RIDGE_ALPHAS,
        "sparse_ridge_tuning":"3-fold GroupKFold within each training split",
        "no_new_variables":True,
    },
    "summary":{
        "full_ridge":summarize("full_ridge"),
        "core3_ols":summarize("core3_ols"),
        "core3_ridge":summarize("core3_ridge"),
        "core4_ols":summarize("core4_ols"),
        "core4_ridge":summarize("core4_ridge"),
    },
    "splits":records,
    "limitations":[
        "The sparse cores were discovered on this same historical period; this is not a fresh independent holdout.",
        "Repeated group splits are overlapping and summary quantiles are sensitivity diagnostics, not classical confidence intervals.",
        "The 2% and 5% bands are descriptive reporting bands only; they are not pre-declared acceptance thresholds.",
        "No production model is changed automatically."
    ]
}
(D/"neutral_three_forecast_sparse_core_robustness.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out["summary"],indent=2),flush=True)
