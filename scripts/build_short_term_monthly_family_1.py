#!/usr/bin/env python3
import csv, json, re, unicodedata, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

OUT=Path("docs/data/short_term_monthly_candidate_family_1.csv")
META=Path("docs/data/short_term_monthly_candidate_family_1_manifest.json")

BAS_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210B/YrkStallningM"
CKM_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101G/MBefStatRegionCKM"
GDP_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/NR/NR9999/NR9999A/NR9999ENS2010BNPIndN"
ASYL_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101P/AsylsokandeN"

def get_meta(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Lulea-statistik-short-term-monthly/1.0"})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.load(r)

def post_json(url, query):
    body=json.dumps({"query":query,"response":{"format":"json"}}).encode()
    req=urllib.request.Request(url,data=body,headers={
        "Content-Type":"application/json",
        "User-Agent":"Lulea-statistik-short-term-monthly/1.0"
    })
    with urllib.request.urlopen(req,timeout=120) as r:
        return json.load(r)

def item(code, values):
    return {"code":code,"selection":{"filter":"item","values":values}}

def allq(code):
    return {"code":code,"selection":{"filter":"all","values":["*"]}}

def meta_maps(meta):
    out={}
    for v in meta.get("variables",[]):
        vals=v.get("values",[])
        texts=v.get("valueTexts",[])
        out[v["code"]]=dict(zip(vals,texts))
    return out

def rows_from_classic_json(payload):
    cols=[c["code"] for c in payload.get("columns",[])]
    out=[]
    for rec in payload.get("data",[]):
        row=dict(zip(cols,rec.get("key",[])))
        vals=rec.get("values",[])
        row["_value"]=vals[0] if vals else None
        out.append(row)
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

# ---- metadata ----
bas_meta=get_meta(BAS_URL); bas_map=meta_maps(bas_meta)
ckm_meta=get_meta(CKM_URL); ckm_map=meta_maps(ckm_meta)
gdp_meta=get_meta(GDP_URL); gdp_map=meta_maps(gdp_meta)
asyl_meta=get_meta(ASYL_URL); asyl_map=meta_maps(asyl_meta)

# Find a non-overlapping total age category if SCB publishes one.
age_values=bas_map.get("Alder",{})
total_age_candidates=[
    code for code,text in age_values.items()
    if str(text).lower() in ("totalt","15–74 år","15-74 år","15–74","15-74")
]
if not total_age_candidates:
    # Do not sum overlapping published age bands. Keep BAS extraction valid but mark total unavailable.
    bas_age_values=list(age_values.keys())
    bas_total_age_code=None
else:
    bas_total_age_code=total_age_candidates[0]
    bas_age_values=[bas_total_age_code]

# ---- fetch ----
bas=[]
for content_code in bas_map.get("ContentsCode",{}):
    payload=post_json(BAS_URL,[
        item("Region",["2580"]),
        item("Yrkesstallning",["TOT"]),
        item("Kon",["1+2"]),
        item("Alder",bas_age_values),
        item("Fodelseregion",["tot"]),
        item("ContentsCode",[content_code]),
        allq("Tid")
    ])
    part=rows_from_classic_json(payload)
    for r in part:
        r["ContentsCode"]=content_code
    bas.extend(part)

ckm_payload=post_json(CKM_URL,[
    item("Region",["2580"]),
    allq("Forandringar"),
    item("Kon",["TotSa"]),
    allq("ContentsCode"),
    allq("Tid")
])
ckm=rows_from_classic_json(ckm_payload)

gdp=[]
for content_code in gdp_map.get("ContentsCode",{}):
    payload=post_json(GDP_URL,[
        allq("BNPMarknadspris"),
        item("ContentsCode",[content_code]),
        allq("Tid")
    ])
    part=rows_from_classic_json(payload)
    for r in part:
        r["ContentsCode"]=content_code
    gdp.extend(part)

# Asylum table has year in Tid and month in Period.
monthly_period_codes=[
    code for code,text in asyl_map.get("Period",{}).items()
    if str(text).lower() in {
      "januari","februari","mars","april","maj","juni",
      "juli","augusti","september","oktober","november","december"
    }
]
asyl_payload=post_json(ASYL_URL,[
    item("Medbland",["SAMTL"]),
    item("Kon",["1+2"]),
    item("Period",monthly_period_codes),
    allq("ContentsCode"),
    allq("Tid")
])
asyl=rows_from_classic_json(asyl_payload)

rows=defaultdict(dict)

# BAS
for r in bas:
    m=r.get("Tid")
    if not m: continue
    label=bas_map.get("ContentsCode",{}).get(r.get("ContentsCode"),r.get("ContentsCode",""))
    if bas_total_age_code is not None and r.get("Alder")==bas_total_age_code:
        if "arbetsställets" in str(label):
            rows[m]["bas_workplace_employed"]=num(r["_value"])
        elif "bostadens" in str(label):
            rows[m]["bas_residence_employed"]=num(r["_value"])

# CKM all published change components
for r in ckm:
    m=r.get("Tid")
    if not m: continue
    label=ckm_map.get("Forandringar",{}).get(r.get("Forandringar"),r.get("Forandringar",""))
    rows[m]["ckm_"+slug(label)]=num(r["_value"])

# GDP all six contents
for r in gdp:
    m=r.get("Tid")
    if not m: continue
    label=gdp_map.get("ContentsCode",{}).get(r.get("ContentsCode"),r.get("ContentsCode",""))
    rows[m]["gdp_"+slug(label)]=num(r["_value"])

# Asylum month mapping from metadata labels
month_no={"januari":1,"februari":2,"mars":3,"april":4,"maj":5,"juni":6,
          "juli":7,"augusti":8,"september":9,"oktober":10,"november":11,"december":12}
for r in asyl:
    year=r.get("Tid"); pcode=r.get("Period")
    plabel=str(asyl_map.get("Period",{}).get(pcode,pcode)).lower()
    if year and plabel in month_no:
        m=f"{year}M{month_no[plabel]:02d}"
        rows[m]["asylum_seekers_sweden"]=num(r["_value"])

# Derived features
def mk(s):
    return int(s[:4])*12+int(s[-2:])

ordered=sorted(rows,key=mk)
byk={mk(m):m for m in ordered}
raw_candidates=[
    "bas_workplace_employed","bas_residence_employed",
    "ckm_folkmangd","asylum_seekers_sweden"
]
for m in ordered:
    k=mk(m); d=rows[m]
    for col in raw_candidates:
        v=d.get(col)
        if v is None: continue
        for lag,suffix in [(12,"yoy_pct"),(3,"change_3m_pct"),(6,"change_6m_pct")]:
            pm=byk.get(k-lag)
            prev=rows[pm].get(col) if pm else None
            if prev not in (None,0):
                d[col+"_"+suffix]=100*(v/prev-1)
    a=d.get("bas_workplace_employed"); b=d.get("bas_residence_employed")
    if a is not None and b is not None:
        d["bas_workplace_minus_residence"]=a-b
        if b:
            d["bas_workplace_residence_gap_pct"]=100*(a/b-1)

# Drop months that contain no actual observation in any source.
rows={m:d for m,d in rows.items() if any(v is not None and v != "" for v in d.values())}
ordered=sorted(rows,key=mk)

allcols=sorted({key for d in rows.values() for key in d})
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",newline="",encoding="utf-8") as fh:
    w=csv.DictWriter(fh,fieldnames=["month"]+allcols)
    w.writeheader()
    for m in ordered:
        w.writerow({"month":m,**rows[m]})

manifest={
    "status":"short_term_monthly_candidate_family_1_built",
    "generated_at_utc":datetime.now(timezone.utc).isoformat(),
    "production_changed":False,
    "structural_core4_changed":False,
    "rows":len(ordered),
    "first_month":ordered[0] if ordered else None,
    "last_month":ordered[-1] if ordered else None,
    "columns":allcols,
    "source_row_counts":{"bas":len(bas),"ckm":len(ckm),"gdp":len(gdp),"asylum":len(asyl)},
    "bas_total_age_code":bas_total_age_code,
    "bas_total_age_label":age_values.get(bas_total_age_code) if bas_total_age_code else None,
    "quality_checks":{
      "has_bas_workplace":"bas_workplace_employed" in allcols,
      "has_bas_residence":"bas_residence_employed" in allcols,
      "gdp_content_columns":[x for x in allcols if x.startswith("gdp_")],
      "has_ckm_population":"ckm_folkmangd" in allcols,
      "has_asylum":"asylum_seekers_sweden" in allcols
    },
    "notes":[
      "SCB classic JSON is used instead of CSV so dimensions are addressed by stable API codes.",
      "Each multi-content SCB table is queried one ContentsCode at a time so measures cannot collapse into one unnamed value.",
      "Raw SCB series are preserved before derived features.",
      "BAS totals are populated only if SCB exposes an explicit total-age category; overlapping age groups are never summed.",
      "CKM has short history and is primarily a real-time/nowcast signal.",
      "No forecasting model is fitted in this build step."
    ]
}
META.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
