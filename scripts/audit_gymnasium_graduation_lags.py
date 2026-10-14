#!/usr/bin/env python3
"""Discover observed Kolada gymnasium graduation rates and audit 1-5 year lags.

No regression until coverage and time definition are confirmed. Hemkommun
preferred to school location; observed years only, never fabricated backfills.
"""
import json,re
from pathlib import Path
import numpy as np
import pandas as pd
from build_analysis import _kolada_json,_kolada_year_rows,_kolada_total_value,_norm_header
D=Path("docs/data")
SPECS={
 "examen_3_ar":("gymnasieelever med examen inom 3 ar","hemkommun"),
 "examen_4_ar":("gymnasieelever med examen inom 4 ar","hemkommun"),
 "hogskolebehorighet_3_ar":("gymnasieelever som uppnatt grundlaggande behorighet","hemkommun")}
YEARS=list(range(2013,2025))
def fetch_kpi(search,required):
 data=_kolada_json("/kpi",{"title":search,"per_page":5000}).get("values",[])
 selected=[x for x in data if all(v in _norm_header(str(x.get("title",""))) for v in required)]
 return selected
def main():
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[(p.year.eq(2024))&p.inflyttning_per_1000.notna(),"kommun_kod"])
 if len(ids)!=290:raise RuntimeError("Municipality validation failed")
 p=p[p.kommun_kod.isin(ids)]
 output={"status":"gymnasium_graduation_lag_coverage","years_queried":YEARS,
   "focus":"Home-municipality gymnasium qualification outcomes, never school location",
   "candidate_results":{},"production_model_changed":False}
 for short,(search,hemloc) in SPECS.items():
  try:
   options=fetch_kpi(search,[hemloc])
   # Search again broadly to catch differing inflections, but never silently map
   # to school-location or a different educational outcome.
   if not options:options=fetch_kpi("Gymnasieelever",[hemloc])
   options=[o for o in options if ("examen inom 3" if short=="examen_3_ar" else "examen inom 4" if short=="examen_4_ar" else "grundlaggande behorighet") in _norm_header(str(o.get("title","")))]
   if not options:raise RuntimeError("No exact concept-matching KPI found")
   candidates=[]
   for o in options[:8]:
    kid=str(o["id"]);yearly={}
    for y in YEARS:
     try:
      observations=_kolada_year_rows(kid,y);vals={}
      for row in observations:
       code=str(row.get("municipality","")).strip()
       if code not in ids:continue
       v=_kolada_total_value(row.get("values",[]))
       if np.isfinite(v):vals[code]=float(v)
      yearly[y]=len(vals)
     except Exception as exc:
      yearly[y]=0
    candidates.append({"id":kid,"title":o.get("title"),"coverage":yearly,
       "years_290":sum(n==290 for n in yearly.values()),"municipality_observations":sum(yearly.values())})
   candidates.sort(key=lambda t:(t["years_290"],t["municipality_observations"]),reverse=True)
   winner=candidates[0];complete=[y for y,n in winner["coverage"].items() if n==290]
   output["candidate_results"][short]={"selected":winner,"other_matches":candidates[1:],
     "lag_coverage":{str(lag):{"forecast_years_with_290_coverage":[year for year in range(2016,2025) if year-lag in complete],
       "five_year_fixed_training_forecasts":[year for year in range(2016,2025) if all(y-lag in complete for y in range(year-5,year+1))]}
       for lag in range(1,6)}}
  except Exception as exc:
   output["candidate_results"][short]={"error":str(exc)}
 for col in ["lag1_gymnasium_hogskoleforberedande_pct","lag1_gymnasium_yrkesprogram_pct"]:
  if col not in p:continue
  pivot=p.pivot(index="year",columns="kommun_kod",values=col).sort_index()
  v={}
  for lag in range(1,6):
   # Existing lag1(y) = original measure (y-1), thus lag-k(y) = lag1(y-k+1)
   shifted=pivot.shift(lag-1)
   complete=[int(year) for year,row in shifted.iterrows() if row.notna().sum()==290]
   v[str(lag)]={"complete_forecast_years":complete,
    "five_year_fixed_training_forecasts":[year for year in complete if all(y in complete for y in range(year-5,year))]}
  output["candidate_results"][col]={"lag_coverage":v,"note":"Already-lagged panel field; shift k-1 extra years"}
 output["limitations"]=["Examination within 3 or 4 years is a cohort completion outcome, not necessarily a measure of moves immediately after graduation.",
  "Even with complete regional coverage, year-of-publication vs cohort time reference needs verification.",
  "Lag 1-5 candidates must compete fairly on identical forecast years; no optimization on held-out outcomes."]
 (D/"gymnasium_graduation_lag_audit.json").write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
 print(json.dumps({k:("error: "+v["error"] if "error" in v else v.get("selected",{}).get("id","existing panel")) for k,v in output["candidate_results"].items()},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
