#!/usr/bin/env python3
"""Fair common-sample compact outmigration comparison + 2024 holdout.

Corrects the prior compact study where some labor variables had only 2021-2023
coverage and therefore were not directly comparable with 2019-2023 models.

Primary comparison:
- exact same 290 municipalities and years per arm;
- full-coverage candidates only for 2019-2023;
- municipality-blocked nested CV;
- independent 2024 holdout using model/hyperparameter selection from pre-2024 data.

Research only; no production change.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

D=Path("docs/data")
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
TARGET="utflyttning_per_1000"
BASE="lag1_utflyttning_per_1000"

MODELS={
 "lag1_only":[BASE],
 "lag1_plus_age20_34":[BASE,"lag1_andel_20_34"],
 "lag1_plus_log_fritidshus":[BASE,"lag1_log_fritidshus_per_1000_inv"],
 "lag1_plus_structure":[BASE,"lag1_log_folkmangd","lag1_log_fritidshus_per_1000_inv"],
 "lag1_plus_brott":[BASE,"lag1_brott_per_100000"],
 "lag1_plus_fardigstallda_bostader":[BASE,"lag1_fardigstallda_bostader_per_1000"],
 "lag1_plus_age_fritid":[BASE,"lag1_andel_20_34","lag1_log_fritidshus_per_1000_inv"],
 "lag1_plus_age_structure":[BASE,"lag1_andel_20_34","lag1_log_folkmangd","lag1_log_fritidshus_per_1000_inv"]
}
for c in sorted(set([TARGET]+sum(MODELS.values(),[]))):
    if c not in p: raise RuntimeError(f"Missing {c}")
    p[c]=pd.to_numeric(p[c],errors="coerce")

ALPHAS=[0.0,0.1,1.0,10.0]
def pipe(a):
    return make_pipeline(StandardScaler(),Ridge(alpha=1e-10 if a==0 else a))

def choose(X,y,groups):
    inner=GroupKFold(n_splits=3); scores=[]
    for a in ALPHAS:
        errs=[]
        for tr,va in inner.split(X,y,groups):
            m=pipe(a);m.fit(X.iloc[tr],y[tr]);pr=m.predict(X.iloc[va])
            errs.extend((y[va]-pr).tolist())
        scores.append((float(np.sqrt(np.mean(np.square(errs)))),a))
    return sorted(scores,key=lambda z:(z[0],-z[1]))[0]

def cv_eval(q,features):
    X=q[features]; y=q[TARGET].to_numpy(float); groups=q.kommun_kod.to_numpy()
    outer=GroupKFold(n_splits=5); errs=[]; fold=[]
    for k,(tr,te) in enumerate(outer.split(X,y,groups),1):
        best=choose(X.iloc[tr],y[tr],groups[tr])
        m=pipe(best[1]);m.fit(X.iloc[tr],y[tr]);pr=m.predict(X.iloc[te])
        e=y[te]-pr;errs.extend(e.tolist())
        fold.append({"fold":k,"rmse":float(np.sqrt(np.mean(e*e))),
                     "mae":float(np.mean(np.abs(e))),"alpha":best[1]})
    return {"rmse":float(np.sqrt(np.mean(np.square(errs)))),
            "mae":float(np.mean(np.abs(errs))),
            "bias_actual_minus_prediction":float(np.mean(errs)),"folds":fold}

def balanced(years,features):
    q=p[p.year.isin(years)].dropna(subset=[TARGET]+features).copy()
    q=q.sort_values(["kommun_kod","year"]).reset_index(drop=True)
    if len(q)!=290*len(years) or q.groupby("year").kommun_kod.nunique().min()!=290:
        return None
    return q

out={"status":"outmigration_compact_common_sample_validation",
     "production_changed":False,"inflow_model_changed":False,
     "target":TARGET,
     "correction_note":"Prior compact ranking mixed 1450-row and 870-row evaluations; this file restricts primary arms to exact common balanced samples.",
     "cv":{},"holdout_2024":{}}

for label,years in {"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]}.items():
    rr={}
    for name,features in MODELS.items():
        q=balanced(years,features)
        if q is None:
            continue
        rr[name]={"features":features,"n":len(q),**cv_eval(q,features)}
    base=rr["lag1_only"]
    for m in rr.values():
        m["delta_rmse_pct_vs_lag1_only"]=100*(m["rmse"]/base["rmse"]-1)
        m["delta_mae_pct_vs_lag1_only"]=100*(m["mae"]/base["mae"]-1)
    out["cv"][label]={"years":years,"results":rr,
                      "ranking":sorted(rr,key=lambda n:(rr[n]["rmse"],len(rr[n]["features"])))}

# Cross-window ranking only exact comparable arms.
rank=[]
for name,features in MODELS.items():
    vals=[out["cv"][w]["results"][name]["delta_rmse_pct_vs_lag1_only"] for w in ["five","three"]]
    rank.append({"model":name,"features":features,
                 "mean_delta_rmse_pct":float(np.mean(vals)),
                 "worst_window_delta_rmse_pct":float(np.max(vals))})
out["cross_window_ranking"]=sorted(rank,key=lambda r:(r["mean_delta_rmse_pct"],r["worst_window_delta_rmse_pct"],len(r["features"])))

# 2024 genuine holdout: fit each model on 2019-2023; alpha chosen by municipality-blocked CV on training only.
train_years=[2019,2020,2021,2022,2023]
test_year=2024
for name,features in MODELS.items():
    tr=balanced(train_years,features)
    te=balanced([test_year],features)
    if tr is None or te is None: continue
    best=choose(tr[features],tr[TARGET].to_numpy(float),tr.kommun_kod.to_numpy())
    m=pipe(best[1]);m.fit(tr[features],tr[TARGET].to_numpy(float));pr=m.predict(te[features])
    e=te[TARGET].to_numpy(float)-pr
    out["holdout_2024"][name]={"features":features,"alpha":best[1],"n":len(te),
      "rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e))),
      "bias_actual_minus_prediction":float(np.mean(e))}
if "lag1_only" in out["holdout_2024"]:
    b=out["holdout_2024"]["lag1_only"]
    for m in out["holdout_2024"].values():
        m["delta_rmse_pct_vs_lag1_only"]=100*(m["rmse"]/b["rmse"]-1)
        m["delta_mae_pct_vs_lag1_only"]=100*(m["mae"]/b["mae"]-1)

(D/"outmigration_compact_common_sample_validation.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
