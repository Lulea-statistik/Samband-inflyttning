#!/usr/bin/env python3
"""Build source-audited untouched 2025 outmigration outcome from SCB only.

Outcome-only guardrails:
- does not import any model code;
- does not read frozen predictions;
- does not refit/tune/select anything;
- exits without creating an outcome if SCB 2025 annual data are unavailable.

Sources:
- BE0101J/Flyttningar97, Utflyttningar (BE0101AV)
- BE0101A/BefolkningNy, Folkmängd (BE0101N1)
"""
import hashlib, json, re
from pathlib import Path
import pandas as pd
import requests

ROOT=Path("docs/data/outcomes/2025_scb_outmigration")
ROOT.mkdir(parents=True,exist_ok=True)
OUT=Path("docs/data/outcomes/utflyttning_2025.csv")
MANIFEST=ROOT/"manifest.json"
STATUS=Path("docs/data/outmigration_2025_outcome_availability_status.json")

S=requests.Session()
S.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-outmigration-outcome-2025/1.0"})
MIG="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97"
POP="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy"

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def dump(name,obj):
    p=ROOT/name
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return p

def get(url):
    r=S.get(url,timeout=90); r.raise_for_status(); return r.json()

def post(url,q):
    r=S.post(url,json=q,timeout=180); r.raise_for_status(); return r.json()

def variable(meta,code):
    return next(v for v in meta["variables"] if v["code"]==code)

def municipalities(meta):
    return [x for x in variable(meta,"Region")["values"] if re.fullmatch(r"\d{4}",str(x))]

def js2long(js):
    dims=js["id"]; sizes=js["size"]; values=js["value"]; cats=[]
    for d in dims:
        idx=js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx,key=idx.get) if isinstance(idx,dict) else list(idx))
    rows=[]
    for flat,v in enumerate(values):
        if v is None: continue
        rem=flat; pos=[]
        for size in reversed(sizes):
            pos.append(rem%size); rem//=size
        pos=list(reversed(pos))
        row={d:cats[i][pos[i]] for i,d in enumerate(dims)}
        row["value"]=float(v); rows.append(row)
    return pd.DataFrame(rows)

mig_meta=get(MIG)
pop_meta=get(POP)
dump("scb_migration_metadata.json",mig_meta)
dump("scb_population_metadata.json",pop_meta)

mig_years=[str(x) for x in variable(mig_meta,"Tid")["values"]]
pop_years=[str(x) for x in variable(pop_meta,"Tid")["values"]]
if "2025" not in mig_years or "2025" not in pop_years:
    status={
      "status":"waiting_for_scb_2025_outmigration_outcome",
      "forecast_year":2025,
      "migration_2025_available":"2025" in mig_years,
      "population_2025_available":"2025" in pop_years,
      "blocking_source":"SCB BE0101J/Flyttningar97" if "2025" not in mig_years else "SCB BE0101A/BefolkningNy",
      "frozen_predictions_changed":False,
      "frozen_predictions_read":False,
      "model_refit":False,
      "production_changed":False,
      "next_action":"Run this workflow again only after both annual 2025 SCB sources are available."
    }
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(status,ensure_ascii=False,indent=2))
    raise SystemExit(0)

mig_q={"query":[
 {"code":"Region","selection":{"filter":"item","values":municipalities(mig_meta)}},
 {"code":"Alder","selection":{"filter":"item","values":["tot"]}},
 {"code":"Kon","selection":{"filter":"item","values":["1","2"]}},
 {"code":"ContentsCode","selection":{"filter":"item","values":["BE0101AV"]}},
 {"code":"Tid","selection":{"filter":"item","values":["2025"]}}
],"response":{"format":"json-stat2"}}

pop_q={"query":[
 {"code":"Region","selection":{"filter":"item","values":municipalities(pop_meta)}},
 {"code":"Civilstand","selection":{"filter":"item","values":variable(pop_meta,"Civilstand")["values"]}},
 {"code":"Alder","selection":{"filter":"item","values":["tot"]}},
 {"code":"Kon","selection":{"filter":"item","values":["1","2"]}},
 {"code":"ContentsCode","selection":{"filter":"item","values":["BE0101N1"]}},
 {"code":"Tid","selection":{"filter":"item","values":["2025"]}}
],"response":{"format":"json-stat2"}}

dump("scb_migration_query.json",mig_q)
dump("scb_population_query.json",pop_q)
mig_js=post(MIG,mig_q)
pop_js=post(POP,pop_q)
dump("scb_migration_values.json",mig_js)
dump("scb_population_values.json",pop_js)

mig=js2long(mig_js)
pop=js2long(pop_js)
for df in (mig,pop):
    df["Region"]=df["Region"].astype(str).str.zfill(4)

mg=mig.groupby("Region",as_index=False)["value"].sum().rename(
    columns={"Region":"kommun_kod","value":"utflyttningar"})
pg=pop.groupby("Region",as_index=False)["value"].sum().rename(
    columns={"Region":"kommun_kod","value":"population"})
out=mg.merge(pg,on="kommun_kod",how="inner",validate="one_to_one")
out["year"]=2025
out["utflyttning_per_1000"]=1000*out["utflyttningar"]/out["population"]
out=out[["kommun_kod","year","utflyttning_per_1000","utflyttningar","population"]].sort_values("kommun_kod")

if len(out)!=290 or out.kommun_kod.nunique()!=290:
    raise SystemExit(f"Outcome coverage incomplete: rows={len(out)}, unique={out.kommun_kod.nunique()}")
if (out["population"]<=0).any():
    raise SystemExit("Non-positive population denominator")

OUT.parent.mkdir(parents=True,exist_ok=True)
out.to_csv(OUT,index=False)

files=[
 ROOT/"scb_migration_metadata.json",ROOT/"scb_population_metadata.json",
 ROOT/"scb_migration_query.json",ROOT/"scb_population_query.json",
 ROOT/"scb_migration_values.json",ROOT/"scb_population_values.json",OUT
]
manifest={
 "status":"scb_2025_outmigration_outcome_built",
 "outcome_year":2025,
 "municipalities":290,
 "definition":"utflyttning_per_1000 = 1000 * SCB BE0101AV / SCB BE0101N1",
 "migration_source":MIG,
 "population_source":POP,
 "migration_content_code":"BE0101AV",
 "population_content_code":"BE0101N1",
 "model_code_imported":False,
 "frozen_predictions_read":False,
 "refit_performed":False,
 "files_sha256":{str(p):sha(p) for p in files}
}
MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
STATUS.write_text(json.dumps({
  "status":"scb_2025_outmigration_outcome_available_and_built",
  "forecast_year":2025,
  "municipalities":290,
  "production_changed":False,
  "next_action":"Run Score untouched 2025 outmigration outcome."
},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

print(json.dumps({
 "status":manifest["status"],
 "rows":len(out),
 "lulea":out[out.kommun_kod=="2580"].to_dict("records")
},ensure_ascii=False,indent=2))
