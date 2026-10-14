#!/usr/bin/env python3
"""Build regime-labelled RAMS/BAS employment research levels, without smoothing or panel edits."""
import csv,json
from pathlib import Path
from collections import defaultdict
D=Path("docs/data")
def read_csv(name):
    with (D/name).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def main():
    r=read_csv("commuting_historical_rams.csv")
    b=read_csv("commuting_flows_2020_2024.csv")
    status=json.loads((D/"commuting_import_status.json").read_text(encoding="utf-8"))
    if not status.get("aggregation_approved"):raise RuntimeError("BAS origin-destination aggregation not approved")
    counts=defaultdict(lambda:[0.,0.]);seen=set()
    for x in b:
        year=int(x["year"]);h=x["home"].zfill(4);w=x["work"].zfill(4)
        key=(year,h,w)
        if key in seen:raise RuntimeError("Duplicate BAS pair "+str(key))
        seen.add(key)
        n=float(x["employed"])
        counts[(year,h)][0]+=n
        counts[(year,w)][1]+=n
    results=[]
    for x in r:
        y=int(x["year"]);c=x["kommun_kod"].zfill(4)
        local=float(x["local"]);out=float(x["outgoing"]);inc=float(x["incoming"])
        results.append({"year":y,"kommun_kod":c,"regime":x["regime"],
          "employed_residence":local+out,"employed_workplace":local+inc,
          "source":"RAMS_PendlingK","method_break_2011":int(y==2011),
          "method_break_2019":int(y==2019),"method_break_2024":0})
    for (y,c),(home,work) in counts.items():
        results.append({"year":y,"kommun_kod":c,"regime":"BAS_2020_2024",
          "employed_residence":home,"employed_workplace":work,
          "source":"BAS_ArRegPend2","method_break_2011":0,
          "method_break_2019":0,"method_break_2024":int(y==2024)})
    groups=defaultdict(set)
    for x in results:groups[(x["regime"],x["year"])].add(x["kommun_kod"])
    if len(r)!=5220 or any(len(v)!=290 for v in groups.values()):raise RuntimeError("Incomplete municipality year")
    if len(groups)!=23:raise RuntimeError("Expected 18 RAMS + 5 BAS years, got "+str(len(groups)))
    results.sort(key=lambda x:(x["year"],x["regime"],x["kommun_kod"]))
    out=D/"employment_historical_regime_research.csv"
    with out.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    # Growth is defined within each source regime; baseline year of each regime left blank.
    by_regime=defaultdict(list)
    for x in results:by_regime[(x["regime"],x["kommun_kod"])].append(x)
    changes=[]
    for (regime,c),ls in by_regime.items():
        ls.sort(key=lambda x:x["year"])
        for prev,curr in zip(ls,ls[1:]):
            if curr["year"]!=prev["year"]+1:raise RuntimeError("Gap within regime")
            changes.append({"year":curr["year"],"kommun_kod":c,"regime":regime,
                "residence_growth_pct":100*(curr["employed_residence"]/prev["employed_residence"]-1),
                "workplace_growth_pct":100*(curr["employed_workplace"]/prev["employed_workplace"]-1)})
    growth=D/"employment_growth_within_regimes.csv"
    with growth.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(changes[0]));w.writeheader();w.writerows(changes)
    report={"status":"separate_regime_research_only","level_records":len(results),
      "within_regime_growth_records":len(changes),"regime_year_coverage":{
         label:sorted(y for (lab,y) in groups if lab==label) for label in sorted({x["regime"] for x in results})},
      "overlap_years":[2020,2021],"production_changed":False,"limitations":[
       "No 2018/2019 RAMS cross-break growth computed; no RAMS/BAS cross-source growth computed.",
       "2011 and 2024 within-series changes are flagged because definitions may shift.",
       "BAS municipal pair totals may differ from separately published totals due to statistical disclosure control.",
       "No level correction has yet been applied; compare alternate bridge methods separately.",
       "Historic as-of publication dates must be confirmed before forecasting."
      ]}
    (D/"employment_historical_regime_status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
