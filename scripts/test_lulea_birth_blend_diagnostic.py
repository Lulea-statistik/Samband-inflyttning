#!/usr/bin/env python3
"""Test Lulea birth forecast blends between local-stable lag1 and national 2-feature core.

Candidates:
- lag1_only
- national_core = lag1 birth rate + share age 20-34
- blends 25/50/75% national_core
Each also tested with rolling 3-origin Lulea bias correction.

No production model changes.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")
ALPHAS=[0.0,0.3,3.0,30.0]
WEIGHTS=[0.0,0.25,0.5,0.75,1.0]  # weight on national 2-feature model

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
t=t.sort_values(["kommun_kod","year"])
t["lag1_fodelsetal_per_100"]=t.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one").sort_values(["kommun_kod","year"])

SPECS={
 "lag1":["lag1_fodelsetal_per_100"],
 "national":["lag1_fodelsetal_per_100","lag1_andel_20_34"]
}

def mdl(a):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=a))

def choose_alpha(tr,features):
    X=tr[features];y=tr["fodelsetal_per_100"].to_numpy(float);g=tr.kommun_kod.to_numpy()
    cv=GroupKFold(n_splits=5);scores=[]
    for a in ALPHAS:
        e=[]
        for ti,vi in cv.split(X,y,g):
            m=mdl(a);m.fit(X.iloc[ti],y[ti]);e.extend((y[vi]-m.predict(X.iloc[vi])).tolist())
        scores.append((float(np.sqrt(np.mean(np.square(e)))),a))
    return min(scores,key=lambda x:x[0])[1]

base=[]
for y in range(2016,2025):
    tr=q[q.year.isin(range(y-3,y))].copy()
    te=q[q.year.eq(y)].copy()
    if len(tr)!=870 or len(te)!=290: continue
    lu=te[te.kommun_kod.eq("2580")].iloc[[0]]
    preds={}
    alphas={}
    for name,features in SPECS.items():
        a=choose_alpha(tr,features)
        m=mdl(a);m.fit(tr[features],tr["fodelsetal_per_100"].to_numpy(float))
        preds[name]=float(m.predict(lu[features])[0]);alphas[name]=a
    actual=float(lu["fodelsetal_per_100"].iloc[0])
    base.append({"year":y,"actual":actual,"lag1":preds["lag1"],"national":preds["national"],
                 "alpha_lag1":alphas["lag1"],"alpha_national":alphas["national"]})

df=pd.DataFrame(base)
out={"status":"lulea_birth_blend_diagnostic","production_changed":False,"window_years":3,"candidates":[]}
for w in WEIGHTS:
    errs=[];corr_errs=[];hist=[];years=[]
    for r in df.itertuples(index=False):
        raw=(1-w)*r.lag1+w*r.national
        err=r.actual-raw
        corr=float(np.mean(hist[-3:])) if len(hist)>=3 else 0.0
        corrected=raw+corr
        cerr=r.actual-corrected
        years.append({"year":int(r.year),"actual_rate":float(r.actual),"raw_rate":float(raw),
                      "raw_error_actual_minus_prediction":float(err),
                      "bias_correction":float(corr),"corrected_rate":float(corrected),
                      "corrected_error_actual_minus_prediction":float(cerr)})
        errs.append(err);corr_errs.append(cerr);hist.append(err)
    e=np.asarray(errs);ce=np.asarray(corr_errs)
    recent=np.array([y["year"]>=2019 for y in years])
    out["candidates"].append({
      "national_weight":w,
      "raw":{"rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e))),"bias":float(np.mean(e)),
             "recent_rmse_2019_2024":float(np.sqrt(np.mean(e[recent]**2)))},
      "bias3":{"rmse":float(np.sqrt(np.mean(ce*ce))),"mae":float(np.mean(np.abs(ce))),"bias":float(np.mean(ce)),
               "recent_rmse_2019_2024":float(np.sqrt(np.mean(ce[recent]**2)))},
      "years":years
    })

rank=[]
for c in out["candidates"]:
    for mode in ["raw","bias3"]:
        rank.append({"national_weight":c["national_weight"],"mode":mode,
                     "recent_rmse":c[mode]["recent_rmse_2019_2024"],"full_rmse":c[mode]["rmse"],
                     "full_mae":c[mode]["mae"],"bias":c[mode]["bias"]})
out["ranking_recent"]=sorted(rank,key=lambda x:(x["recent_rmse"],x["full_rmse"],x["full_mae"]))
out["ranking_full"]=sorted(rank,key=lambda x:(x["full_rmse"],x["full_mae"],abs(x["bias"])))

(D/"lulea_birth_blend_diagnostic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
