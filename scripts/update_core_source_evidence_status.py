#!/usr/bin/env python3
"""Non-predictive evidence-status update for corrected 3-year forecast core.

Uses documented SCB finality rules for annual population statistics to distinguish
strong final-release equivalence from exact archived table-vintage evidence.
"""
import json
from pathlib import Path

D=Path("docs/data")
wayback=json.loads((D/"neutral_scb_wayback_vintage_evidence.json").read_text(encoding="utf-8"))
origin=json.loads((D/"neutral_scb_core_forecast_origin_gate.json").read_text(encoding="utf-8"))

out={
 "status":"core_source_evidence_status_after_scb_finality_review",
 "production_changed":False,
 "forecast_origin":"2024-05-01",
 "evidence_levels":{
   "lag1_inflyttning_per_1000":{
      "method_definition_verified":True,
      "source_identity_verified":True,
      "official_release_before_origin":True,
      "annual_statistics_final_after_release":True,
      "exact_archived_table_value_snapshot":False,
      "evidence_status":"strong_final_release_equivalence_not_exact_vintage",
      "asof_verified":False,
      "reason":"SCB documents that annual population statistics become final at December/full-year publication and are not revised further; exact historical Flyttningar97 POST-value snapshot is still absent."
   },
   "lag1_utflyttning_per_1000":{
      "method_definition_verified":True,
      "source_identity_verified":True,
      "official_release_before_origin":True,
      "annual_statistics_final_after_release":True,
      "exact_archived_table_value_snapshot":False,
      "evidence_status":"strong_final_release_equivalence_not_exact_vintage",
      "asof_verified":False,
      "reason":"Same SCB finality rule as inflow; exact historical table-value snapshot is still absent."
   },
   "lag1_bostadsbestandsforandring_pct":{
      "method_definition_verified":True,
      "source_identity_verified":True,
      "official_release_before_origin":True,
      "annual_statistics_final_after_release":None,
      "exact_archived_table_value_snapshot":False,
      "evidence_status":"blocked_revision_policy_not_yet_verified",
      "asof_verified":False,
      "reason":"Wayback proves the table page existed before the 2023 product release, so page existence cannot certify 2023 values. A product-specific revision/finality rule or value snapshot is still needed."
   },
   "lag1_kolada_arbetslosa_18_65_pct":{
      "method_definition_verified":True,
      "source_identity_verified":True,
      "source_id":"N03937",
      "definition_break":"Through 2022 age 18-64; from 2023 age 18-65.",
      "historical_publication_identity_verified":False,
      "evidence_status":"blocked_historical_publication_and_definition_break",
      "asof_verified":False,
      "reason":"Current KPI identity is pinned, but historical publication/replacement timing is not certified and the age definition changes in 2023."
   }
 },
 "wayback_summary":{
   "population_pxweb_captures":[c["timestamp"] for c in wayback["results"]["population"]["pxweb"].get("captures",[])],
   "housing_pxweb_captures":[c["timestamp"] for c in wayback["results"]["housing"]["pxweb"].get("captures",[])],
   "migration_exact_captures_found":bool(wayback["results"]["migration"]["api"].get("captures") or wayback["results"]["migration"]["pxweb"].get("captures"))
 },
 "decision":{
   "full_core_asof_lock_allowed":False,
   "migration_population_evidence_upgraded":True,
   "next_blockers":[
      "housing-stock product-specific revision/finality evidence or archived 2023 value snapshot",
      "Kolada N03937 historical publication/replacement evidence and treatment of 2023 age-definition break"
   ],
   "no_new_model_selection":True,
   "temporal_module_deferred":True
 }
}
(D/"neutral_core_source_evidence_status.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
