#!/usr/bin/env python3
"""Build laggable demographic candidate features for birth/death models from SCB.

All raw features are annual municipality-level summaries. The modeling script
applies lag 1 year before model selection, preventing same-year target leakage.

Source families:
Birth/fertility:
- FoddaK: births by mother's age
- MedelAlder1: mean parental age at birth (mothers)
- FruktsamhetHVD: age-specific fertility rates
- FruktsamhetSum: total fertility rate (women)
Death/mortality:
- DodaFodelsearK: deaths by age
- DodaHandelseK: deaths by attained age
- DodaManadReg: monthly deaths (seasonality)
- DodFoddaAlderMorK1: stillbirths by mother's age

FodelstalHVD and DodstalHVD are modeled targets and enter only through their
lagged target histories in the model script.
"""
import json,re
from pathlib import Path
import numpy as np
import pandas as pd
import requests

D=Path("docs/data"); D.mkdir(parents=True,exist_ok=True)
BASE="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101"
URLS={
 "fodda":"BE0101H/FoddaK",
 "medelalder":"BE0101H/MedelAlder1",
 "fruktsamhet_alder":"BE0101H/FruktsamhetHVD",
 "fruktsamhet_sum":"BE0101H/FruktsamhetSum",
 "doda_fodelsear":"BE0101I/DodaFodelsearK",
 "doda_handelse":"BE0101I/DodaHandelseK",
 "doda_manad":"BE0101I/DodaManadReg",
 "dodfodda":"BE0101I/DodFoddaAlderMorK1",
}
YEARS=set(str(y) for y in range(2017,2025))
S=requests.Session();S.headers.update({"User-Agent":"Samband-inflyttning-demographic-feature-pool/1.0"})

def getmeta(url):
    r=S.get(url,timeout=90);r.raise_for_status();return r.json()
def post(url,q):
    r=S.post(url,json={"query":q,"response":{"format":"json-stat2"}},timeout=180)
    r.raise_for_status();return r.json()

def municipalities(v):
    return [x for x in v.get("values",[]) if re.fullmatch(r"\d{4}",str(x))]
def region_var(meta):
    c=[v for v in meta["variables"] if len(municipalities(v))>=250]
    if not c: raise RuntimeError("municipality dimension not found")
    return max(c,key=lambda v:len(municipalities(v)))
def time_var(meta):
    c=[v for v in meta["variables"] if v.get("time")]
    if c:return c[0]
    c=[v for v in meta["variables"] if "tid" in v.get("code","").lower() or "år" in v.get("text","").lower()]
    if not c:raise RuntimeError("time dimension not found")
    return c[0]
def pairs(v): return list(zip(v["values"],v.get("valueTexts",v["values"])))
def find_value(v,needles,default=None):
    needles=[n.lower() for n in needles]
    for code,txt in pairs(v):
        t=str(txt).lower()
        if all(n in t for n in needles): return code
    return default
def total_value(v):
    for terms in (["totalt"],["samtliga"],["båda","könen"],["alla"]):
        x=find_value(v,terms)
        if x is not None:return x
    return None
def query(meta, all_dimensions=None, selectors=None, region_values=None):
    all_dimensions=set(all_dimensions or [])
    selectors=selectors or {}
    rv=region_var(meta);tv=time_var(meta)
    regs=list(region_values) if region_values is not None else municipalities(rv)
    q=[{"code":rv["code"],"selection":{"filter":"item","values":regs}}]
    for v in meta["variables"]:
        if v["code"] in (rv["code"],tv["code"]):continue
        if v["code"] in selectors:
            vals=selectors[v["code"]]
        elif v["code"] in all_dimensions:
            vals=list(v["values"])
        else:
            t=total_value(v)
            vals=[t] if t is not None else list(v["values"])
        q.append({"code":v["code"],"selection":{"filter":"item","values":vals}})
    # annual tables use YYYY; monthly tables use YYYY[M]MM or YYYYMM-like labels
    vals=[x for x in tv["values"] if str(x)[:4] in YEARS]
    q.append({"code":tv["code"],"selection":{"filter":"item","values":vals}})
    return q,rv,tv

