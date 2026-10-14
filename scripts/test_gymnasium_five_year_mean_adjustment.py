#!/usr/bin/env python3
"""Fixed five-year municipal mean + lagged graduation adjustments.

Same exact training and evaluation rows for simple mean, graduation-only
demeaned residual correction, and graduation plus demeaned geographic controls.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _kolada_year_rows,_kolada_total_value
D=Path("docs/data")
KPI={"exam3":"N17445","exam4":"N17461"}
TARGETS=["inflyttning_18_23_per_1000","inflyttning_24_34_per_1000"]
GEO=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
def score(y,p):
 return {"rmse":float(np.sqrt(np.mean((y-p)**2))),"mae":float(np.mean(abs(y-p)))}
def main():
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[p.year.eq(2024)&p.inflyttning_per_1000.notna(),"kommun_kod"])
 if len(ids)!=290:raise RuntimeError("290 municipalities required")
 p=p[p.kommun_kod.isin(ids)].copy()
 for short,kpi in KPI.items():
  data=[]
  for y in range(2014,2024):
   for r in _kolada_year_rows(kpi,y):
    k=str(r.get("municipality","")).strip()
    if k not in ids:continue
    v=_kolada_total_value(r.get("values",[]))
    if np.isfinite(v):data.append({"kommun_kod":k,"exam_year":y,"rate":float(v)})
  source=pd.DataFrame(data).drop_duplicates(["kommun_kod","exam_year"])
  for lag in (1,2):
   q=source.rename(columns={"exam_year":"year","rate":f"{short}_lag{lag}"}).copy();q.year+=lag
   p=p.merge(q,on=["kommun_kod","year"],how="left",validate="one_to_one")
 report={"design":"Five-year historical municipal outcome mean, then a learned correction from graduation rate relative to its local five-year mean.",
  "window":5,"KPIs":KPI,"models":["five_year_mean","mean_plus_graduation","mean_plus_graduation_and_geography"],"research_only":True,"results":{},
  "limitations":["Municipal aggregates are not linked individual graduate migration.",
   "Academic KPI year and release-time availability remain to be independently verified.",
   "Municipal history makes this a forecasting model, not a demographically blind structural explanation.",
   "Betygspoang is a separate proposed candidate; discontinued N17500 differs in denominator from newer N17701."]}
 for kind,first in [("exam3",2014),("exam4",2015)]:
  for lag in (1,2):
   feature=f"{kind}_lag{lag}"
   block={"years":{}}
   for year in range(first+lag+5,2025):
    tr=p[p.year.between(year-5,year-1)].sort_values(["kommun_kod","year"]).copy()
    te=p[p.year.eq(year)].sort_values("kommun_kod").copy()
    if len(tr)!=1450 or len(te)!=290:continue
    required=TARGETS+GEO+[feature]
    if pd.concat([tr,te])[required].isna().any().any():
     block["years"][str(year)]={"status":"incomplete"};continue
    ym={"status":"evaluated","n_train":1450,"n_test":290,"outcomes":{}}
    means=tr.groupby("kommun_kod")[[feature]+GEO+TARGETS].mean()
    for target in TARGETS:
     reference=te.kommun_kod.map(means[target]).to_numpy()
     truth=te[target].to_numpy()
     predictions={"five_year_mean":reference}
     for modelname,features in [("mean_plus_graduation",[feature]),("mean_plus_graduation_and_geography",[feature]+GEO)]:
      center=tr[features].to_numpy()-means.loc[tr.kommun_kod,features].to_numpy()
      residual=tr[target].to_numpy()-means.loc[tr.kommun_kod,target].to_numpy()
      tester=te[features].to_numpy()-means.loc[te.kommun_kod,features].to_numpy()
      reg=make_pipeline(StandardScaler(with_mean=False),RidgeCV(alphas=np.logspace(-2,4,25),fit_intercept=False))
      reg.fit(center,residual)
      predictions[modelname]=reference+reg.predict(tester)
     ix=int(np.flatnonzero(te.kommun_kod.to_numpy()=="2580")[0])
     ym["outcomes"][target]={k:{**score(truth,pred),"lulea_prediction":float(pred[ix]),"lulea_actual":float(truth[ix])} for k,pred in predictions.items()}
    block["years"][str(year)]=ym
   valid=[x for x in block["years"].values() if x.get("status")=="evaluated"]
   block["summary"]={target:{"evaluated_years":len(valid),
    "graduation_improvement_years":sum(z["outcomes"][target]["mean_plus_graduation"]["rmse"]<z["outcomes"][target]["five_year_mean"]["rmse"] for z in valid),
    "graduation_geo_improvement_years":sum(z["outcomes"][target]["mean_plus_graduation_and_geography"]["rmse"]<z["outcomes"][target]["five_year_mean"]["rmse"] for z in valid),
    "avg_rmse_gain":float(np.mean([z["outcomes"][target]["five_year_mean"]["rmse"]-z["outcomes"][target]["mean_plus_graduation"]["rmse"] for z in valid])) if valid else None} for target in TARGETS}
   report["results"][f"{kind}_lag{lag}"]=block
   print(f"{kind} lag{lag}: {len(valid)} years",flush=True)
 (D/"gymnasium_five_year_mean_residual_adjustment.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
