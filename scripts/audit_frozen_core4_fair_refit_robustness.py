#!/usr/bin/env python3
"""Fair refit robustness audit for the frozen 3-year forecast core.

No feature selection occurs. The four frozen predictors are fixed.
Compares:
- core4 OLS
- core4 Ridge with inner grouped CV alpha tuning
- full Ridge with the same inner grouped CV alpha tuning
over repeated municipality-group splits.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.model_selection import GroupKFold, GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
lock=json.loads((D/"three_year_forecast_frozen_candidate_set.json").read_text(encoding="utf-8"))
core=lock["features"]

panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
panel["kommun_kod"]=panel["kommun_kod"].str.zfill(4)

emp=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
emp["kommun_kod"]=emp["kommun_kod"].str.zfill(4)
codes=set(emp.loc[emp.target_year==2024,"kommun_kod"])
extra=(emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
       .reset_index()
       .rename(columns={"target_year":"year",
                        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
                        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"}))

q=(panel[panel.kommun_kod.isin(codes)&panel.year.between(2021,2023)]
   .merge(extra,on=["year","kommun_kod"],how="left",validate="one_to_one")
   .sort_values(["kommun_kod","year"]).reset_index(drop=True))

pool=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))["records"]
pool_names={r["feature"] for r in pool}
gate=json.loads((D/"neutral_80_candidate_data_gate.json").read_text(encoding="utf-8"))["variables"]
lookahead={"lag1_valdeltagande_pct","lag1_valdeltagande_gap_pp"}
full=sorted(n for n in pool_names if n in q and all(gate[n][str(y)]==290 for y in range(2021,2024)) and n not in lookahead)

target="inflyttning_per_1000"
ALPHAS=[0.01,0.1,1,3,10,30,100]
N_SPLITS=100
SEED=20261016

need=list(dict.fromkeys(full+core+[target,"kommun_kod"]))
work=q[need].dropna().reset_index(drop=True)
y=work[target].to_numpy(float)
groups=work["kommun_kod"].to_numpy()

def rmse(a,b): return float(np.sqrt(np.mean((np.asarray(a)-np.asarray(b))**2)))
def mae(a,b): return float(np.mean(np.abs(np.asarray(a)-np.asarray(b))))

def tune_ridge(X,y,g):
    cv=GroupKFold(3)
    rows=[]
    for a in ALPHAS:
        losses=[]
        for tr,va in cv.split(X,y,g):
            m=make_pipeline(StandardScaler(),Ridge(alpha=a)).fit(X.iloc[tr],y[tr])
            losses.append(rmse(y[va],m.predict(X.iloc[va])))
        rows.append((float(np.mean(losses)),float(a)))
    rows.sort(key=lambda z:(z[0],z[1]))
    return rows[0][1]

splitter=GroupShuffleSplit(n_splits=N_SPLITS,test_size=.20,random_state=SEED)
rows=[]
for i,(tr,te) in enumerate(splitter.split(work,y,groups),1):
    ty,vy=y[tr],y[te]; tg=groups[tr]
    xfull_tr=work.iloc[tr][full]; xfull_te=work.iloc[te][full]
    xcore_tr=work.iloc[tr][core]; xcore_te=work.iloc[te][core]

    af=tune_ridge(xfull_tr,ty,tg)
    mf=make_pipeline(StandardScaler(),Ridge(alpha=af)).fit(xfull_tr,ty)
    pf=mf.predict(xfull_te)

    ao=tune_ridge(xcore_tr,ty,tg)
    mr=make_pipeline(StandardScaler(),Ridge(alpha=ao)).fit(xcore_tr,ty)
    pr=mr.predict(xcore_te)

    mo=make_pipeline(StandardScaler(),LinearRegression()).fit(xcore_tr,ty)
    po=mo.predict(xcore_te)

    rf=rmse(vy,pf)
    for name,pred,alpha in [
        ("full_ridge_tuned",pf,af),
        ("core4_ridge_tuned",pr,ao),
        ("core4_ols",po,None)
    ]:
        r=rmse(vy,pred); m=mae(vy,pred)
        rows.append({
          "split":i,"model":name,"rmse":r,"mae":m,
          "alpha":alpha,
          "delta_rmse_vs_full":r-rf,
          "relative_rmse_vs_full_pct":100*(r-rf)/rf
        })

df=pd.DataFrame(rows)
summary={}
for name,g in df.groupby("model"):
    summary[name]={
      "mean_rmse":float(g.rmse.mean()),
      "median_rmse":float(g.rmse.median()),
      "mean_mae":float(g.mae.mean()),
      "mean_delta_rmse_vs_full":float(g.delta_rmse_vs_full.mean()),
      "median_delta_rmse_vs_full":float(g.delta_rmse_vs_full.median()),
      "delta_rmse_p05":float(g.delta_rmse_vs_full.quantile(.05)),
      "delta_rmse_p95":float(g.delta_rmse_vs_full.quantile(.95)),
      "mean_relative_rmse_vs_full_pct":float(g.relative_rmse_vs_full_pct.mean()),
      "relative_rmse_p05_pct":float(g.relative_rmse_vs_full_pct.quantile(.05)),
      "relative_rmse_p95_pct":float(g.relative_rmse_vs_full_pct.quantile(.95)),
      "share_splits_better_than_full":float((g.delta_rmse_vs_full<0).mean()),
      "share_splits_within_2pct_of_full":float((g.relative_rmse_vs_full_pct<=2).mean()),
      "share_splits_within_5pct_of_full":float((g.relative_rmse_vs_full_pct<=5).mean()),
      "alpha_counts":({str(k):int(v) for k,v in g.alpha.dropna().value_counts().sort_index().items()} if g.alpha.notna().any() else {})
    }

out={
 "status":"research_only_frozen_core4_fair_refit_robustness",
 "production_changed":False,
 "selection_phase_closed":True,
 "frozen_features":core,
 "full_candidate_count":len(full),
 "period":[2021,2022,2023],
 "n_rows":len(work),
 "n_municipalities":int(work.kommun_kod.nunique()),
 "splits":N_SPLITS,
 "splitter":"GroupShuffleSplit by municipality, 20% test",
 "ridge_alpha_grid":ALPHAS,
 "summary":summary,
 "limitations":[
   "Same 2021-2023 era has been inspected previously; this is robustness, not untouched temporal confirmation.",
   "Repeated group splits overlap and are not independent confidence intervals.",
   "No variable selection occurs in this audit."
 ]
}
(D/"three_year_forecast_frozen_core4_fair_refit_robustness.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
