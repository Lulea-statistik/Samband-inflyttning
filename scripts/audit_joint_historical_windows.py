#!/usr/bin/env python3
"""Compute common municipality-year windows, without fitting models."""
import json
from collections import Counter
from pathlib import Path
D=Path("docs/data")
CONTROLS=["lag1_log_folkmangd","lag1_tatortsgrad_pct","lag1_regional_centre_distance_km"]
def main():
    j=json.loads((D/"fair_all_candidate_historical_coverage.json").read_text(encoding="utf-8"))
    features=j["features"]
    by_name={x["feature"]:x for x in features}
    years=j["years"]
    if len(by_name)!=73:raise RuntimeError("Unexpected candidate count")
    # The historical original-vs-expanded comparison must keep a shared sample.
    output={"status":"joint_historical_window_feasibility","n_candidates":73,
      "controls":CONTROLS,"control_missing":[c for c in CONTROLS if c not in by_name],
      "coverage_threshold":290,"production_changed":False,"windows":{}}
    for length in (3,5,10):
        result=[]
        for forecast in years:
            required=list(range(forecast-length,forecast+1))
            if not set(required).issubset(years):continue
            complete=[x for x in features if all(x["yearly_municipalities"].get(str(y),0)==290 for y in required)]
            by_theme=Counter(x["theme"] for x in complete)
            old=sum(bool(x["original_candidate_pool"]) for x in complete)
            controls_ready=all(c in {x["feature"] for x in complete} for c in CONTROLS)
            result.append({"forecast_year":forecast,"training_years":required[:-1],
                "eligible_count":len(complete),"old_candidates":old,
                "new_candidates":len(complete)-old,"controls_ready":controls_ready,
                "available_themes":dict(sorted(by_theme.items())),
                "features":[x["feature"] for x in complete]})
        output["windows"][str(length)]=result
    output["warnings"]=[
      "Full municipality coverage in a current restated panel does not confirm historic publication timing.",
      "Candidate availability is tested jointly on common years but not on missingness within non-290 subsets.",
      "Control features are pre-specified and must be assessed explicitly before any modeling.",
      "Historical 2023/2024 outcomes have already been inspected and are not pristine validation."
    ]
    (D/"fair_joint_historical_windows.json").write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:[{"year":r["forecast_year"],"n":r["eligible_count"],"controls_ready":r["controls_ready"]} for r in v]
        for k,v in output["windows"].items()},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
