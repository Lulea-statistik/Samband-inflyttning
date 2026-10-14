#!/usr/bin/env python3
"""Audit historical municipality grade-point measure and 2022 KPI break.

N17500: diploma OR study certificate 2500 points (old definition)
N17701: diploma only (new definition); never splice without documented bridge.
"""
import json
from pathlib import Path
import numpy as np
from build_analysis import _kolada_year_rows,_kolada_total_value
D=Path("docs/data")
def main():
 out={"source":"Kolada","measures":{
  "N17500":{"label":"Average grade points, diploma or study certificate 2500 points (old definition)","coverage":{}},
  "N17701":{"label":"Average grade points, diploma only (new definition)","coverage":{}}},
  "definition_warning":"Different populations around 2022; cannot splice N17500 and N17701 as continuous identical measure.",
  "research_only":True}
 for k,obj in out["measures"].items():
  for year in range(2014,2025):
   try:
    vals={}
    for r in _kolada_year_rows(k,year):
     c=str(r.get("municipality","")).strip()
     if len(c)!=4 or not c.isdigit():continue
     v=_kolada_total_value(r.get("values",[]))
     if np.isfinite(v):vals[c]=float(v)
    obj["coverage"][str(year)]={"n_municipalities":len(vals),"min":min(vals.values()) if vals else None,"max":max(vals.values()) if vals else None}
   except Exception as exc:
    obj["coverage"][str(year)]={"error":str(exc)}
 out["recommendation"]="Find uninterrupted comparable years and enforce five observed years for a rolling forecast. Distinguish home municipality from school municipality and grade points from admission merit."
 (D/"gymnasium_grade_points_history_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
 print(json.dumps({k:{y:v.get("n_municipalities",0) for y,v in o["coverage"].items()} for k,o in out["measures"].items()}),flush=True)
if __name__=="__main__":main()
