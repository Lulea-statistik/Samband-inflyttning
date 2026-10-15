#!/usr/bin/env python3
"""Produce an evidence-first as-of gate; never infer publication dates from data year."""
import json
from collections import Counter
from pathlib import Path
D=Path("docs/data")
load=lambda n:json.loads((D/n).read_text(encoding="utf-8"))
inv=load("neutral_variable_pool_reboot.json")
gate=load("neutral_80_candidate_data_gate.json")
elig=load("fair_variable_eligibility_audit.json")
decision=load("production_decision.json")
e={x["feature"]:x for x in elig["features"]}
rows=[]
for x in inv["records"]:
    n=x["feature"]
    a=e.get(n,{})
    rows.append({
        "feature":n,"theme":x["theme"],"incumbent":x["incumbent"],
        "blind_model_allowed_preliminarily":x["blind_model_eligible_subject_to_audit"],
        "observed_2019_2023":all(gate["variables"][n][str(y)]==290 for y in range(2019,2024)),
        "observed_2021_2023":all(gate["variables"][n][str(y)]==290 for y in range(2021,2024)),
        "observed_2022_2023":all(gate["variables"][n][str(y)]==290 for y in range(2022,2024)),
        "source_release_review":a.get("source_and_release_timing_review","not_recorded"),
        "source_version_evidence":None,
        "first_publication_datetime":None,
        "forecast_origin_datetime":None,
        "historical_asof_eligible":False,
        "blocker":"No verified archived source release and forecast-origin evidence."
    })
out={
 "status":"neutral_temporal_asof_evidence_gate",
 "n_candidates":len(rows),
 "n_full_five_years":sum(x["observed_2019_2023"] for x in rows),
 "n_full_three_years":sum(x["observed_2021_2023"] for x in rows),
 "n_historically_asof_verified":sum(x["historical_asof_eligible"] for x in rows),
 "n_source_release_verified":sum(x["first_publication_datetime"] is not None for x in rows),
 "production_decision_status":decision.get("status"),
 "production_active_model":decision.get("active_model"),
 "production_challenger":decision.get("challenger"),
 "historical_outcome_2023_2024_already_inspected":True,
 "blocked_strict_temporal_comparison":True,
 "features":rows,
 "next_requirements":[
  "Retrieve archived source publication records for each intended original vintage.",
  "Specify forecast origin cutoff, data revisions and available municipality coverage.",
  "Reconstruct active production pipeline and predictions for identical cutoff dates.",
  "Freeze an independent subsequent outcome year before reporting confirmatory performance."
 ],
 "warning":"Full present-day historical coverage does not imply as-of availability. No vintage verification performed.",
 "production_changed":False
}
assert len(rows)==80
(D/"neutral_temporal_asof_evidence_gate.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:out[k] for k in ("n_candidates","n_full_five_years","n_full_three_years","n_historically_asof_verified","production_active_model")}))
