#!/usr/bin/env python3
"""RAMS/BAS overlap: paired 2020-2021 employment growth agreement, no splicing."""
import csv,json,statistics
from pathlib import Path
D=Path("docs/data")
with (D/"employment_historical_regime_research.csv").open(encoding="utf-8",newline="") as f:
    rows=list(csv.DictReader(f))
idx={(x["regime"],int(x["year"]),x["kommun_kod"]):x for x in rows}
def pct(a,b):return 100*(float(b)/float(a)-1)
def describe(values):
    s=sorted(values)
    return {"n":len(s),"mean":statistics.mean(s),"median":statistics.median(s),
      "p10":s[int(.1*(len(s)-1))],"p90":s[int(.9*(len(s)-1))],
      "max_abs":max(abs(x) for x in s)}
results={"status":"separate_overlap_growth_diagnostic","years":[2020,2021],
 "production_changed":False,"growth":{},"limitations":[
 "Comparison is limited to one common annual change (2020-2021); stability beyond the overlap cannot be inferred.",
 "RAMS 2018/2019 method change and BAS 2024 classification change are separate and unresolved.",
 "Close agreement does not validate historic publication availability or support automatic series splicing."]}
for dimension in ("residence","workplace"):
    differences=[];details=[]
    for municipality in sorted(x["kommun_kod"] for x in rows if x["regime"]=="RAMS_2019_2021" and x["year"]=="2021"):
        series={}
        for regime in ("RAMS_2019_2021","BAS_2020_2024"):
            a=idx[(regime,2020,municipality)]
            b=idx[(regime,2021,municipality)]
            series[regime]=pct(a["employed_"+dimension],b["employed_"+dimension])
        difference=series["BAS_2020_2024"]-series["RAMS_2019_2021"]
        differences.append(difference)
        details.append({"kommun_kod":municipality,"rams_growth_pct":series["RAMS_2019_2021"],
          "bas_growth_pct":series["BAS_2020_2024"],"difference_pp":difference})
    if len(details)!=290:raise RuntimeError("Expected 290 paired municipalities")
    results["growth"][dimension]={"difference_bas_minus_rams_pp":describe(differences),
      "n_abs_difference_gt_1pp":sum(abs(x)>1 for x in differences),
      "n_abs_difference_gt_2pp":sum(abs(x)>2 for x in differences),
      "lulea":next(x for x in details if x["kommun_kod"]=="2580"),
      "top_absolute_differences":sorted(details,key=lambda x:-abs(x["difference_pp"]))[:20],
      "paired_municipalities":details}
(D/"rams_bas_growth_overlap_diagnostic.json").write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps({k:{"median_diff_pp":v["difference_bas_minus_rams_pp"]["median"],"abs_gt_1":v["n_abs_difference_gt_1pp"]} for k,v in results["growth"].items()},ensure_ascii=False))
