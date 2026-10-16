#!/usr/bin/env python3
"""Research-only PFER-feasible Lasso stability path.

Motivation: the prior nested Elastic Net run selected l1_ratio=1.0 in all
20 outer folds, so this follow-up isolates the Lasso path and asks a narrower
question: how much predictive performance must be sacrificed before
PFER=1 stability selection becomes mathematically feasible?

No production files are changed.
"""
import json, math, warnings
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Lasso, Ridge
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
assert len(codes)==290
extra=(emp.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
       .reset_index()
       .rename(columns={"target_year":"year",
                        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
                        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"}))
p=(panel[panel.kommun_kod.isin(codes)&panel.year.between(2019,2023)]
   .merge(extra,on=["year","kommun_kod"],how="left",validate="one_to_one"))

ALPHAS=np.logspace(-3,1.5,22).tolist()
RIDGE_ALPHA=10.0
OUTER_SPLITS=5
INNER_SPLITS=3
CPSS_PAIRS=20
PFER_TARGET=1.0
SEED=20261016
ZERO_TOL=1e-8

def rmse(y,p):
    return float(np.sqrt(np.mean((y-p)**2)))

def mae(y,p):
    return float(np.mean(np.abs(y-p)))

def fit_lasso(x,y,alpha):
    m=make_pipeline(StandardScaler(),Lasso(alpha=float(alpha),max_iter=30000,tol=1e-6,selection="cyclic"))
    m.fit(x,y)
    return m

def active(m,names):
    coef=m.named_steps["lasso"].coef_
    return [n for n,v in zip(names,coef) if abs(float(v))>ZERO_TOL]

def inner_curve(x,y,g,names):
    rows=[]
    cv=GroupKFold(INNER_SPLITS)
    for alpha in ALPHAS:
        losses=[];counts=[]
        for tr,va in cv.split(x,y,g):
            m=fit_lasso(x.iloc[tr],y[tr],alpha)
            losses.append(rmse(y[va],m.predict(x.iloc[va])))
            counts.append(len(active(m,names)))
        rows.append({"alpha":float(alpha),
                     "mean_rmse":float(np.mean(losses)),
                     "se_rmse":float(np.std(losses,ddof=1)/np.sqrt(len(losses))),
                     "mean_active":float(np.mean(counts))})
    best=min(rows,key=lambda r:r["mean_rmse"])
    limit=best["mean_rmse"]+best["se_rmse"]
    for r in rows:r["within_one_se"]=bool(r["mean_rmse"]<=limit)
    return rows,best,limit

def cpss(x,y,g,names,alpha):
    rng=np.random.default_rng(SEED)
    unique=np.array(sorted(set(g)))
    counts=Counter();sizes=[];fits=0
    for _ in range(CPSS_PAIRS):
        perm=rng.permutation(unique);cut=len(perm)//2
        for half in (set(perm[:cut]),set(perm[cut:])):
            mask=np.array([v in half for v in g])
            m=fit_lasso(x.loc[mask],y[mask],alpha)
            sel=active(m,names)
            counts.update(sel);sizes.append(len(sel));fits+=1
    q=float(np.mean(sizes));pcount=len(names)
    raw=q*q/(PFER_TARGET*pcount) if pcount else math.inf
    required_pi=0.5*(1.0+raw)
    feasible=bool(required_pi<=1.0)
    threshold=max(0.5000001,required_pi) if feasible else None
    freq={n:counts[n]/fits for n in names}
    stable=sorted([n for n,v in freq.items() if threshold is not None and v>=threshold])
    return {"alpha":float(alpha),"mean_selected_q":q,"p":pcount,
            "required_selection_probability":threshold,
            "pfer_target_feasible":feasible,
            "stable_features":stable,"stable_feature_count":len(stable),
            "selection_frequency":dict(sorted(freq.items(),key=lambda kv:(-kv[1],kv[0])))}

def evaluate_case(q,candidates):
    x=q[candidates].astype(float).reset_index(drop=True)
    y=q.inflyttning_per_1000.to_numpy(float)
    g=q.kommun_kod.to_numpy()
    folds=[];err_ridge=[];err_one=[];err_stable=[]
    for fold,(tr,te) in enumerate(GroupKFold(OUTER_SPLITS).split(x,y,g),1):
        tx,vx=x.iloc[tr],x.iloc[te];ty,vy=y[tr],y[te];tg=g[tr]

        ridge=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(tx,ty)
        pr=ridge.predict(vx);err_ridge.extend((vy-pr).tolist())

        curve,best,limit=inner_curve(tx,ty,tg,candidates)
        one_candidates=[r for r in curve if r["within_one_se"]]
        one=min(one_candidates,key=lambda r:(r["mean_active"],-r["alpha"],r["mean_rmse"]))
        lm=fit_lasso(tx,ty,one["alpha"]);pl=lm.predict(vx)
        err_one.extend((vy-pl).tolist())

        # Evaluate stability down the path from least to strongest penalization.
        stability=[]
        for row in sorted(curve,key=lambda r:r["alpha"]):
            s=cpss(tx.reset_index(drop=True),ty,tg,candidates,row["alpha"])
            s["inner_mean_rmse"]=row["mean_rmse"]
            s["inner_se_rmse"]=row["se_rmse"]
            s["within_one_se"]=row["within_one_se"]
            stability.append(s)

        feasible=[s for s in stability if s["pfer_target_feasible"] and s["stable_feature_count"]>0]
        feasible_one=[s for s in feasible if s["within_one_se"]]
        best_feasible=min(feasible,key=lambda s:(s["inner_mean_rmse"],s["stable_feature_count"],s["alpha"])) if feasible else None
        best_feasible_one=min(feasible_one,key=lambda s:(s["stable_feature_count"],s["inner_mean_rmse"],-s["alpha"])) if feasible_one else None

        chosen=best_feasible_one or best_feasible
        stable_metrics=None
        if chosen:
            names=chosen["stable_features"]
            sm=fit_lasso(tx[names],ty,chosen["alpha"])
            ps=sm.predict(vx[names]);e=vy-ps;err_stable.extend(e.tolist())
            stable_metrics={"source":"within_1se" if best_feasible_one else "outside_1se",
                            "alpha":chosen["alpha"],"stable_feature_count":len(names),
                            "stable_features":names,"rmse":rmse(vy,ps),"mae":mae(vy,ps),
                            "inner_mean_rmse":chosen["inner_mean_rmse"],
                            "inner_excess_over_min":float(chosen["inner_mean_rmse"]-best["mean_rmse"]),
                            "required_selection_probability":chosen["required_selection_probability"]}

        folds.append({"fold":fold,
                      "ridge":{"rmse":rmse(vy,pr),"mae":mae(vy,pr)},
                      "one_se_lasso":{"alpha":one["alpha"],"active_count":len(active(lm,candidates)),
                                      "rmse":rmse(vy,pl),"mae":mae(vy,pl),
                                      "inner_min":best,"inner_1se_limit":limit},
                      "pfer_feasible_within_1se":bool(best_feasible_one),
                      "best_pfer_stable":stable_metrics,
                      "stability_path":[{k:v for k,v in s.items() if k!="selection_frequency"} for s in stability]})
    def agg(err):
        a=np.asarray(err,float);return {"rmse":float(np.sqrt(np.mean(a*a))),"mae":float(np.mean(np.abs(a)))}
    return {"candidate_count":len(candidates),"rows":len(q),
            "summary":{"ridge":agg(err_ridge),"one_se_lasso":agg(err_one),
                       "pfer_stable_lasso":agg(err_stable) if len(err_stable)==len(y) else
                       {"rmse":None,"mae":None,"all_outer_folds_available":False}},
            "outer_folds":folds}

out={"status":"research_only_pfer_feasible_lasso_stability_path",
     "production_changed":False,
     "motivation":"Prior nested Elastic Net selected l1_ratio=1.0 in all 20 outer folds.",
     "protocol":{"outer_cv":"GroupKFold(5) by municipality","inner_cv":"GroupKFold(3) by municipality",
                 "alphas":ALPHAS,"cpss_pairs":CPSS_PAIRS,"pfer_target":PFER_TARGET,
                 "selection_rule":"prefer non-empty PFER-feasible stable set within 1-SE; otherwise report best-RMSE non-empty PFER-feasible set outside 1-SE",
                 "candidate_universe_frozen":True},
     "results":{},
     "limitations":["Research-only on previously inspected historical years.",
                    "PFER feasibility is based on the conservative Meinshausen-Buehlmann bound.",
                    "If no PFER-feasible model lies within 1-SE, the outside-1-SE model is diagnostic only and quantifies the cost of strict stability control.",
                    "Selected coefficients are predictive, not causal."]}

for window,years in {"five":range(2019,2024),"three":range(2021,2024)}.items():
    q=p[p.year.isin(years)].sort_values(["kommun_kod","year"]).reset_index(drop=True)
    complete=[n for n in pool if n in q and all(coverage[n][str(t)]==290 for t in years)]
    for branch in ("blind","forecast"):
        candidates=sorted(n for n in complete if branch=="forecast" or pool[n]["blind_model_eligible_subject_to_audit"])
        key=f"{window}_{branch}"
        print(key,len(candidates),flush=True)
        out["results"][key]=evaluate_case(q,candidates)
        print(key,out["results"][key]["summary"],flush=True)

(D/"neutral_pfer_feasible_lasso_stability_path.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
