#!/usr/bin/env python3
"""Research-only fair five-year mean tests: grade points and graduation.
Hold fixed forecast years, municipalities, outcomes, and training periods.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from build_analysis import _kolada_year_rows,_kolada_total_value
OUT=Path("docs/data")
KPI={"exam3":"N17445","grade":"N17701"}
OUTCOMES=["inflyttning_18_23_per_1000","inflyttning_24_34_per_1000"]
def metrics(t,p):
 return {"rmse":float(np.sqrt(np.mean((t-p)**2))),"mae":float(np.mean(abs(t-p)))}
def main():
 p=pd.read_csv(OUT/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p["kommun_kod"]=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[p.year.eq(2024)&p.inflyttning_per_1000.notna(),"kommun_kod"])
 assert len(ids)==290
 p=p[p.kommun_kod.isin(ids)].copy()
 for label,kpi in KPI.items():
  rows=[]
  for year in range(2014,2024):
   for record in _kolada_year_rows(kpi,year):
    code=str(record.get("municipality","")).strip()
    if code not in ids:continue
    v=_kolada_total_value(record.get("values",[]))
    if np.isfinite(v):rows.append({"kommun_kod":code,"source_year":year,"value":float(v)})
  original=pd.DataFrame(rows).drop_duplicates(["kommun_kod","source_year"])
  for lag in [1,2]:
   frame=original.rename(columns={"source_year":"year","value":f"{label}{lag}"}).copy()
   frame["year"]+=lag
   p=p.merge(frame,on=["kommun_kod","year"],how="left",validate="one_to_one")
 results={"purpose":"Compare municipality 5-year mean with graduate rate and grade points separately or together",
  "common_forecast_years":[2021,2022,2023,2024],
  "n_municipalities":290,"train_years":5,"graduation":"N17445","grades":"N17701",
  "research_only":True,"results":{}}
 for lag in [1,2]:
  cols=[f"exam3{lag}",f"grade{lag}"]
  design={}
  for yr in [2021,2022,2023,2024]:
   train=p[p.year.between(yr-5,yr-1)].sort_values(["kommun_kod","year"])
   test=p[p.year.eq(yr)].sort_values("kommun_kod")
   assert len(train)==1450 and len(test)==290
   req=cols+OUTCOMES
   if pd.concat([train,test])[req].isna().any().any():
    design[str(yr)]={"status":"insufficient_data","non_missing":{c:int(pd.concat([train,test])[c].notna().sum()) for c in req}}
    continue
   baselines=train.groupby("kommun_kod")[req].mean()
   record={"status":"evaluated","training_period":[yr-5,yr-1],"outcomes":{}}
   for target in OUTCOMES:
    actual=test[target].to_numpy()
    base=test.kommun_kod.map(baselines[target]).to_numpy()
    pred={"five_year_mean":base}
    for label,features in [("plus_graduation",[cols[0]]),("plus_grade_points",[cols[1]]),("plus_both",cols)]:
     X=train[features].to_numpy()-baselines.loc[train.kommun_kod,features].to_numpy()
     y=train[target].to_numpy()-baselines.loc[train.kommun_kod,target].to_numpy()
     Z=test[features].to_numpy()-baselines.loc[test.kommun_kod,features].to_numpy()
     model=make_pipeline(StandardScaler(with_mean=False),RidgeCV(alphas=np.logspace(-2,4,25),fit_intercept=False))
     model.fit(X,y)
     pred[label]=base+model.predict(Z)
    lu=int(np.flatnonzero(test.kommun_kod.to_numpy()=="2580")[0])
    record["outcomes"][target]={key:{**metrics(actual,estimated),"lulea_actual":float(actual[lu]),"lulea_prediction":float(estimated[lu])} for key,estimated in pred.items()}
   design[str(yr)]=record
   print(f"lag {lag} forecast {yr} done",flush=True)
  results["results"][f"lag{lag}"]=design
 results["limitations"]=["Kolada N17701 definition and publication-date availability are not independently validated.",
 "All forecasts are municipal aggregate relationships, not individual follow-up of gymnasium cohorts.",
 "Only 2021-2024 can be compared across lag 1 and lag 2 with fixed five-year history.",
 "Migration history is a predictor so these models are not demographically blind.",
 "No change to production or frozen commuter challenger."]
 (OUT/"gymnasium_grade_points_five_year_mean_test.json").write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
