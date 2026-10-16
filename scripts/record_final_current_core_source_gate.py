#!/usr/bin/env python3
"""Finalize current source-evidence gate and record future snapshot requirements.

Non-predictive. No model fit and no production change.
"""
import json
from pathlib import Path

D=Path("docs/data")
prev=json.loads((D/"neutral_core_source_evidence_status.json").read_text(encoding="utf-8"))

out={
  "status":"core_source_gate_after_housing_finality_and_kolada_revision_review",
  "production_changed":False,
  "forecast_origin_research_reference":"2024-05-01",
  "features":{
    "lag1_inflyttning_per_1000":{
      "evidence_status":"strong_final_release_equivalence_not_exact_vintage",
      "strict_historical_snapshot_verified":False,
      "eligible_for_research_temporal_reconstruction":True,
      "reason":"SCB annual population statistics are final after full-year publication; exact historical API value snapshot is absent."
    },
    "lag1_utflyttning_per_1000":{
      "evidence_status":"strong_final_release_equivalence_not_exact_vintage",
      "strict_historical_snapshot_verified":False,
      "eligible_for_research_temporal_reconstruction":True,
      "reason":"Same annual SCB final-release rule as inflow."
    },
    "lag1_bostadsbestandsforandring_pct":{
      "evidence_status":"strong_final_release_equivalence_not_exact_vintage",
      "strict_historical_snapshot_verified":False,
      "eligible_for_research_temporal_reconstruction":True,
      "reason":"SCB BO0104 quality declaration states only final statistics are reported and publication is annual in April."
    },
    "lag1_kolada_arbetslosa_18_65_pct":{
      "source_id":"N03937",
      "evidence_status":"current_identity_verified_but_historical_vintage_not_certifiable",
      "strict_historical_snapshot_verified":False,
      "eligible_for_research_temporal_reconstruction":False,
      "definition_break":"Through 2022 the KPI refers to ages 18-64; from 2023 ages 18-65.",
      "reason":"Kolada states API data may be revised without separate notice and KPIs may be removed without notice. Current API cannot certify what values/definition were present at a past forecast origin."
    }
  },
  "decision":{
    "historical_strict_asof_core4_lock_allowed":False,
    "historical_research_reconstruction_without_kolada_possible":True,
    "do_not_run_further_variable_selection_on_2021_2023":True,
    "next_required_action":"start date-stamped source snapshots now so a future untouched outcome can be evaluated with truly frozen predictor vintages",
    "kolada_policy":"retain N03937 as provisional predictive candidate, but do not call it historically as-of verified; future validation must use a stored snapshot captured before the outcome",
    "temporal_module_deferred":True
  }
}
(D/"neutral_core_source_gate_final_current_evidence.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
