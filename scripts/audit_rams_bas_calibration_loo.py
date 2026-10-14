#!/usr/bin/env python3
"""Two directional leave-one-overlap-year-out BAS calibration tests. Research-only."""
import csv,json,math,statistics
from pathlib import Path
D=Path("docs/data")
with (D/"employment_historical_regime_research.csv").open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
idx={(r["regime"],int(r["year"]),r["kommun_kod"]):r for r in rows}
municipalities=sorted({r["kommun_kod"] for r in rows if r["regime"]=="BAS_2020_2024" and int(r["year"])==2020})
if len(municipalities)!=290:raise RuntimeError("Municipality count mismatch")
methods=["no_adjustment","national_log_median","municipal_full","municipal_shrink_40"]
report={"status":"two_way_leave_one_year_out","methods":methods,"results":{},
 "important":["Only 2020 and 2021 are available in both systems; holdout is one year, not multi-year temporal validation.","Year-specific differences may combine revisions and true method effects.","No method is promoted to production by this audit."],"production_changed":False}
for dim in ("residence","workplace"):
    examples=[];by_method={m:[] for m in methods}
    for train,test in [(2020,2021),(2021,2020)]:
        factors={}
        for c in municipalities:
            a=float(idx[("RAMS_2019_2021",train,c)]["employed_"+dim])
            b=float(idx[("BAS_2020_2024",train,c)]["employed_"+dim])
            if a<=0 or b<=0:raise RuntimeError("Nonpositive employment")
            factors[c]=math.log(b/a)
        nationwide=statistics.median(factors.values())
        for method in methods:
            errors=[]
            for c in municipalities:
                x=0 if method=="no_adjustment" else nationwide if method=="national_log_median" else factors[c] if method=="municipal_full" else .4*factors[c]+.6*nationwide
                ram=float(idx[("RAMS_2019_2021",test,c)]["employed_"+dim])
                bas=float(idx[("BAS_2020_2024",test,c)]["employed_"+dim])
                err=100*(ram*math.exp(x)/bas-1)
                errors.append(abs(err));by_method[method].append(abs(err))
                if c=="2580":examples.append({"train":train,"test":test,"method":method,"absolute_error_percent":abs(err),"signed_error_percent":err})
            report["results"].setdefault(dim,{}).setdefault(method,{})[f"train_{train}_test_{test}"]={
                "median_abs_percent":statistics.median(errors),"mean_abs_percent":statistics.mean(errors),
                "p90_abs_percent":sorted(errors)[int(.9*(len(errors)-1))]}
    for method in methods:
        e=by_method[method]
        report["results"][dim][method]["pooled_holdout"]={"median_abs_percent":statistics.median(e),
            "mean_abs_percent":statistics.mean(e),"p90_abs_percent":sorted(e)[int(.9*(len(e)-1))]}
    report["results"][dim]["lulea"]=examples
(D/"rams_bas_calibration_loo_comparison.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
for dim in ("residence","workplace"):
    print(dim,{m:round(report["results"][dim][m]["pooled_holdout"]["mean_abs_percent"],4) for m in methods},flush=True)
