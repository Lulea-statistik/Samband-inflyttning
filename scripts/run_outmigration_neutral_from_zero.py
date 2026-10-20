#!/usr/bin/env python3
"""Neutral from-zero geographic nested CV for annual outmigration.

Purpose:
- start the outmigration model from zero;
- reuse the same neutral gross candidate pool as the inflow study;
- give no previously selected inflow variables any incumbent privilege;
- target utflyttning_per_1000;
- keep all tuning inside municipality-blocked CV.

Research only. No production changes.
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

# Same official 290-municipality reference used in the neutral inflow study.
lag=pd.read_csv(D/"employment_lag1_research_availability.csv",dtype={"kommun_kod":str})
lag["kommun_kod"]=lag["kommun_kod"].astype(str).str.zfill(4)
official=set(lag.loc[lag.target_year==2024,"kommun_kod"])
if len(official)!=290:
    raise RuntimeError("Invalid SCB municipality reference")

# Add the same two historical employment-growth candidates used by the inflow neutral study.
wide=(lag.pivot(index=["target_year","kommun_kod"],columns="dimension",values="growth_pct")
      .reset_index()
      .rename(columns={
        "target_year":"year",
        "residence":"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct",
        "workplace":"lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct"
      }))

p=(p[p.kommun_kod.isin(official)&p.year.between(2019,2023)]
   .merge(wide,on=["year","kommun_kod"],how="left",validate="one_to_one"))
if len(p)!=1450:
    raise RuntimeError(f"Panel not 290 x five years: {len(p)}")

TARGET="utflyttning_per_1000"
if TARGET not in p:
    raise RuntimeError("Outmigration outcome absent from panel")

allnames=list(records)
for name in allnames+[TARGET]:
    if name not in p:
        raise RuntimeError(f"Missing candidate/outcome {name}")
    p[name]=pd.to_numeric(p[name],errors="coerce")

# Avoid direct target leakage: target itself is not a candidate; lagged outmigration remains
# a legitimate prior-information candidate and receives no special privilege.
if TARGET in allnames:
    raise RuntimeError("Target unexpectedly present in candidate pool")

def eligible(years):
    return sorted(n for n in allnames
                  if all(gate["variables"][n][str(y)]==290 for y in years))

GRID=[(alpha,l1) for alpha in [0.03,0.3,3.0,30.0] for l1 in [0.3,0.8,1.0]]

def pipeline(alpha,l1):
    return make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        ElasticNet(alpha=alpha,l1_ratio=l1,max_iter=9000,tol=1e-4,random_state=51)
    )

def choose(X,y,groups):
    inner=GroupKFold(n_splits=3)
    assessments=[]
    for alpha,l1 in GRID:
        errs=[]
        counts=[]
        for tr,va in inner.split(X,y,groups):
            model=pipeline(alpha,l1)
            model.fit(X.iloc[tr],y[tr])
            pred=model.predict(X.iloc[va])
            errs.extend((y[va]-pred).tolist())
            counts.append(int(np.sum(np.abs(model[-1].coef_)>1e-8)))
        assessments.append({
            "rmse":float(np.sqrt(np.mean(np.square(errs)))),
            "mae":float(np.mean(np.abs(errs))),
            "alpha":alpha,
            "l1_ratio":l1,
            "mean_nonzero":float(np.mean(counts))
        })
    assessments.sort(key=lambda r:(r["rmse"],r["mean_nonzero"],-r["alpha"],-r["l1_ratio"]))
    return assessments[0],assessments

out={
 "status":"outmigration_neutral_from_zero_geographic_nested_cv",
 "target":TARGET,
 "production_changed":False,
 "inflow_model_changed":False,
 "outmigration_model_status":"research_only",
 "gross_pool_source":"neutral_variable_pool_reboot.json; same gross pool as inflow neutral study",
 "incumbent_privilege":False,
 "window_years":{"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]},
 "hyperparameter_grid":{"alpha":[0.03,0.3,3.0,30.0],"l1_ratio":[0.3,0.8,1.0]},
 "notes":[
   "Outmigration is selected independently from inflow.",
   "Previously selected inflow variables receive no incumbent status or preference.",
   "Groups are municipality IDs; all records for a municipality are held out together.",
   "Outer GroupKFold=5 and inner GroupKFold=3.",
   "No 2024 outcome is used for selection or evaluation.",
   "Lagged outmigration and lagged inflow are allowed only as ordinary prior-information candidates from the shared gross pool.",
   "Demographic-blind and demographics-allowed branches are reported separately.",
   "Historical coverage does not by itself certify source-vintage/as-of availability."
 ],
 "results":{}
}

for window,years in out["window_years"].items():
    q=p[p.year.isin(years)].copy().sort_values(["kommun_kod","year"]).reset_index(drop=True)
    if len(q)!=290*len(years):
        raise RuntimeError(f"Unbalanced {window} window")
    pool=eligible(years)
    groups=q.kommun_kod.to_numpy()
    y=q[TARGET].to_numpy(float)
    if not np.isfinite(y).all():
        raise RuntimeError("Missing outcome")

    for branch in ["blind","forecast"]:
        features=sorted(n for n in pool
                        if branch=="forecast" or records[n]["blind_model_eligible_subject_to_audit"])
        X=q[features]
        if not np.isfinite(X.to_numpy(dtype=float)).all():
            raise RuntimeError(f"Not fully covered: {window} {branch}")

        outer=GroupKFold(n_splits=5)
        errors=[]
        preds=[]
        actuals=[]
        selected=Counter()
        folds=[]
        for fold,(tr,te) in enumerate(outer.split(X,y,groups),1):
            best,_=choose(X.iloc[tr],y[tr],groups[tr])
            model=pipeline(best["alpha"],best["l1_ratio"])
            model.fit(X.iloc[tr],y[tr])
            pred=model.predict(X.iloc[te])
            e=y[te]-pred
            errors.extend(e.tolist())
            preds.extend(pred.tolist())
            actuals.extend(y[te].tolist())
            for f,c in zip(features,model[-1].coef_):
                if abs(float(c))>1e-8:
                    selected[f]+=1
            folds.append({
              "fold":fold,
              "municipalities":len(set(groups[te])),
              "n_test":len(te),
              "rmse":float(np.sqrt(np.mean(e*e))),
              "mae":float(np.mean(np.abs(e))),
              "alpha":best["alpha"],
              "l1_ratio":best["l1_ratio"],
              "nonzero_features":int(np.sum(np.abs(model[-1].coef_)>1e-8))
            })

        out["results"][f"{window}_{branch}"]={
          "years":years,
          "n_rows":len(q),
          "n_municipalities":290,
          "n_candidates":len(features),
          "rmse":float(np.sqrt(np.mean(np.square(errors)))),
          "mae":float(np.mean(np.abs(errors))),
          "bias_actual_minus_prediction":float(np.mean(errors)),
          "selection_frequency_outer_folds":dict(selected.most_common()),
          "folds":folds
        }

(D/"outmigration_neutral_from_zero_geographic_nested_cv.json").write_text(
    json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
