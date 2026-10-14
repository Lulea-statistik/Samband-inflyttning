#!/usr/bin/env python3
"""Audit literal cohort-origin rule E+n..E+n+5 -> forecast E+n+6.

The six inclusive outcome years require graduation covariates sourced from
the corresponding historical cohorts; never interpolate missing earlier KPI.
"""
import json
from pathlib import Path
import pandas as pd
from build_analysis import _kolada_year_rows,_kolada_total_value
import numpy as np
D=Path("docs/data")
KPIS={"exam3":"N17445","exam4":"N17461"}
def main():
 p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
 p.kommun_kod=p.kommun_kod.str.zfill(4)
 ids=set(p.loc[p.year.eq(2024)&p.inflyttning_per_1000.notna(),"kommun_kod"])
 output={"design":"For cohort exam calendar E and delay n, train on outcome years E+n through E+n+5 inclusive, then predict year E+n+6",
 "training_length_years":6,"requested_forecasts":[2023,2024],
 "kpis":KPIS,"results":{},"production_model_changed":False}
 for kind,kpi in KPIS.items():
  available={}
  for year in range(2009,2025):
   try:
    vals={}
    for row in _kolada_year_rows(kpi,year):
     c=str(row.get("municipality","")).strip()
     if c not in ids:continue
     v=_kolada_total_value(row.get("values",[]))
     if np.isfinite(v):vals[c]=v
    available[year]=len(vals)
   except Exception as exc:
    available[year]=0
  result={"year_coverage":available,"designs":{}}
  for n in (1,2):
   for y in (2023,2024):
    e=y-(n+6)
    # All original cohort source years needed for a historical rolling design.
    # Training observations t=y-6..y-1 must each use cohort t-(n+6).
    train=list(range(y-6,y))
    needed=[t-(n+6) for t in train]+[e]
    missing=[yr for yr in sorted(set(needed)) if available.get(yr,0)!=290]
    key=f"lag{n}_forecast{y}"
    result["designs"][key]={"forecast_year":y,"focal_graduation_cohort_year":e,
      "cohort_window":[e+n,e+n+5],"forecast_from_cohort":e+n+6,
      "training_outcome_years":train,"training_source_exam_years":[t-(n+6) for t in train],
      "test_exam_year":e,"unavailable_complete_kpi_years":missing,
      "can_evaluate_without_backfill":not missing}
  output["results"][kind]=result
 (D/"gymnasium_literal_cohort_sixyear_audit.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:[(name,v["can_evaluate_without_backfill"]) for name,v in r["designs"].items()] for k,r in output["results"].items()}),flush=True)
if __name__=="__main__":main()
