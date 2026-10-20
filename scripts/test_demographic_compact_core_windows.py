#!/usr/bin/env python3
"""Rolling-origin 3/6/10-year window comparison for compact birth/death cores.

Primary candidates from compact ablation:
Birth:
  lag1_fodelsetal_per_100 + lag1_andel_20_34
Death:
  lag1_dodstal_per_1000 + lag1_bas_pensionarer_andel_pct

Each origin year is predicted from only the preceding W years.
Evaluation reports all municipalities and Lulea separately.
2024 remains exposed diagnostic validation, not an untouched lockbox.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold

D=Path("docs/data")
WINDOWS=[3,6,10]
ALPHAS=[0.0,0.3,3.0,30.0]

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
t=t.sort_values(["kommun_kod","year"])
t["lag1_fodelsetal_per_100"]=t.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
t["lag1_dodstal_per_1000"]=t.groupby("kommun_kod")["dodstal_per_1000"].shift(1)

q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one")

SPECS={
 "birth":{
   "target":"fodelsetal_per_100",
   "features":["lag1_fodelsetal_per_100","lag1_andel_20_34"]
 },
 "death":{
   "target":"dodstal_per_1000",
   "features":["lag1_dodstal_per_1000","lag1_bas_pensionarer_andel_pct"]
 }
}

def make_model(a):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=a))

def choose_alpha(train,target,features):
    X=train[features]; y=train[target].to_numpy(float); g=train.kommun_kod.to_numpy()
    cv=GroupKFold(n_splits=5)
    rows=[]
    for a in ALPHAS:
        errs=[]
        for tr,va in cv.split(X,y,g):
            m=make_model(a);m.fit(X.iloc[tr],y[tr]);pr=m.predict(X.iloc[va])
            errs.extend((y[va]-pr).tolist())
        rows.append((float(np.sqrt(np.mean(np.square(errs)))),a))
    return min(rows,key=lambda z:z[0])[1]

out={"status":"demographic_compact_core_window_comparison","production_changed":False,
     "windows":WINDOWS,"results":{}}

for fam,spec in SPECS.items():
    target=spec["target"]; features=spec["features"]
    z=q[["kommun_kod","year",target]+features].copy()
    for c in [target]+features:z[c]=pd.to_numeric(z[c],errors="coerce")
    years=sorted(int(y) for y in z.year.dropna().unique())
    famout={"target":target,"features":features,"windows":{}}
    for w in WINDOWS:
        rows=[]
        for y in years:
            train_years=list(range(y-w,y))
            if min(train_years)<min(years):continue
            tr=z[z.year.isin(train_years)].copy()
            te=z[z.year.eq(y)].copy()
            if len(tr)!=290*w or len(te)!=290:continue
            if not np.isfinite(tr[target]).all() or not np.isfinite(te[target]).all():continue
            a=choose_alpha(tr,target,features)
            m=make_model(a);m.fit(tr[features],tr[target].to_numpy(float))
            pr=m.predict(te[features]);actual=te[target].to_numpy(float);err=actual-pr
            for i,row in te.reset_index(drop=True).iterrows():
                rows.append({
                  "year":y,"kommun_kod":row.kommun_kod,"actual":float(actual[i]),
                  "prediction":float(pr[i]),"error_actual_minus_prediction":float(err[i]),
                  "alpha":a
                })
        r=pd.DataFrame(rows)
        if r.empty:
            famout["windows"][str(w)]={"status":"no_common_origins"};continue
        e=r.error_actual_minus_prediction.to_numpy(float)
        lu=r[r.kommun_kod.eq("2580")].copy()
        le=lu.error_actual_minus_prediction.to_numpy(float)
        byyear=[]
        for y,g in r.groupby("year"):
            ee=g.error_actual_minus_prediction.to_numpy(float)
            byyear.append({"year":int(y),"rmse":float(np.sqrt(np.mean(ee*ee))),
                           "mae":float(np.mean(np.abs(ee))),"bias":float(np.mean(ee))})
        famout["windows"][str(w)]={
          "first_origin":int(r.year.min()),"last_origin":int(r.year.max()),
          "n_origins":int(r.year.nunique()),"n_rows":int(len(r)),
          "rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e))),"bias":float(np.mean(e)),
          "lulea_rmse":float(np.sqrt(np.mean(le*le))),"lulea_mae":float(np.mean(np.abs(le))),
          "lulea_bias":float(np.mean(le)),
          "lulea_years":[{"year":int(x.year),"actual":float(x.actual),"prediction":float(x.prediction),
                          "error_actual_minus_prediction":float(x.error_actual_minus_prediction)}
                         for x in lu.itertuples(index=False)],
          "by_year":byyear
        }
    valid=[(int(w),v) for w,v in famout["windows"].items() if "rmse" in v]
    famout["ranking_national"]=sorted(
      [{"window_years":w,"rmse":v["rmse"],"mae":v["mae"]} for w,v in valid],
      key=lambda x:(x["rmse"],x["mae"],x["window_years"]))
    famout["ranking_lulea"]=sorted(
      [{"window_years":w,"rmse":v["lulea_rmse"],"mae":v["lulea_mae"]} for w,v in valid],
      key=lambda x:(x["rmse"],x["mae"],x["window_years"]))
    out["results"][fam]=famout

(D/"demographic_compact_core_window_comparison.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