def jsdf(js):
    ids=js["id"];sizes=js["size"];vals=js["value"]; cats=[]
    for d in ids:
        idx=js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx,key=idx.get) if isinstance(idx,dict) else list(idx))
    rows=[]
    for flat,val in enumerate(vals):
        if val is None:continue
        rem=flat;pos=[]
        for sz in reversed(sizes):pos.append(rem%sz);rem//=sz
        pos=list(reversed(pos))
        row={d:cats[i][pos[i]] for i,d in enumerate(ids)};row["value"]=float(val);rows.append(row)
    return pd.DataFrame(rows)

def response_col(df,preferred,kind):
    if preferred in df:return preferred
    low={str(c).lower():c for c in df.columns}
    if preferred.lower() in low:return low[preferred.lower()]
    needles={"region":["region","kommun"],"time":["tid","år","time"]}[kind]
    for c in df.columns:
        if any(n in str(c).lower() for n in needles):return c
    raise RuntimeError(f"{kind} response column not found: {list(df.columns)}")

def fetch(name, all_dims=None, selectors_fn=None, chunk_regions=False):
    url=f"{BASE}/{URLS[name]}";meta=getmeta(url)
    selectors=selectors_fn(meta) if selectors_fn else {}
    rv=region_var(meta); regs=municipalities(rv)
    chunks=[regs]
    if chunk_regions:
        chunks=[regs[i:i+60] for i in range(0,len(regs),60)]
    frames=[]
    tv=None
    for reg_chunk in chunks:
        q,rv,tv=query(meta,all_dims,selectors,region_values=reg_chunk)
        frames.append(jsdf(post(url,q)))
    df=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    rc=response_col(df,rv["code"],"region");tc=response_col(df,tv["code"],"time")
    df["kommun_kod"]=df[rc].astype(str).str.zfill(4)
    df["period"]=df[tc].astype(str)
    df["year"]=pd.to_numeric(df["period"].str[:4],errors="coerce").astype("Int64")
    labels={}
    for v in meta["variables"]:
        labels[v["code"]]=dict(pairs(v))
    return df,meta,labels,url

def age_num(label):
    s=str(label).lower().replace("–","-").replace("−","-")
    nums=[int(x) for x in re.findall(r"\d+",s)]
    if not nums:return None
    return nums[0]

def annual_age_summary(df,meta,labels,prefix):
    agev=next((v for v in meta["variables"] if "ålder" in v.get("text","").lower()),None)
    if agev is None:raise RuntimeError("age dimension absent")
    ac=agev["code"]; amap=labels[ac]
    d=df.copy();d["age_label"]=d[ac].map(amap);d["age0"]=d["age_label"].map(age_num)
    d=d[d.age0.notna()]
    grp=d.groupby(["kommun_kod","year"],as_index=False)["value"].sum().rename(columns={"value":f"{prefix}_total"})
    total=d.groupby(["kommun_kod","year"])["value"].sum()
    bins={"0_64":(0,64),"65_79":(65,79),"80_plus":(80,999)}
    for key,(lo,hi) in bins.items():
        x=d[d.age0.between(lo,hi)].groupby(["kommun_kod","year"])["value"].sum()
        grp=grp.merge((100*x/total).rename(f"{prefix}_share_{key}_pct").reset_index(),
                      on=["kommun_kod","year"],how="left")
    return grp

features=[]; manifest={"status":"demographic_scb_feature_pool","sources":{},"same_year_target_leakage_allowed":False}

