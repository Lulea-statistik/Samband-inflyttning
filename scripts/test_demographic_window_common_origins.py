#!/usr/bin/env python3
"""Common-origin comparison for compact demographic window choices.

Avoids ranking 3/6/10-year windows on different forecast-origin sets.
Birth and death use the already selected compact cores.
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
ALPHAS=[0.0,0.3,3.0,30.0]
SPECS={
 "birth":{"target":"fodelsetal_per_100","features":["lag1_fodelsetal_per_100","lag1_andel_20_34"]},
 "death":{"target":"dodstal_per_1000","features":["lag1_dodstal_per_1000","lag1_bas_pensionarer_andel_pct"]}
}

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
t=pd.read_csv(D/"demographic_birth_death_targets.csv",dtype={"kommun_kod":str})
t["kommun_kod"]=t["kommun_kod"].astype(str).str.zfill(4)
t=t.sort_values(["kommun_kod","year"])
t["lag1_fodelsetal_per_100"]=t.groupby("kommun_kod")["fodelsetal_per_100"].shift(1)
t["lag1_dodstal_per_1000"]=t.groupby("kommun_kod")["dodstal_per_1000"].shift(1)
q=p.merge(t,on=["kommun_kod","year"],how="inner",validate="one_to_one")

def mdl(a): return make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),Ridge(alpha=a))
def alpha_cv(tr,target,features):
    X=tr[features]; y=tr[target].to_numpy(float); g=tr.kommun_kod.to_numpy()
    cv=GroupKFold(n_splits=5); scores=[]
    for a in ALPHAS:
        ee=[]
        for ti,vi in cv.split(X,y,g):
            m=mdl(a);m.fit(X.iloc[ti],y[ti]);ee.extend((y[vi]-m.predict(X.iloc[vi])).tolist())
        scores.append((float(np.sqrt(np.mean(np.square(ee)))),a))
    return min(scores,key=lambda x:x[0])[1]

def predict_window(z,target,features,w,origins):
    rows=[]
    for y in origins:
        yrs=list(range(y-w,y))
        tr=z[z.year.isin(yrs)].copy();te=z[z.year.eq(y)].copy()
        if len(tr)!=290*w or len(te)!=290: continue
        a=alpha_cv(tr,target,features)
        m=mdl(a);m.fit(tr[features],tr[target].to_numpy(float))
        pr=m.predict(te[features]);ac=te[target].to_numpy(float)
        for i,r in te.reset_index(drop=True).iterrows():
            rows.append({"year":y,"kommun_kod":r.kommun_kod,"actual":float(ac[i]),"prediction":float(pr[i]),
                         "error":float(ac[i]-pr[i]),"alpha":a})
    return pd.DataFrame(rows)

out={"status":"demographic_window_common_origin_comparison","production_changed":False,"results":{}}
for fam,s in SPECS.items():
    z=q[["kommun_kod","year",s["target"]]+s["features"]].copy()
    for c in [s["target"]]+s["features"]: z[c]=pd.to_numeric(z[c],errors="coerce")
    famout={}
    for label,windows,origins in [
      ("common_3_6",[3,6],list(range(2019,2025))),
      ("common_3_6_10",[3,6,10],[2023,2024])
    ]:
        block={"origins":origins,"windows":{}}
        preds={}
        for w in windows:
            r=predict_window(z,s["target"],s["features"],w,origins);preds[w]=r
            e=r.error.to_numpy(float); lu=r[r.kommun_kod.eq("2580")];le=lu.error.to_numpy(float)
            block["windows"][str(w)]={
              "n_rows":int(len(r)),"rmse":float(np.sqrt(np.mean(e*e))),"mae":float(np.mean(np.abs(e))),
              "bias":float(np.mean(e)),"lulea_rmse":float(np.sqrt(np.mean(le*le))),
              "lulea_mae":float(np.mean(np.abs(le))),"lulea_bias":float(np.mean(le))
            }
        best=min(windows,key=lambda w:(block["windows"][str(w)]["rmse"],block["windows"][str(w)]["mae"]))
        block["best_national_window"]=best
        bestl=min(windows,key=lambda w:(block["windows"][str(w)]["lulea_rmse"],block["windows"][str(w)]["lulea_mae"]))
        block["best_lulea_window"]=bestl
        famout[label]=block
    out["results"][fam]=famout

(D/"demographic_window_common_origin_comparison.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
