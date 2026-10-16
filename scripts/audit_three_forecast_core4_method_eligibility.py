#!/usr/bin/env python3
"""Audit strict forecast eligibility of the provisional core-4 and declare exclusions.

Non-predictive. Reads executable feature derivations and the neutral inventory.
"""
import json
from pathlib import Path

D=Path("docs/data")
pool={r["feature"]:r for r in json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))["records"]}

records=[
 {
  "feature":"lag1_inflyttning_per_1000",
  "method_definition_verified":True,
  "derivation":"1000 * inflyttade / folkmangd, then municipality shift(1)",
  "upstream_source":"SCB BE0101J/Flyttningar97 + SCB population denominator",
  "strict_forecast_status":"blocked_pending_exact_source_vintage",
  "reason":"Derivation is explicit, but exact historical PxWeb table vintage/publication availability is not yet certified."
 },
 {
  "feature":"lag1_utflyttning_per_1000",
  "method_definition_verified":True,
  "derivation":"1000 * utflyttade / folkmangd, then municipality shift(1)",
  "upstream_source":"SCB BE0101J/Flyttningar97 + SCB population denominator",
  "strict_forecast_status":"blocked_pending_exact_source_vintage",
  "reason":"Derivation is explicit, but exact historical PxWeb table vintage/publication availability is not yet certified."
 },
 {
  "feature":"lag1_valdeltagande_gap_pp",
  "method_definition_verified":True,
  "derivation":"municipality max-minus-min district turnout at election years; annual values linearly interpolated between election years; then shift(1)",
  "upstream_source":"Valmyndigheten election-result workbooks",
  "strict_forecast_status":"ineligible_current_derivation_lookahead",
  "reason":"build_analysis.py explicitly lists this feature in LOOKAHEAD_ONLY_FEATURES. Linear interpolation uses later election results for intervening historical years, so it is not an as-of predictor."
 },
 {
  "feature":"lag1_bostadsbestandsforandring_pct",
  "method_definition_verified":True,
  "derivation":"100 * municipality pct_change(bostader_totalt), then shift(1)",
  "upstream_source":"SCB BO0104D/BO0104T04",
  "strict_forecast_status":"blocked_pending_exact_source_vintage",
  "reason":"Derivation is explicit. SCB product release dates are known for recent years, but exact historical table vintages and revision state are not certified."
 }
]

out={
 "status":"strict_forecast_core4_method_eligibility_audit",
 "production_changed":False,
 "records":records,
 "lookahead_only_features_in_code":["lag1_valdeltagande_pct","lag1_valdeltagande_gap_pp"],
 "method_definition_verified_count":sum(r["method_definition_verified"] for r in records),
 "strictly_eligible_now":[r["feature"] for r in records if r["strict_forecast_status"]=="eligible"],
 "ineligible_due_to_lookahead":[r["feature"] for r in records if "lookahead" in r["strict_forecast_status"]],
 "blocked_pending_vintage":[r["feature"] for r in records if r["strict_forecast_status"]=="blocked_pending_exact_source_vintage"],
 "decision":{
   "provisional_core4_invalid_for_strict_forecast_as_currently_derived":True,
   "required_model_action":"repeat the already-registered neutral 3-year forecast selection protocol with only the two code-declared LOOKAHEAD_ONLY_FEATURES removed; do not add or otherwise alter candidates",
   "reason_for_reselection":"eligibility correction, not outcome-driven optimization",
   "temporal_module_deferred":True
 }
}
(D/"neutral_three_forecast_core4_method_eligibility_audit.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
