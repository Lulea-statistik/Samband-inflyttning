#!/usr/bin/env python3
"""Build annual municipal birth/death targets from SCB municipal event tables.

Municipal targets:
- fodelsetal_per_100 = live births / mean population * 100
- dodstal_per_1000 = deaths / mean population * 1000

Counts:
- FoddaK
- DodaHandelseK

Population:
- existing verified project panel.csv, folkmangd
Mean population is approximated as average of year-end population in Y-1 and Y,
matching the usual crude-rate denominator much better than a single year-end stock.

Regional HVD tables are not used as municipal targets because FodelstalHVD exposes
only 31 regional aggregates in the current SCB publication.
"""
import json,re
from pathlib import Path
import numpy as np
import pandas as pd
import requests

D=Path("docs/data")
BIRTH_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101H/FoddaK"
DEATH_URL="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101I/DodaHandelseK"
YEARS=list(range(2013,2025))
S=requests.Session();S.headers.update({"User-Agent":"Samband-inflyttning-demographic-targets/2.0"})

def meta(url):
    r=S.get(url,timeout=90);r.raise_for_status();return r.json()

def municipality_var(m):
    cand=[]
    for v in m["variables"]:
        vals=v.get("values",[])
        n=sum(bool(re.fullmatch(r"\d{4}",str(x))) for x in vals)
        if n>=250:cand.append((n,v))
    if not cand:
        raise RuntimeError("No municipality dimension with >=250 four-digit codes")
    return max(cand,key=lambda x:x[0])[1]

def time_var(m):
    x=[v for v in m["variables"] if v.get("time")]
    if x:return x[0]
    for v in m["variables"]:
        if "tid" in v.get("code","").lower() or "år" in v.get("text","").lower():
            return v
    raise RuntimeError("No time dimension")

def pairs(v):
    return list(zip(v["values"],v.get("valueTexts",v["values"])))

def total_code(v):
    pref=[
      ("totalt",),("samtliga",),("båda","könen"),("bada","konen"),
      ("alla",),("samtliga","åldrar"),("samtliga","aldrar")
    ]
    for terms in pref:
        for code,txt in pairs(v):
            t=str(txt).lower()
            if all(term in t for term in terms):
                return code
    return None

def jsonstat2_df(js):
    ids=js["id"];sizes=js["size"];vals=js["value"];cats=[]
    for d in ids:
        idx=js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx,key=idx.get) if isinstance(idx,dict) else list(idx))
    rows=[]
    for flat,val in enumerate(vals):
        if val is None:continue
        rem=flat;pos=[]
        for sz in reversed(sizes):
            pos.append(rem%sz);rem//=sz
        pos=list(reversed(pos))
        row={d:cats[i][pos[i]] for i,d in enumerate(ids)}
        row["value"]=float(val);rows.append(row)
    return pd.DataFrame(rows)

def fetch_counts(url,label):
    m=meta(url);rv=municipality_var(m);tv=time_var(m)
    regions=[str(x) for x in rv["values"] if re.fullmatch(r"\d{4}",str(x))]
    years=[str(y) for y in YEARS if str(y) in set(map(str,tv["values"]))]
    q=[{"code":rv["code"],"selection":{"filter":"item","values":regions}}]
    expanded=[]
    for v in m["variables"]:
        if v["code"] in (rv["code"],tv["code"]):continue
        tc=total_code(v)
        if tc is not None:
            vals=[tc]
        else:
            vals=list(v["values"])
            expanded.append(v["code"])
        q.append({"code":v["code"],"selection":{"filter":"item","values":vals}})
    q.append({"code":tv["code"],"selection":{"filter":"item","values":years}})
    r=S.post(url,json={"query":q,"response":{"format":"json-stat2"}},timeout=180)
    r.raise_for_status();df=jsonstat2_df(r.json())
    # SCB response IDs should match query codes; resolve case-insensitively as fallback.
    cmap={str(c).lower():c for c in df.columns}
    rc=rv["code"] if rv["code"] in df else cmap.get(rv["code"].lower())
    tc=tv["code"] if tv["code"] in df else cmap.get(tv["code"].lower())
    if rc is None or tc is None:
        raise RuntimeError(f"{label}: response dimensions missing. columns={list(df.columns)}")
    df["kommun_kod"]=df[rc].astype(str).str.zfill(4)
    df["year"]=pd.to_numeric(df[tc],errors="raise").astype(int)
    out=df.groupby(["kommun_kod","year"],as_index=False)["value"].sum().rename(columns={"value":f"{label}_count"})
    if out.kommun_kod.nunique()!=290:
        raise RuntimeError(f"{label}: expected 290 municipalities, got {out.kommun_kod.nunique()}")
    return out,{
      "url":url,"municipality_dimension":rv["code"],"time_dimension":tv["code"],
      "expanded_non_total_dimensions":expanded,"years":years,"municipalities":len(regions)
    }

