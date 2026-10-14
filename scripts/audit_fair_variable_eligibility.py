#!/usr/bin/env python3
"""Stage A3: common-sample and correlation audit, never changes production."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

D=Path("docs/data")
BLOCK=("inflytt","utflytt","befolkningstillvaxt","inflyttare_medelalder","andel_20_34")
def main():
    reconciled=json.loads((D/"fair_variable_inventory_reconciliation.json").read_text(encoding="utf-8"))
    prior=json.loads((D/"fair_variable_inventory.json").read_text(encoding="utf-8"))
    data=pd.read_csv(D/"panel.csv",dtype={"kommun_kod":str},low_memory=False)
    years=[2022,2023,2024]
    subset=data.loc[data.year.isin(years)&data.kommun_kod.str.fullmatch(r"\d{4}",na=False)].copy()
    base={v["feature"] for v in prior["variables"]}
    extra={v["feature"] for v in reconciled["previously_researched_outside_pool"]+reconciled["other_untracked_lagged_fields"]}
    all_candidates=sorted(base|extra)
    report={"status":"stage_a3_preselection_eligibility","production_changed":False,"years":years,
      "n_sample_rows":len(subset),"n_unique_municipalities":int(subset.kommun_kod.nunique()),
      "features":[],"high_correlations":[],"limitations":[
        "Coverage is only technical; forecast-time publication dates and semantic definitions remain unverified.",
        "Never treat any feature as production-approved based on this audit.",
        "Strongly correlated variables are flagged for group substitution, not automatically deleted.",
        "Known 2023-2024 evaluations are exploratory, not an independent test."]}
    }
    eligible=[]
    for v in all_candidates:
        counts={str(year):int(subset.loc[subset.year.eq(year),v].notna().sum()) if v in subset else 0 for year in years}
        complete=bool(v in subset and subset[v].notna().all() and len(subset)==870)
        blocked=any(f in v for f in BLOCK)
        report["features"].append({"feature":v,"historical_pool":v in base,"newly_discovered":v in extra,
          "n_by_year":counts,"complete_sample_2022_2024":complete,
          "blind_predictor_allowed_by_name":not blocked,
          "source_and_release_timing_review":"pending",
          "candidate_status":"technical_screen_only"})
        if complete and not blocked and pd.api.types.is_numeric_dtype(subset[v]):eligible.append(v)
    vals=subset[eligible].replace([np.inf,-np.inf],np.nan)
    corr=vals.corr().abs()
    for i,a in enumerate(eligible):
        for b in eligible[i+1:]:
            score=corr.loc[a,b]
            if pd.notna(score) and score>=.9:
                report["high_correlations"].append({"a":a,"b":b,"abs_pearson":round(float(score),4)})
    report["high_correlations"].sort(key=lambda x:-x["abs_pearson"])
    report["summary"]={"total":len(all_candidates),
      "complete_and_name_allowed":len(eligible),
      "incomplete_or_forbidden":len(all_candidates)-len(eligible),
      "high_corr_pairs":len(report["high_correlations"])}
    (D/"fair_variable_eligibility_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(report["summary"],ensure_ascii=False),flush=True)
if __name__=="__main__":main()
