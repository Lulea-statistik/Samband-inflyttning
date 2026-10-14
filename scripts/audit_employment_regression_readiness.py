#!/usr/bin/env python3
"""Research-only evaluation design for historically extended employment growth.
No models are fit; current panel coverage is not proof of publication-time availability.
"""
import csv,json
from collections import defaultdict
from pathlib import Path
D=Path("docs/data")
with (D/"employment_lag1_research_availability.csv").open(encoding="utf-8",newline="") as f:
    lag=list(csv.DictReader(f))
with (D/"panel.csv").open(encoding="utf-8",newline="") as f:
    panel=list(csv.DictReader(f))
model=json.loads((D/"model.json").read_text(encoding="utf-8"))
target=model["target"]
history=json.loads((D/"fair_all_candidate_historical_coverage.json").read_text(encoding="utf-8"))
index={(int(x["target_year"]),x["kommun_kod"],x["dimension"]):x for x in lag}
if len(index)!=len(lag):raise RuntimeError("Duplicate lagged candidate entries")
panel_map={(int(x["year"]),x["kommun_kod"]):x for x in panel}
years=sorted({x[0] for x in index})
dims=("residence","workplace")
def present(v):return v is not None and v!="" and v.lower() not in ("nan","none","null")
result={"status":"pre_registered_retro_coverage_only","target":target,"years":{},
  "fixed_structural_controls":["lag1_log_folkmangd","lag1_tatortsgrad_pct"],
  "excluded_short_history_control":"lag1_regional_centre_distance_km",
  "production_changed":False,
  "asof_gate":"blocked_until_exact_forecast_origin_and_source_vintages_defined",
  "rules":[
   "Use common municipality-year observations with outcomes available; no per-method sample changes.",
   "Retrospective association analysis may use revised historic predictors if identified as such; do not claim genuine historical forecasting.",
   "Strict forecasting must fit BAS calibration only from vintages known at each historic training origin; currently no as-of-approved rows.",
   "An identical constant municipality correction cancels from RAMS percent growth, so corrected and uncorrected within-regime growth cannot be independent regression candidates.",
   "Exclude method break years 2011 and 2024 and do not compute 2018-to-2019 or cross-source annual growth.",
   "Preserve previously inspected 2023 and 2024 as exploratory; do not choose the best model by those years."
  ]}
for y in years:
    valid={d:set() for d in dims}
    for d in dims:
        for c in {k[1] for k in index if k[0]==y and k[2]==d}:
            p=panel_map.get((y,c))
            if p and present(p.get(target)):valid[d].add(c)
    both=valid["residence"]&valid["workplace"]
    controls={}
    for feat in result["fixed_structural_controls"]:
        controls[feat]=len({c for c in both if present(panel_map[(y,c)].get(feat))})
    with_controls={c for c in both if all(present(panel_map[(y,c)].get(feat)) for feat in result["fixed_structural_controls"])}
    result["years"][str(y)]={"outcome_and_residence":len(valid["residence"]),
        "outcome_and_workplace":len(valid["workplace"]),
        "both_growth_plus_outcome":len(both),
        "structural_controls_each":controls,
        "both_growth_outcome_and_controls":len(with_controls),
        "source_release_verified":False}
for window in (3,5,10):
    possible=[]
    for y in years:
        if all(result["years"].get(str(t),{}).get("both_growth_outcome_and_controls")==290 for t in range(y-window,y+1)):
            possible.append(y)
    result["years_with_complete_train_and_test_"+str(window)]=possible
(D/"employment_retrospective_regression_readiness.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"complete_windows":{str(w):result["years_with_complete_train_and_test_"+str(w)] for w in (3,5,10)}, "all_years":len(years)},ensure_ascii=False))
