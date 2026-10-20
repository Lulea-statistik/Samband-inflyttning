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

def region_code(series):
    # Bulk region labels may be e.g. "2580 Luleå" or just "2580".
    return series.astype(str).str.extract(r"(?<!\d)(\d{4})(?!\d)",expand=False)

def numeric(series):
    return pd.to_numeric(series.astype(str).str.replace(",",".",regex=False),errors="coerce")

def build_birth():
    df,name,enc=load_bulk(BIRTH_ZIP)
    region=pick_col(df,["region"])
    year=pick_col(df,["ar"])
    value_candidates=[c for c in df.columns if c not in (region,year)]
    if len(value_candidates)!=1:
        # Prefer the published rate content column.
        value=next((c for c in value_candidates if "1000" in norm(c) or "fodd" in norm(c)),None)
        if value is None: raise RuntimeError(f"Birth value column ambiguous: {value_candidates}")
    else:value=value_candidates[0]
    out=pd.DataFrame({
      "kommun_kod":region_code(df[region]),
      "year":pd.to_numeric(df[year],errors="coerce"),
      "fodelsetal_per_1000_scb":numeric(df[value])
    })
    out=out[out.kommun_kod.notna() & out.year.isin(YEARS)].copy()
    out["year"]=out["year"].astype(int)
    out["fodelsetal_per_100"]=out["fodelsetal_per_1000_scb"]/10.0
    out=out.groupby(["kommun_kod","year"],as_index=False)[["fodelsetal_per_1000_scb","fodelsetal_per_100"]].mean()
    return out,{"zip":BIRTH_ZIP,"member":name,"encoding":enc,"columns":list(df.columns)}

def find_total_value(series,terms):
    vals=series.dropna().astype(str).unique().tolist()
    for v in vals:
        nv=norm(v)
        if all(t in nv for t in terms):return v
    return None

def build_death():
    df,name,enc=load_bulk(DEATH_ZIP)
    region=pick_col(df,["region"])
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
      "kommun_kod":region_code(q[region]),
      "year":pd.to_numeric(q[year],errors="coerce"),
      "dodstal_per_1000":numeric(q[value])
    })
    out=out[out.kommun_kod.notna() & out.year.isin(YEARS)].copy()
    out["year"]=out["year"].astype(int)
    out=out.groupby(["kommun_kod","year"],as_index=False)["dodstal_per_1000"].mean()
    return out,{"zip":DEATH_ZIP,"member":name,"encoding":enc,"columns":list(df.columns),"sex_total":str(sex_total),"age_total":str(age_total)}

b,bmeta=build_birth()
d,dmeta=build_death()
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
