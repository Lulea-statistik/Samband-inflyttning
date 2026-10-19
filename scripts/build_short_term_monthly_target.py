#!/usr/bin/env python3
import csv, json, re, unicodedata, urllib.request
from pathlib import Path
from datetime import datetime, timezone

OUT=Path("docs/data/short_term_monthly_target_lulea.csv")
META=Path("docs/data/short_term_monthly_target_lulea_manifest.json")

LEGACY_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101G/ManadBefStatRegion"
CKM_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101G/MBefStatRegionCKM"

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Lulea-statistik-short-term-target/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.load(r)

def post_json(url,query):
    body=json.dumps({"query":query,"response":{"format":"json"}}).encode()
    req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json","User-Agent":"Lulea-statistik-short-term-target/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r:
        return json.load(r)

def item(code,vals): return {"code":code,"selection":{"filter":"item","values":vals}}
def allq(code): return {"code":code,"selection":{"filter":"all","values":["*"]}}

def maps(meta):
    out={}
    for v in meta.get("variables",[]):
        out[v["code"]]=dict(zip(v.get("values",[]),v.get("valueTexts",[])))
    return out

def rows(payload):
    cols=[c["code"] for c in payload.get("columns",[])]
    out=[]
    for d in payload.get("data",[]):
        r=dict(zip(cols,d.get("key",[])))
        vals=d.get("values",[])
        r["_value"]=vals[0] if vals else None
        out.append(r)
    return out

def num(x):
    if x is None: return None
    s=str(x).strip().replace(" ","").replace(",",".")
    if s in ("","..",".","-"): return None
    try: return float(s)
    except: return None

def slug(s):
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","_",s).strip("_")

def detect_codes(meta):
    vars_=meta.get("variables",[])
    bytext={v.get("text","").lower():v["code"] for v in vars_}
    codes={v["code"] for v in vars_}
    region=next((x for x in ["Region","region"] if x in codes),bytext.get("region"))
    change=next((x for x in ["Forandringar","förändringar","ContentsCode"] if x in codes),None)
    if not change:
        change=next((v["code"] for v in vars_ if "föränd" in v.get("text","").lower()),None)
    sex=next((x for x in ["Kon","kön"] if x in codes),None)
    if not sex:
        sex=next((v["code"] for v in vars_ if v.get("text","").lower()=="kön"),None)
    time=next((v["code"] for v in vars_ if v.get("time")),None)
    return region,change,sex,time

def fetch_source(url, source_name):
    meta=get_json(url); mp=maps(meta)
    region,change,sex,time=detect_codes(meta)
    if not all([region,change,sex,time]):
        raise RuntimeError(f"{source_name}: could not identify dimensions: {region},{change},{sex},{time}")
    # Locate Lulea and total-sex codes by labels when necessary.
    region_code=next((k for k,v in mp[region].items() if "Luleå" in v),"2580")
    sex_code=next((k for k,v in mp[sex].items() if "totalt" in v.lower() or "samtliga" in v.lower()),None)
    if sex_code is None:
        raise RuntimeError(f"{source_name}: total sex code not found")
    payload=post_json(url,[item(region,[region_code]),allq(change),item(sex,[sex_code]),allq(time)])
    data=rows(payload)
    out={}
    for r in data:
        month=r.get(time)
        if not month: continue
        label=mp[change].get(r.get(change),r.get(change,""))
        out.setdefault(month,{})[slug(label)]=num(r["_value"])
    return meta,out,{"region":region,"change":change,"sex":sex,"time":time,"region_code":region_code,"sex_code":sex_code}

legacy_meta,legacy,legacy_dims=fetch_source(LEGACY_URL,"legacy")
ckm_meta,ckm,ckm_dims=fetch_source(CKM_URL,"ckm")

all_months=sorted(set(legacy)|set(ckm))
fields=sorted(set(k for d in legacy.values() for k in d)|set(k for d in ckm.values() for k in d))

# Canonical mapping by normalized label names from source.
def pick(d,*names):
    for n in names:
        if n in d: return d[n]
    return None

records=[]
for m in all_months:
    use_ckm=m>="2025M01" and m in ckm
    src=ckm.get(m,{}) if use_ckm else legacy.get(m,{})
    rec={
      "month":m,
      "source":"ckm_2025_plus" if use_ckm else "legacy_2000_2024",
      "source_break_2025":1 if m>="2025M01" else 0,
      "all_inmigrations":pick(src,"samtliga_inflyttningar"),
      "all_outmigrations":pick(src,"samtliga_utflyttningar"),
      "internal_inmigrations":pick(src,"samtliga_inrikes_inflyttningar"),
      "internal_outmigrations":pick(src,"samtliga_inrikes_utflyttningar"),
      "immigrations":pick(src,"invandringar"),
      "emigrations":pick(src,"utvandringar"),
      "migration_surplus_total":pick(src,"flyttningsoverskott_totalt"),
      "population":pick(src,"folkmangd")
    }
    records.append(rec)

with OUT.open("w",newline="",encoding="utf-8") as fh:
    cols=list(records[0].keys())
    w=csv.DictWriter(fh,fieldnames=cols); w.writeheader(); w.writerows(records)

non_null=sum(1 for r in records if r["all_inmigrations"] is not None)
manifest={
 "status":"short_term_monthly_target_stitched",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "first_month":records[0]["month"] if records else None,
 "last_month":records[-1]["month"] if records else None,
 "rows":len(records),
 "rows_with_all_inmigrations":non_null,
 "legacy_rows":len(legacy),
 "ckm_rows":len(ckm),
 "legacy_dimensions":legacy_dims,
 "ckm_dimensions":ckm_dims,
 "break_month":"2025M01",
 "primary_target":"all_inmigrations",
 "forecast_horizons_months":[3,6,9,12],
 "quality_checks":{
   "has_2000_history":any(r["month"].startswith("2000") and r["all_inmigrations"] is not None for r in records),
   "has_2024_history":any(r["month"].startswith("2024") and r["all_inmigrations"] is not None for r in records),
   "has_2025_ckm":any(r["month"].startswith("2025") and r["source"]=="ckm_2025_plus" and r["all_inmigrations"] is not None for r in records)
 }
}
META.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
