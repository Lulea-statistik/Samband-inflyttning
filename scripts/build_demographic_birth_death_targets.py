#!/usr/bin/env python3
"""Build annual municipal birth/death rate targets from SCB.

Targets:
- fodelsetal_per_100 = SCB births per 1,000 of mean population / 10
- dodstal_per_1000 = SCB deaths per 1,000 of mean population

The birth target is intentionally rescaled to per 100 to match the project
definition. This is a pure scale transform of SCB's official per-1,000 rate.

No model code is imported or run here.
"""
import json, re
from pathlib import Path
import pandas as pd
import requests

OUT=Path("docs/data")
OUT.mkdir(parents=True,exist_ok=True)

BIRTH_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101H/FodelstalHVD"
DEATH_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101I/DodstalHVD"
YEARS=[str(y) for y in range(2013,2026)]

S=requests.Session()
S.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-demographic-targets/1.0"})

def get(url):
    r=S.get(url,timeout=90); r.raise_for_status(); return r.json()

def post(url,q):
    r=S.post(url,json=q,timeout=180); r.raise_for_status(); return r.json()

def var(meta, pred):
    for v in meta["variables"]:
        if pred(v): return v
    raise KeyError("Variable not found")

def textmap(v):
    return dict(zip(v["values"],v.get("valueTexts",v["values"])))

def total_code(v):
    pairs=list(zip(v["values"],v.get("valueTexts",v["values"])))
    preferred=("totalt","samtliga","båda könen","bada konen","samtliga åldrar")
    for code,txt in pairs:
        if str(txt).strip().lower() in preferred:return code
    for code,txt in pairs:
        t=str(txt).strip().lower()
        if "samtliga åldrar" in t or "båda könen" in t or "totalt" in t:return code
    return None

def query_all_regions(meta, extra_totals=False):
    # Identify the municipal geography dimension from its values, not merely its label.
    # SCB content dimensions can contain the word "region" in their descriptive text.
    region_candidates=[]
    for v in meta["variables"]:
        municipal_codes=[x for x in v.get("values",[]) if re.fullmatch(r"\d{4}",str(x))]
        if len(municipal_codes)>=250:
            region_candidates.append((len(municipal_codes),v))
    if not region_candidates:
        raise KeyError("No SCB dimension with >=250 four-digit municipality codes found")
    region=max(region_candidates,key=lambda z:z[0])[1]

    time_candidates=[v for v in meta["variables"] if v.get("time")]
    if time_candidates:
        time=time_candidates[0]
    else:
        time=var(meta,lambda v:"tid" in v.get("code","").lower() or "år" in v.get("text","").lower())

    regions=[x for x in region["values"] if re.fullmatch(r"\d{4}",str(x))]
    if len(regions)!=290:
        raise RuntimeError(f"Expected 290 municipality codes in SCB region dimension, got {len(regions)}; code={region.get('code')}")
    q=[
      {"code":region["code"],"selection":{"filter":"item","values":regions}}
    ]
    for v in meta["variables"]:
        if v["code"] in (region["code"],time["code"]):continue
        tc=total_code(v)
        if tc is not None:
            q.append({"code":v["code"],"selection":{"filter":"item","values":[tc]}})
        else:
            # Content dimensions normally have a single rate value in these tables.
            q.append({"code":v["code"],"selection":{"filter":"item","values":[v["values"][0]]}})
    available=set(str(x) for x in time["values"])
    years=[y for y in YEARS if y in available]
    q.append({"code":time["code"],"selection":{"filter":"item","values":years}})
    return q,region["code"],time["code"],regions,years

def jsonstat2_df(js):
    dims=js["id"]; sizes=js["size"]; vals=js["value"]; cats=[]
    for d in dims:
        idx=js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx,key=idx.get) if isinstance(idx,dict) else list(idx))
    rows=[]
    for flat,value in enumerate(vals):
        if value is None:continue
        rem=flat; pos=[]
        for size in reversed(sizes):
            pos.append(rem%size); rem//=size
        pos=list(reversed(pos))
        row={d:cats[i][pos[i]] for i,d in enumerate(dims)}
        row["value"]=float(value); rows.append(row)
    return pd.DataFrame(rows)

def resolve_response_column(df, preferred, kind):
    """Resolve JSON-stat response dimension IDs robustly across SCB schemas."""
    cols=list(df.columns)
    if preferred in cols:
        return preferred
    lower={str(x).lower():x for x in cols}
    if str(preferred).lower() in lower:
        return lower[str(preferred).lower()]
    needles={
      "region":["region","kommun"],
      "time":["tid","år","ar","year"]
    }[kind]
    for col in cols:
        s=str(col).lower()
        if any(n in s for n in needles):
            return col
    raise KeyError(f"Could not resolve {kind} response column. preferred={preferred!r}, columns={cols}")

def build(url,label):
    meta=get(url)
    q,region_code,time_code,regions,years=query_all_regions(meta)
    payload={"query":q,"response":{"format":"json-stat2"}}
    js=post(url,payload)
    df=jsonstat2_df(js)
    if df.empty:
        raise RuntimeError(f"{label}: SCB returned no observations")
    response_region=resolve_response_column(df,region_code,"region")
    response_time=resolve_response_column(df,time_code,"time")
    df["kommun_kod"]=df[response_region].astype(str).str.zfill(4)
    df["year"]=pd.to_numeric(df[response_time],errors="raise").astype(int)
    out=df.groupby(["kommun_kod","year"],as_index=False)["value"].sum()
    return meta,payload,out,regions,years

bm,bq,b,br,by=build(BIRTH_URL,"birth")
dm,dq,d,dr,dy=build(DEATH_URL,"death")

b=b.rename(columns={"value":"fodelsetal_per_1000_scb"})
b["fodelsetal_per_100"]=b["fodelsetal_per_1000_scb"]/10.0
d=d.rename(columns={"value":"dodstal_per_1000"})

panel=b.merge(d,on=["kommun_kod","year"],how="inner",validate="one_to_one")
panel=panel.sort_values(["kommun_kod","year"])
if panel.kommun_kod.nunique()!=290:
    raise RuntimeError(f"Expected 290 municipalities, got {panel.kommun_kod.nunique()}")

panel.to_csv(OUT/"demographic_birth_death_targets.csv",index=False)
(OUT/"demographic_birth_death_targets_manifest.json").write_text(json.dumps({
 "status":"demographic_birth_death_targets_built",
 "production_changed":False,
 "municipalities":int(panel.kommun_kod.nunique()),
 "first_year":int(panel.year.min()),
 "last_year":int(panel.year.max()),
 "rows":int(len(panel)),
 "birth_target":"fodelsetal_per_100",
 "birth_definition":"SCB FodelstalHVD births per 1,000 of mean population divided by 10",
 "death_target":"dodstal_per_1000",
 "death_definition":"SCB DodstalHVD deaths per 1,000 of mean population",
 "birth_source":BIRTH_URL,
 "death_source":DEATH_URL,
 "birth_years_requested":by,
 "death_years_requested":dy,
 "scb_birth_rate_original_unit":"per 1,000 of mean population",
 "project_birth_rate_unit":"per 100 of mean population",
 "model_code_imported":False
},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"demographic_birth_query.json").write_text(json.dumps(bq,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"demographic_death_query.json").write_text(json.dumps(dq,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(panel.groupby("year").size().to_string())
