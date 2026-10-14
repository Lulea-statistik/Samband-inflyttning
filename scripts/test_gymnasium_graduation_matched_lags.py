#!/usr/bin/env python3
"""Matched 2023/2024 one-year forecasts: school completion with 1-3-year lags.

Five fixed calendar training years, 290 municipalities, and common sample.
Do not infer causality or availability from a Kolada calendar-year label.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error,mean_squared_error
from build_analysis import _kolada_year_rows,_kolada_total_value
D=Path("docs/data")
KPIS={"exam3":"N17445","exam4":"N17461"}
OUTCOMES=["inflyttning_per_1000","utflyttning_per_1000"]
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct"]
FORECASTS=[2023,2024]
LAGS=[1,2,3]
def main():
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[p.year.eq(2024)&p.inflyttning_per_1000.notna(),"kommun_kod"])
 if len(ids)!=290:raise RuntimeError("Expected 290 municipalities")
 p=p[p.kommun_kod.isin(ids)].copy()
 for feature,kpi in KPIS.items():
  records=[]
  for year in range(2015,2024):
   rows=_kolada_year_rows(kpi,year)
   for row in rows:
    code=str(row.get("municipality","")).strip()
    if code not in ids:continue
    value=_kolada_total_value(row.get("values",[]))
    if np.isfinite(value):records.append({"kommun_kod":code,"source_year":year,feature:float(value)})
  obs=pd.DataFrame(records).drop_duplicates(["kommun_kod","source_year"])
  if obs.empty:raise RuntimeError(f"No observed Kolada values {feature}")
  for lag in LAGS:
   t=obs.rename(columns={"source_year":"year",feature:f"{feature}_lag{lag}"}).copy()
   t["year"]+=lag
   p=p.merge(t,on=["kommun_kod","year"],how="left",validate="one_to_one")
 candidates=[f"{feature}_lag{lag}" for feature in KPIS for lag in LAGS]
 required=CONTROLS+OUTCOMES+candidates
 audit={"status":"gymnasium_matched_one_year_lag_test","training_window_years":5,
  "forecast_horizon_years":1,"forecast_years":FORECASTS,
  "train_years_by_forecast":{"2023":[2018,2019,2020,2021,2022],"2024":[2019,2020,2021,2022,2023]},
  "kolada_ids":KPIS,"candidates":candidates,"controls":CONTROLS,
  "source_year_rule":"candidate_for_forecast_year_y = Kolada measure labelled year y-minus-lag",
  "coverage":{},"results":{},"production_model_changed":False}
 for forecast_year in FORECASTS:
  train=p[p.year.between(forecast_year-5,forecast_year-1)].sort_values(["year","kommun_kod"]).copy()
  test=p[p.year.eq(forecast_year)].sort_values("kommun_kod").copy()
  common=pd.concat([train.assign(split="train"),test.assign(split="test")])
  audit["coverage"][str(forecast_year)]={c:int(common[c].notna().sum()) for c in required}
  if len(train)!=1450 or len(test)!=290:raise RuntimeError(f"Panel sample invalid {forecast_year}")
  if common[required].isna().any().any():
   audit["results"][str(forecast_year)]={"status":"incomplete_common_sample","minimum_nonmissing":min(audit["coverage"][str(forecast_year)].values())}
   continue
  year_result={"status":"evaluated","n_train":len(train),"n_test":len(test),"outcomes":{}}
  for outcome in OUTCOMES:
   comparisons={}
   for name,add in [("reference",[]),*[(name,[name]) for name in candidates]]:
    cols=CONTROLS+add
    m=make_pipeline(StandardScaler(),RidgeCV(alphas=np.logspace(-3,3,25)))
    m.fit(train[cols],train[outcome]);pred=m.predict(test[cols]);truth=test[outcome].to_numpy()
    ix=int(np.flatnonzero(test.kommun_kod.to_numpy()=="2580")[0])
    comparisons[name]={"rmse":float(np.sqrt(mean_squared_error(truth,pred))),
      "mae":float(mean_absolute_error(truth,pred)),
      "lulea_actual":float(truth[ix]),"lulea_prediction":float(pred[ix]),
      "coefficient":float(m.named_steps["ridgecv"].coef_[-1]) if add else None}
   year_result["outcomes"][outcome]=comparisons
  audit["results"][str(forecast_year)]=year_result
  print(f"Forecast {forecast_year}: full matched 290 municipalities",flush=True)
 audit["limitations"]=["Cohort/start-year versus outcome/publication-year Kolada semantics must be externally verified.",
  "The source year is lagged, but actual data release date was not verified; this is retrospective, not proven release-date-safe forecasting.",
  "No historical migration variables; simple fixed geographic/population controls, not production model.",
  "Only two forecast years; compare same test years and training windows, no automatic challenger promotion."]
 (D/"gymnasium_graduation_matched_lags.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
 print(json.dumps({"status":{y:r["status"] for y,r in audit["results"].items()},"coverage":audit["coverage"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
