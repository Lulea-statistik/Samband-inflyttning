#!/usr/bin/env python3
"""Capture dated metadata/data snapshots for the provisional forecast core.

This workflow is for future untouched validation. It stores source responses
with an explicit UTC timestamp and never overwrites prior snapshots.
"""
import json, datetime, re
from pathlib import Path
import requests

ROOT=Path("docs/data/source_snapshots")
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
dest=ROOT/stamp
dest.mkdir(parents=True,exist_ok=False)

s=requests.Session()
s.headers.update({"User-Agent":"Lulea-statistik-Samband-inflyttning-snapshot/1.0"})

SCB={
 "migration":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97",
 "population":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy",
 "housing":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04"
}

manifest={"captured_at_utc":stamp,"sources":{}}
for name,url in SCB.items():
    r=s.get(url,timeout=60)
    r.raise_for_status()
    data=r.json()
    (dest/f"scb_{name}_metadata.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest["sources"][name]={"url":url,"metadata_file":f"scb_{name}_metadata.json","status_code":r.status_code}

# Freeze Kolada KPI identity + all current municipality observations for recent years.
base="https://api.kolada.se/v3"
kpi="N03937"
r=s.get(f"{base}/kpi/{kpi}",timeout=60); r.raise_for_status()
meta=r.json()
(dest/"kolada_N03937_metadata.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
manifest["sources"]["kolada_N03937"]={"url":f"{base}/kpi/{kpi}","metadata_file":"kolada_N03937_metadata.json","years":{}}
for year in range(2019, datetime.datetime.now().year+1):
    rr=s.get(f"{base}/data/kpi/{kpi}/year/{year}",params={"region_type":"municipality","per_page":5000},timeout=60)
    rr.raise_for_status()
    payload=rr.json()
    fn=f"kolada_N03937_{year}.json"
    (dest/fn).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest["sources"]["kolada_N03937"]["years"][str(year)]={"file":fn,"status_code":rr.status_code}

(dest/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(manifest,ensure_ascii=False,indent=2))
