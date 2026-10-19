#!/usr/bin/env python3
import csv, io, json, urllib.request
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

OUT=Path("docs/data/short_term_monthly_candidate_family_1.csv")
META=Path("docs/data/short_term_monthly_candidate_family_1_manifest.json")

def post_csv(url, query):
    body=json.dumps({"query":query,"response":{"format":"csv"}}).encode()
    req=urllib.request.Request(url,data=body,headers={
        "Content-Type":"application/json",
        "User-Agent":"Lulea-statistik-short-term-monthly/1.0"
    })
    with urllib.request.urlopen(req,timeout=120) as r:
        payload=r.read()
        ctype=r.headers.get_content_charset()
    encodings=[ctype,"utf-8-sig","utf-8","cp1252","latin-1"]
    raw=None
    for enc in [e for e in encodings if e]:
        try:
            raw=payload.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        raise UnicodeDecodeError("unknown",payload,0,1,"Could not decode SCB CSV response")
    return list(csv.DictReader(io.StringIO(raw),delimiter=";"))

def allq(code):
    return {"code":code,"selection":{"filter":"all","values":["*"]}}

BAS_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0210/AM0210B/YrkStallningM"
CKM_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101G/MBefStatRegionCKM"
GDP_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/NR/NR9999/NR9999A/NR9999ENS2010BNPIndN"
ASYL_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101P/AsylsokandeN"

# BAS: Lulea, total occupation status/sex/birth region, aggregate age categories are not guaranteed.
# Use all ages then aggregate only where an explicit total age category is present; otherwise sum disjoint age bins.
bas=post_csv(BAS_URL,[
 {"code":"Region","selection":{"filter":"item","values":["2580"]}},
 {"code":"Yrkesstallning","selection":{"filter":"item","values":["TOT"]}},
 {"code":"Kon","selection":{"filter":"item","values":["1+2"]}},
 allq("Alder"),
 {"code":"Fodelseregion","selection":{"filter":"item","values":["tot"]}},
 allq("ContentsCode"), allq("Tid")
])

# CKM: all change types for Lulea, total sex.
ckm=post_csv(CKM_URL,[
 {"code":"Region","selection":{"filter":"item","values":["2580"]}},
 allq("Forandringar"),
 {"code":"Kon","selection":{"filter":"item","values":["TotSa"]}},
 allq("ContentsCode"), allq("Tid")
])

# GDP: all six published contents.
gdp=post_csv(GDP_URL,[allq("BNPMarknadspris"),allq("ContentsCode"),allq("Tid")])

# Asylum: all citizenship, total sex, monthly periods only + years.
asyl=post_csv(ASYL_URL,[
 {"code":"Medbland","selection":{"filter":"item","values":["SAMTL"]}},
 {"code":"Kon","selection":{"filter":"item","values":["1+2"]}},
 allq("Period"),allq("ContentsCode"),allq("Tid")
])

rows=defaultdict(dict)
def num(x):
    if x is None: return None
    x=str(x).replace(" ","").replace(",",".")
    try: return float(x)
    except: return None

# BAS CSV headers are labels, not codes. Detect.
if bas:
    keys=list(bas[0])
    timek=next(k for k in keys if k.lower()=="månad")
    agek=next(k for k in keys if k.lower()=="ålder")
    contentk=next(k for k in keys if k.lower()=="tabellinnehåll")
    valk=next(k for k in keys if k not in {"region","yrkesställning","kön","ålder","födelseregion","tabellinnehåll","månad"})
    by=defaultdict(lambda:defaultdict(list))
    for r in bas:
        by[r[timek]][r[contentk]].append((r[agek],num(r[valk])))
    for m,contents in by.items():
        for label, vals in contents.items():
            explicit=[v for a,v in vals if a.lower() in ("totalt","15–74 år","15-74 år") and v is not None]
            if explicit:
                total=explicit[0]
            else:
                # published age classes overlap in some tables; only sum if unique disjoint bins can be identified.
                # Prefer widest explicit categories; otherwise leave NA rather than risk double count.
                total=None
            if "arbetsställets" in label:
                rows[m]["bas_workplace_employed"]=total
            elif "bostadens" in label:
                rows[m]["bas_residence_employed"]=total

# CKM: store all change labels as slug columns.
if ckm:
    keys=list(ckm[0]); timek=next(k for k in keys if k.lower()=="månad")
    changek=next(k for k in keys if k.lower()=="förändringar")
    valk=next(k for k in keys if k not in {"region","förändringar","kön","tabellinnehåll","månad"})
    import re, unicodedata
    def slug(s):
        s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+","_",s).strip("_")
    for r in ckm:
        rows[r[timek]]["ckm_"+slug(r[changek])]=num(r[valk])

# GDP all content labels.
if gdp:
    keys=list(gdp[0]); timek=next(k for k in keys if k.lower()=="månad")
    contentk=next(k for k in keys if k.lower()=="tabellinnehåll")
    valk=next(k for k in keys if k not in {"bnp, marknadspris","tabellinnehåll","månad"})
    import re, unicodedata
    def slug2(s):
        s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+","_",s).strip("_")
    for r in gdp:
        rows[r[timek]]["gdp_"+slug2(r[contentk])]=num(r[valk])

# Asylum monthly Period labels.
months_sv={"januari":1,"februari":2,"mars":3,"april":4,"maj":5,"juni":6,"juli":7,"augusti":8,"september":9,"oktober":10,"november":11,"december":12}
if asyl:
    keys=list(asyl[0]); periodk=next(k for k in keys if k.lower()=="period")
    yeark=next(k for k in keys if k.lower()=="år")
    valk=next(k for k in keys if k not in {"medborgarskapsland","kön","period","tabellinnehåll","år"})
    for r in asyl:
        p=r[periodk].lower()
        if p in months_sv:
            m=f"{r[yeark]}M{months_sv[p]:02d}"
            rows[m]["asylum_seekers_sweden"]=num(r[valk])

# Derived features from raw monthly series.
def month_key(s):
    y=int(s[:4]); m=int(s[-2:]); return y*12+m
ordered=sorted(rows,key=month_key)
index={month_key(m):m for m in ordered}
for m in ordered:
    k=month_key(m)
    d=rows[m]
    for col in ["bas_workplace_employed","bas_residence_employed","ckm_folkmangd","asylum_seekers_sweden"]:
        v=d.get(col)
        if v is not None:
            prev=rows.get(index.get(k-12),{}).get(col) if index.get(k-12) else None
            prev3=rows.get(index.get(k-3),{}).get(col) if index.get(k-3) else None
            prev6=rows.get(index.get(k-6),{}).get(col) if index.get(k-6) else None
            if prev not in (None,0): d[col+"_yoy_pct"]=100*(v/prev-1)
            if prev3 not in (None,0): d[col+"_change_3m_pct"]=100*(v/prev3-1)
            if prev6 not in (None,0): d[col+"_change_6m_pct"]=100*(v/prev6-1)
    a=d.get("bas_workplace_employed"); b=d.get("bas_residence_employed")
    if a is not None and b is not None:
        d["bas_workplace_minus_residence"]=a-b
        if b: d["bas_workplace_residence_gap_pct"]=100*(a/b-1)

allcols=sorted({k for d in rows.values() for k in d})
with OUT.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["month"]+allcols)
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
 "notes":[
  "Raw SCB series are preserved before derived features.",
  "BAS totals are only populated when an explicit total-age observation is available; overlapping age groups are not summed.",
  "CKM has short history and is primarily a real-time/nowcast signal.",
  "No forecasting model is fitted in this build step."
 ]
}
META.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
