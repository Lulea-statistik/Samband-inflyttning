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

# Dedicated SCB demographic candidate block. Every source feature is shifted one
# year before modeling, so no same-year birth/death information can leak.
scb_demo=pd.read_csv(D/"demographic_scb_candidate_features.csv",dtype={"kommun_kod":str})
scb_demo["kommun_kod"]=scb_demo["kommun_kod"].astype(str).str.zfill(4)
scb_demo=scb_demo.sort_values(["kommun_kod","year"])
RAW_DEMO_FEATURES=[c for c in scb_demo.columns if c not in ("kommun_kod","year")]
for name in RAW_DEMO_FEATURES:
    scb_demo[name]=pd.to_numeric(scb_demo[name],errors="coerce")
    scb_demo["lag1_"+name]=scb_demo.groupby("kommun_kod")[name].shift(1)
LAG_DEMO_FEATURES=["lag1_"+x for x in RAW_DEMO_FEATURES]
scb_demo=scb_demo[["kommun_kod","year"]+LAG_DEMO_FEATURES]

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
   .merge(scb_demo,on=["year","kommun_kod"],how="left",validate="one_to_one")
   .merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one"))

BASE_FEATURES=list(records)
TARGET_HISTORY=["lag1_fodelsetal_per_100","lag1_dodstal_per_1000"]
# A demographic source is eligible for a window if it has observed values for
# at least 200 of 290 municipalities in every target year. Missing eligible
# values are median-imputed inside each CV training fold.
DEMO_MIN_MUNICIPALITIES_PER_YEAR=200
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
 "extra_prior_history_candidates":TARGET_HISTORY,
 "demographic_candidate_source":"demographic_scb_candidate_features.csv",
 "demographic_raw_candidates":RAW_DEMO_FEATURES,
 "demographic_lagged_candidates":LAG_DEMO_FEATURES,
 "demographic_min_municipalities_per_year":DEMO_MIN_MUNICIPALITIES_PER_YEAR,
 "windows":{"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]},
 "results":{}
}

for target in out["targets"]:
  for w,years in out["windows"].items():
    q=p[p.year.isin(years)].copy().sort_values(["kommun_kod","year"]).reset_index(drop=True)
    if len(q)!=290*len(years):
        raise RuntimeError(f"Unbalanced panel {target} {w}: {len(q)}")
    demographic_coverage={}
    eligible_demo=[]
    for name in LAG_DEMO_FEATURES:
        counts={str(y):int(q.loc[q.year.eq(y),name].notna().sum()) for y in years}
        demographic_coverage[name]=counts
        if all(v>=DEMO_MIN_MUNICIPALITIES_PER_YEAR for v in counts.values()):
            eligible_demo.append(name)
    features=eligible_base(years)+TARGET_HISTORY+eligible_demo
    features=sorted(dict.fromkeys(features))
    for c in features+[target]:
        q[c]=pd.to_numeric(q[c],errors="coerce")
    if not np.isfinite(q[target]).all():
        raise RuntimeError(f"Missing target {target}")
    # Lagged target histories must be complete; auxiliary demographic features
    # may contain SCB suppression gaps and are imputed strictly inside CV folds.
    if q[TARGET_HISTORY].isna().any().any():
        raise RuntimeError(f"Missing demographic target lag history for {w}")
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
      "eligible_demographic_candidates":eligible_demo,
      "demographic_candidate_coverage_by_year":demographic_coverage,
      "selection_frequency_outer_folds":dict(selected.most_common()),
      "folds":folds
    }

(D/"demographic_birth_death_neutral_from_zero_nested_cv.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
