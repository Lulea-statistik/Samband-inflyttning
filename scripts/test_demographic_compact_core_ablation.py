#!/usr/bin/env python3
"""Compact demographic core ablation for birth/death rate models.

Purpose:
- Compare simple interpretable lagged cores after the broad neutral screen.
- Keep 2024 as an exposed diagnostic holdout only; it is not an untouched lockbox.
- No production model is changed by this script.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D=Path("docs/data")

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)

t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
t=t.sort_values(["kommun_kod","year"])
t["lag1_fodelsetal_per_100"]=t.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
t["lag1_dodstal_per_1000"]=t.groupby("kommun_kod")["dodstal_per_1000"].shift(1)

d=pd.read_csv(D/"demographic_scb_candidate_features.csv",dtype={"kommun_kod":str})
d["kommun_kod"]=d["kommun_kod"].astype(str).str.zfill(4)
d=d.sort_values(["kommun_kod","year"])
for c in [x for x in d.columns if x not in ("kommun_kod","year")]:
    d[c]=pd.to_numeric(d[c],errors="coerce")
    d["lag1_"+c]=d.groupby("kommun_kod")[c].shift(1)
d=d[["kommun_kod","year"]+[c for c in d.columns if c.startswith("lag1_")]]

q=(p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one")
     .merge(d,on=["kommun_kod","year"],how="left",validate="one_to_one"))

# Only compact, interpretable candidate sets motivated by the neutral recurrence.
SPECS={
 "birth":{
   "target":"fodelsetal_per_100",
   "sets":{
     "lag1_only":["lag1_fodelsetal_per_100"],
     "lag1_plus_age20_34":["lag1_fodelsetal_per_100","lag1_andel_20_34"],
     "lag1_plus_mother_25_29":["lag1_fodelsetal_per_100","lag1_fodda_share_mor_25_29_pct"],
     "lag1_plus_mother_25_29_40plus":["lag1_fodelsetal_per_100","lag1_fodda_share_mor_25_29_pct","lag1_fodda_share_mor_40_plus_pct"],
     "lag1_plus_age20_34_mother25_29":["lag1_fodelsetal_per_100","lag1_andel_20_34","lag1_fodda_share_mor_25_29_pct"]
   }
 },
 "death":{
   "target":"dodstal_per_1000",
   "sets":{
     "lag1_only":["lag1_dodstal_per_1000"],
     "lag1_plus_80plus_death_share":["lag1_dodstal_per_1000","lag1_doda_fodelsear_share_80_plus_pct"],
     "lag1_plus_pensioner_share":["lag1_dodstal_per_1000","lag1_bas_pensionarer_andel_pct"],
     "lag1_plus_80plus_and_pensioner":["lag1_dodstal_per_1000","lag1_doda_fodelsear_share_80_plus_pct","lag1_bas_pensionarer_andel_pct"],
     "lag1_plus_80plus_age20_34":["lag1_dodstal_per_1000","lag1_doda_fodelsear_share_80_plus_pct","lag1_andel_20_34"]
   }
 }
}
ALPHAS=[0.0,0.3,3.0,30.0]
WINDOWS={"five":[2019,2020,2021,2022,2023],"three":[2021,2022,2023]}

def model(alpha):
    return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),
                         Ridge(alpha=alpha,random_state=73))

def tune_cv(df,target,features):
    X=df[features]; y=df[target].to_numpy(float); groups=df.kommun_kod.to_numpy()
    outer=GroupKFold(n_splits=5)
    errs=[];folds=[]
    for fold,(tr,te) in enumerate(outer.split(X,y,groups),1):
        inner=GroupKFold(n_splits=3)
        scores=[]
        for a in ALPHAS:
            ee=[]
            for itr,iva in inner.split(X.iloc[tr],y[tr],groups[tr]):
                m=model(a);m.fit(X.iloc[tr].iloc[itr],y[tr][itr])
                pr=m.predict(X.iloc[tr].iloc[iva]);ee.extend((y[tr][iva]-pr).tolist())
            scores.append((float(np.sqrt(np.mean(np.square(ee)))),a))
        _,a=min(scores,key=lambda z:z[0])
        m=model(a);m.fit(X.iloc[tr],y[tr]);pr=m.predict(X.iloc[te]);e=y[te]-pr
        errs.extend(e.tolist())
        folds.append({"fold":fold,"alpha":a,"rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e)))})
    return {
      "rmse":float(np.sqrt(np.mean(np.square(errs)))),
      "mae":float(np.mean(np.abs(errs))),
      "bias_actual_minus_prediction":float(np.mean(errs)),
      "folds":folds
    }

def exposed_2024(df,target,features,train_years):
    tr=df[df.year.isin(train_years)].copy()
    te=df[df.year.eq(2024)].copy()
    if len(te)!=290:return {"available":False,"n_test":len(te)}
    # choose alpha by municipality-blocked CV on training years only
    X=tr[features]; y=tr[target].to_numpy(float); g=tr.kommun_kod.to_numpy()
    cv=GroupKFold(n_splits=5); scores=[]
    for a in ALPHAS:
        ee=[]
        for ti,vi in cv.split(X,y,g):
            m=model(a);m.fit(X.iloc[ti],y[ti]);pr=m.predict(X.iloc[vi]);ee.extend((y[vi]-pr).tolist())
        scores.append((float(np.sqrt(np.mean(np.square(ee)))),a))
    _,a=min(scores,key=lambda z:z[0])
    m=model(a);m.fit(X,y)
    pr=m.predict(te[features]);e=te[target].to_numpy(float)-pr
    lulea=te.kommun_kod.eq("2580").to_numpy()
    return {
      "available":True,"alpha":a,"n_test":len(te),
      "rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e))),
      "bias_actual_minus_prediction":float(np.mean(e)),
      "lulea_actual":float(te.loc[te.kommun_kod.eq("2580"),target].iloc[0]),
      "lulea_prediction":float(pr[lulea][0]),
      "lulea_error_actual_minus_prediction":float(e[lulea][0])
    }

out={"status":"demographic_compact_core_ablation","production_changed":False,
     "note_2024":"2024 is exposed diagnostic validation, not an untouched lockbox.",
     "windows":WINDOWS,"results":{}}

for family,spec in SPECS.items():
    target=spec["target"]
    out["results"][family]={}
    for w,years in WINDOWS.items():
        base=q[q.year.isin(years)].copy().sort_values(["kommun_kod","year"]).reset_index(drop=True)
        for name,features in spec["sets"].items():
            miss=[c for c in features+[target] if c not in base.columns]
            if miss:
                out["results"][family][f"{w}:{name}"]={"status":"missing_columns","columns":miss};continue
            z=base[["kommun_kod","year",target]+features].copy()
            for c in features+[target]:z[c]=pd.to_numeric(z[c],errors="coerce")
            if not np.isfinite(z[target]).all():
                out["results"][family][f"{w}:{name}"]={"status":"missing_target"};continue
            res=tune_cv(z,target,features)
            res["features"]=features
            res["years"]=years
            res["n_rows"]=len(z)
            res["exposed_2024"]=exposed_2024(q,target,features,years)
            out["results"][family][f"{w}:{name}"]=res

for family in out["results"]:
    valid=[(k,v) for k,v in out["results"][family].items() if "rmse" in v]
    valid.sort(key=lambda kv:(kv[1]["rmse"],kv[1]["mae"],len(kv[1]["features"])))
    out["results"][family]["ranking"]=[{"spec":k,"rmse":v["rmse"],"mae":v["mae"],"features":v["features"]} for k,v in valid]

(D/"demographic_compact_core_ablation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
