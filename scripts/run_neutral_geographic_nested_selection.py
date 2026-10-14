#!/usr/bin/env python3
"""Geographic nested CV for neutral variables; no 2024 selection and no production updates."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import ElasticNet
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error,mean_squared_error
D=Path("docs/data")
inv=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
gate=json.loads((D/"neutral_80_candidate_data_gate.json").read_text(encoding="utf-8"))
prior=json.loads((D/"fair_variable_inventory.json").read_text(encoding="utf-8"))
records={x["feature"]:x for x in inv["records"]}
previous={x["feature"]:x for x in prior["variables"]}
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag["kommun_kod"]=lag["kommun_kod"].str.zfill(4)
official=set(lag.loc[lag.target_year==2024,"kommun_kod"])
if len(official)!=290:raise RuntimeError("Invalid SCB municipality reference")
wide=lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index().rename(columns={
"target_year":"year","residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
"workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"})
p=p[p.kommun_kod.isin(official)&p.year.between(2019,2023)].merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one")
if len(p)!=1450:raise RuntimeError("Panel not 290 x five years")
TARGET="inflyttning_per_1000"
if TARGET not in p:raise RuntimeError("Outcome absent")
allnames=list(records)
for name in allnames+[TARGET]:
    if name not in p:raise RuntimeError(f"Missing candidate {name}")
    p[name]=pd.to_numeric(p[name],errors="coerce")
def eligible(years):
    return sorted(n for n in allnames if all(gate["variables"][n][str(y)]==290 for y in years))
# Hyperparameter grid fixed before CV; selection always within training folds.
grid=[(alpha,l1) for alpha in [0.03,0.3,3.0,30.0] for l1 in [0.3,0.8,1.0]]
def pipeline(alpha,l1):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
       ElasticNet(alpha=alpha,l1_ratio=l1,max_iter=9000,tol=1e-4,random_state=51))
def choose(X,y,groups):
    inner=GroupKFold(n_splits=3)
    assessments=[]
    for alpha,l1 in grid:
        errs=[]
        for tr,va in inner.split(X,y,groups):
            model=pipeline(alpha,l1)
            model.fit(X.iloc[tr],y[tr])
            pred=model.predict(X.iloc[va])
            errs.extend(((y[va]-pred)**2).tolist())
        assessments.append((float(np.sqrt(np.mean(errs))),alpha,l1))
    assessments.sort(key=lambda t:(t[0],-t[1],-t[2]))
    return assessments[0]
out={"status":"geographic_nested_cv_research_not_asof","target":TARGET,
 "window_years":{"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]},
 "notes":["Groups are municipality IDs; all records of a municipality held out together.",
 "Outer GroupKFold=5, inner GroupKFold=3; all tuning and feature selection within training.",
 "Incumbent and neutral arms share identical samples and model family, no incumbent advantage.",
 "No 2024 values used for tuning or evaluation.",
 "Retrospective associations only; SCB publication as-of not verified.",
 "Neutral candidate family may include close correlated representations; elastic net penalizes redundancies.",
 "Demographic-blind and demographics-allowed branches analyzed separately.",
 "Research exercise not a production challenger approval."],
 "hyperparameter_grid":{"alpha":[0.03,0.3,3.,30.],"l1_ratio":[0.3,0.8,1.]},
 "results":{},"production_changed":False}
for window,years in out["window_years"].items():
    q=p[p.year.isin(years)].copy().sort_values(["kommun_kod","year"])
    assert len(q)==290*len(years)
    pool=eligible(years)
    for branch in ["blind","forecast"]:
        allowed=set(n for n in pool if branch=="forecast" or records[n]["blind_model_eligible_subject_to_audit"])
        newfeatures=sorted(allowed)
        incumbents=sorted(n for n in allowed if previous.get(n,{}).get("incumbent",False))
        arms={"intercept":[],"incumbent_retrain":incumbents,"neutral_from_zero":newfeatures}
        groups=q.kommun_kod.to_numpy()
        y=q[TARGET].to_numpy()
        if not np.isfinite(y).all():raise RuntimeError("Missing outcome")
        allresults={}
        outer=GroupKFold(n_splits=5)
        for arm,features in arms.items():
            detail=[]; errors=[]; chosen=Counter()
            for fold,(tr,te) in enumerate(outer.split(q,y,groups),1):
                if not features:
                    pred=np.full(len(te),float(y[tr].mean()))
                    best=None
                else:
                    X=q[features]
                    if not np.isfinite(X.to_numpy(dtype=float)).all():
                        raise RuntimeError(f"Not fully covered: {window} {arm}")
                    best=choose(X.iloc[tr],y[tr],groups[tr])
                    model=pipeline(best[1],best[2])
                    model.fit(X.iloc[tr],y[tr])
                    pred=model.predict(X.iloc[te])
                    for f,c in zip(features,model[-1].coef_):
                        if abs(c)>1e-8:chosen[f]+=1
                e=y[te]-pred
                errors.extend(e.tolist())
                detail.append({"fold":fold,"municipalities":len(set(groups[te])),
                   "n_test":len(te),"rmse":float(np.sqrt(np.mean(e*e))),
                   "mae":float(np.mean(abs(e))),
                   "alpha":None if best is None else best[1],
                   "l1_ratio":None if best is None else best[2],
                   "nonzero_features":None if best is None else int(sum(abs(model[-1].coef_)>1e-8))})
            allresults[arm]={"n_candidates":len(features),"n_evaluated":len(errors),
                "rmse":float(np.sqrt(np.mean(np.square(errors)))),
                "mae":float(np.mean(np.abs(errors))),
                "folds":detail,"selection_frequency_outer_folds":dict(chosen.most_common())}
            print(window,branch,arm,round(allresults[arm]["rmse"],4),flush=True)
        out["results"][window+"_"+branch]={"years":years,"n_train_rows":len(q),
            "n_municipalities":290,"models":allresults}
(D/"neutral_geographic_nested_selection_results.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
