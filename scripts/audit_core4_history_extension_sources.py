#!/usr/bin/env python3
"""Audit whether the two limiting core-4 predictors can be reconstructed further back.

Queries current public APIs only. Research-only; no model fit and no production change.
Checks:
- Kolada N03937 municipality coverage by year 2010-current
- SCB BO0104T04 housing years/coverage sufficient to derive annual stock change
"""
import json, re, datetime
from pathlib import Path
import requests

D=Path("docs/data")
s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-history-audit/1.0"})

def get(url,**kwargs):
    r=s.get(url,timeout=90,**kwargs)
    r.raise_for_status()
    return r.json()

base="https://api.kolada.se/v3"
kpi="N03937"
kolada={}
for year in range(2010,datetime.datetime.now().year+1):
    try:
        j=get(f"{base}/data/kpi/{kpi}/year/{year}",params={"region_type":"municipality","per_page":5000})
        vals=j.get("values",j.get("data",j))
        if isinstance(vals,dict):
            vals=vals.get("values",[])
        regions=set()
        n_numeric=0
        for r in vals if isinstance(vals,list) else []:
            rid=str(r.get("municipality",r.get("region",r.get("region_id",""))))
            if re.fullmatch(r"\d{4}",rid):
                regions.add(rid)
                v=r.get("value")
                if isinstance(v,(int,float)):
                    n_numeric+=1
                elif isinstance(v,list):
                    if any(isinstance(x,dict) and x.get("value") is not None for x in v):
                        n_numeric+=1
        kolada[str(year)]={"municipality_regions":len(regions),"rows_with_numeric_value":n_numeric}
    except Exception as e:
        kolada[str(year)]={"error":str(e)}

housing_url="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
meta=get(housing_url)
vars={v["code"]:v for v in meta["variables"]}
housing_years=[str(y) for y in vars["Tid"]["values"] if str(y).isdigit()]
municipalities=[x for x in vars["Region"]["values"] if re.fullmatch(r"\d{4}",str(x))]

out={
 "status":"core4_history_extension_source_audit",
 "production_changed":False,
 "kolada_N03937_coverage":kolada,
 "housing":{
   "available_years":housing_years,
   "first_year":min(map(int,housing_years)) if housing_years else None,
   "last_year":max(map(int,housing_years)) if housing_years else None,
   "municipality_codes_in_metadata":len(municipalities),
   "derivation_requirement":"To create lag1_bostadsbestandsforandring_pct for target year Y, housing totals are needed for Y-2 and Y-1."
 },
 "interpretation":{
   "six_year_backtest_target_example_2021":{
     "training_target_years":[2015,2016,2017,2018,2019,2020],
     "n03937_source_years_needed":[2014,2015,2016,2017,2018,2019],
     "housing_years_needed_for_training":[2013,2014,2015,2016,2017,2018,2019]
   }
 }
}
(D/"three_year_forecast_core4_history_extension_source_audit.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
