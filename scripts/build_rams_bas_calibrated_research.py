#!/usr/bin/env python3
"""BAS-scale RAMS history, research-only. Two-year overlap, guarded level correction."""
import csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
D=Path("docs/data")
def read(name):
    with (D/name).open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def median(x):return statistics.median(x)
def main():
    rows=read("employment_historical_regime_research.csv")
    idx={(x["regime"],int(x["year"]),x["kommun_kod"]):x for x in rows}
    bridge=json.loads((D/"rams_bas_employment_level_bridge.json").read_text(encoding="utf-8"))
    growth=json.loads((D/"rams_bas_growth_overlap_diagnostic.json").read_text(encoding="utf-8"))
    out=[];audit={"status":"research_bas_calibrated_rams","production_changed":False,"metrics":{},
      "limitations":["2020-2021 overlap is insufficient to infer time-varying methodological effects.",
      "Method break 2018/2019 unresolved; method adjustment is only calibrated at 2020-2021.",
      "Same overlap years are fitted and evaluated; in-sample residuals are not independent validation.",
      "Never overwrite historic raw RAMS, BAS, or production panel."]}
    for dimension in ("residence","workplace"):
        factors=bridge["series"][dimension]["municipal_factors"]
        rawratios={x["kommun_kod"]:{2020:float(x["ratio_2020"]),2021:float(x["ratio_2021"])} for x in factors}
        # Pooled annual mean log ratio is the reference. Shrink municipal offsets to avoid overfitting 2 years.
        common=median([math.log(v) for ratios in rawratios.values() for v in ratios.values()])
        local={c:math.log(ratios[2020])*0.5+math.log(ratios[2021])*0.5 for c,ratios in rawratios.items()}
        # Compromise: 40% municipality-specific offset, 60% common, fixed ex ante.
        adj={c:math.exp(.4*x+.6*common) for c,x in local.items()}
        bas_residuals=[];raw_residuals=[]
        for c in sorted(adj):
            for yr in (2020,2021):
                a=float(idx[("RAMS_2019_2021",yr,c)]["employed_"+dimension])
                b=float(idx[("BAS_2020_2024",yr,c)]["employed_"+dimension])
                raw_residuals.append(100*(a/b-1))
                bas_residuals.append(100*(a*adj[c]/b-1))
        def err(v):
            return {"median_absolute_percent":median([abs(x) for x in v]),
              "mean_absolute_percent":statistics.mean(abs(x) for x in v),
              "p90_absolute_percent":sorted(abs(x) for x in v)[int(.9*(len(v)-1))]}
        audit["metrics"][dimension]={"before":err(raw_residuals),"after":err(bas_residuals),
          "growth_overlap_median_difference_pp":growth["growth"][dimension]["difference_bas_minus_rams_pp"]["median"],
          "calibration_rule":"exp(0.40 * mean(log(BAS/RAMS) at 2020,2021) + 0.60 * pooled log-median)",
          "municipality_factors":adj}
        for r in rows:
            if not r["regime"].startswith("RAMS_"):continue
            c=r["kommun_kod"];year=int(r["year"])
            raw=float(r["employed_"+dimension])
            out.append({"year":year,"kommun_kod":c,"dimension":dimension,
              "regime":r["regime"],"raw_rams":raw,"bas_calibrated_rams":raw*adj[c],
              "adjustment_factor":adj[c],"method_break_2011":int(year==2011),
              "method_break_2019":int(year==2019),"production_approved":False})
    out.sort(key=lambda r:(r["dimension"],r["kommun_kod"],r["year"]))
    with (D/"rams_bas_calibrated_research.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    (D/"rams_bas_calibration_diagnostic.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"n":len(out),"scores":{d:{k:v[k] for k in ["before","after"]} for d,v in audit["metrics"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