birth,bq=fetch_counts(BIRTH_URL,"birth")
death,dq=fetch_counts(DEATH_URL,"death")

p=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
p["kommun_kod"]=p["kommun_kod"].astype(str).str.zfill(4)
if "folkmangd" not in p.columns:
    raise RuntimeError("panel.csv lacks folkmangd")
pop=p[["kommun_kod","year","folkmangd"]].copy()
pop["folkmangd"]=pd.to_numeric(pop["folkmangd"],errors="coerce")
pop=pop.sort_values(["kommun_kod","year"])
pop["folkmangd_prev"]=pop.groupby("kommun_kod")["folkmangd"].shift(1)
pop["mean_population"]=(pop["folkmangd"]+pop["folkmangd_prev"])/2.0
pop=pop[pop.year.isin(YEARS)]

out=(birth.merge(death,on=["kommun_kod","year"],how="inner",validate="one_to_one")
          .merge(pop,on=["kommun_kod","year"],how="inner",validate="one_to_one"))
if out.mean_population.isna().any():
    raise RuntimeError("Missing mean population denominator")
out["fodelsetal_per_100"]=100.0*out["birth_count"]/out["mean_population"]
out["dodstal_per_1000"]=1000.0*out["death_count"]/out["mean_population"]
out=out.sort_values(["kommun_kod","year"])

counts=out.groupby("year").kommun_kod.nunique()
if not (counts==290).all():
    raise RuntimeError(f"Unbalanced targets: {counts.to_dict()}")

cols=["kommun_kod","year","birth_count","death_count","mean_population","fodelsetal_per_100","dodstal_per_1000"]
out[cols].to_csv(D/"demographic_birth_death_targets.csv",index=False)
manifest={
 "status":"demographic_birth_death_targets_built",
 "production_changed":False,
 "municipalities":290,
 "first_year":int(out.year.min()),"last_year":int(out.year.max()),"rows":int(len(out)),
 "birth_target":"fodelsetal_per_100",
 "birth_definition":"live births from SCB FoddaK divided by average of Y-1 and Y year-end municipal population, times 100",
 "death_target":"dodstal_per_1000",
 "death_definition":"deaths from SCB DodaHandelseK divided by average of Y-1 and Y year-end municipal population, times 1000",
 "birth_source":bq,"death_source":dq,
 "population_source":"docs/data/panel.csv folkmangd",
 "regional_hvd_tables_used_as_targets":False,
 "regional_hvd_reason":"FodelstalHVD current publication contains 31 regional aggregates, not 290 municipalities",
 "same_year_target_leakage":False
}
(D/"demographic_birth_death_targets_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(D/"demographic_birth_query.json").write_text(json.dumps(bq,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(D/"demographic_death_query.json").write_text(json.dumps(dq,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
print(out[out.kommun_kod.eq("2580")][cols].tail(5).to_string(index=False))
