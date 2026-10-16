#!/usr/bin/env python3
"""Capture immutable, dated source snapshots for the frozen forecast core.

For strict future validation this stores both:
- source metadata, and
- the actual SCB/Kolada values needed to reconstruct the frozen predictors.

Snapshots never overwrite earlier snapshots.
"""
import json, datetime, re
from pathlib import Path
import requests

ROOT=Path("docs/data/source_snapshots")
now=datetime.datetime.now(datetime.timezone.utc)
stamp=now.strftime("%Y%m%dT%H%M%SZ")
dest=ROOT/stamp
dest.mkdir(parents=True,exist_ok=False)

s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-snapshot/2.0"})

SCB={
 "migration":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97",
 "population":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy",
 "housing":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
}

def get_json(url):
    r=s.get(url,timeout=60)
    r.raise_for_status()
    return r.json(),r.status_code

def post_json(url,query):
    r=s.post(url,json=query,timeout=120)
    r.raise_for_status()
    return r.json(),r.status_code

def variable(meta,code):
    return next(v for v in meta["variables"] if v["code"]==code)

def municipality_codes(meta):
    vals=variable(meta,"Region")["values"]
    return [x for x in vals if re.fullmatch(r"\d{4}",str(x))]

def years_from(meta,start=2019):
    vals=variable(meta,"Tid")["values"]
    return [str(y) for y in vals if str(y).isdigit() and int(y)>=start]

manifest={
  "captured_at_utc":stamp,
  "snapshot_protocol_version":2,
  "purpose":"freeze exact predictor-source values before a future untouched outcome",
  "sources":{}
}

# ---- SCB metadata + exact value responses ----
metadata={}
for name,url in SCB.items():
    data,status=get_json(url)
    metadata[name]=data
    mf=f"scb_{name}_metadata.json"
    (dest/mf).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest["sources"][name]={
      "url":url,
      "metadata_file":mf,
      "metadata_status_code":status
    }

# Migration: total age, both sexes, inflow/outflow, municipality, 2019-latest.
meta=metadata["migration"]
mig_query={
 "query":[
   {"code":"Region","selection":{"filter":"item","values":municipality_codes(meta)}},
   {"code":"Alder","selection":{"filter":"item","values":["tot"]}},
   {"code":"Kon","selection":{"filter":"item","values":["1","2"]}},
   {"code":"ContentsCode","selection":{"filter":"item","values":["BE0101AU","BE0101AV"]}},
   {"code":"Tid","selection":{"filter":"item","values":years_from(meta,2019)}}
 ],
 "response":{"format":"json-stat2"}
}
mig,status=post_json(SCB["migration"],mig_query)
(dest/"scb_migration_values.json").write_text(json.dumps(mig,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
(dest/"scb_migration_query.json").write_text(json.dumps(mig_query,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
manifest["sources"]["migration"].update({
 "values_file":"scb_migration_values.json",
 "query_file":"scb_migration_query.json",
 "values_status_code":status,
 "years":years_from(meta,2019),
 "derivation_note":"sum sexes for age=tot separately for Inflyttningar and Utflyttningar"
})

# Population denominator: total age, all civil states, both sexes, population, 2019-latest.
meta=metadata["population"]
pop_query={
 "query":[
   {"code":"Region","selection":{"filter":"item","values":municipality_codes(meta)}},
   {"code":"Civilstand","selection":{"filter":"item","values":variable(meta,"Civilstand")["values"]}},
   {"code":"Alder","selection":{"filter":"item","values":["tot"]}},
   {"code":"Kon","selection":{"filter":"item","values":["1","2"]}},
   {"code":"ContentsCode","selection":{"filter":"item","values":["BE0101N1"]}},
   {"code":"Tid","selection":{"filter":"item","values":years_from(meta,2019)}}
 ],
 "response":{"format":"json-stat2"}
}
pop,status=post_json(SCB["population"],pop_query)
(dest/"scb_population_values.json").write_text(json.dumps(pop,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
(dest/"scb_population_query.json").write_text(json.dumps(pop_query,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
manifest["sources"]["population"].update({
 "values_file":"scb_population_values.json",
 "query_file":"scb_population_query.json",
 "values_status_code":status,
 "years":years_from(meta,2019),
 "derivation_note":"sum all civil states and both sexes for age=tot and Folkmängd"
})

# Housing: all house types and tenure forms, municipality, 2019-latest.
meta=metadata["housing"]
housing_query={
 "query":[
   {"code":"Region","selection":{"filter":"item","values":municipality_codes(meta)}},
   {"code":"Hustyp","selection":{"filter":"item","values":variable(meta,"Hustyp")["values"]}},
   {"code":"Upplatelseform","selection":{"filter":"item","values":variable(meta,"Upplatelseform")["values"]}},
   {"code":"ContentsCode","selection":{"filter":"item","values":["BO0104AH"]}},
   {"code":"Tid","selection":{"filter":"item","values":years_from(meta,2019)}}
 ],
 "response":{"format":"json-stat2"}
}
housing,status=post_json(SCB["housing"],housing_query)
(dest/"scb_housing_values.json").write_text(json.dumps(housing,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
(dest/"scb_housing_query.json").write_text(json.dumps(housing_query,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
manifest["sources"]["housing"].update({
 "values_file":"scb_housing_values.json",
 "query_file":"scb_housing_query.json",
 "values_status_code":status,
 "years":years_from(meta,2019),
 "derivation_note":"sum all house-type x tenure cells to total dwelling stock; annual pct_change then lag1"
})

# ---- Kolada exact identity + annual municipality responses ----
base="https://api.kolada.se/v3"
kpi="N03937"
meta,status=get_json(f"{base}/kpi/{kpi}")
(dest/"kolada_N03937_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
manifest["sources"]["kolada_N03937"]={
 "url":f"{base}/kpi/{kpi}",
 "metadata_file":"kolada_N03937_metadata.json",
 "metadata_status_code":status,
 "years":{}
}
for year in range(2019, now.year+1):
    rr=s.get(f"{base}/data/kpi/{kpi}/year/{year}",
             params={"region_type":"municipality","per_page":5000},timeout=60)
    rr.raise_for_status()
    payload=rr.json()
    fn=f"kolada_N03937_{year}.json"
    (dest/fn).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest["sources"]["kolada_N03937"]["years"][str(year)]={
      "file":fn,"status_code":rr.status_code
    }

manifest["validation_requirements"]={
 "future_scoring_must_use_snapshot_values":True,
 "metadata_only_snapshot_is_insufficient":True,
 "refit_before_scoring":False,
 "reselect_before_scoring":False,
 "retune_before_scoring":False
}
(dest/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
