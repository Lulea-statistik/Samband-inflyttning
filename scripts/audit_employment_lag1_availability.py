#!/usr/bin/env python3
"""Audit lag-1 RAMS/BAS employment predictors by target year, without claiming source availability."""
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
D=Path("docs/data")
with (D/"employment_growth_regime_gated.csv").open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
preferred={"RAMS_2004_2018":0,"RAMS_2019_2021":1,"BAS_2020_2024":2}
# A target-year T uses a growth value labelled T-1; no source is *assumed* available then.
candidates=defaultdict(list)
for x in rows:
    if x["eligible_for_exploratory_predictor"]!="1":continue
    target=int(x["year"])+1
    candidates[(target,x["kommun_kod"],x["dimension"])].append(x)
out=[];counts=Counter();coverage=defaultdict(Counter);conflicts=0
for key,options in sorted(candidates.items()):
    t,c,dimension=key
    if len(options)>1:
        conflicts+=1
    # BAS is preferred in overlapping years, but only as a research default;
    # actual publication availability may invalidate the default for a target year.
    chosen=max(options,key=lambda x:preferred[x["regime"]])
    out.append({"target_year":t,"source_growth_year":t-1,"kommun_kod":c,
      "dimension":dimension,"preferred_research_regime":chosen["regime"],
      "growth_pct":chosen["raw_within_regime_growth_pct"],
      "alternative_regimes":";".join(sorted(x["regime"] for x in options if x is not chosen)),
      "source_release_verified":"0","eligible_for_regression_asof":"0",
      "block_reason":"source_release_date_not_verified"})
    coverage[t][dimension]+=1
    counts[chosen["regime"]]+=1
expected_years=sorted(coverage)
report={"status":"lag1_structural_coverage_only_asof_blocked","target_year_min":min(expected_years),
 "target_year_max":max(expected_years),"rows":len(out),"overlapping_choices":conflicts,
 "preferred_regime_counts":dict(counts),
 "target_year_coverage":{str(y):dict(v) for y,v in sorted(coverage.items())},
 "asof_approved_rows":0,"production_changed":False,
 "requirements":[
 "Verify annual source publication dates, edition/vintage and release month for each RAMS/BAS regime.",
 "For target year T, a lag1 employment-growth predictor uses observations T-1 and T-2; establish it was published by the chosen forecast origin, not merely by end of T.",
 "If the prediction is issued before publication, use a longer lag or a genuinely available data vintage; never backfill with hindsight.",
 "Treat RAMS/BAS overlapping candidate sources as distinct sensitivity variants, not an automatic approved blend.",
 "Compare predictive model runs on precisely common train/test municipalities and target years with no use of a repeatedly inspected holdout as a selection criterion.",
 "Resolve earlier RAMS 2011/2019 break uncertainty separately from BAS calibration."
 ]}
with (D/"employment_lag1_research_availability.csv").open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
(D/"employment_lag1_availability_gate_status.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"rows":len(out),"years":expected_years,"overlap_conflicts":conflicts,"asof_approved_rows":0},ensure_ascii=False))
