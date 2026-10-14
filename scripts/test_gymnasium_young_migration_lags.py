#!/usr/bin/env python3
"""Test completion rates lagged 1 or 2 years for age-specific in-migration.

Equal five-year training windows in 2023 and 2024, matched observations.
No young out-migration series exists in current panel: never infer it.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
D=Path("docs/data")
KPIS={"exam3":"N17445","exam4":"N17461"}
LAGS=(1,2)
OUTCOMES=("inflyttning_18_23_per_1000","inflyttning_24_34_per_1000")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
def main():
 from build_analysis import _kolada_year_rows,_kolada_total_value
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[p.year.eq(2024)&p.inflyttning_per_1000.notna(),"kommun_kod"])
 if len(ids)!=290:raise RuntimeError("Expected 290 municipalities")
 p=p[p.kommun_kod.isin(ids)].copy()
 for source,kpi in KPIS.items():
  records=[]
  for year in range(2015,2024):
   for row in _kolada_year_rows(kpi,year):
    k=str(row.get("municipality","")).strip()
    if k not in ids:continue
    v=_kolada_total_value(row.get("values",[]))
    if np.isfinite(v):records.append({"kommun_kod":k,"source_year":year,"graduation":float(v)})
  src=pd.DataFrame(records).drop_duplicates(["kommun_kod","source_year"])
  for lag in LAGS:
   feature=f"{source}_lag{lag}"
   frame=src.rename(columns={"source_year":"year","graduation":feature}).copy()
   frame.year+=lag
   p=p.merge(frame,on=["kommun_kod","year"],how="left",validate="one_to_one")
 candidates=[f"{s}_lag{l}" for s in KPIS for l in LAGS]
 out={"status":"gymnasium_young_inmigration_fixed_window","source_kpi":KPIS,"ages":["18-23","24-34"],
      "forecast_years":[2023,2024],"training_window_years":5,
      "training_by_forecast":{"2023":[2018,2019,2020,2021,2022],"2024":[2019,2020,2021,2022,2023]},
      "candidate_lags":[1,2],"controls":CONTROLS,"results":{},
      "age_specific_outmigration_available":False,"production_model_changed":False}
 for year in [2023,2024]:
  tr=p[p.year.between(year-5,year-1)].sort_values(["year","kommun_kod"])
  te=p[p.year.eq(year)].sort_values("kommun_kod")
  if len(tr)!=1450 or len(te)!=290:raise RuntimeError(f"Invalid number of observations {year}")
  complete_cols=CONTROLS+candidates+list(OUTCOMES)
  combined=pd.concat([tr,te])
  missing={col:int(combined[col].notna().sum()) for col in complete_cols}
  result={"n_train":len(tr),"n_test":len(te),"coverage":missing,"outcomes":{}}
  if combined[complete_cols].isna().any().any():
   result["status"]="incomplete_matched_sample";out["results"][str(year)]=result;continue
  result["status"]="evaluated"
  for outcome in OUTCOMES:
   result["outcomes"][outcome]={}
   for name,add in [("reference",[]),*[(k,[k]) for k in candidates]]:
    cols=CONTROLS+add
    model=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
    model.fit(tr[cols],tr[outcome])
    pred=model.predict(te[cols]);truth=te[outcome].to_numpy()
    ix=int(np.flatnonzero(te.kommun_kod.to_numpy()=="2580")[0])
    result["outcomes"][outcome][name]={"rmse":float(np.sqrt(np.mean((truth-pred)**2))),
     "mae":float(np.mean(abs(truth-pred))),"lulea_actual":float(truth[ix]),
     "lulea_prediction":float(pred[ix]),
     "standardized_coefficient":float(model.named_steps["ridgecv"].coef_[-1]) if add else None}
  out["results"][str(year)]=result
  print(f"{year} evaluated, 5-year fixed window, 290 municipalities",flush=True)
 out["limitations"]=["Age-specific outmigration is not present in the current panel; only age-specific in-migration evaluated.",
  "Lag from Kolada label year, NOT verified years since actual graduation for individual students.",
  "Kolada outcome-year and release-date semantics remain to be verified; these retrospective lags do not establish release-time availability.",
  "Only two held-out years and a simplified structural baseline; no production promotion."]
 (D/"gymnasium_young_migration_lags.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
 print(json.dumps({year:r["status"] for year,r in out["results"].items()}),flush=True)
if __name__=="__main__":main()
