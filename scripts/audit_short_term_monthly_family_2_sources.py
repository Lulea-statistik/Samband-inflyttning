#!/usr/bin/env python3
import json, urllib.request
from pathlib import Path
from datetime import datetime, timezone

SOURCES=[
 {
  "id":"scb_bas_labour_status_monthly",
  "label":"SCB BAS arbetsmarknadsstatus månadsvis",
  "url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210A/ArbStatusM",
  "role":"local_labour_status"
 },
 {
  "id":"scb_new_cars_monthly",
  "label":"SCB nyregistrerade personbilar månadsvis",
  "url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/TK/TK1001/TK1001A/PersBilarDrivMedel",
  "role":"local_household_cycle"
 },
 {
  "id":"scb_monthly_income",
  "label":"SCB individuell disponibel inkomst månadsvis",
  "url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/HE/HE0110/HE0110M/MistTab5",
  "role":"local_household_income_realtime"
 }
]
OUT=Path("docs/data/short_term_monthly_candidate_family_2_source_audit.json")

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Lulea-statistik-short-term-family2-audit/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.load(r)

def pack_var(v):
    vals=v.get("values",[])
    texts=v.get("valueTexts",[])
    return {
      "code":v.get("code"),
      "text":v.get("text"),
      "time":bool(v.get("time")),
      "n_values":len(vals),
      "values":vals,
      "valueTexts":texts
    }

out={
 "status":"short_term_monthly_candidate_family_2_source_audit",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "sources":[]
}
for s in SOURCES:
    rec=dict(s)
    try:
        meta=get(s["url"])
        rec["reachable"]=True
        rec["title"]=meta.get("title")
        rec["variables"]=[pack_var(v) for v in meta.get("variables",[])]
        tv=next((v for v in meta.get("variables",[]) if v.get("time")),None)
        if tv:
            vals=tv.get("values",[])
            rec["time_range"]={
              "code":tv.get("code"),
              "first":vals[0] if vals else None,
              "last":vals[-1] if vals else None,
              "n":len(vals)
            }
    except Exception as e:
        rec["reachable"]=False
        rec["error"]=repr(e)
    out["sources"].append(rec)

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
