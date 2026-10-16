#!/usr/bin/env python3
"""Non-predictive source/method gate for corrected no-lookahead 3-year forecast core."""
import json
from pathlib import Path

D=Path("docs/data")
corr=json.loads((D/"neutral_three_forecast_no_lookahead_correction.json").read_text(encoding="utf-8"))
pool={r["feature"]:r for r in json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))["records"]}

core4=[
 "lag1_inflyttning_per_1000",
 "lag1_utflyttning_per_1000",
 "lag1_kolada_arbetslosa_18_65_pct",
 "lag1_bostadsbestandsforandring_pct",
]

freq={f:0 for f in core4}
for fold in corr["outer_folds"]:
    stable=(fold.get("stable") or {}).get("stable_features",[])
    for f in core4:
        if f in stable:
            freq[f]+=1

records=[
 {
  "feature":"lag1_inflyttning_per_1000",
  "fold_frequency":freq["lag1_inflyttning_per_1000"],
  "method_definition_verified":True,
  "derivation":"1000 * inflyttade / folkmangd, then municipality shift(1)",
  "source":"SCB BE0101J/Flyttningar97 plus SCB population denominator",
  "source_identifier_fixed_in_code":True,
  "asof_verified":False,
  "blocking_issue":"Exact historical table vintage/publication availability and revision state are not certified."
 },
 {
  "feature":"lag1_utflyttning_per_1000",
  "fold_frequency":freq["lag1_utflyttning_per_1000"],
  "method_definition_verified":True,
  "derivation":"1000 * utflyttade / folkmangd, then municipality shift(1)",
  "source":"SCB BE0101J/Flyttningar97 plus SCB population denominator",
  "source_identifier_fixed_in_code":True,
  "asof_verified":False,
  "blocking_issue":"Exact historical table vintage/publication availability and revision state are not certified."
 },
 {
  "feature":"lag1_kolada_arbetslosa_18_65_pct",
  "fold_frequency":freq["lag1_kolada_arbetslosa_18_65_pct"],
  "method_definition_verified":True,
  "derivation":"Observed annual Kolada municipality KPI value, then municipality shift(1)",
  "source":"Kolada API v3; semantic title 'Arbetslösa i befolkningen, 18-65 år, andel (%)'",
  "source_identifier_fixed_in_code":False,
  "asof_verified":False,
  "blocking_issue":"KPI id is resolved dynamically by semantic title and recent coverage rather than pinned in KOLADA_UNEMPLOYMENT_SPECS. Historical KPI identity, replacement history, publication timing and revisions must be frozen before strict as-of use.",
  "known_research_alias":"Repository diagnostics refer to this candidate as N03937, but executable source selection currently remains dynamic."
 },
 {
  "feature":"lag1_bostadsbestandsforandring_pct",
  "fold_frequency":freq["lag1_bostadsbestandsforandring_pct"],
  "method_definition_verified":True,
  "derivation":"100 * pct_change(bostader_totalt) within municipality, then shift(1)",
  "source":"SCB BO0104D/BO0104T04",
  "source_identifier_fixed_in_code":True,
  "asof_verified":False,
  "blocking_issue":"Exact historical PxWeb vintages and revision state are not certified; recent product release dates alone are insufficient."
 }
]

out={
 "status":"corrected_core4_source_method_gate",
 "production_changed":False,
 "corrected_core4":core4,
 "selection_frequency_outer_folds":freq,
 "core_rule":"three variables selected in 5/5 corrected folds plus housing-stock change selected in 4/5; no manual substitute added",
 "all_method_definitions_verified":all(r["method_definition_verified"] for r in records),
 "all_asof_verified":all(r["asof_verified"] for r in records),
 "lockin_allowed":False,
 "records":records,
 "decision":{
   "model_status":"corrected_provisional_core4_not_locked",
   "next_priority":[
      "freeze and verify exact Kolada unemployment KPI identity and historical availability",
      "verify SCB migration table vintages and denominator availability at explicit forecast origins",
      "verify SCB housing-stock table vintages and revisions",
      "only then perform temporal confirmation under the already frozen protocol"
   ],
   "no_new_model_selection":True,
   "temporal_module_deferred":True
 }
}
(D/"neutral_three_forecast_corrected_core4_source_gate.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
