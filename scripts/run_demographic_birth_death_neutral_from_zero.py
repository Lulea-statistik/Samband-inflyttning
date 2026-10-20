#!/usr/bin/env python3
"""Neutral from-zero nested CV for annual birth and death rates.

Uses the same gross neutral candidate pool as the migration work.
Adds only prior demographic history as ordinary candidates:
- lag1_fodelsetal_per_100
- lag1_dodstal_per_1000

Targets are modeled independently.
No migration-model feature is privileged.
"""
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

D=Path("docs/data")
inv=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
gate=json.loads((D/"neutral_80_candidate_data_gate.json").read_text(encoding="utf-8"))
records={x["feature"]:x for x in inv["records"]}

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
dem=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
dem["kommun_kod"]=dem["kommun_kod"].astype(str).str.zfill(4)
dem=dem.sort_values(["kommun_kod","year"])
dem["lag1_fodelsetal_per_100"]=dem.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
dem["lag1_dodstal_per_1000"]=dem.groupby("kommun_kod")["dodstal_per_1000"].shift(1)

lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag["kommun_kod"]=lag["kommun_kod"].astype(str).str.zfill(4)
official=set(lag.loc[lag.target_year==2024,"kommun_kod"])
if len(official)!=290: raise RuntimeError("Invalid municipality reference")

wide=(lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
      .reset_index().rename(columns={
        "target_year":"year",
        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"
      }))

p=(p[p.kommun_kod.isin(official)]
   .merge(dem,on=["year","kommun_kod"],how="inner",validate="one_to_one")
   .merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one"))

BASE_FEATURES=list(records)
EXTRA=["lag1_fodelsetal_per_100","lag1_dodstal_per_1000"]
GRID=[(a,l1) for a in [0.03,0.3,3.0,30.0] for l1 in [0.3,0.8,1.0]]

def pipeline(alpha,l1):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
                         ElasticNet(alpha=alpha,l1_ratio=l1,max_iter=9000,tol=1e-4,random_state=73))

def choose(X,y,groups):
    inner=GroupKFold(n_splits=3); rows=[]
    for alpha,l1 in GRID:
        errs=[]; nz=[]
        for tr,va in inner.split(X,y,groups):
            m=pipeline(alpha,l1);m.fit(X.iloc[tr],y[tr]);pred=m.predict(X.iloc[va])
            errs.extend((y[va]-pred).tolist());nz.append(int(np.sum(np.abs(m[-1].coef_)>1e-8)))
        rows.append((float(np.sqrt(np.mean(np.square(errs)))),float(np.mean(nz)),alpha,l1))
    rows.sort(key=lambda x:(x[0],x[1],-x[2],-x[3]))
    return rows[0]

def eligible_base(years):
    return sorted(n for n in BASE_FEATURES if all(gate["variables"][n].get(str(y))==290 for y in years))

out={
 "status":"demographic_birth_death_neutral_from_zero_nested_cv",
 "production_changed":False,
 "gross_pool_source":"neutral_variable_pool_reboot.json",
 "incumbent_privilege":False,
 "targets":["fodelsetal_per_100","dodstal_per_1000"],
 "extra_prior_history_candidates":EXTRA,
 "windows":{"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]},
 "results":{}
}

for target in out["targets"]:
  for w,years in out["windows"].items():
    q=p[p.year.isin(years)].copy().sort_values(["kommun_kod","year"]).reset_index(drop=True)
    if len(q)!=290*len(years):
        raise RuntimeError(f"Unbalanced panel {target} {w}: {len(q)}")
    features=eligible_base(years)+EXTRA
    features=sorted(dict.fromkeys(features))
    for c in features+[target]:
        q[c]=pd.to_numeric(q[c],errors="coerce")
    if not np.isfinite(q[target]).all():
        raise RuntimeError(f"Missing target {target}")
    # extra history candidates must be complete on these windows.
    if q[EXTRA].isna().any().any():
        raise RuntimeError(f"Missing demographic lag history for {w}")
    X=q[features]; y=q[target].to_numpy(float); groups=q.kommun_kod.to_numpy()
    outer=GroupKFold(n_splits=5)
    errs=[];selected=Counter();folds=[]
    for fold,(tr,te) in enumerate(outer.split(X,y,groups),1):
        _,_,alpha,l1=choose(X.iloc[tr],y[tr],groups[tr])
        m=pipeline(alpha,l1);m.fit(X.iloc[tr],y[tr]);pred=m.predict(X.iloc[te]);e=y[te]-pred
        errs.extend(e.tolist())
        for f,c in zip(features,m[-1].coef_):
            if abs(float(c))>1e-8:selected[f]+=1
        folds.append({"fold":fold,"rmse":float(np.sqrt(np.mean(e*e))),
                      "mae":float(np.mean(np.abs(e))),"alpha":alpha,"l1_ratio":l1,
                      "nonzero_features":int(np.sum(np.abs(m[-1].coef_)>1e-8))})
    out["results"][f"{target}_{w}"]={
      "years":years,"n_rows":len(q),"n_municipalities":290,"n_candidates":len(features),
      "rmse":float(np.sqrt(np.mean(np.square(errs)))),
      "mae":float(np.mean(np.abs(errs))),
      "bias_actual_minus_prediction":float(np.mean(errs)),
      "selection_frequency_outer_folds":dict(selected.most_common()),
      "folds":folds
    }

(D/"demographic_birth_death_neutral_from_zero_nested_cv.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
