#!/usr/bin/env python3
"""Neutral reboot inventory: original model incumbents, 73 fair pool, and new employment candidates."""
import csv,json
from collections import Counter
from pathlib import Path
D=Path("docs/data")
def load(f):return json.loads((D/f).read_text(encoding="utf-8"))
reg=load("fair_variable_thematic_register.json")
history=load("fair_all_candidate_historical_coverage.json")
inventory=load("fair_variable_inventory.json")
hist={x["feature"]:x for x in history["features"]}
previous={x["feature"]:x for x in inventory["variables"]}
name_registry={x["feature"]:x for x in reg["records"]}
if len(name_registry)!=73 or len(hist)!=73:raise RuntimeError("Registry changed; review before proceeding")
with (D/"employment_lag1_research_availability.csv").open(newline="",encoding="utf-8") as f:lag=list(csv.DictReader(f))
new={"lag1_sysselsatta_bostad_rams_bas_historisk_forandring_pct":"residence",
     "lag1_sysselsatta_arbetsstalle_rams_bas_historisk_forandring_pct":"workplace"}
new_coverage={}
for feature,dimension in new.items():
    counts=Counter(int(x["target_year"]) for x in lag if x["dimension"]==dimension)
    new_coverage[feature]={str(y):counts[y] for y in range(2002,2025)}
names=sorted(set(hist)|set(previous)|set(new))
records=[]
for name in names:
    old=previous.get(name,{})
    h=hist.get(name,{})
    reg_record=name_registry.get(name,{})
    added=name in new
    coverage=new_coverage[name] if added else h.get("yearly_municipalities",old.get("coverage_by_year",{}))
    complete=sorted(int(y) for y,n in coverage.items() if n==290)
    prior_incumbent=bool(old.get("incumbent",False))
    blind_block=bool(old.get("blocked_for_blind",False))
    if added:blind_block=False
    windows={str(w):[y for y in complete if all(t in complete for t in range(y-w,y))] for w in (3,5,10)}
    records.append({"feature":name,"theme":reg_record.get("theme","arbetsmarknad_historisk" if added else "needs_classification"),
      "origin":"new_historical_rams_bas_candidate" if added else "fair_pool" if name in hist else "prior_inventory_only",
      "incumbent":prior_incumbent,"in_73_pool":name in hist,
      "eligible_original_pool":bool(old.get("eligible_pool",reg_record.get("original_candidate_pool",False))),
      "blind_model_eligible_subject_to_audit":not blind_block,
      "asof_verified":False,"method_definition_verified":False,
      "historical_year_coverage":coverage,"possible_full_year_windows":windows,
      "new_employment_growth_not_new_information_if_constant_factor":added,
      "notes":"Regime-gated historical growth, 2020 target gap; no publication-vintage validation" if added else
        "Historical coverage != as-of eligibility. Previously chosen and new candidates evaluated equally."})
out={"status":"neutral_inventory_only_no_selection","records":records,
 "counts":{"unique_variables":len(records),"fair_pool_original":len(hist),
   "prior_inventory":len(previous),"new_historical_employment_candidates":len(new),
   "incumbents_identified":sum(r["incumbent"] for r in records)},
 "no_default_incumbent_privilege":True,"production_changed":False,
 "requirements":[
 "One common selection protocol for incumbent and new candidates, no permanently fixed prior winners.",
 "Demographically blind and demographics-allowed model branches must remain separate.",
 "Document definition, source, chronology, lookahead, missingness, regime breaks and collinearity for every candidate.",
 "Treat the two new historical employment growth series as alternate history of existing BAS growth variables, not automatically two additional independent predictors.",
 "Choose control variables a priori, fix common rows/windows, do all imputations and hyperparameter selection within training only.",
 "Retrospective 2024 results are exploratory, not an unseen holdout.",
 "No new model fits or production changes in this inventory."
 ]}
(D/"neutral_variable_pool_reboot.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(out["counts"],ensure_ascii=False))
