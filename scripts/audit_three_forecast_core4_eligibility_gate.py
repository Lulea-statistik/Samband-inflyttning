#!/usr/bin/env python3
"""Create a machine-readable eligibility gate for the provisional 3-year forecast core-4.

This is a non-predictive audit. It does not fit any model and does not change production.
"""
import json
from pathlib import Path

D=Path("docs/data")
read=lambda n:json.loads((D/n).read_text(encoding="utf-8"))
pool={r["feature"]:r for r in read("neutral_variable_pool_reboot.json")["records"]}
coverage=read("neutral_80_candidate_data_gate.json")["variables"]

CORE4=[
    "lag1_inflyttning_per_1000",
    "lag1_utflyttning_per_1000",
    "lag1_valdeltagande_gap_pp",
    "lag1_bostadsbestandsforandring_pct",
]

rows=[]
for f in CORE4:
    r=pool[f]
    cov=coverage[f]
    rows.append({
        "feature":f,
        "theme":r.get("theme"),
        "origin":r.get("origin"),
        "incumbent":r.get("incumbent"),
        "asof_verified":bool(r.get("asof_verified",False)),
        "method_definition_verified":bool(r.get("method_definition_verified",False)),
        "coverage_2020_2024":{str(y):cov.get(str(y),0) for y in range(2020,2025)},
        "possible_full_year_windows":r.get("possible_full_year_windows",{}),
        "gate_status":"eligible_for_lockin" if r.get("asof_verified") and r.get("method_definition_verified") else "blocked_pending_source_vintage_and_definition_audit",
        "notes":r.get("notes")
    })

out={
    "status":"non_predictive_core4_eligibility_gate",
    "production_changed":False,
    "core4":CORE4,
    "all_asof_verified":all(r["asof_verified"] for r in rows),
    "all_method_definitions_verified":all(r["method_definition_verified"] for r in rows),
    "lockin_allowed":all(r["gate_status"]=="eligible_for_lockin" for r in rows),
    "records":rows,
    "decision":{
        "model_status":"provisional_sparse_candidate_not_locked",
        "next_required_step":"verify source vintage and exact feature derivation for all four variables before any temporal confirmation or production reconsideration",
        "no_more_reselection_on_2021_2023":True,
        "temporal_module_deferred":True
    }
}
(D/"neutral_three_forecast_core4_eligibility_gate.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
