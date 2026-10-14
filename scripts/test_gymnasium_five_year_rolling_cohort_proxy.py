#!/usr/bin/env python3
"""Municipality-level rolling graduation lags vs five-year migration mean.

Train on five *outcome* years, test the next year. Start only after 2014
graduation measures, no fabricated backfill. Compare both candidate and
five-year historical mean on identical municipality-year rows.
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
TARGETS=["inflyttning_18_23_per_1000","inflyttning_24_34_per_1000"]
KPIS={"exam3":"N17445","exam4":"N17461"}
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
def main():
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[p.year.eq(2024)&p.inflyttning_per_1000.notna(),"kommun_kod"])
 if len(ids)!=290:raise RuntimeError("Expected 290 municipalities")
 p=p[p.kommun_kod.isin(ids)].copy()
 for key,kpi in KPIS.items():
  vals=[]
  for y in range(2014,2024):
   for item in _kolada_year_rows(kpi,y):
    c=str(item.get("municipality","")).strip()
    if c not in ids:continue
    v=_kolada_total_value(item.get("values",[]))
    if np.isfinite(v):vals.append({"kommun_kod":c,"source_year":y,"value":float(v)})
  source=pd.DataFrame(vals).drop_duplicates(["kommun_kod","source_year"])
  for lag in (1,2):
   frame=source.rename(columns={"source_year":"year","value":f"{key}_lag{lag}"}).copy()
   frame.year+=lag
   p=p.merge(frame,on=["kommun_kod","year"],how="left",validate="one_to_one")
 report={"status":"fixed_five_year_rolling_gymnasium","train_window":5,
  "cohort_mapping":"Kolada graduation source year E is paired with municipality migration outcome in E+lag",
  "warning":"These are municipal aggregate associations, NOT migrations of identified graduates.",
  "kpis":KPIS,"results":{},"production_model_changed":False}
 for kind in KPIS:
  for lag in (1,2):
   feature=f"{kind}_lag{lag}"
   label=f"{kind}_lag{lag}"
   first=2014 if kind=="exam3" else 2015
   # First 5 training years are E+lag through E+lag+4, then predict E+lag+5.
   earliest=first+lag+5
   item={"first_possible_forecast":earliest,"years":{}}
   for year in range(earliest,2025):
    tr=p[p.year.between(year-5,year-1)].sort_values(["year","kommun_kod"])
    te=p[p.year.eq(year)].sort_values("kommun_kod")
    if len(tr)!=1450 or len(te)!=290:continue
    required=CONTROLS+[feature]+TARGETS
    if pd.concat([tr,te])[required].isna().any().any():
     item["years"][str(year)]={"status":"incomplete","coverage":{c:int(pd.concat([tr,te])[c].notna().sum()) for c in required}}
     continue
    yr={"status":"evaluated","train_years":[year-5,year-1],"n_train":1450,"n_test":290,"targets":{}}
    for target in TARGETS:
     actual=te[target].to_numpy()
     historical=tr.groupby("kommun_kod")[target].mean()
     five_mean=te.kommun_kod.map(historical).to_numpy()
     ix=int(np.flatnonzero(te.kommun_kod.to_numpy()=="2580")[0])
     comparison={}
     for name,pred in [("five_year_mean",five_mean)]:
      comparison[name]={"rmse":float(np.sqrt(np.mean((actual-pred)**2))),
       "mae":float(np.mean(abs(actual-pred))),"lulea_actual":float(actual[ix]),
       "lulea_prediction":float(pred[ix])}
     for name,cols in [("structural",CONTROLS),("structural_plus_graduation",CONTROLS+[feature])]:
      model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
      model.fit(tr[cols],tr[target]);pred=model.predict(te[cols])
      comparison[name]={"rmse":float(np.sqrt(np.mean((actual-pred)**2))),
       "mae":float(np.mean(abs(actual-pred))),"lulea_prediction":float(pred[ix]),
       "coefficient":float(model.named_steps["ridgecv"].coef_[-1]) if feature in cols else None}
     yr["targets"][target]=comparison
    item["years"][str(year)]=yr
   complete=[v for v in item["years"].values() if v["status"]=="evaluated"]
   if complete:
    item["summary"]={target:{"n_years":len(complete),
     "graduation_better_than_structural":sum(y["targets"][target]["structural_plus_graduation"]["rmse"]<y["targets"][target]["structural"]["rmse"] for y in complete),
     "graduation_better_than_five_year_mean":sum(y["targets"][target]["structural_plus_graduation"]["rmse"]<y["targets"][target]["five_year_mean"]["rmse"] for y in complete),
     "mean_rmse_improvement_vs_structural":float(np.mean([y["targets"][target]["structural"]["rmse"]-y["targets"][target]["structural_plus_graduation"]["rmse"] for y in complete]))}
     for target in TARGETS}
   report["results"][label]=item
   print(f"{label}: {len(complete)} years assessed",flush=True)
 report["limitations"]=["Only municipal-level aggregate relationships; individual graduates are not followed.",
  "Potential publication-time leakage remains until Kolada reference-year and release date are audited.",
  "Five-year mean is a municipality-specific univariate baseline; structural Ridge model is pooled over municipalities.",
  "Different lag/KPI designs have different first forecast years. Compare candidates on shared forecast years.",
  "Out-migration by age unavailable in panel. No production promotion."]
 (D/"gymnasium_five_year_rolling_cohort_proxy.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
