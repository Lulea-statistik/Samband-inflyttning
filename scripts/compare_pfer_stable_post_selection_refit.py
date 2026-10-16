#!/usr/bin/env python3
"""Research-only post-selection refit of PFER-stable Lasso sets.

Purpose: test whether the predictive loss of the very sparse PFER-stable sets
comes from omitted predictors or from Lasso shrinkage. Stable sets are selected
strictly inside each outer training fold using the existing frozen protocol,
then refit with OLS and inner-CV-tuned Ridge. Production is unchanged.
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
codes=set(emp.loc[emp.target_year==2024,"kommun_kod"]); assert len(codes)==290
extra=(emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
       .reset_index()
       .rename(columns={"target_year":"year",
                        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
                        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"}))
p=(panel[panel.kommun_kod.isin(codes)&panel.year.between(2019,2023)]
   .merge(extra,on=["year","kommun_kod"],how="left",validate="one_to_one"))

ALPHAS=np.logspace(-3,1.5,22).tolist()
RIDGE_ALPHAS=[0.01,0.1,1.0,3.0,10.0,30.0,100.0]
OUTER=5; INNER=3; CPSS_PAIRS=20; PFER=1.0; SEED=20261016; ZERO=1e-8

def rmse(y,p): return float(np.sqrt(np.mean((y-p)**2)))
def mae(y,p): return float(np.mean(np.abs(y-p)))

def fit_lasso(x,y,a):
    m=make_pipeline(StandardScaler(),Lasso(alpha=float(a),max_iter=30000,tol=1e-6))
    m.fit(x,y); return m

def active(m,names):
    return [n for n,v in zip(names,m.named_steps["lasso"].coef_) if abs(float(v))>ZERO]

def inner_curve(x,y,g,names):
    rows=[]
    for a in ALPHAS:
        losses=[]; counts=[]
        for tr,va in GroupKFold(INNER).split(x,y,g):
            m=fit_lasso(x.iloc[tr],y[tr],a)
            losses.append(rmse(y[va],m.predict(x.iloc[va])))
            counts.append(len(active(m,names)))
        rows.append({"alpha":float(a),"mean_rmse":float(np.mean(losses)),
                     "se_rmse":float(np.std(losses,ddof=1)/np.sqrt(len(losses))),
                     "mean_active":float(np.mean(counts))})
    best=min(rows,key=lambda r:r["mean_rmse"])
    limit=best["mean_rmse"]+best["se_rmse"]
    for r in rows:r["within_one_se"]=r["mean_rmse"]<=limit
    return rows,best,limit

def cpss(x,y,g,names,a):
    rng=np.random.default_rng(SEED); ug=np.array(sorted(set(g)))
    c=Counter(); sizes=[]; fits=0
    for _ in range(CPSS_PAIRS):
        perm=rng.permutation(ug); cut=len(perm)//2
        for half in (set(perm[:cut]),set(perm[cut:])):
            mask=np.array([v in half for v in g])
            sel=active(fit_lasso(x.loc[mask],y[mask],a),names)
            c.update(sel); sizes.append(len(sel)); fits+=1
    q=float(np.mean(sizes)); pp=len(names)
    req=.5*(1+q*q/(PFER*pp))
    feasible=req<=1
    thr=max(.5000001,req) if feasible else None
    freq={n:c[n]/fits for n in names}
    stable=sorted(n for n,v in freq.items() if thr is not None and v>=thr)
    return {"alpha":float(a),"q":q,"threshold":thr,"feasible":bool(feasible),
            "stable":stable,"stable_count":len(stable)}

def choose_stable_set(tx,ty,tg,names):
    curve,best,limit=inner_curve(tx,ty,tg,names)
    candidates=[]
    for row in curve:
        s=cpss(tx.reset_index(drop=True),ty,tg,names,row["alpha"])
        s["inner_mean_rmse"]=row["mean_rmse"]; s["within_one_se"]=row["within_one_se"]
        if s["feasible"] and s["stable_count"]>0:candidates.append(s)
    inside=[s for s in candidates if s["within_one_se"]]
    if inside:
        chosen=min(inside,key=lambda s:(s["stable_count"],s["inner_mean_rmse"],-s["alpha"]))
        source="within_1se"
    elif candidates:
        chosen=min(candidates,key=lambda s:(s["inner_mean_rmse"],s["stable_count"],s["alpha"]))
        source="outside_1se"
    else:
        return None,best,limit
    chosen=dict(chosen); chosen["source"]=source
    chosen["inner_excess_over_min"]=float(chosen["inner_mean_rmse"]-best["mean_rmse"])
    return chosen,best,limit

def tune_ridge(x,y,g):
    scores=[]
    for a in RIDGE_ALPHAS:
        losses=[]
        for tr,va in GroupKFold(INNER).split(x,y,g):
            m=make_pipeline(StandardScaler(),Ridge(alpha=a)).fit(x.iloc[tr],y[tr])
            losses.append(rmse(y[va],m.predict(x.iloc[va])))
        scores.append((float(np.mean(losses)),a))
    return min(scores)[1]

def evaluate(q,names):
    x=q[names].astype(float).reset_index(drop=True); y=q.inflyttning_per_1000.to_numpy(float); g=q.kommun_kod.to_numpy()
    errs={k:[] for k in ("full_ridge","stable_lasso","stable_ols","stable_ridge")}
    folds=[]
    for fold,(tr,te) in enumerate(GroupKFold(OUTER).split(x,y,g),1):
        tx,vx=x.iloc[tr],x.iloc[te]; ty,vy=y[tr],y[te]; tg=g[tr]
        full=make_pipeline(StandardScaler(),Ridge(alpha=10.0)).fit(tx,ty)
        pf=full.predict(vx); errs["full_ridge"].extend((vy-pf).tolist())

        sel,best,limit=choose_stable_set(tx,ty,tg,names)
        if sel is None:
            folds.append({"fold":fold,"stable_set":None}); continue
        ss=sel["stable"]

        lm=fit_lasso(tx[ss],ty,sel["alpha"]); pl=lm.predict(vx[ss]); errs["stable_lasso"].extend((vy-pl).tolist())
        ols=make_pipeline(StandardScaler(),LinearRegression()).fit(tx[ss],ty); po=ols.predict(vx[ss]); errs["stable_ols"].extend((vy-po).tolist())
        ra=tune_ridge(tx[ss].reset_index(drop=True),ty,tg)
        rr=make_pipeline(StandardScaler(),Ridge(alpha=ra)).fit(tx[ss],ty); pr=rr.predict(vx[ss]); errs["stable_ridge"].extend((vy-pr).tolist())

        folds.append({"fold":fold,"source":sel["source"],"stable_features":ss,"stable_count":len(ss),
                      "selection_alpha":sel["alpha"],"threshold":sel["threshold"],
                      "inner_excess_over_min":sel["inner_excess_over_min"],
                      "ridge_refit_alpha":ra,
                      "rmse":{"full_ridge":rmse(vy,pf),"stable_lasso":rmse(vy,pl),
                              "stable_ols":rmse(vy,po),"stable_ridge":rmse(vy,pr)}})
    summary={}
    for k,e in errs.items():
        if len(e)==len(y):
            a=np.asarray(e,float); summary[k]={"rmse":float(np.sqrt(np.mean(a*a))),"mae":float(np.mean(np.abs(a)))}
        else:
            summary[k]={"rmse":None,"mae":None,"all_outer_folds_available":False}
    return {"candidate_count":len(names),"summary":summary,"outer_folds":folds}

out={"status":"research_only_post_selection_refit","production_changed":False,
     "purpose":"Distinguish Lasso shrinkage loss from omitted-variable loss after PFER-stable selection.",
     "ridge_refit_alphas":RIDGE_ALPHAS,"results":{},
     "limitations":["Research-only; historical years have been repeatedly inspected.",
                    "Stable sets are selected within each outer training fold.",
                    "OLS/Ridge refit improves prediction only if shrinkage bias, not omitted predictors, drives the sparse-model loss.",
                    "No production decision is made automatically."]}

for window,years in {"five":range(2019,2024),"three":range(2021,2024)}.items():
    q=p[p.year.isin(years)].sort_values(["kommun_kod","year"]).reset_index(drop=True)
    complete=[n for n in pool if n in q and all(coverage[n][str(t)]==290 for t in years)]
    for branch in ("blind","forecast"):
        names=sorted(n for n in complete if branch=="forecast" or pool[n]["blind_model_eligible_subject_to_audit"])
        key=f"{window}_{branch}"; print(key,flush=True)
        out["results"][key]=evaluate(q,names)
        print(key,out["results"][key]["summary"],flush=True)

(D/"neutral_pfer_stable_post_selection_refit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
