#!/usr/bin/env python3
"""Classify correlated candidate pairs without eliminating variables or choosing by outcome."""
import json
from pathlib import Path
D=Path("docs/data")
audit=json.loads((D/"neutral_variable_family_correlation_audit.json").read_text(encoding="utf-8"))
inventory=json.loads((D/"neutral_variable_pool_reboot.json").read_text(encoding="utf-8"))
known={
 frozenset(["lag1_arbetskraftsdeltagande","lag1_utanf_arbetkraften_andel_pct"]):"complement_candidate",
 frozenset(["lag1_fritidshus_per_1000_inv","lag1_log_fritidshus_per_1000_inv"]):"monotone_transform",
 frozenset(["lag1_regional_centre_distance_km","lag1_log_regional_centre_distance_km"]):"monotone_transform",
 frozenset(["lag1_smahuspris_medel_tkr","lag1_log_smahuspris_medel"]):"monotone_transform",
 frozenset(["lag1_snoskoterandel_alla_fordon_pct","lag1_snoskoterandel_exkl_dragfordon_pct"]):"alternative_denominator",
 frozenset(["lag1_gymnasium_hogskoleforberedande_pct","lag1_gymnasium_yrkesprogram_pct"]):"possible_compositional_complement"
}
pairs=[]
for p in audit["high_correlation_pairs"]:
    key=frozenset([p["a"],p["b"]])
    tag=known.get(key,"empirical_association_only")
    pairs.append({"a":p["a"],"b":p["b"],"rho":p["spearman"],
      "n_complete_pairs":p["n_complete_pairs"],"provisional_relationship":tag,
      "algebraic_identity_proven":False,
      "restrict_joint_selection":False,
      "requires_definition_check":True})
res={"status":"neutral_correlated_pair_classification","inventory_size":len(inventory["records"]),
 "pair_count":len(pairs),"pairs":pairs,
 "rules":{
 "monotone_transform":"Consider alternative functional forms, not two independent signals; compare with train-only models.",
 "complement_candidate":"Confirm denominators and algebraic identity before treating as exact complements.",
 "alternative_denominator":"Different denominators may matter; compare definition and missingness, no forced exclusion.",
 "possible_compositional_complement":"Check shares cover same denominator and whether other categories exist.",
 "empirical_association_only":"Correlation alone does not justify forcing one variable per network or dropping one."
 },
 "fairness":["Incumbent and new variables have equal prior status.",
 "Separate demographic-blind and demographics-allowed universes.",
 "Report identical-row windows, source releases and full feature-family alternatives prior to tests.",
 "Use no outcome-based ranking or model selection in this report."],
 "production_changed":False,"variables_removed":0}
(D/"neutral_correlated_pair_classification.json").write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"pairs":len(pairs),"tagged_for_definition_review":sum(p["provisional_relationship"]!="empirical_association_only" for p in pairs),"removed":0},ensure_ascii=False))
