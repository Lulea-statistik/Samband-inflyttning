#!/usr/bin/env python3
"""Build annual municipal birth/death rate targets from SCB bulk CSV.

Targets:
- fodelsetal_per_100 = SCB births per 1,000 of mean population / 10
- dodstal_per_1000 = SCB deaths per 1,000 of mean population

Official SCB bulk tables:
- FodelstalHVD: TAB4644_sv.zip
- DodstalHVD: TAB4667_sv.zip

Bulk CSV is preferred over PxWeb API dimension handling because it preserves
SCB's published table directly and is more robust to internal dimension-code changes.
"""
import io,json,re,zipfile,unicodedata
from pathlib import Path
import pandas as pd
import requests

OUT=Path("docs/data"); OUT.mkdir(parents=True,exist_ok=True)
BIRTH_ZIP="https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4644_sv.zip"
DEATH_ZIP="https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4667_sv.zip"
BIRTH_META="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101H/FodelstalHVD"
DEATH_META="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101I/DodstalHVD"
YEARS=set(range(2013,2026))
S=requests.Session();S.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-demographic-targets/1.1"})

def norm(s):
    s=unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","_",s).strip("_")

def load_bulk(url):
    r=S.get(url,timeout=180); r.raise_for_status()
    z=zipfile.ZipFile(io.BytesIO(r.content))
    names=[n for n in z.namelist() if n.lower().endswith((".csv",".txt"))]
    if not names: raise RuntimeError(f"No CSV/TXT in {url}: {z.namelist()}")
    raw=z.read(names[0])
    last=None
    for enc in ("utf-8-sig","utf-8","cp1252","latin1"):
        try:
            txt=raw.decode(enc)
            df=pd.read_csv(io.StringIO(txt),sep=None,engine="python")
            if len(df.columns)>=2:return df,names[0],enc
        except Exception as e:last=e
    raise RuntimeError(f"Could not parse bulk file {url}: {last}")

def pick_col(df,needles):
    nmap={norm(c):c for c in df.columns}
    for n,c in nmap.items():
        if all(x in n for x in needles):return c
    raise KeyError(f"Column with {needles} not found. Columns={list(df.columns)}")

def region_lookup(meta_url):
    """Build normalized SCB region label -> official four-digit municipality code."""
    r=S.get(meta_url,timeout=90); r.raise_for_status(); meta=r.json()
    print("SCB metadata dimensions:")
    for v in meta.get("variables",[]):
        vals=v.get("values",[])
        txts=v.get("valueTexts",vals)
        print({
          "code":v.get("code"),
          "text":v.get("text"),
          "n_values":len(vals),
          "sample_values":[str(x) for x in vals[:8]],
          "sample_texts":[str(x) for x in txts[:8]],
          "time":bool(v.get("time"))
        })
    candidates=[]
    for v in meta.get("variables",[]):
        vals=v.get("values",[])
        texts=v.get("valueTexts",vals)
        pairs=list(zip(vals,texts))
        mapped=[]
        for code,label in pairs:
            m=re.search(r"(?<!\d)(\d{4})(?!\d)",str(code))
            if not m:
                m=re.search(r"(?<!\d)(\d{4})(?!\d)",str(label))
            if m:
                mapped.append((norm(label),m.group(1)))
        if len(mapped)>=250:
            candidates.append((len(mapped),mapped,v.get("code"),v.get("text")))
    if not candidates:
        # Some SCB region codes can carry prefixes. Use the highest-cardinality
        # non-time dimension and extract the final four digits from its codes.
        for v in meta.get("variables",[]):
            if v.get("time"): continue
            vals=v.get("values",[])
            texts=v.get("valueTexts",vals)
            mapped=[]
            for code,label in zip(vals,texts):
                digs=re.findall(r"\d{4}",str(code))
                if digs:
                    mapped.append((norm(label),digs[-1]))
            if len(mapped)>=250:
                candidates.append((len(mapped),mapped,v.get("code"),v.get("text")))
    if not candidates:
        raise RuntimeError("Could not construct municipality lookup from SCB metadata")
    _,mapped,code,text=max(candidates,key=lambda x:x[0])
    out={}
    for label,kod in mapped:
        if kod and len(kod)==4:
            out[label]=kod
    return out,{"dimension_code":code,"dimension_text":text,"mapped_labels":len(out)}

def region_code(series, lookup):
    raw=series.astype(str)
    embedded=raw.str.extract(r"(?<!\d)(\d{4})(?!\d)",expand=False)
    by_name=raw.map(lambda x: lookup.get(norm(x)))
    return embedded.fillna(by_name)

def numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(",",".",regex=False),errors="coerce")

