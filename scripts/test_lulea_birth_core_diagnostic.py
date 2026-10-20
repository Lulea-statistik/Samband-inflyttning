#!/usr/bin/env python3
"""Lulea-focused birth-core diagnostic after integrated balance backtest.

Compares:
1) lag1 birth rate only
2) lag1 birth rate + share age 20-34
3) the same two models with rolling 3-origin local bias correction

Training remains national 3-year rolling; only the correction is Lulea-specific and
uses prior forecast errors, never future data. No production model is changed.
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
p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
t=t.sort_values(["kommun_kod","year"])
t["lag1_fodelsetal_per_100"]=t.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one").sort_values(["kommun_kod","year"])

SPECS={
 "lag1_only":["lag1_fodelsetal_per_100"],
 "lag1_plus_age20_34":["lag1_fodelsetal_per_100","lag1_andel_20_34"]
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

out={"status":"lulea_birth_core_diagnostic","production_changed":False,"window_years":3,"specs":{}}
for name,features in SPECS.items():
    rows=[]
    local_errors=[]
    for y in range(2016,2025):
        tr=q[q.year.isin(range(y-3,y))].copy()
        te=q[q.year.eq(y)].copy()
        if len(tr)!=870 or len(te)!=290: continue
        a=choose_alpha(tr,features)
        m=mdl(a);m.fit(tr[features],tr["fodelsetal_per_100"].to_numpy(float))
        lu=te[te.kommun_kod.eq("2580")].iloc[[0]]
        raw=float(m.predict(lu[features])[0])
        actual=float(lu["fodelsetal_per_100"].iloc[0])
        err=actual-raw
        corr=float(np.mean(local_errors[-3:])) if len(local_errors)>=3 else 0.0
        corrected=raw+corr
        corr_err=actual-corrected
        mean_pop=float(lu["mean_population"].iloc[0])
        rows.append({
          "year":y,"alpha":a,"actual_rate":actual,"raw_rate":raw,
          "raw_error_actual_minus_prediction":err,
          "bias_correction":corr,"corrected_rate":corrected,
          "corrected_error_actual_minus_prediction":corr_err,
          "actual_births":actual*mean_pop/100.0,
          "raw_births":raw*mean_pop/100.0,
          "corrected_births":corrected*mean_pop/100.0
        })
        local_errors.append(err)
    r=pd.DataFrame(rows)
    e=r.raw_error_actual_minus_prediction.to_numpy(float)
    ce=r.corrected_error_actual_minus_prediction.to_numpy(float)
    recent=r[r.year>=2019]
    out["specs"][name]={
      "features":features,
      "raw":{"rmse_rate":float(np.sqrt(np.mean(e*e))),"mae_rate":float(np.mean(np.abs(e))),
             "bias_rate":float(np.mean(e))},
      "corrected":{"rmse_rate":float(np.sqrt(np.mean(ce*ce))),"mae_rate":float(np.mean(np.abs(ce))),
                   "bias_rate":float(np.mean(ce))},
      "recent_2019_2024":{
         "raw_rmse_rate":float(np.sqrt(np.mean(np.square(recent.raw_error_actual_minus_prediction)))),
         "corrected_rmse_rate":float(np.sqrt(np.mean(np.square(recent.corrected_error_actual_minus_prediction))))
      },
      "years":rows
    }

# Rank correction choices on recent period and full rolling history.
rank=[]
for name,v in out["specs"].items():
    rank.append({"spec":name,"mode":"raw","recent_rmse":v["recent_2019_2024"]["raw_rmse_rate"],
                 "full_rmse":v["raw"]["rmse_rate"]})
    rank.append({"spec":name,"mode":"local_bias3","recent_rmse":v["recent_2019_2024"]["corrected_rmse_rate"],
                 "full_rmse":v["corrected"]["rmse_rate"]})
out["ranking"]=sorted(rank,key=lambda x:(x["recent_rmse"],x["full_rmse"]))

(D/"lulea_birth_core_diagnostic.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
