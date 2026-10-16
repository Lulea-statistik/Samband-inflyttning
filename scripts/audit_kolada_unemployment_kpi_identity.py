#!/usr/bin/env python3
"""Audit exact live Kolada KPI identity for the unemployment core feature.

Non-predictive source audit. Queries Kolada API v3 using the same semantic
matching logic as build_analysis.py, records all matching candidates and
coverage, and compares the resolver winner with the research alias N03937.
"""
import json, re, time, unicodedata
from pathlib import Path
import requests

OUT=Path("docs/data")
BASE="https://api.kolada.se/v3"
YEARS=list(range(2019,2026))
SPEC={
    "search":"Arbetslösa i befolkningen",
    "required_terms":["arbetslösa","befolkningen","18-65","andel"],
    "forbidden_terms":["långtids"],
    "label":"Arbetslösa i befolkningen, 18-65 år, andel (%)",
}
KNOWN_ALIAS="N03937"

s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-source-audit/1.0"})

def norm(x):
    x=unicodedata.normalize("NFKD",str(x or ""))
    x="".join(c for c in x if not unicodedata.combining(c))
    x=x.casefold()
    return re.sub(r"[^a-z0-9]+"," ",x).strip()

def get(path,params=None):
    last=None
    for attempt in range(1,5):
        try:
            r=s.get(BASE+path,params=params or {},timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last=e
            if attempt<4: time.sleep(attempt*2)
    raise RuntimeError(last)

def total_value(values):
    active=[v for v in (values or []) if not v.get("isdeleted",False) and v.get("value") is not None]
    if not active:return None
    totals=[]
    for v in active:
        g=str(v.get("gender") or "").strip().casefold()
        if g in {"","t","tot","total","totalt","alla"}: totals.append(v)
    chosen=totals[0] if totals else (active[0] if len(active)==1 else None)
    if chosen is None:return None
    try:return float(chosen["value"])
    except:return None

payload=get("/kpi",{"title":SPEC["search"],"per_page":5000})
required=[norm(x) for x in SPEC["required_terms"]]
forbidden=[norm(x) for x in SPEC["forbidden_terms"]]
matches=[]
for item in payload.get("values",[]):
    title=str(item.get("title") or "")
    n=norm(title)
    if all(t in n for t in required) and not any(t in n for t in forbidden):
        rec={
            "id":str(item.get("id")),
            "title":title,
            "description":item.get("description"),
            "operating_area":item.get("operating_area"),
            "perspective":item.get("perspective"),
            "is_divided_by_gender":item.get("is_divided_by_gender"),
            "municipality_type":item.get("municipality_type"),
            "coverage_by_year":{},
        }
        total=0; years150=0
        for year in YEARS:
            rows=get(f"/data/kpi/{rec['id']}/year/{year}",{"region_type":"municipality","per_page":5000}).get("values",[])
            nmun=sum(1 for row in rows if re.fullmatch(r"\d{4}",str(row.get("municipality",""))) and total_value(row.get("values",[])) is not None)
            rec["coverage_by_year"][str(year)]=nmun
            total+=nmun
            if nmun>=150: years150+=1
        rec["coverage_total"]=total
        rec["years_with_150_plus"]=years150
        matches.append(rec)

matches.sort(key=lambda r:(r["years_with_150_plus"],r["coverage_total"],r["id"]),reverse=True)
winner=matches[0] if matches else None

alias_payload=None
try:
    alias_payload=get(f"/kpi/{KNOWN_ALIAS}")
except Exception as e:
    alias_payload={"error":str(e)}

alias_values=alias_payload.get("values",[]) if isinstance(alias_payload,dict) else []
alias_meta=alias_values[0] if alias_values else None

out={
    "status":"live_kolada_unemployment_identity_audit",
    "production_changed":False,
    "query_spec":SPEC,
    "years_checked":YEARS,
    "matching_candidates":matches,
    "resolver_winner":winner,
    "known_research_alias":KNOWN_ALIAS,
    "known_alias_metadata":alias_meta,
    "winner_is_known_alias":bool(winner and winner["id"]==KNOWN_ALIAS),
    "decision":{
        "can_pin_id_now":bool(winner and winner["id"]==KNOWN_ALIAS),
        "asof_verified":False,
        "remaining_blocker":"Historical publication/replacement timestamps and revision history are still required even if current KPI identity is pinned."
    }
}
(OUT/"neutral_kolada_unemployment_kpi_identity_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
