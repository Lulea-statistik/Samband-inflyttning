#!/usr/bin/env python3
import csv, json, re, unicodedata, urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT=Path("docs/data/short_term_monthly_candidate_family_2.csv")
META=Path("docs/data/short_term_monthly_candidate_family_2_manifest.json")

BAS="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210A/ArbStatusM"
CARS="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/TK/TK1001/TK1001A/PersBilarDrivMedel"
INC="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/HE/HE0110/HE0110M/MistTab5"

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Lulea-statistik-short-term-family2/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r: return json.load(r)

def post(url,q):
    body=json.dumps({"query":q,"response":{"format":"json"}}).encode()
    req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json","User-Agent":"Lulea-statistik-short-term-family2/1.0"})
    with urllib.request.urlopen(req,timeout=120) as r: return json.load(r)

def item(c,v): return {"code":c,"selection":{"filter":"item","values":v}}
def allq(c): return {"code":c,"selection":{"filter":"all","values":["*"]}}

def maps(meta):
    return {v["code"]:dict(zip(v.get("values",[]),v.get("valueTexts",[]))) for v in meta.get("variables",[])}

def rows(payload):
    cols=[c["code"] for c in payload.get("columns",[])]
    out=[]
    for rec in payload.get("data",[]):
        r=dict(zip(cols,rec.get("key",[])))
        vv=rec.get("values",[])
        r["_value"]=vv[0] if vv else None
        out.append(r)
    return out

def num(x):
    if x is None:return None
    s=str(x).strip().replace(" ","").replace(",",".")
    if s in ("","..",".","-"): return None
    try:return float(s)
    except:return None

def slug(s):
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","_",s).strip("_")

def mk(m): return int(m[:4])*12+int(m[-2:])

bas_meta=get(BAS); bas_map=maps(bas_meta)
car_meta=get(CARS); car_map=maps(car_meta)
inc_meta=get(INC); inc_map=maps(inc_meta)

rowsout=defaultdict(dict)

# BAS: fixed, non-overlapping analytic slices. Never aggregate overlapping age groups.
# 15-74 = broad status; 20-24 and 25-29 = student/young-adult signals; 20-66 = labour-market rates.
bas_slices=[
 ("15-74","all_15_74"),
 ("20-24","age20_24"),
 ("25-29","age25_29"),
 ("20-66","age20_66")
]
for age,age_name in bas_slices:
    for cc,label in bas_map["ContentsCode"].items():
        payload=post(BAS,[
          item("Region",["2580"]),item("Kon",["1+2"]),item("Alder",[age]),
          item("Fodelseregion",["tot"]),item("ContentsCode",[cc]),allq("Tid")
        ])
        for r in rows(payload):
            m=r.get("Tid")
            if m: rowsout[m][f"bas2_{age_name}_{slug(label)}"]=num(r["_value"])

# Extra birth-region split for the two migration-relevant broad status counts only.
for birth,bname in [("in","native"),("ut","foreign_born")]:
    for cc in ["000006HI","000004YH","000006IE"]: # employed, unemployed, students
        label=bas_map["ContentsCode"][cc]
        payload=post(BAS,[
          item("Region",["2580"]),item("Kon",["1+2"]),item("Alder",["15-74"]),
          item("Fodelseregion",[birth]),item("ContentsCode",[cc]),allq("Tid")
        ])
        for r in rows(payload):
            m=r.get("Tid")
            if m: rowsout[m][f"bas2_{bname}_15_74_{slug(label)}"]=num(r["_value"])

# Cars: fuels are mutually exclusive categories, so total may be summed safely.
payload=post(CARS,[item("Region",["2580"]),allq("Drivmedel"),allq("ContentsCode"),allq("Tid")])
car_months=defaultdict(list)
for r in rows(payload):
    m=r.get("Tid"); v=num(r["_value"])
    if m and v is not None:
        fuel=car_map["Drivmedel"].get(r.get("Drivmedel"),r.get("Drivmedel",""))
        rowsout[m][f"cars_new_{slug(fuel)}"]=v
        car_months[m].append(v)
for m,vals in car_months.items():
    rowsout[m]["cars_new_total"]=sum(vals)

# Income: short-history realtime diagnostics. Total sex, 20-66.
for cc,label in inc_map["ContentsCode"].items():
    payload=post(INC,[
      item("Region",["2580"]),item("Kon",["1+2"]),item("Alder",["20-66"]),
      item("ContentsCode",[cc]),allq("Tid")
    ])
    for r in rows(payload):
        m=r.get("Tid")
        if m: rowsout[m][f"income_20_66_{slug(label)}"]=num(r["_value"])

# Derived lagged changes for count/index-like columns.
ordered=sorted(rowsout,key=mk)
byk={mk(m):m for m in ordered}
rawcols=sorted({k for d in rowsout.values() for k in d})
for m in ordered:
    k=mk(m)
    for col in rawcols:
        v=rowsout[m].get(col)
        if v is None: continue
        for lag,suf in [(3,"change_3m_pct"),(6,"change_6m_pct"),(12,"yoy_pct")]:
            pm=byk.get(k-lag)
            pv=rowsout[pm].get(col) if pm else None
            if pv not in (None,0):
                rowsout[m][col+"_"+suf]=100*(v/pv-1)

# Remove empty months.
rowsout={m:d for m,d in rowsout.items() if any(v is not None for v in d.values())}
ordered=sorted(rowsout,key=mk)
cols=sorted({k for d in rowsout.values() for k in d})

OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["month"]+cols); w.writeheader()
    for m in ordered:w.writerow({"month":m,**rowsout[m]})

manifest={
 "status":"short_term_monthly_candidate_family_2_built",
 "generated_at_utc":datetime.now(timezone.utc).isoformat(),
 "production_changed":False,
 "structural_core4_changed":False,
 "rows":len(ordered),
 "first_month":ordered[0] if ordered else None,
 "last_month":ordered[-1] if ordered else None,
 "columns":cols,
 "bas_age_slices":[x[0] for x in bas_slices],
 "bas_contents":bas_map["ContentsCode"],
 "cars_fuels":car_map["Drivmedel"],
 "income_contents":inc_map["ContentsCode"],
 "notes":[
   "BAS age slices are retained separately; overlapping age groups are never summed.",
   "Car fuel categories are mutually exclusive and may be summed to total new registrations.",
   "Income history begins in 2025 and is diagnostic/realtime only until longer history exists."
 ]
}
META.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
