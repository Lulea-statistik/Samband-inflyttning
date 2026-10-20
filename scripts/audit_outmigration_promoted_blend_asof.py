#!/usr/bin/env python3
"""Production as-of/source-vintage gate for promoted outmigration blend.

The statistical specification is already selected:
  25% lag1-only 3y + 75% lag1-only 10y.

This gate is intentionally non-predictive. It only checks whether the sole
feature's source and denominator are historically as-of certified.

Production must remain blocked until exact historical value-vintage evidence is
available for both SCB migration counts and population denominator.
"""
import json
from pathlib import Path

D=Path("docs/data")
pool=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
core=json.loads((D/"neutral_scb_core_forecast_origin_gate.json").read_text(encoding="utf-8"))
wayback=json.loads((D/"neutral_scb_wayback_vintage_evidence.json").read_text(encoding="utf-8"))
blend=json.loads((D/"outmigration_blend_promotion_gate.json").read_text(encoding="utf-8"))

feature=next(x for x in pool["records"] if x["feature"]=="lag1_utflyttning_per_1000")
migration=core["sources"]["migration"]
population=core["sources"]["population_denominator"]

checks={
 "blend_statistical_gate_passed": bool(blend["passes"]),
 "feature_asof_verified_in_registry": bool(feature.get("asof_verified",False)),
 "feature_method_definition_verified": bool(feature.get("method_definition_verified",False)),
 "migration_exact_historical_table_vintage_certified": bool(migration.get("exact_historical_table_vintage_certified",False)),
 "population_exact_historical_table_vintage_certified": bool(population.get("exact_historical_table_vintage_certified",False)),
}

migration_captures=(wayback.get("results",{}).get("migration",{}).get("pxweb",{}).get("captures") or [])
population_captures=(wayback.get("results",{}).get("population",{}).get("pxweb",{}).get("captures") or [])

checks["migration_wayback_metadata_capture_exists"]=len(migration_captures)>0
checks["population_wayback_metadata_capture_exists"]=len(population_captures)>0

strict_required=[
 "blend_statistical_gate_passed",
 "feature_asof_verified_in_registry",
 "feature_method_definition_verified",
 "migration_exact_historical_table_vintage_certified",
 "population_exact_historical_table_vintage_certified",
]
passes=all(checks[k] for k in strict_required)

out={
 "status":"outmigration_promoted_blend_asof_source_vintage_gate",
 "candidate":"0.25 * lag1-only 3y + 0.75 * lag1-only 10y",
 "feature":"lag1_utflyttning_per_1000",
 "source_definition":{
   "migration_table":migration["table_id"],
   "population_table":population["table_id"],
   "migration_url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101J/Flyttningar97",
   "population_url":"https://api.scb.se/OV0104/v1/doris/sv/ssd/START/BE/BE0101/BE0101A/BefolkningNy"
 },
 "checks":checks,
 "strict_required_checks":strict_required,
 "passes_production_asof_gate":passes,
 "production_status":"eligible" if passes else "blocked_pending_exact_historical_value_vintage",
 "statistical_specification_status":"promoted_and_frozen",
 "production_changed":False,
 "inflow_model_changed":False,
 "evidence_interpretation":{
   "wayback_metadata_capture_is_sufficient_for_table_existence":True,
   "wayback_metadata_capture_is_sufficient_for_exact_cell_values":False,
   "current_blocker":"Exact historical value snapshots or equivalent version-specific evidence are still required for migration and population denominator."
 },
 "next_required_evidence":[
   "Exact/version-specific evidence showing municipal Flyttningar97 values available at each relevant historical forecast origin.",
   "Exact/version-specific evidence showing BefolkningNy denominator values and revision state at each relevant historical forecast origin.",
   "After evidence is obtained, update neutral_variable_pool_reboot.json flags for lag1_utflyttning_per_1000 only through a documented audit."
 ]
}
(D/"outmigration_promoted_blend_asof_source_vintage_gate.json").write_text(
 json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