# Births by mother's age -> shares.
try:
    df,meta,lab,url=fetch("fodda",all_dims=[next(v["code"] for v in getmeta(f"{BASE}/{URLS['fodda']}")["variables"] if "moderns ålder" in v.get("text","").lower())],chunk_regions=True)
    av=next(v for v in meta["variables"] if "moderns ålder" in v.get("text","").lower());ac=av["code"]
    d=df.copy();d["alabel"]=d[ac].map(lab[ac]);d["age0"]=d.alabel.map(age_num);d=d[d.age0.notna()]
    # sum child sex if sex dimension remained expanded
    g=d.groupby(["kommun_kod","year","age0"],as_index=False)["value"].sum()
    tot=g.groupby(["kommun_kod","year"])["value"].sum()
    out=tot.rename("fodda_total").reset_index()
    for key,lo,hi in [("mor_15_24",0,24),("mor_25_29",25,29),("mor_30_34",30,34),("mor_35_39",35,39),("mor_40_plus",40,99)]:
        x=g[g.age0.between(lo,hi)].groupby(["kommun_kod","year"])["value"].sum()
        out=out.merge((100*x/tot).rename(f"fodda_share_{key}_pct").reset_index(),on=["kommun_kod","year"],how="left")
    features.append(out);manifest["sources"]["FoddaK"]={"ok":True,"url":url,"features":[c for c in out if c not in ("kommun_kod","year")]}
except Exception as e:manifest["sources"]["FoddaK"]={"ok":False,"error":str(e)}

# Mother's mean age: keep all numeric content collapsed to municipality-year mean where table selections identify mothers.
try:
    def sel_m(meta):
        s={}
        for v in meta["variables"]:
            if "förälder" in v.get("text","").lower() or "foralder" in v.get("code","").lower():
                m=find_value(v,["mödrar"]) or find_value(v,["mor"])
                if m:s[v["code"]]=[m]
            if "ordnings" in v.get("text","").lower():
                t=total_value(v)
                if t:s[v["code"]]=[t]
        return s
    df,meta,lab,url=fetch("medelalder",selectors_fn=sel_m)
    out=df.groupby(["kommun_kod","year"],as_index=False)["value"].mean().rename(columns={"value":"medelalder_mor_vid_fodsel"})
    features.append(out);manifest["sources"]["MedelAlder1"]={"ok":True,"url":url,"features":["medelalder_mor_vid_fodsel"]}
except Exception as e:manifest["sources"]["MedelAlder1"]={"ok":False,"error":str(e)}

# Age-specific fertility rates.
try:
    meta0=getmeta(f"{BASE}/{URLS['fruktsamhet_alder']}")
    av=next(v for v in meta0["variables"] if "moderns ålder" in v.get("text","").lower())
    df,meta,lab,url=fetch("fruktsamhet_alder",all_dims=[av["code"]])
    d=df.copy();d["alabel"]=d[av["code"]].map(lab[av["code"]])
    piv=d.pivot_table(index=["kommun_kod","year"],columns="alabel",values="value",aggfunc="mean")
    ren={}
    for c in piv.columns:
        a=age_num(c)
        if a is not None:ren[c]=f"fruktsamhet_{a}_{a+4}_per1000_kvinnor"
    out=piv.rename(columns=ren)[list(ren.values())].reset_index()
    features.append(out);manifest["sources"]["FruktsamhetHVD"]={"ok":True,"url":url,"features":list(ren.values())}
except Exception as e:manifest["sources"]["FruktsamhetHVD"]={"ok":False,"error":str(e)}

# Total fertility rate, women.
try:
    def sel_w(meta):
        s={}
        for v in meta["variables"]:
            if "kön" in v.get("text","").lower():
                x=find_value(v,["kvinnor"])
                if x:s[v["code"]]=[x]
        return s
    df,meta,lab,url=fetch("fruktsamhet_sum",selectors_fn=sel_w)
    out=df.groupby(["kommun_kod","year"],as_index=False)["value"].mean().rename(columns={"value":"summerad_fruktsamhet_kvinnor"})
    features.append(out);manifest["sources"]["FruktsamhetSum"]={"ok":True,"url":url,"features":["summerad_fruktsamhet_kvinnor"]}
except Exception as e:manifest["sources"]["FruktsamhetSum"]={"ok":False,"error":str(e)}