def build_birth():
    df,name,enc=load_bulk(BIRTH_ZIP)
    print("Birth bulk columns:", list(df.columns))
    region=pick_col(df,["region"])
    print("Birth bulk region sample:", df[region].astype(str).drop_duplicates().head(30).tolist())
    lookup,lookup_meta=region_lookup(BIRTH_META)
    year=pick_col(df,["ar"])
    value_candidates=[c for c in df.columns if c not in (region,year)]
    if len(value_candidates)!=1:
        # Prefer the published rate content column.
        value=next((c for c in value_candidates if "1000" in norm(c) or "fodd" in norm(c)),None)
        if value is None: raise RuntimeError(f"Birth value column ambiguous: {value_candidates}")
    else:value=value_candidates[0]
    out=pd.DataFrame({
      "kommun_kod":region_code(df[region],lookup),
      "year":pd.to_numeric(df[year],errors="coerce"),
      "fodelsetal_per_1000_scb":numeric(df[value])
    })
    out=out[out.kommun_kod.notna() & out.year.isin(YEARS)].copy()
    out["year"]=out["year"].astype(int)
    out["fodelsetal_per_100"]=out["fodelsetal_per_1000_scb"]/10.0
    out=out.groupby(["kommun_kod","year"],as_index=False)[["fodelsetal_per_1000_scb","fodelsetal_per_100"]].mean()
    return out,{"zip":BIRTH_ZIP,"member":name,"encoding":enc,"columns":list(df.columns),"region_lookup":lookup_meta}

def find_total_value(series,terms):
    vals=series.dropna().astype(str).unique().tolist()
    for v in vals:
        nv=norm(v)
        if all(t in nv for t in terms):return v
    return None

def build_death():
    df,name,enc=load_bulk(DEATH_ZIP)
    print("Death bulk columns:", list(df.columns))
    region=pick_col(df,["region"])
    print("Death bulk region sample:", df[region].astype(str).drop_duplicates().head(30).tolist())
    lookup,lookup_meta=region_lookup(DEATH_META)
    year=pick_col(df,["ar"])
    sex=pick_col(df,["kon"])
    age=pick_col(df,["alder"])
    other=[c for c in df.columns if c not in (region,year,sex,age)]
    if not other:raise RuntimeError(f"Death value column absent: {list(df.columns)}")
    value=next((c for c in other if "antal" in norm(c) or "1000" in norm(c) or "dod" in norm(c)),other[0])
    sex_total=find_total_value(df[sex],["totalt"]) or find_total_value(df[sex],["bada"])
    age_total=find_total_value(df[age],["samtliga"]) or find_total_value(df[age],["totalt"])
    if sex_total is None or age_total is None:
        raise RuntimeError(f"Could not identify total sex/age. sex={df[sex].drop_duplicates().tolist()[:10]} age={df[age].drop_duplicates().tolist()[:10]}")
    q=df[(df[sex].astype(str)==str(sex_total)) & (df[age].astype(str)==str(age_total))].copy()
    out=pd.DataFrame({
      "kommun_kod":region_code(q[region],lookup),
      "year":pd.to_numeric(q[year],errors="coerce"),
      "dodstal_per_1000":numeric(q[value])
    })
    out=out[out.kommun_kod.notna() & out.year.isin(YEARS)].copy()
    out["year"]=out["year"].astype(int)
    out=out.groupby(["kommun_kod","year"],as_index=False)["dodstal_per_1000"].mean()
    return out,{"zip":DEATH_ZIP,"member":name,"encoding":enc,"columns":list(df.columns),"sex_total":str(sex_total),"age_total":str(age_total),"region_lookup":lookup_meta}

b,bmeta=build_birth()
d,dmeta=build_death()
if b.empty:
    raise RuntimeError(f"Birth target extraction returned 0 rows; source={bmeta}")
if d.empty:
    raise RuntimeError(f"Death target extraction returned 0 rows; source={dmeta}")
print(f"Birth extraction: rows={len(b)}, municipalities={b.kommun_kod.nunique()}, years={sorted(b.year.unique())}")
print(f"Death extraction: rows={len(d)}, municipalities={d.kommun_kod.nunique()}, years={sorted(d.year.unique())}")
panel=b.merge(d,on=["kommun_kod","year"],how="inner",validate="one_to_one").sort_values(["kommun_kod","year"])

counts=panel.groupby("year").kommun_kod.nunique().to_dict()
bad={int(y):int(n) for y,n in counts.items() if n!=290}
if bad:
    raise RuntimeError(f"Expected 290 municipalities per year, got deviations: {bad}")
if panel.kommun_kod.nunique()!=290:
    raise RuntimeError(f"Expected 290 municipalities total, got {panel.kommun_kod.nunique()}")

panel.to_csv(OUT/"demographic_birth_death_targets.csv",index=False)
manifest={
 "status":"demographic_birth_death_targets_built",
 "production_changed":False,
 "municipalities":290,
 "first_year":int(panel.year.min()),
 "last_year":int(panel.year.max()),
 "rows":int(len(panel)),
 "rows_per_year":{str(k):int(v) for k,v in counts.items()},
 "birth_target":"fodelsetal_per_100",
 "birth_definition":"SCB FodelstalHVD births per 1,000 of mean population divided by 10",
 "death_target":"dodstal_per_1000",
 "death_definition":"SCB DodstalHVD deaths per 1,000 of mean population, both sexes and all ages",
 "birth_source":bmeta,
 "death_source":dmeta,
 "scb_birth_rate_original_unit":"per 1,000 of mean population",
 "project_birth_rate_unit":"per 100 of mean population",
 "method":"official SCB full-table bulk CSV ZIP",
 "model_code_imported":False
}
(OUT/"demographic_birth_death_targets_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
# Keep query audit filenames for workflow compatibility, now documenting bulk retrieval.
(OUT/"demographic_birth_query.json").write_text(json.dumps({"method":"bulk_csv","source":bmeta},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"demographic_death_query.json").write_text(json.dumps({"method":"bulk_csv","source":dmeta},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
