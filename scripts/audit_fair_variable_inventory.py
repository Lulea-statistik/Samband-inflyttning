#!/usr/bin/env python3
"""Stage A: inventory incumbent and eligible variables without fitting or changing any model."""
import json
from pathlib import Path
import pandas as pd
D=Path("docs/data")
BLOCK=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
def main():
    model=json.loads((D/"model.json").read_text(encoding="utf-8"))
    panel=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    fair=model.get("fair_reselection_test",{})
    incumbent=list(fair.get("incumbent_features",[]))
    eligible=list(fair.get("eligible_pool",[]))
    selected=list(model.get("features",[]) or [])
    names=list(dict.fromkeys(incumbent+eligible+selected))
    years=sorted(int(x) for x in panel.year.dropna().unique())
    entries=[]
    for name in names:
        present=name in panel.columns
        counts={str(y):int(panel.loc[panel.year.eq(y),name].notna().sum()) if present else 0 for y in years}
        entries.append({"feature":name,"present_in_panel":present,
           "incumbent":name in incumbent,"eligible_pool":name in eligible,
           "listed_model_features":name in selected,
           "blocked_for_blind":any(x in name for x in BLOCK),
           "coverage_by_year":counts,
           "definition_verified":False,"availability_date_verified":False,
           "historical_selection_standard_verified":False})
    report={"status":"stage_a_inventory","production_changed":False,"target":model.get("target"),
       "years":years,"n_panel_rows":len(panel),"incumbent_count":len(incumbent),
       "eligible_pool_count":len(eligible),"listed_model_features_count":len(selected),
       "variables":entries,
       "warnings":["Inventory lists declared candidates only; further external and historically rejected candidates need reconciliation.",
       "Definition, selection provenance and source publication availability still require manual audit.",
       "No new variable is approved for production by this inventory."]}
    (D/"fair_variable_inventory.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"incumbents":len(incumbent),"eligible":len(eligible),"present":sum(v["present_in_panel"] for v in entries),
       "blocked_for_blind":sum(v["blocked_for_blind"] for v in entries)},ensure_ascii=False))
if __name__=="__main__":main()
