#!/usr/bin/env python3
"""Independent RAMS municipality-pair vs published commuting totals audit. No model writes."""
import json,re
from pathlib import Path
from import_scb_commuting import request
import pandas as pd
D=Path("docs/data")
BASE="https://api.scb.se/OV0104/v1/doris/sv/ssd/START/AM/AM0207/AM0207L/"
URLS=[BASE+"AM0207PendlKomA04",BASE+"AM0207AB"]
YEARS=["2008","2011","2018"]
SAMPLE=["0180","0380","0580","1280","1480","1780","1880","2080","2281","2380","2480","2580"]
def var(meta,terms):
    matches=[x for x in meta["variables"] if any(t in (x.get("code","")+" "+x.get("text","")).lower() for t in terms)]
    if len(matches)!=1:raise RuntimeError(f"Ambiguous dimension {terms}: {matches}")
    return matches[0]
def main():
    errors=[];meta=None;url=None
    for u in URLS:
        try:meta=request("GET",u);url=u;break
        except Exception as e:errors.append(str(e))
    if meta is None:raise RuntimeError("No known SCB API endpoint resolves: "+str(errors))
    home=var(meta,["bostadskommun"]);work=var(meta,["arbetsställekommun","arbetsstallekommun"])
    year=var(meta,["tid","år"]);sex=next((v for v in meta["variables"] if "kön" in v.get("text","").lower()),None)
    content=next((v for v in meta["variables"] if v.get("code","").lower()=="contentscode"),None)
    available=set(home["values"])&set(work["values"])
    origins=sorted(str(x) for x in available if re.fullmatch(r"\d{4}",str(x)))
    if len(origins)!=290:raise RuntimeError(f"Expected 290 municipalities, found {len(origins)}")
    chosen=[v for v in SAMPLE if v in origins]
    if len(chosen)<10:raise RuntimeError("Unexpected sample coverage")
    sex_values=[]
    sex_mode="dimension_absent"
    if sex:
        candidates=list(zip(sex["values"],sex.get("valueTexts",[])))
        totals=[code for code,label in candidates if any(t in label.lower() for t in ("totalt","båda","samtliga"))]
        if len(totals)==1:
            sex_values=totals
            sex_mode="published_total"
        elif len(totals)==0 and len(candidates)==2 and all(any(t in label.lower() for t in ("män","kvinnor","man","kvinna")) for _,label in candidates):
            sex_values=[code for code,_ in candidates]
            sex_mode="sum_men_women"
        else:
            raise RuntimeError("Ambiguous SCB gender categories: "+str(candidates))
    data={}
    def fetch(selected_home,selected_work,yr):
        query=[{"code":home["code"],"selection":{"filter":"item","values":selected_home}},
           {"code":work["code"],"selection":{"filter":"item","values":selected_work}},
           {"code":year["code"],"selection":{"filter":"item","values":[yr]}}]
        if sex:query.append({"code":sex["code"],"selection":{"filter":"item","values":sex_values}})
        if content:
            vals=list(zip(content["values"],content.get("valueTexts",[])))
            if len(vals)!=1:raise RuntimeError("Multiple SCB measures need explicit review: "+str(vals))
            query.append({"code":content["code"],"selection":{"filter":"item","values":[vals[0][0]]}})
        res=request("POST",url,json={"query":query,"response":{"format":"json"}})
        dims=[x["code"] for x in res["columns"] if x.get("type")!="c"]
        if home["code"] not in dims or work["code"] not in dims:raise RuntimeError("Unexpected response dimensions "+str(dims))
        for row in res["data"]:
            d=dict(zip(dims,row["key"]))
            h=str(d[home["code"]]).zfill(4);w=str(d[work["code"]]).zfill(4)
            if h==w:raise RuntimeError("Expected intermunicipal-only flows; found diagonal")
            value=row["values"][0]
            if value in (None,"","..",".","-"):raise RuntimeError(f"Suppressed cell {yr} {h} {w}")
            key=(yr,h,w)
            # Two sex categories must be summed for the same municipality pair.
            data[key]=data.get(key,0.0)+float(str(value).replace(" ","").replace(",","."))
    for yr in YEARS:
        for a in range(0,len(chosen),6):
            fetch(chosen[a:a+6],origins,yr)
        for a in range(0,len(chosen),6):
            fetch(origins,chosen[a:a+6],yr)
        print("Fetched year",yr,flush=True)
    old=pd.read_csv(D/"commuting_historical_rams.csv",dtype={"kommun_kod":str})
    old.kommun_kod=old.kommun_kod.str.zfill(4)
    report={"status":"independent_sample_commuter_flow_crosscheck",
      "sex_handling":sex_mode,"source":url,"years":YEARS,"municipalities":chosen,"rows":[],
      "production_changed":False,
      "limitations":["Commuters crossing a municipal border are not total employed persons.",
        "Only a fixed selection of 12 municipalities and 3 years is checked.",
        "A total difference could reflect missing/unknown workplace or SCB confidentiality handling.",
        "No historical model or series has been altered."]}
    for yr in YEARS:
        for code in chosen:
            frame=old.loc[(old.kommun_kod==code)&(old.year==int(yr))]
            if len(frame)!=1:raise RuntimeError("Missing RAMS "+yr+" "+code)
            outward=sum(v for (y,h,w),v in data.items() if y==yr and h==code)
            inward=sum(v for (y,h,w),v in data.items() if y==yr and w==code)
            row=frame.iloc[0]
            report["rows"].append({"year":int(yr),"kommun_kod":code,
                "rams_outgoing":float(row.outgoing),"od_outgoing":outward,"out_diff":outward-float(row.outgoing),
                "rams_incoming":float(row.incoming),"od_incoming":inward,"in_diff":inward-float(row.incoming)})
    report["different_rows"]=sum(bool(z["out_diff"] or z["in_diff"]) for z in report["rows"])
    (D/"rams_2004_2018_od_sample_crosscheck.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print("comparison rows",len(report["rows"]),"differences",report["different_rows"],flush=True)
if __name__=="__main__":main()
