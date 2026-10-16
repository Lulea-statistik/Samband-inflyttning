#!/usr/bin/env python3
"""Research-only archive evidence audit for exact SCB core table URLs.

Queries the Internet Archive CDX index for captures of the exact SCB API and
PxWeb table URLs around the 2024 forecast-origin window. This does not certify
historical POST-response values unless a capture actually contains them.
"""
import json, urllib.parse
from pathlib import Path
import requests

OUT=Path("docs/data")
TABLES={
 "migration":{
   "api":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97",
   "pxweb":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101J/Flyttningar97/"
 },
 "population":{
   "api":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy",
   "pxweb":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BE__BE0101__BE0101A/BefolkningNy/"
 },
 "housing":{
   "api":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BO/BO0104/BO0104D/BO0104T04",
   "pxweb":"https://www.statistikdatabasen.scb.se/pxweb/sv/ssd/START__BO__BO0104__BO0104D/BO0104T04/"
 }
}
FROM="20240201"
TO="20240515"
session=requests.Session()
session.headers.update({"User-Agent":"Lulea-statistik-vintage-audit/1.0"})

def cdx(url):
    params={
      "url":url,
      "from":FROM,
      "to":TO,
      "output":"json",
      "fl":"timestamp,original,statuscode,mimetype,digest",
      "filter":"statuscode:200",
      "collapse":"digest"
    }
    r=session.get("https://web.archive.org/cdx/search/cdx",params=params,timeout=60)
    if not r.ok:
        return {"ok":False,"status":r.status_code,"error":r.text[:500],"captures":[]}
    try:data=r.json()
    except Exception:
        return {"ok":False,"status":r.status_code,"error":"non-json response","captures":[]}
    if not data or len(data)<2:return {"ok":True,"status":r.status_code,"captures":[]}
    hdr=data[0]
    rows=[dict(zip(hdr,row)) for row in data[1:]]
    for row in rows:
        row["archive_url"]="https://web.archive.org/web/"+row["timestamp"]+"id_/"+row["original"]
    return {"ok":True,"status":r.status_code,"captures":rows}

results={}
for name,urls in TABLES.items():
    results[name]={}
    for kind,url in urls.items():
        results[name][kind]={"url":url,**cdx(url)}

out={
 "status":"research_only_scb_wayback_vintage_evidence",
 "production_changed":False,
 "window":{"from":FROM,"to":TO},
 "results":results,
 "interpretation":{
   "metadata_capture_can_support_table_existence":True,
   "metadata_capture_does_not_certify_posted_cell_values":True,
   "strict_asof_requires_value_snapshot_or_equivalent_version_specific_evidence":True
 },
 "decision":{
   "no_model_run":True,
   "no_asof_upgrade_automatically":True
 }
}
(OUT/"neutral_scb_wayback_vintage_evidence.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
