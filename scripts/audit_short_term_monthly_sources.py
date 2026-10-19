#!/usr/bin/env python3
"""Audit first four monthly sources for the short-term forecasting module."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("docs/data/short_term_monthly_source_audit.json")
SOURCES=[
 {
  "id":"scb_bas_employment_monthly",
  "label":"SCB BAS sysselsättning månadsvis",
  "pxweb_url":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__AM__AM0210__AM0210B/YrkStallningM/",
  "api_url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210B/YrkStallningM",
  "role":"local_labour_market",
  "expected_frequency":"month"
 },
 {
  "id":"scb_asylum_seekers",
  "label":"SCB asylsökande",
  "pxweb_url":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101P/AsylsokandeN/",
  "api_url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101P/AsylsokandeN",
  "role":"exogenous_migration",
  "expected_frequency":"month_or_quarter"
 },
 {
  "id":"scb_gdp_indicator_monthly",
  "label":"SCB BNP-indikator",
  "pxweb_url":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__NR__NR9999__NR9999A/NR9999ENS2010BNPIndN/",
  "api_url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/NR/NR9999/NR9999A/NR9999ENS2010BNPIndN",
  "role":"national_business_cycle",
  "expected_frequency":"month"
 },
 {
  "id":"scb_monthly_population_ckm",
  "label":"SCB månadsvis befolkningsstatistik CKM",
  "pxweb_url":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101G/MBefStatRegionCKM/",
  "api_url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101G/MBefStatRegionCKM",
  "role":"local_demographic_realtime",
  "expected_frequency":"month"
 }
]

def fetch_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Lulea-statistik-short-term-source-audit/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.load(r)

rows=[]
for s in SOURCES:
    rec=dict(s)
    try:
        meta=fetch_json(s["api_url"])
        rec["reachable"]=True
        rec["title"]=meta.get("title")
        vars_out=[]
        for v in meta.get("variables",[]):
            vals=v.get("values",[])
            texts=v.get("valueTexts",[])
            vars_out.append({
              "code":v.get("code"),
              "text":v.get("text"),
              "time":bool(v.get("time")),
              "n_values":len(vals),
              "first_value":vals[0] if vals else None,
              "last_value":vals[-1] if vals else None,
              "first_text":texts[0] if texts else None,
              "last_text":texts[-1] if texts else None
            })
        rec["variables"]=vars_out
        timevars=[v for v in vars_out if v["time"]]
        rec["time_range"]=timevars[0] if timevars else None
    except Exception as e:
        rec["reachable"]=False
        rec["error"]=repr(e)
    rows.append(rec)

result={
 "status":"short_term_monthly_candidate_family_1_source_audit",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "sources":rows,
 "forecast_horizons_months":[3,6,9,12],
 "next_gate":"Use metadata to define exact API queries and freeze a real-time-safe monthly feature table before modelling."
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