# Death age distributions from both definitions.
for nm,pref in [("doda_fodelsear","doda_fodelsear"),("doda_handelse","doda_handelse")]:
    try:
        meta0=getmeta(f"{BASE}/{URLS[nm]}")
        av=next(v for v in meta0["variables"] if "ålder" in v.get("text","").lower())
        df,meta,lab,url=fetch(nm,all_dims=[av["code"]],chunk_regions=True)
        out=annual_age_summary(df,meta,lab,pref);features.append(out)
        manifest["sources"][URLS[nm].split("/")[-1]]={"ok":True,"url":url,"features":[c for c in out if c not in ("kommun_kod","year")]}
    except Exception as e:manifest["sources"][URLS[nm].split("/")[-1]]={"ok":False,"error":str(e)}

# Monthly deaths -> annual total and seasonal concentration.
try:
    df,meta,lab,url=fetch("doda_manad")
    d=df.copy()
    # after total selectors, duplicates from alternative content definitions may remain; sum consistently
    d["month"]=pd.to_numeric(d.period.str.extract(r"(\d{2})$")[0],errors="coerce")
    g=d.groupby(["kommun_kod","year","month"],as_index=False)["value"].sum()
    tot=g.groupby(["kommun_kod","year"])["value"].sum()
    out=tot.rename("doda_manad_total").reset_index()
    for name,months in [("winter",[12,1,2,3]),("summer",[6,7,8])]:
        x=g[g.month.isin(months)].groupby(["kommun_kod","year"])["value"].sum()
        out=out.merge((100*x/tot).rename(f"doda_{name}_share_pct").reset_index(),on=["kommun_kod","year"],how="left")
    features.append(out);manifest["sources"]["DodaManadReg"]={"ok":True,"url":url,"features":[c for c in out if c not in ("kommun_kod","year")]}
except Exception as e:manifest["sources"]["DodaManadReg"]={"ok":False,"error":str(e)}

# Stillbirths: total and mother's-age shares.
try:
    meta0=getmeta(f"{BASE}/{URLS['dodfodda']}")
    av=next(v for v in meta0["variables"] if "moderns ålder" in v.get("text","").lower())
    df,meta,lab,url=fetch("dodfodda",all_dims=[av["code"]])
    d=df.copy();d["alabel"]=d[av["code"]].map(lab[av["code"]]);d["age0"]=d.alabel.map(age_num);d=d[d.age0.notna()]
    g=d.groupby(["kommun_kod","year","age0"],as_index=False)["value"].sum();tot=g.groupby(["kommun_kod","year"])["value"].sum()
    out=tot.rename("dodfodda_total").reset_index()
    x=g[g.age0>=35].groupby(["kommun_kod","year"])["value"].sum()
    out=out.merge((100*x/tot).rename("dodfodda_mor_35plus_share_pct").reset_index(),on=["kommun_kod","year"],how="left")
    features.append(out);manifest["sources"]["DodFoddaAlderMorK1"]={"ok":True,"url":url,"features":[c for c in out if c not in ("kommun_kod","year")]}
except Exception as e:manifest["sources"]["DodFoddaAlderMorK1"]={"ok":False,"error":str(e)}

if not features:raise RuntimeError("No demographic feature source succeeded")
base=features[0]
for x in features[1:]:
    base=base.merge(x,on=["kommun_kod","year"],how="outer",validate="one_to_one")
base=base.sort_values(["kommun_kod","year"])
base.to_csv(D/"demographic_scb_candidate_features.csv",index=False)
manifest["rows"]=int(len(base));manifest["municipalities"]=int(base.kommun_kod.nunique())
manifest["first_year"]=int(base.year.min());manifest["last_year"]=int(base.year.max())
manifest["feature_columns"]=[c for c in base if c not in ("kommun_kod","year")]
manifest["notes"]=[
 "All variables are raw annual summaries; modeling applies lag 1 year.",
 "FodelstalHVD and DodstalHVD are excluded here because they are the modeled targets; lagged target histories are added separately.",
 "Correlated age definitions from DodaFodelsearK and DodaHandelseK are intentionally retained as neutral candidates; regularization decides whether either adds value."
]
(D/"demographic_scb_candidate_features_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
