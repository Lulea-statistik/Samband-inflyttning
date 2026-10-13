#!/usr/bin/env python3
"""Historical SCB RAMS commute summary, stored as separate regimes (no silent splice).

2004-2018: RAMS older classification, 2019-2021: RAMS new AGI series.
BAS 2020-2024 remains unchanged in the separate main commuting import.
"""
import csv
import json
import re
from pathlib import Path
from import_scb_commuting import request

ROOT="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0207"
SOURCES={
 "RAMS_2004_2018":ROOT+"/AM0207L/PendlingK",
 "RAMS_2019_2021":ROOT+"/AM0207Z/PendlingKN",
}
OUT=Path("docs/data")

def identify(meta):
    variables=meta["variables"]
    region=next(v for v in variables if v["code"].lower() in {"region","kommun"} or v["text"].strip().lower()=="region")
    year=next(v for v in variables if v["code"].lower() in {"tid","year","år"} or v["text"].strip().lower()=="år")
    contents=next(v for v in variables if v["code"].lower()=="contentscode" or "tabellinnehåll" in v["text"].lower())
    sex=next((v for v in variables if "kön" in v["text"].lower() or v["code"].lower()=="kon"),None)
    labels=list(zip(contents["values"],contents["valueTexts"]))
    picks={}
    for key,word in {"incoming":"inpendlare","outgoing":"utpendlare","local":"bor och arbetar"}.items():
        matches=[c for c,t in labels if word in t.lower()]
        if len(matches)!=1: raise RuntimeError(f"{key}: ambiguous SCB series {labels}")
        picks[key]=matches[0]
    if sex:
        cats=list(zip(sex["values"],sex["valueTexts"]))
        total=next((c for c,t in cats if any(z in t.lower() for z in ("totalt","båda","samtliga","män och kvinnor"))),None)
        if total is None: raise RuntimeError(f"Missing total sex category: {cats}")
    else: total=None
    municipality=[str(c) for c in region["values"] if re.fullmatch(r"\d{4}",str(c))]
    if len(municipality)!=290: raise RuntimeError(f"Expected 290 municipalities, found {len(municipality)}")
    return region,year,contents,sex,total,municipality,picks

def main():
    records=[]
    provenance={}
    for regime,url in SOURCES.items():
        meta=request("GET",url)
        region,year,contents,sex,total,municipality,picks=identify(meta)
        available=sorted(v for v in year["values"] if re.fullmatch(r"20\d{2}",str(v)))
        expected=[str(y) for y in (range(2004,2019) if "2004" in regime else range(2019,2022))]
        if available!=expected:
            raise RuntimeError(f"Unexpected years for {regime}: {available}")
        count=0
        for yr in available:
            query=[
              {"code":contents["code"],"selection":{"filter":"item","values":list(picks.values())}},
              {"code":region["code"],"selection":{"filter":"item","values":municipality}},
              {"code":year["code"],"selection":{"filter":"item","values":[yr]}},
            ]
            if sex: query.append({"code":sex["code"],"selection":{"filter":"item","values":[total]}})
            response=request("POST",url,json={"query":query,"response":{"format":"json"}})
            dimensions=[c["code"] for c in response["columns"] if c.get("type")!="c"]
            content_columns=[c for c in response["columns"] if c.get("type")=="c"]
            if len(content_columns)!=1 or content_columns[0]["code"]!=contents["code"]:
                raise RuntimeError(f"Unexpected SCB contents columns: {response['columns']}")
            content_order=content_columns[0].get("values",[])
            if set(content_order)!=set(picks.values()) or len(content_order)!=3:
                raise RuntimeError(f"Unexpected contents order: {content_order}; expected {picks}")
            mapped={}
            for ob in response["data"]:
                dim=dict(zip(dimensions,ob["key"]))
                if region["code"] not in dim:
                    raise RuntimeError(f"Region dimension missing from response: {dimensions}")
                if len(ob["values"])!=len(content_order):
                    raise RuntimeError(f"Unexpected value count: {len(ob['values'])} != {len(content_order)}")
                for content_code,value in zip(content_order,ob["values"]):
                    key=(dim[region["code"]],content_code)
                    if value in (None,"","..",".","-"):
                        raise RuntimeError(f"SCB missing value for {regime}, {yr}, {key}")
                    if key in mapped: raise RuntimeError(f"Duplicate key {key}")
                    mapped[key]=float(str(value).replace(" ","").replace(",","."))
            if len(mapped)!=290*3:raise RuntimeError(f"Incomplete historical year {yr}: {len(mapped)}")
            for kommune in municipality:
                vals={k:mapped[(kommune,v)] for k,v in picks.items()}
                total_residents=vals["local"]+vals["outgoing"]
                if total_residents<=0:raise RuntimeError("Zero denominator")
                records.append({"year":int(yr),"kommun_kod":kommune,"regime":regime,
                                "outcommuting_share_pct":100*vals["outgoing"]/total_residents,
                                "outgoing":vals["outgoing"],"incoming":vals["incoming"],"local":vals["local"]})
                count+=1
        provenance[regime]={"url":url,"years":available,"rows":count,"metrics":picks}
    OUT.mkdir(parents=True,exist_ok=True)
    filename=OUT/"commuting_historical_rams.csv"
    with filename.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)
    metadata={"status":"imported_separate_regimes","series":provenance,
              "years":list(range(2004,2022)),"total_rows":len(records),
              "breakpoints":[
                {"from":2011,"details":"RAMS classification adjustment for older workers"},
                {"from":2019,"details":"RAMS AGI methodology replaces annual employer statements"},
                {"from":2020,"details":"BAS methodology begins, distinct from RAMS; 2020-21 overlap not interchangeable"},
                {"from":2024,"details":"BAS classification change for self-employed"},
              ],
              "warning":"Do not pool or difference across the 2018/2019 or RAMS/BAS regime boundaries without an explicit harmonization experiment. RAMS denominator is local workers + outbound commuters.",
              "production_model_changed":False}
    (OUT/"commuting_historical_status.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    print(json.dumps({"rows":len(records),"sources":provenance},ensure_ascii=False))

if __name__=="__main__":main()
