#!/usr/bin/env python3
"""Pre-specified sparse neutral challenger: nested municipality-group CV.

No use of 2024 outcome. This is a new exploratory analysis after prior CV inspection,
not an independent confirmation. Selection uses training only.
"""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

D=Path("docs/data")
inventory=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
gate=json.loads((D/"neutral_80_candidate_data_gate.json").read_text(encoding="utf-8"))
prior=json.loads((D/"fair_variable_inventory.json").read_text(encoding="utf-8"))
records={x["feature"]:x for x in inventory["records"]}
previous={x["feature"]:x for x in prior["variables"]}
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p.kommun_kod.str.zfill(4)
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag["kommun_kod"]=lag.kommun_kod.str.zfill(4)
official=set(lag.loc[lag.target_year==2024,"kommun_kod"])
assert len(official)==290
wide=lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct").reset_index().rename(columns={
 "target_year":"year",
 "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
 "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"})
p=p.loc[p.kommun_kod.isin(official)&p.year.between(2019,2023)].merge(
    wide,on=["year","kommun_kod"],how="left",validate="one_to_one")
assert len(p)==1450
# Fixed family-wide complexity budgets: no performance-based refitting of budget grid.
BUDGETS=(5,10,20)
RIDGE_ALPHA=10.0
TARGET="inflyttning_per_1000"
out={"status":"exploratory_nested_sparse_geographic_cv",
  "model":"top_k_absolute_training_pearson_then_standardized_ridge",
  "fixed_budgets":BUDGETS,"fixed_ridge_alpha":RIDGE_ALPHA,
  "cv":{"outer":"GroupKFold(5) municipalities","inner":"GroupKFold(3) municipalities"},
  "results":{},"production_changed":False,
  "caveats":["Model budget is selected inside inner training folds from predeclared 5/10/20 grid.",
  "Ranking computed only on inner and outer training parts; no feature is selected on heldout municipalities.",
  "Already inspected geographic splits and years 2019–2023: this is exploratory, not independent confirmation.",
  "Temporal as-of verification is not established; never interpret this as future forecast skill.",
  "Incumbent baseline uses identical sparse model and data, not production pipeline.",
  "Selection by univariate association may miss conditional/suppressor predictors."]}
def rank_features(frame,features,y):
    # Use training data only; constant variables score zero.
    v=frame[features].to_numpy(dtype=float)
    yy=y-y.mean()
    denom=np.sqrt(((v-v.mean(axis=0))**2).sum(axis=0) * (yy**2).sum())
    numer=((v-v.mean(axis=0))*yy[:,None]).sum(axis=0)
    score=np.divide(abs(numer),denom,out=np.zeros_like(numer),where=denom>0)
    return sorted(range(len(features)),key=lambda i:(-score[i],features[i]))
def train_predict(tr_x,tr_y,te_x,features,budget):
    indexes=rank_features(tr_x,features,tr_y)[:min(budget,len(features))]
    selected=[features[i] for i in indexes]
    m=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA))
    m.fit(tr_x[selected],tr_y)
    return m.predict(te_x[selected]),selected
def select_budget(train_x,train_y,train_groups,features):
    splits=list(GroupKFold(n_splits=3).split(train_x,train_y,train_groups))
    scores=[]
    for budget in BUDGETS:
        ss=0;n=0
        for a,b in splits:
            pred,_=train_predict(train_x.iloc[a],train_y[a],train_x.iloc[b],features,budget)
            ss+=float(np.square(train_y[b]-pred).sum());n+=len(b)
        scores.append((ss/n,budget))
    return min(scores)[1]
for key,years in {"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]}.items():
    q=p[p.year.isin(years)].sort_values(["kommun_kod","year"]).copy()
    y=q[TARGET].to_numpy(dtype=float);grp=q.kommun_kod.to_numpy()
    assert len(q)==290*len(years) and np.isfinite(y).all()
    eligible=sorted(name for name in records if all(gate["variables"][name][str(yr)]==290 for yr in years))
    for branch in ("blind","forecast"):
        pool=[f for f in eligible if branch=="forecast" or records[f]["blind_model_eligible_subject_to_audit"]]
        incumbent=[f for f in pool if previous.get(f,{}).get("incumbent")]
        section={"rows":len(q),"n_candidates":len(pool),"models":{}}
        for arm,features in (("incumbent_sparse",incumbent),("neutral_sparse",pool)):
            x=q[features].astype(float)
            assert np.isfinite(x.to_numpy()).all()
            errors=[]; folds=[]; freq=Counter()
            for i,(train,test) in enumerate(GroupKFold(n_splits=5).split(x,y,grp),1):
                budget=select_budget(x.iloc[train],y[train],grp[train],features)
                pred,selected=train_predict(x.iloc[train],y[train],x.iloc[test],features,budget)
                err=y[test]-pred
                errors.extend(err.tolist());freq.update(selected)
                folds.append({"fold":i,"budget":budget,"n_selected":len(selected),
                 "rmse":float(np.sqrt(np.mean(err**2))),"mae":float(np.mean(abs(err)))})
            section["models"][arm]={"candidates":len(features),"rmse":float(np.sqrt(np.mean(np.square(errors)))),
              "mae":float(np.mean(np.abs(errors))),"folds":folds,
              "selected_5fold_count":sum(v==5 for v in freq.values()),
              "selected_frequency":dict(freq.most_common())}
            print(key,branch,arm,section["models"][arm]["rmse"],flush=True)
        out["results"][key+"_"+branch]=section
(D/"neutral_sparse_geographic_cv_results.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
