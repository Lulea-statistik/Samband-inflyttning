#!/usr/bin/env python3
"""Stage A2: reconcile historic and newer research candidates without changing production."""
import json
from pathlib import Path
import pandas as pd
D=Path("docs/data")
EXPLICIT={
 "lag1_kolada_utbetalt_lok_stod_kr_per_inv":"LOK civic support",
 "lag1_sysselsatta_bostad_forandring_pct":"Employment growth",
 "lag1_tatortsgrad_pct":"Urbanisation",
 "lag1_naturpraglad_mark_andel_land_pct":"Natural land",
 "lag1_strand_hav_bostader_tatort_per_1000":"Coastal housing",
 "lag1_kolada_langtidsarbetslosa_pct":"Long-term unemployment",
 "lag1_regional_centre_distance_km":"Regional centre distance",
}
FORBIDDEN=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
def main():
    inventory=json.loads((D/"fair_variable_inventory.json").read_text(encoding="utf-8"))
    data=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    tracked={x["feature"] for x in inventory["variables"]}
    candidate_fields=sorted([c for c in data.columns if c.startswith("lag1_")])
    missed=[c for c in candidate_fields if c not in tracked]
    years=[2022,2023,2024]
    added=[]
    for field in missed:
        added.append({"feature":field,"context":EXPLICIT.get(field,"Panel variable not in declared candidate pool"),
          "previously_researched":field in EXPLICIT,
          "blind_forbidden":any(z in field for z in FORBIDDEN),
          "coverage":{str(y):int(data.loc[data.year.eq(y),field].notna().sum()) for y in years},
          "eligibility":"requires manual definition and source timing verification",
          "automatically_selected":False})
    missing_explicit=[k for k in EXPLICIT if k not in data.columns]
    report={"status":"reconciled_inventory_diagnostic","production_changed":False,
       "original_incumbents":inventory["incumbent_count"],
       "original_candidate_pool":inventory["eligible_pool_count"],
       "panel_lagged_fields":len(candidate_fields),
       "not_in_original_pool":len(missed),"previously_researched_outside_pool":[x for x in added if x["previously_researched"]],
       "other_untracked_lagged_fields":[x for x in added if not x["previously_researched"]],
       "missing_explicit_candidates":missing_explicit,
       "caveats":["Not every lag1 panel column is scientifically admissible.",
          "No automatic candidate promotion; source definition, forecast-time availability and coverage require verification.",
          "A fair selection run must freeze the confirmed pool and common samples before testing.",
          "Historical rejection and source provenance must also be reviewed manually."]}
    (D/"fair_variable_inventory_reconciliation.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("original_incumbents","original_candidate_pool","panel_lagged_fields","not_in_original_pool","missing_explicit_candidates")},ensure_ascii=False))
if __name__=="__main__":main()
