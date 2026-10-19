#!/usr/bin/env python3
import json, urllib.request, urllib.error, time
from pathlib import Path
from datetime import datetime, timezone

KPI="N03937"
CANDIDATES=[
    f"https://api.kolada.se/v3/kpi/{KPI}",
    f"https://api.kolada.se/v3/meta/kpi/{KPI}",
]
OUT=Path("docs/data/kolada_n03937_publication_metadata.json")

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Samband-inflyttning-asof-audit/1.0"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

attempts=[]
payload=None
used=None
for url in CANDIDATES:
    try:
        data=get(url)
        attempts.append({"url":url,"ok":True})
        payload=data
        used=url
        break
    except Exception as e:
        attempts.append({"url":url,"ok":False,"error":f"{type(e).__name__}: {e}"})
        time.sleep(1)

if payload is None:
    raise SystemExit("No Kolada v3 KPI metadata endpoint succeeded: "+json.dumps(attempts,ensure_ascii=False))

# Normalize likely response shapes without discarding raw metadata.
values = payload.get("values") if isinstance(payload,dict) else None
if isinstance(values,list) and values:
    rec=values[0]
elif isinstance(payload,dict):
    rec=payload
else:
    rec={}

result={
  "status":"kolada_n03937_publication_metadata_audit",
  "generated_at_utc":datetime.now(timezone.utc).isoformat(),
  "kpi":KPI,
  "endpoint_used":used,
  "endpoint_attempts":attempts,
  "publication_date":rec.get("publication_date"),
  "prel_publication_date":rec.get("prel_publication_date"),
  "publication_period":rec.get("publ_period") or rec.get("publication_period"),
  "title":rec.get("title") or rec.get("name"),
  "raw":payload
}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
