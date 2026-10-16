#!/usr/bin/env python3
"""Corrected research-only 3-year forecast selection with lookahead-only features excluded.

This repeats the registered nested 1-SE Lasso + PFER stability protocol after a
method-eligibility correction. No new variables or thresholds are introduced.
"""
import json, math, warnings
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Lasso, Ridge, LinearRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)
D=Path("docs/data")
read=lambda n:json.loads((D/n).read_text(encoding="utf-8"))
pool={r["feature"]:r for r in read("neutral_variable_pool_reboot.json")["records"]}
coverage=read("neutral_80_candidate_data_gate.json")["variables"]

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

LOOKAHEAD_ONLY={"lag1_valdeltagande_pct","lag1_valdeltagande_gap_pp"}
candidates=sorted(n for n in pool if n in q and all(coverage[n][str(y)]==290 for y in range(2021,2024)) and n not in LOOKAHEAD_ONLY)

ALPHAS=np.logspace(-3,1.5,22).tolist()
RIDGE_ALPHA=10.0
OUTER=5; INNER=3; CPSS_PAIRS=20; PFER=1.0; SEED=20261016; ZERO=1e-8

x=q[candidates].astype(float).reset_index(drop=True)
y=q.inflyttning_per_1000.to_numpy(float)
g=q.kommun_kod.to_numpy()

def rmse(y,p): return float(np.sqrt(np.mean((y-p)**2)))
def mae(y,p): return float(np.mean(np.abs(y-p)))
def fit_lasso(x,y,a):
    m=make_pipeline(StandardScaler(),Lasso(alpha=float(a),max_iter=30000,tol=1e-6))
    m.fit(x,y);return m
def active(m,names):
    return [n for n,v in zip(names,m.named_steps["lasso"].coef_) if abs(float(v))>ZERO]

def inner_curve(tx,ty,tg):
    rows=[]
    for a in ALPHAS:
        losses=[];counts=[]
        for tr,va in GroupKFold(INNER).split(tx,ty,tg):
            m=fit_lasso(tx.iloc[tr],ty[tr],a)
            losses.append(rmse(ty[va],m.predict(tx.iloc[va])))
            counts.append(len(active(m,candidates)))
        rows.append({"alpha":float(a),"mean_rmse":float(np.mean(losses)),
                     "se_rmse":float(np.std(losses,ddof=1)/np.sqrt(len(losses))),
                     "mean_active":float(np.mean(counts))})
    best=min(rows,key=lambda r:r["mean_rmse"]);limit=best["mean_rmse"]+best["se_rmse"]
    for r in rows:r["within_one_se"]=bool(r["mean_rmse"]<=limit)
    return rows,best,limit

def cpss(tx,ty,tg,a):
    rng=np.random.default_rng(SEED);ug=np.array(sorted(set(tg)))
    c=Counter();sizes=[];fits=0
    for _ in range(CPSS_PAIRS):
        perm=rng.permutation(ug);cut=len(perm)//2
        for half in (set(perm[:cut]),set(perm[cut:])):
            mask=np.array([v in half for v in tg])
            sel=active(fit_lasso(tx.loc[mask],ty[mask],a),candidates)
            c.update(sel);sizes.append(len(sel));fits+=1
    qsel=float(np.mean(sizes));p=len(candidates)
    req=.5*(1+qsel*qsel/(PFER*p))
    feasible=req<=1;thr=max(.5000001,req) if feasible else None
    freq={n:c[n]/fits for n in candidates}
    stable=sorted(n for n,v in freq.items() if thr is not None and v>=thr)
    return {"alpha":float(a),"mean_selected_q":qsel,"threshold":thr,"feasible":bool(feasible),
            "stable_features":stable,"stable_count":len(stable),
            "selection_frequency":dict(sorted(freq.items(),key=lambda kv:(-kv[1],kv[0])))}

folds=[];errs={"full_ridge":[],"one_se_lasso":[],"pfer_lasso":[],"pfer_ols":[]}
for fold,(tr,te) in enumerate(GroupKFold(OUTER).split(x,y,g),1):
    tx,vx=x.iloc[tr],x.iloc[te];ty,vy=y[tr],y[te];tg=g[tr]
    ridge=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(tx,ty)
    pr=ridge.predict(vx);errs["full_ridge"].extend((vy-pr).tolist())

    curve,best,limit=inner_curve(tx,ty,tg)
    one=min([r for r in curve if r["within_one_se"]],key=lambda r:(r["mean_active"],-r["alpha"],r["mean_rmse"]))
    lm=fit_lasso(tx,ty,one["alpha"]);pl=lm.predict(vx)
    errs["one_se_lasso"].extend((vy-pl).tolist())

    stab=[]
    for row in curve:
        s=cpss(tx.reset_index(drop=True),ty,tg,row["alpha"])
        s["inner_mean_rmse"]=row["mean_rmse"];s["within_one_se"]=row["within_one_se"]
        stab.append(s)
    feasible=[s for s in stab if s["feasible"] and s["stable_count"]>0]
    inside=[s for s in feasible if s["within_one_se"]]
    chosen=min(inside,key=lambda s:(s["stable_count"],s["inner_mean_rmse"],-s["alpha"])) if inside else (min(feasible,key=lambda s:(s["inner_mean_rmse"],s["stable_count"],s["alpha"])) if feasible else None)

    stable_result=None
    if chosen:
        ss=chosen["stable_features"]
        sl=fit_lasso(tx[ss],ty,chosen["alpha"]);ps=sl.predict(vx[ss]);errs["pfer_lasso"].extend((vy-ps).tolist())
        ols=make_pipeline(StandardScaler(),LinearRegression()).fit(tx[ss],ty);po=ols.predict(vx[ss]);errs["pfer_ols"].extend((vy-po).tolist())
        stable_result={"source":"within_1se" if inside and chosen in inside else "outside_1se",
                       "alpha":chosen["alpha"],"stable_features":ss,"stable_count":len(ss),
                       "threshold":chosen["threshold"],"inner_mean_rmse":chosen["inner_mean_rmse"],
                       "inner_excess_over_min":float(chosen["inner_mean_rmse"]-best["mean_rmse"]),
                       "lasso_rmse":rmse(vy,ps),"ols_rmse":rmse(vy,po)}
    folds.append({"fold":fold,"one_se_alpha":one["alpha"],"one_se_active_count":len(active(lm,candidates)),
                  "full_ridge_rmse":rmse(vy,pr),"one_se_lasso_rmse":rmse(vy,pl),
                  "stable":stable_result})

def agg(v):
    if len(v)!=len(y):return {"rmse":None,"mae":None,"all_outer_folds_available":False}
    a=np.asarray(v,float);return {"rmse":float(np.sqrt(np.mean(a*a))),"mae":float(np.mean(np.abs(a)))}

out={"status":"research_only_corrected_three_forecast_no_lookahead",
     "production_changed":False,
     "excluded_method_ineligible_features":sorted(LOOKAHEAD_ONLY),
     "candidate_count":len(candidates),
     "protocol":"same nested 1-SE Lasso plus PFER=1 CPSS; only pre-existing LOOKAHEAD_ONLY features removed",
     "summary":{k:agg(v) for k,v in errs.items()},
     "outer_folds":folds,
     "limitations":["Same 2021-2023 historical era remains previously inspected.","This correction addresses known feature lookahead, not exact source-vintage certification.","No new variables or thresholds were introduced."]}
(D/"neutral_three_forecast_no_lookahead_correction.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out["summary"],indent=2),flush=True)
